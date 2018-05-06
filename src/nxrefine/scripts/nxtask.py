import argparse, os, subprocess, sys
import numpy as np
from nexusformat.nexus import nxload
from nexpy.gui.utils import natural_sort


def main():

    parser = argparse.ArgumentParser(
        description="Perform workflow for scan")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files linked to this file')
    parser.add_argument('-f', '--first', default=20, type=int, 
                        help='first frame')
    parser.add_argument('-l', '--last', default=3630, type=int, 
                        help='last frame')
    parser.add_argument('-p', '--parent', help='file name of file to copy from')
    parser.add_argument('-r', '--refine', action='store_true',
                        help='refine lattice parameters')
    parser.add_argument('-t', '--transform', action='store_true',
                        help='perform CCTW transforms')
   
    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    scan = os.path.basename(directory)
    wrapper_file = os.path.join(sample, label, '%s_%s.nxs' % (sample, scan))
    entries = args.entries
    parent = args.parent
    first = args.first
    last = args.last
    refine = args.refine
    transform = args.transform

    if not os.path.exists(wrapper_file):
        print("'%s' does not exist" % wrapper_file)
        sys.exit(1)
    else:
        root = nxload(wrapper_file, 'rw')

    if parent == wrapper_file:
        parent = None
    elif parent:
        if not os.path.exists(parent):
            print("'%s' does not exist" % parent)
            sys.exit(1)
        
    print('Performing workflow on', wrapper_file)

    for entry in entries:
        print("Processing", entry)
        subprocess.call('nxlink -d %s -e %s' % (directory, entry), shell=True)
        subprocess.call('nxmax -d %s -e %s' % (directory, entry), shell=True)
        subprocess.call('nxfind -d %s -e %s -f %s -l %s'
                        % (directory, entry, first, last), shell=True)

    if parent:
        subprocess.call('nxcopy -i %s -o %s' % (parent, wrapper_file), shell=True)
    if refine and 'orientation_matrix' in root[entries[0]]['instrument/detector']:
        subprocess.call('nxrefine -d %s' % directory, shell=True)
    if transform and parent:
        subprocess.call('nxtransform -d %s -p %s' % (directory, parent), shell=True)
        subprocess.call('nxcombine -d %s' % directory, shell=True)


if __name__=="__main__":
    main()
