import argparse
import logging
import os
import time
from multiprocessing import Process, Queue, JoinableQueue

class Worker(Process):
    
    def __init__(self, node, task_queue, result_queue):
        Process.__init__(self)
        self.node = node
        self.task_queue = task_queue
        self.result_queue = result_queue

    def run(self):
        while True:
            next_task = self.task_queue.get()
            next_task.execute(self.node)
            self.task_queue.task_done()
            self.result_queue.put(next_task.command)
        return


class Task(object):

    def __init__(self, path, command):
        self.path = path
        self.command = command

    def execute(self, node):
        print("pdsh -w %s 'cd %s; %s >> tasks/%s.out'"
              % (node, self.path, self.command, node))
#        subprocess.call("pdsh -w %s 'cd %s; %s >> tasks/%s.out'" 
#                        % (node, self.path, self.command, node), shell=True)


def read_nodes(node_file):
    """Read available nodes"""
    with open('nodefile') as f:
        nodes = [line.strip() for line in f.readlines()]
    return nodes

def initialize_logs(log_file):
    """Initialize the nxserver logger."""
    handler = logging.handlers.RotatingFileHandler(log_file, 
                                                   maxBytes=50000,
                                                   backupCount=5)
    fmt = '%(asctime)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(fmt, None)
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)


def main():

    parser = argparse.ArgumentParser(
        description="Perform workflow for scan")
    parser.add_argument('-c', '--cwd', default='/data/user6idd', 
                        help='directory containing GUP directories')
    parser.add_argument('-g', '--gup', default='GUP-57342',
                        help='GUP number, e.g., GUP-57342')
    
    args = parser.parse_args()
    cwd = args.cwd
    gup = args.gup

    path = os.path.join(cwd, gup)
    if 'tasks' not in os.listdir(path):
        os.mkdir(os.path.join(path, 'tasks'))
    task_list = os.path.join(path, 'tasks', 'task_list')
    if not os.path.exists(task_list):
        os.mkfifo(task_list)  

    nodes = read_nodes(os.path.join(cwd, 'nodefile'))
    initialize_logs(os.path.join(path, 'tasks', 'nxserver.log'))

    tasks = JoinableQueue()
    results = Queue()
    
    workers = [Workers(node, tasks, results) for node in nodes]
    for worker in workers:
        worker.start()

    task_fifo = open(task_list, 'r')    
    while True:
        time.sleep(10)
        command = task_fifo.readline()[:-1]
        logging.info("'%s' added to task queue" % command)
        tasks.put(Task(path, command))    
    

if __name__=="__main__":
    main()
