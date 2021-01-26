import os
import psutil
import subprocess
import time
from configparser import ConfigParser
from datetime import datetime
from multiprocessing import Process, Queue, JoinableQueue

from nexusformat.nexus import NeXusError
from .daemon import NXDaemon


class NXWorker(Process):
    """Class for processing tasks on a specific cpu."""
    def __init__(self, cpu, task_queue, result_queue, server_log):
        Process.__init__(self)
        self.cpu = cpu
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.server_log = server_log
        self.cpu_log = os.path.join(os.path.dirname(self.server_log), 
                                    self.cpu + '.log')

    def run(self):
        self.log("Started worker on {} (pid={})".format(self.cpu, os.getpid()))
        while True:
            time.sleep(5)
            next_task = self.task_queue.get()
            if next_task is None:
                self.log('%s: Exiting' % self.cpu)
                self.task_queue.task_done()
                break
            else:
                self.log("%s: Executing '%s'" % (self.cpu, next_task.command))
                next_task.execute(self.cpu)
            self.task_queue.task_done()
            self.log("%s: Finished '%s'" % (self.cpu, next_task.command))
            self.result_queue.put(next_task.command)
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
            return "pdsh -w %s '%s'" % (self.cpu, self.command)

    def execute(self, cpu, log_file):
        process = subprocess.run(self.executable_command(cpu), 
                                 shell=True, 
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
        with open(log_file, 'a') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' ' + 
                    self.command + '\n' + process.stdout.decode() + '\n')


class NXServer(NXDaemon):

    def __init__(self, directory=None, server_type=None, nodes=None):
        self.pid_name = 'NXServer'
        self.initialize(directory, server_type, nodes)
        if self.directory:
            self.task_list = os.path.join(self.directory, 'task_list')
            self.log_file = os.path.join(self.directory, 'nxserver.log')
            self.pid_file = os.path.join(self.directory, 'nxserver.pid')
        self.tasks = None
        self.results = None
        self.workers = []

        super(NXServer, self).__init__(self.pid_name, self.pid_file)

    def __repr__(self):
        return "NXServer(directory='{}', type='{}')".format(self.directory,
                                                            self.server_type)

    def initialize(self, directory, server_type, nodes):
        self.home_settings = ConfigParser()
        self.home_file = os.path.join(os.path.abspath(os.path.expanduser('~')), 
                                      '.nxserver', 'settings.ini')
        self.home_settings.read(self.home_file)
        if 'setup' not in self.home_settings.sections():
            self.home_settings.add_section('setup')
        if directory:
            self.home_settings.set('setup', 'directory', directory)
            with open(self.home_file, 'w') as f:
                self.home_settings.write(f)
        elif self.home_settings.has_option('setup', 'directory'):
            directory = self.home_settings.get('setup', 'directory')
        else:
            raise NeXusError('Server directory not specified')
        self.directory = os.path.join(directory, 'nxserver')
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)

        self.server_settings = ConfigParser(allow_no_value=True)
        self.server_file = os.path.join(self.directory, 'settings.ini')
        self.server_settings.read(self.server_file)
        if 'setup' not in self.server_settings.sections():
            self.server_settings.add_section('setup')
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
            self.cpus = ['cpu'+str(cpu) for cpu in range(psutil.cpu_count())]
        with open(self.server_file, 'w') as f:
            self.server_settings.write(f)

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
        with open(self.server_file, 'w') as f:
            self.server_settings.write(f)
        self.cpus = self.read_nodes()

    def remove_nodes(self, nodes):
        """Remove specified nodes"""
        for node in nodes:
            self.server_settings.remove_option('nodes', node)
        with open(self.server_file, 'w') as f:
            self.server_settings.write(f)
        self.cpus = self.read_nodes()

    def log(self, message):
        with open(self.log_file, 'a') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' ' +
                    str(message) + '\n')

    def run(self):
        """
        Create worker processes to process commands from the task_fifo

        Create a worker for each cpu, read commands from task_list, submit
            an NXTask for each command to a JoinableQueue
        """
        self.log('Starting server (pid={})'.format(os.getpid()))
        self.tasks = JoinableQueue()
        self.results = Queue()
        self.workers = [NXWorker(cpu, self.tasks, self.results, self.log_file)
                        for cpu in self.cpus]
        for worker in self.workers:
            worker.start()
        self.task_fifo = open(self.task_list, 'r')
        while True:
            time.sleep(5)
            command = self.read_task()
            if command == 'stop':
                break
            elif command:
                self.tasks.put(NXTask(command, self.server_type))
                self.log('Server listening')
        for worker in self.workers:
            self.tasks.put(None)
        self.tasks.join()
        for worker in self.workers:
            worker.terminate()
            worker.join()
        self.log("Stopping server")
        super(NXServer, self).stop()

    def add_task(self, command):
        """Add a task to the server queue"""
        task_fifo = os.open(self.task_list, os.O_RDWR)
        os.write(task_fifo, (command+'\n').encode())
        self.log('Written to FIFO: ' + command)

    def read_task(self):
        command = self.task_fifo.readline()[:-1]
        if command:
            self.log('Read from FIFO: ' + command)
        return command

    def stop(self):
        if self.is_running():
            self.add_task('stop')

    def clear(self):
        if os.path.exists(self.task_list):
            os.remove(self.task_list)
        os.mkfifo(self.task_list)        

    def kill(self):
        """Kill the server process.
        
        This provides a backup mechanism for terminating the server if adding
        'stop' to the task list does not work.
        """
        super(NXServer, self).stop()
