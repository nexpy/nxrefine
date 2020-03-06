import os
import psutil
import subprocess
import time
from datetime import datetime
from multiprocessing import Process, Queue, JoinableQueue
from .daemon import NXDaemon


class NXWorker(Process):
    """Class for processing tasks on a specific cpu."""
    def __init__(self, cpu, task_queue, result_queue, server_log):
        Process.__init__(self)
        self.cpu = 'cpu' + str(cpu)
        self.process = psutil.Process()
        self.process.cpu_affinity([cpu])
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
                next_task.execute(self.cpu_log)
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
    def __init__(self, path, command):
        self.path = path
        self.command = command

    def execute(self, log_file):
        process = subprocess.run("cd %s && %s" % (self.path, self.command), 
                                 shell=True, 
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
        with open(log_file, 'a') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' ' + 
                    self.command + '\n' + process.stdout.decode() + '\n')


class NXServer(NXDaemon):

    def __init__(self, directory='/volt/nxserver', experiment_file=None):
        self.pid_name = 'NXServer'
        if directory:
            self.directory = directory = os.path.realpath(directory)
        else:
            self.directory = os.path.join(os.path.expanduser('~'), '.nxserver')
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)
        if experiment_file is None:
            self.experiment_file = os.path.join(self.directory, 'experiments')
        else:
            self.experiment_file = experiment_file
        self.experiments = self.read_experiments()
        self.log_file = os.path.join(self.directory, 'nxserver.log')
        self.pid_file = os.path.join(self.directory, 'nxserver.pid')
        self.tasks = None
        self.results = None
        self.workers = []

        super(NXServer, self).__init__(self.pid_name, self.pid_file)

    def read_experiments(self):
        """Read registered experiments"""
        self.experiments = {}
        if os.path.exists(self.experiment_file):
            with open(self.experiment_file) as f:
                experiment_list = [line.strip() for line in f.readlines() 
                                   if line.strip() != '']
        else:
            experiment_list = []
        for experiment in experiment_list:
            self.add_experiment(experiment)
        return self.experiments

    def add_experiment(self, experiment):
        e = {}
        e['directory'] = experiment
        e['task_directory'] = os.path.join(e['directory'], 'tasks')
        if 'tasks' not in os.listdir(e['directory']):
            os.mkdir(e['task_directory'])
        e['task_list'] = os.path.join(e['task_directory'], 'task_list')
        if not os.path.exists(e['task_list']):
            os.mkfifo(e['task_list'])
        self.experiments[experiment] = e

    def register(self, experiment):
        if experiment not in self.experiments:
            with open(self.experiment_file, 'a') as f:
                f.write(experiment+'\n')
        self.add_experiment(experiment)

    def remove(self, experiment):
        if experiment in self.experiments:
            with open(self.experiment_file, "r") as f:
                lines = f.readlines()
            with open(self.experiment_file, "w") as f:
                for line in lines:
                    if line.strip("\n") != experiment:
                        f.write(line)

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
                        for cpu in range(psutil.cpu_count())]
        for worker in self.workers:
            worker.start()

        while True:
            for experiment in self.experiments:
                command = self.read_task(experiment)
                if command == 'stop':
                    break
                elif command:
                    self.tasks.put(NXTask(experiment, command))
            if command == 'stop':
                break
            self.log('Server listening')
            time.sleep(5)
        self.stop()

    def add_task(self, command, experiment):
        """Add a task to the server queue"""
        e = self.experiments[experiment]
        with os.open(e['task_list'], os.O_RDWR) as task_fifo:
            os.write(task_fifo, (command+'\n').encode())

    def read_task(self, experiment):
        e = self.experiments[experiment]
        with open(e['task_list']) as task_fifo:
            command = task_fifo.readline()[:-1]
        return command

    def stop(self, experiment=None):
        if experiment:
            del self.experiments[experiment]            
        elif self.is_running():
            for worker in self.workers:
                self.tasks.put(None)
            self.tasks.join()
            for worker in self.workers:
                worker.terminate()
                worker.join()
            self.log("Stopping server")
            super(NXServer, self).stop()
        else:
            super(NXServer, self).stop()

    def clear(self, experiment=None):
        if experiment:
            e = self.experiments[experiment]
            if os.path.exists(e['task_list']):
                os.remove(e['task_list'])
            os.mkfifo(e['task_list'])        
        else:
            for e in self.experiments:
                if os.path.exists(e['task_list']):
                    os.remove(e['task_list'])
                os.mkfifo(e['task_list'])        

    def kill(self):
        """Kill the server process.
        
        This provides a backup mechanism for terminating the server if adding
        'stop' to the task list does not work.
        """
        super(NXServer, self).stop()
