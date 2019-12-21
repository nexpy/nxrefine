import os
import psutil
import subprocess
import time
from datetime import datetime
from multiprocessing import Process, Queue, JoinableQueue
from .daemon import NXDaemon


class NXWorker(Process):
    """Class for processing tasks on a specific cpu."""
    def __init__(self, cpu, task_queue, result_queue, log_file):
        Process.__init__(self)
        self.cpu = cpu
        self.process = psutil.Process()
        self.process.cpu_affinity([self.cpu])
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.log_file = log_file

    def run(self):
        self.log("Started worker on cpu {} (pid={})".format(self.cpu, os.getpid()))
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
        with open(self.log_file, 'a') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S")+' '+str(message)+'\n')


class NXTask(object):
    """Class for submitting tasks to different cpus."""
    def __init__(self, path, command, log_file):
        self.path = path
        self.command = command
        self.log_file = log_file

    def execute(self, cpu):
        os.system("cd %s && %s" % (self.path, self.command))

    def log(self, message):
        with open(self.log_file, 'a') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S")+' '+str(message)+'\n')


class NXServer(NXDaemon):

    def __init__(self, directory=None):
        self.pid_name = 'nxserver'
        if directory:
            self.directory = directory = os.path.realpath(directory)
        else:
            self.directory = os.getcwd()
        self.task_directory = os.path.join(directory, 'tasks')
        if 'tasks' not in os.listdir(directory):
            os.mkdir(self.task_directory)
        self.task_list = os.path.join(self.task_directory, 'task_list')
        if not os.path.exists(self.task_list):
            os.mkfifo(self.task_list)
        self.log_file = os.path.join(self.task_directory, 'nxserver.log')
        self.pid_file = os.path.join(self.task_directory, 'nxserver.pid')

        self.tasks = None
        self.results = None
        self.workers = []

        super(NXServer, self).__init__(self.pid_name, self.pid_file)

    def log(self, message):
        with open(self.log_file, 'a') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S")+' '+str(message)+'\n')

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
                        for cpu in range(psutil.cpu_count())]
        for worker in self.workers:
            worker.start()
        task_fifo = open(self.task_list, 'r')
        while True:
            time.sleep(5)
            command = task_fifo.readline()[:-1]
            if command == 'stop':
                break
            elif command:
                self.tasks.put(NXTask(self.directory, command, self.log_file))
        for worker in self.workers:
            self.tasks.put(None)
        self.tasks.join()
        for worker in self.workers:
            worker.terminate()
            worker.join()
        self.log("Stopping server")
        super(NXServer, self).stop()

    def stop(self):
        if self.is_running():
            self.add_task('stop')
        else:
            super(NXServer, self).stop()

    def kill(self):
        """Kill the server process.
        
        This provides a backup mechanism for terminating the server if adding
        'stop' to the task list does not work.
        """
        super(NXServer, self).stop()

    def clear(self):
        if os.path.exists(self.task_list):
            os.remove(self.task_list)
        os.mkfifo(self.task_list)        

    def add_task(self, command):
        """Add a task to the server queue"""
        task_fifo = os.open(self.task_list, os.O_RDWR)
        os.write(task_fifo, (command+'\n').encode())
