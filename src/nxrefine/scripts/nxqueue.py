import argparse, os, subprocess
from multiprocessing import Process, Queue, JoinableQueue
import numpy as np
from nexpy.gui.utils import natural_sort
from nexusformat.nexus import nxload, NeXusError

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
    
    if 'tasks' not in os.listdir(os.getcwd()):
        os.mkdir(os.path.join(os.getcwd(), 'tasks'))
    task_list = os.path.join(os.getcwd(), 'tasks', 'task_list')
    if not os.path.exists(task_list):
        os.mkfifo(task_list)  

    scans = sorted([scan for scan in os.listdir(directory) 
                    if (os.path.isdir(os.path.join(directory, scan))
                        and not scan.endswith('_1'))], 
                    key=natural_sort)
    parent = os.path.join(sample, label, '%s_%s.nxs' % (sample, scans[0]))

    commands = ['nxtask -d %s -p %s %s %s' 
                % (os.path.join(directory, scan), parent, refine, transform)
                for scan in scans]    

    task_fifo = os.open(task_list, os.O_WRONLY)
    for command in commands:
        os.write(task_fifo, command.encode())
    

if __name__=="__main__":
    main()
