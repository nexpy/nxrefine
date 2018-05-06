import argparse, os, subprocess
from multiprocessing import Process, Queue, JoinableQueue
import numpy as np
from nexpy.gui.utils import natural_sort
from nexusformat.nexus import nxload, NeXusError

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
            if next_task is None:
                print('%s: Exiting' % self.node)
                self.task_queue.task_done()
                break
            next_task.execute(self.node)
            self.task_queue.task_done()
            self.result_queue.put(next_task.command)
        return


class Task(object):

    def __init__(self, path, command):
        self.path = path
        self.command = command

    def execute(self, node):
        subprocess.call("pdsh -w %s 'cd %s; %s >> tasks/%s.out'" 
                        % (node, self.path, self.command, node), shell=True)


def main():

    parser = argparse.ArgumentParser(
        description="Perform workflow for scan")
    parser.add_argument('-d', '--directory', help='scan directory')
    parser.add_argument('-r', '--refine', action='store_false',
                        help='refine lattice parameters')
    parser.add_argument('-t', '--transform', action='store_true',
                        help='perform CCTW transforms')
    parser.add_argument('-c', '--cwd', default='/data/user6idd', 
                        help='directory containing GUP directories')
    parser.add_argument('-g', '--gup', default='GUP-57342',
                        help='GUP number, e.g., GUP-57342')
    
    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(directory))  
    label = os.path.basename(directory)
    if args.refine:
        refine = '-r'
    else:
        refine = ''
    if args.transform:
        transform = '-t'
    else:
        transform = ''

    print("Processing directory '%s'" % directory)
    
    path = os.path.join(args.cwd, args.gup)
    if 'tasks' not in os.listdir(path):
        os.mkdir(os.path.join(path, 'tasks'))

    scans = sorted([scan for scan in os.listdir(directory) 
                    if (os.path.isdir(os.path.join(directory, scan))
                        and not scan.endswith('_1'))], 
                    key=natural_sort)
    parent = os.path.join(sample, label, '%s_%s.nxs' % (sample, scans[0]))

    commands = ['nxtask -d %s -p %s %s %s' 
                % (os.path.join(directory, scan), parent, refine, transform)
                for scan in scans]    

    tasks = JoinableQueue()
    results = Queue()
    
    nodes = [ProcessNode(node, tasks, results) for node in orthros_nodes]
    for node in nodes:
        node.start()
    
    # Enqueue jobs
    for command in commands:
        print(command)      
        tasks.put(Task(path, command))
    
    # Add a poison pill for each node
    for node in nodes:
        tasks.put(None)

    # Wait for all of the tasks to finish
    tasks.join()
    
    # Start printing results
    num_jobs = len(commands)
    while num_jobs:
        result = results.get()
        print('Completed:', result)
        num_jobs -= 1 
    

if __name__=="__main__":
    main()
