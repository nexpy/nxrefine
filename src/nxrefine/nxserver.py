# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from queue import Queue
from threading import Thread

import psutil
from nexusformat.nexus import NeXusError, NXLock
from persistqueue import Queue as FileQueue
from persistqueue.exceptions import Empty
from persistqueue.serializers import json

from .nxdaemon import NXDaemon
from .nxsettings import NXSettings


class NXFileQueue(FileQueue):
    """A file-based queue with locked access"""

    def __init__(self, directory, autosave=False):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o777, exist_ok=True)
        tempdir = self.directory / 'tempdir'
        tempdir.mkdir(mode=0o777, exist_ok=True)
        self.lock = NXLock(self.directory / 'filequeue')
        with self.lock:
            super().__init__(directory, serializer=json, autosave=autosave,
                             tempdir=tempdir)
            self.fix_access()

    def __repr__(self):
        return f"NXFileQueue('{self.directory}')"

    def __enter__(self):
        self.lock.acquire()
        self.info = self._loadinfo()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.fix_access()
        self.lock.release()

    def put(self, item, block=True, timeout=None):
        """Add an item to the queue."""
        with self:
            super().put(str(item), block=block, timeout=timeout)

    def get(self, block=True, timeout=None):
        """Get the next item in the queue."""
        with self:
            item = str(super().get(block=block, timeout=timeout))
        return item

    def queued_items(self):
        """Return a list of items still remaining in the queue."""
        with self:
            items = []
            while self.qsize() > 0:
                items.append(super().get(timeout=0))
        return items

    def fix_access(self):
        """Ensure that the file queue pointer is readable."""
        for f in [f for f in self.directory.iterdir() if f.is_file()]:
            try:
                self.directory.joinpath(f).chmod(0o666)
            except Exception:
                pass
        for f in [f for f in self.directory.iterdir() if f.is_dir()]:
            try:
                self.directory.joinpath(f).chmod(0o777)
            except Exception:
                pass


class NXWorker(Thread):
    """Class for processing tasks on a specific cpu."""

    def __init__(self, cpu, worker_queue, server_log):
        super().__init__()
        self.cpu = cpu
        self.worker_queue = worker_queue
        self.server_log = server_log
        cpu_log = self.cpu + '.log'
        self.cpu_log = Path(self.server_log).parent / cpu_log

    def __repr__(self):
        return f"NXWorker(cpu='{self.cpu}')"

    def run(self):
        self.log(f"Starting worker on {self.cpu} (pid={os.getpid()})")
        while True:
            time.sleep(5)
            next_task = self.worker_queue.get()
            if next_task is None:
                self.log(f"Stopping worker on {self.cpu} (pid={os.getpid()})")
                self.worker_queue.task_done()
                break
            else:
                self.log(f"{self.cpu}: Executing '{next_task.command}'")
                next_task.execute(self.cpu, self.cpu_log)
            self.worker_queue.task_done()
            self.log(f"{self.cpu}: Finished '{next_task.command}'")
        return

    def log(self, message):
        with open(self.server_log, 'a') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' ' +
                    str(message) + '\n')


class NXTask:
    """Class for submitting tasks to different cpus."""

    def __init__(self, command, server):
        self.command = command
        self.name = command.split()[0]
        self.server = server

    def __repr__(self):
        return f"NXTask('{self.name}')"

    def executable_command(self, cpu, cpu_log):
        """Wrap command according to the server type."""
        if self.server.template:
            with open(self.server.template) as f:
                text = f.read()
            self.script = Path(tempfile.mkstemp(suffix='.sh')[1])
            with open(self.script, 'w') as f:
                f.write(text.replace('<NXSERVER>', self.command))
            command = str(self.script)
        else:
            self.script = None
            command = self.command
        if self.server.run_command:
            if self.server.run_command.startswith('pdsh'):
                command = f"{self.server.run_command} -w {cpu} '{command}'"
            elif self.server.run_command.startswith('qsub'):
                command = (f"{self.server.run_command} -j y -o {cpu_log} "
                           f"-N {cpu} -hold_jid {cpu} -S /bin/bash {command}")
        return command

    def execute(self, cpu, cpu_log):
        with open(cpu_log, 'a') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' ' +
                    self.command + '\n')
        process = subprocess.run(self.executable_command(cpu, cpu_log),
                                 shell=True,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
        with open(cpu_log, 'a') as f:
            f.write(process.stdout.decode() + '\n')
        if self.script and self.script.exists():
            self.script.unlink()


class NXServer(NXDaemon):

    def __init__(self, directory=None, server_type=None, nodes=None,
                 concurrent=None, run_command=None, template=None):
        self.pid_name = 'nxserver'
        self.initialize(directory, server_type, nodes, concurrent,
                        run_command, template)
        self.worker_queue = None
        self.workers = []
        super(NXServer, self).__init__(self.pid_name, self.pid_file)

    def __repr__(self):
        return f"NXServer(directory='{self.directory}')"

    def initialize(self, directory, server_type, nodes, concurrent,
                   run_command, template):
        self.settings = NXSettings(directory=directory)
        self.directory = Path(self.settings.directory)
        if server_type:
            self.server_type = server_type
            self.settings.set('server', 'type', server_type)
        elif self.settings.has_option('server', 'type'):
            self.server_type = self.settings.get('server', 'type')
        else:
            raise NeXusError('Server type not specified')
        if self.server_type == 'multinode':
            if 'nodes' not in self.settings.sections():
                self.settings.add_section('nodes')
            if nodes:
                self.write_nodes(nodes)
            self.cpus = self.read_nodes()
        else:
            if self.settings.has_option('server', 'cores'):
                cpu_count = int(self.settings.get('server', 'cores'))
                if cpu_count > psutil.cpu_count():
                    cpu_count = psutil.cpu_count()
            else:
                cpu_count = psutil.cpu_count()
            self.cpus = ['cpu'+str(cpu) for cpu in range(1, cpu_count+1)]
        if concurrent:
            self.concurrent = concurrent
            self.settings.set('server', 'concurrent', concurrent)
        else:
            self.concurrent = self.settings.get('server', 'concurrent')
        if run_command:
            self.run_command = run_command
            self.settings.set('server', 'run_command', run_command)
        else:
            self.run_command = self.settings.get('server', 'run_command')
        if template:
            self.template = template
            self.settings.set('server', 'template', template)
        else:
            self.template = self.settings.get('server', 'template')
        self.settings.save()
        self.log_file = self.directory / 'nxserver.log'
        self.pid_file = self.directory / 'nxserver.pid'
        self.queue_directory = self.directory / 'task_list'
        self.task_queue = NXFileQueue(self.queue_directory)

    def read_nodes(self):
        """Read available nodes"""
        if 'nodes' in self.settings.sections():
            nodes = self.settings.options('nodes')
        else:
            nodes = []
        return sorted(nodes)

    def write_nodes(self, nodes):
        """Write additional nodes"""
        current_nodes = self.read_nodes()
        for node in [cpu for cpu in nodes if cpu not in current_nodes]:
            self.settings.set('nodes', node)
        self.settings.save()
        self.cpus = self.read_nodes()

    def remove_nodes(self, nodes):
        """Remove specified nodes"""
        for node in nodes:
            self.settings.remove_option('nodes', node)
        self.settings.save()
        self.cpus = self.read_nodes()

    def set_cores(self, cpu_count):
        """Select number of cores"""
        try:
            cpu_count = int(cpu_count)
        except ValueError:
            raise NeXusError('Number of cores must be a valid integer')
        self.settings.set('server', 'cores', cpu_count)
        self.settings.save()
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
        self.task_queue = NXFileQueue(self.queue_directory, autosave=True)
        self.worker_queue = Queue()
        self.workers = [NXWorker(cpu, self.worker_queue, self.log_file)
                        for cpu in self.cpus]
        for worker in self.workers:
            worker.start()
        while True:
            time.sleep(5)
            command = self.read_task()
            if command == 'stop':
                break
            elif command:
                self.worker_queue.put(NXTask(command, self))
        for worker in self.workers:
            self.worker_queue.put(None)
        self.worker_queue.join()
        for worker in self.workers:
            worker.join()
        self.log("Stopping server")
        super(NXServer, self).stop()

    def add_task(self, tasks):
        """Add a task to the server queue."""
        if isinstance(tasks, str):
            tasks = tasks.split('\n')
        for task in tasks:
            if task == 'stop':
                self.task_queue.put(task)
            elif task not in self.queued_tasks():
                self.task_queue.put(task)

    def read_task(self):
        """Read the next task from the server queue"""
        try:
            task = self.task_queue.get(block=False)
        except Empty:
            return None
        except Exception as error:
            self.log(str(error))
            return None
        return task

    def remove_task(self, task):
        """Remove task from the server queue."""
        tasks = self.queued_tasks()
        if task in tasks:
            tasks.remove(task)
        self.clear()
        for task in tasks:
            self.add_task(task)

    def queued_tasks(self):
        """List tasks remaining on the server queue."""
        queue = NXFileQueue(self.queue_directory, autosave=False)
        return queue.queued_items()

    def stop(self):
        """Stop the server when active tasks are completed."""
        if self.is_running():
            self.add_task('stop')

    def clear(self):
        """Clear the server queue."""
        with self.task_queue.lock:
            if self.queue_directory.exists():
                import shutil
                shutil.rmtree(self.queue_directory, ignore_errors=True)
        self.task_queue = NXFileQueue(self.queue_directory)

    def kill(self):
        """Kill the server process.

        This provides a backup mechanism for terminating the server if
        adding 'stop' to the task list does not work.
        """
        super(NXServer, self).stop()
