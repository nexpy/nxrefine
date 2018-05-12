import argparse
import logging
import os
import time
from multiprocessing import Process, Queue, JoinableQueue

orthros_nodes = ['puppy%d' % i for i in range(61,77) if i != 75]

class ProcessNode(Process):
    
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
        subprocess.call("pdsh -w %s $'cd %s; echo \'%s\' >> tasks/%s.out'" 
                        % (node, self.path, self.command, node), shell=True)
#        subprocess.call("pdsh -w %s 'cd %s; %s >> tasks/%s.out'" 
#                        % (node, self.path, self.command, node), shell=True)


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

    path = os.path.join(args.cwd, args.gup)
    if 'tasks' not in os.listdir(path):
        os.mkdir(os.path.join(path, 'tasks'))
    task_list = os.path.join(path, 'tasks', 'task_list')
    if not os.path.exists(task_list):
        os.mkfifo(task_list)  

    initialize_logs(os.path.join(path, 'tasks', 'nxserver.log'))

    tasks = JoinableQueue()
    results = Queue()
    
    nodes = [ProcessNode(node, tasks, results) for node in orthros_nodes]
    for node in nodes:
        node.start()

    task_fifo = open(task_list, 'r')    
    while True:
        time.sleep(10)
        command = task_fifo.readline()[:-1]
        logging.info("'%s' added to task queue" % command)
        tasks.put(Task(path, command))    
    

if __name__=="__main__":
    main()
