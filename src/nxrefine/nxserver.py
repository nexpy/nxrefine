import os
import subprocess
import time
from multiprocessing import Process, Queue, JoinableQueue
from .daemon import NXDaemon
import nxrefine.nxdatabase as nxdb

#### DEBUGGING ####
import ipdb;

class NXWorker(Process):
    """Class for processing tasks on a specific node."""
    def __init__(self, node, task_queue, result_queue, log_file):
        Process.__init__(self)
        self.node = node
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.log_file = log_file

    def run(self):
        self.log("Started worker on node {} (pid={})".format(self.node, os.getpid()))
        while True:
            next_task = self.task_queue.get()
            if next_task is None:
                self.log('%s: Exiting' % self.node)
                self.task_queue.task_done()
                break
            else:
                self.log("%s: Executing '%s'" % (self.node, next_task.command))
                next_task.execute(self.node)
            self.task_queue.task_done()
            self.log("%s: Finished '%s'" % (self.node, next_task.command))
            self.result_queue.put(next_task.command)
        return

    def log(self, message):
        with open(self.log_file, 'a') as f:
            f.write(message+'\n')


class NXTask(object):
    """Class for submitting tasks to different nodes."""
    def __init__(self, path, command):
        self.path = path
        self.command = command

    def execute(self, node):
        #### DEBUG ####
        # subprocess.run("pdsh -w %s 'cd %s; %s'"
        #                 % (node, self.path, self.command), shell=True)
        # TODO: for debugging, don't bother starting on a pdsh node
        subprocess.run('cd {}; {}'.format(self.path, self.command), shell=True)


class NXServer(NXDaemon):
    def __init__(self, directory, node_file=None):
        self.directory = directory = os.path.realpath(directory)
        self.task_directory = os.path.join(directory, 'tasks')
        if 'tasks' not in os.listdir(directory):
            os.mkdir(self.task_directory)
        self.task_list = os.path.join(self.task_directory, 'task_list')
        if not os.path.exists(self.task_list):
            os.mkfifo(self.task_list)
        if node_file is None:
            self.node_file = os.path.join(self.task_directory, 'nodefile')
        else:
            self.node_file = node_file
        self.nodes = self.read_nodes(self.node_file)
        self.log_file = os.path.join(self.task_directory, 'nxserver.log')
        self.pid_file = os.path.join(self.task_directory, 'nxserver.pid')

        self.tasks = None
        self.results = None
        self.workers = []

        super(NXServer, self).__init__(self.pid_file)
        db_file = os.path.join(self.directory, 'NXdatabase.db')
        nxdb.init('sqlite:///' + db_file)


    def read_nodes(self, node_file):
        """Read available nodes"""
        with open(node_file) as f:
            nodes = [line.strip() for line in f.readlines() if line.strip() != '']
        return nodes

    def log(self, message):
        with open(self.log_file, 'a') as f:
            f.write(str(message)+'\n')

    def run(self):
        """
        Create worker processes to process commands from the task_fifo

        Create a worker for each node, read commands from task_list, submit
            an NXTask for each command to a JoinableQueue
        """
        self.log('Starting server (pid={})'.format(os.getpid()))
        self.tasks = JoinableQueue()
        self.results = Queue()
        self.workers = [NXWorker(node, self.tasks, self.results, self.log_file)
                        for node in self.nodes]
        for worker in self.workers:
            worker.start()
        task_fifo = open(self.task_list, 'r')
        while True:
            time.sleep(5)
            command = task_fifo.readline()[:-1]
            if command == 'stop':
                break
            elif command:
                self.log('Found command {}'.format(command))
                self.tasks.put(NXTask(self.directory, command))
        for worker in self.workers:
            self.tasks.put(None)
        self.tasks.join()
        for worker in self.workers:
            worker.terminate()
            worker.join()
        self.log("Stopping server")
        super(NXServer, self).stop()

    def stop(self):
        self.add_task('stop')

    def add_task(self, command):
        """Add a task to the server queue"""
        task_fifo = os.open(self.task_list, os.O_RDWR)
        os.write(task_fifo, (command+'\n').encode())
