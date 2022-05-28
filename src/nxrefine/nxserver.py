# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os
import subprocess
import time
from datetime import datetime
from threading import Thread
from queue import Queue

import psutil
from nexusformat.nexus import NeXusError
from persistqueue import Queue as FileQueue
from persistqueue.serializers import json

from .nxdaemon import NXDaemon
from .nxsettings import NXSettings


class NXWorker(Thread):
    """Class for processing tasks on a specific cpu."""

    def __init__(self, cpu, task_queue, server_log):
        super().__init__()
        self.cpu = cpu
        self.task_queue = task_queue
        self.server_log = server_log
        self.cpu_log = os.path.join(os.path.dirname(self.server_log),
                                    self.cpu + '.log')

    def __repr__(self):
        return f"NXWorker(cpu={self.cpu})"

    def run(self):
        self.log(f"Starting worker on {self.cpu} (pid={os.getpid()})")
        while True:
            time.sleep(5)
            next_task = self.task_queue.get()
            if next_task is None:
                self.log(f"Stopping worker on {self.cpu} (pid={os.getpid()})")
                self.task_queue.task_done()
                break
            else:
                self.log(f"{self.cpu}: Executing '{next_task.command}'")
                next_task.execute(self.cpu, self.cpu_log)
            self.task_queue.task_done()
            self.log(f"{self.cpu}: Finished '{next_task.command}'")
        return

    def log(self, message):
        with open(self.server_log, 'a') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' ' +
                    str(message) + '\n')


class NXTask(object):
    """Class for submitting tasks to different cpus."""

    def __init__(self, command, server_type):
        self.command = command
        self.server_type = server_type

    def executable_command(self, cpu):
        """Wrap command according to the server type."""
        if self.server_type == 'multicore':
            return self.command
        else:
            return f"pdsh -w {cpu} '{self.command}'"

    def execute(self, cpu, log_file):
        with open(log_file, 'a') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' ' +
                    self.command + '\n')
        process = subprocess.run(self.executable_command(cpu),
                                 shell=True,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
        with open(log_file, 'a') as f:
            f.write(process.stdout.decode() + '\n')


class NXServer(NXDaemon):

    def __init__(self, directory=None, server_type=None, nodes=None):
        self.pid_name = 'NXServer'
        self.initialize(directory, server_type, nodes)
        self.tasks = None
        self.workers = []
        super(NXServer, self).__init__(self.pid_name, self.pid_file)

    def __repr__(self):
        return (f"NXServer(directory='{self.directory}', "
                "type='{self.server_type}')")

    def initialize(self, directory, server_type, nodes):
        self.server_settings = NXSettings(directory=directory)
        self.directory = self.server_settings.directory
        if server_type:
            self.server_type = server_type
            self.server_settings.set('setup', 'type', server_type)
        elif self.server_settings.has_option('setup', 'type'):
            self.server_type = self.server_settings.get('setup', 'type')
        else:
            raise NeXusError('Server type not specified')
        if self.server_type == 'multinode':
            if 'nodes' not in self.server_settings.sections():
                self.server_settings.add_section('nodes')
            if nodes:
                self.write_nodes(nodes)
            self.cpus = self.read_nodes()
        else:
            if self.server_settings.has_option('setup', 'cores'):
                cpu_count = int(self.server_settings.get('setup', 'cores'))
                if cpu_count > psutil.cpu_count():
                    cpu_count = psutil.cpu_count()
            else:
                cpu_count = psutil.cpu_count()
            self.cpus = ['cpu'+str(cpu) for cpu in range(1, cpu_count+1)]
        self.server_settings.save()
        self.log_file = os.path.join(self.directory, 'nxserver.log')
        self.pid_file = os.path.join(self.directory, 'nxserver.pid')
        self.queue_directory = os.path.join(self.directory, 'task_list')
        self.task_queue = self.initialize_queue()

    def initialize_queue(self, autosave=True):
        tempdir = os.path.join(self.queue_directory, 'tempdir')
        if not os.path.exists(tempdir):
            os.makedirs(tempdir)
        return FileQueue(self.queue_directory, serializer=json,
                         autosave=autosave, chunksize=1, tempdir=tempdir)

    def read_nodes(self):
        """Read available nodes"""
        if 'nodes' in self.server_settings.sections():
            nodes = self.server_settings.options('nodes')
        else:
            nodes = []
        return sorted(nodes)

    def write_nodes(self, nodes):
        """Write additional nodes"""
        current_nodes = self.read_nodes()
        for node in [cpu for cpu in nodes if cpu not in current_nodes]:
            self.server_settings.set('nodes', node)
        self.server_settings.save()
        self.cpus = self.read_nodes()

    def remove_nodes(self, nodes):
        """Remove specified nodes"""
        for node in nodes:
            self.server_settings.remove_option('nodes', node)
        self.server_settings.save()
        self.cpus = self.read_nodes()

    def set_cores(self, cpu_count):
        """Select number of cores"""
        try:
            cpu_count = int(cpu_count)
        except ValueError:
            raise NeXusError('Number of cores must be a valid integer')
        self.server_settings.set('setup', 'cores', str(cpu_count))
        self.server_settings.save()
        self.cpus = ['cpu'+str(cpu) for cpu in range(1, cpu_count+1)]

    def log(self, message):
        with open(self.log_file, 'a') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' ' +
                    str(message) + '\n')

    def run(self):
        """
        Create worker processes to process commands from the task queue

        Create a worker for each cpu, read commands from the server
        queue, and add an NXTask for each command to a Queue.
        """
        self.log(f'Starting server (pid={os.getpid()})')
        self.tasks = Queue(maxsize=len(self.cpus))
        self.workers = [NXWorker(cpu, self.tasks, self.log_file)
                        for cpu in self.cpus]
        for worker in self.workers:
            worker.start()
        while True:
            time.sleep(5)
            command = self.read_task()
            if command == 'stop':
                break
            elif command:
                self.tasks.put(NXTask(command, self.server_type))
        for worker in self.workers:
            self.tasks.put(None)
        self.tasks.join()
        for worker in self.workers:
            worker.join()
        self.log("Stopping server")
        super(NXServer, self).stop()

    def add_task(self, command):
        """Add a task to the server queue"""
        if command not in self.queued_tasks():
            self.task_queue.put(command)

    def read_task(self):
        if self.task_queue.qsize() > 0:
            return self.task_queue.get(block=False)
        else:
            self.task_queue = self.initialize_queue()
            return None

    def remove_task(self, command):
        tasks = self.queued_tasks()
        if command in tasks:
            tasks.remove(command)
        self.clear()
        for task in tasks:
            self.add_task(task)

    def queued_tasks(self):
        queue = self.initialize_queue(autosave=False)
        tasks = []
        while queue.qsize() > 0:
            tasks.append(queue.get(timeout=0))
        return tasks

    def stop(self):
        if self.is_running():
            self.add_task('stop')

    def clear(self):
        if os.path.exists(self.queue_directory):
            import shutil
            shutil.rmtree(self.queue_directory, ignore_errors=True)
        self.task_queue = self.initialize_queue()

    def kill(self):
        """Kill the server process.

        This provides a backup mechanism for terminating the server if adding
        'stop' to the task list does not work.
        """
        super(NXServer, self).stop()
