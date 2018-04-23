import argparse, os, subprocess
import numpy as np
from nexusformat.nexus import nxload
from nexpy.gui.utils import natural_sort


def main():

    parser = argparse.ArgumentParser(
        description="Perform workflow for scan")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files linked to this file')
    parser.add_argument('-t', '--threshold', type=float,
                        help='peak threshold - defaults to maximum counts/20')
    parser.add_argument('-f', '--first', default=20, type=int, 
                        help='first frame')
    parser.add_argument('-l', '--last', default=3630, type=int, 
                        help='last frame')
    parser.add_argument('-p', '--parent', help='file name of file to copy from')
    parser.add_argument('-r', '--refine', action='store_true',
                        help='refine lattice parameters')
    parser.add_argument('-n', '--norun', action='store_true', help='dry run')
   
    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    scan = os.path.basename(directory)
    wrapper_file = os.path.join(sample, label, '%s_%s.nxs' % (sample, scan))

    entries = args.entries
    parent = args.parent
    threshold = args.threshold
    first = args.first
    last = args.last
    refine = args.refine
    dry_run = args.norun

    print("Processing %s" % wrapper_file)
    root = nxload(wrapper_file)
    for e in entries:
        print("Processing %s" % e)
        if 'logs' not in root[e]['instrument']:
            print("Reading in metadata in %s" % e)
            if not dry_run:
                subprocess.call('nxingest -d %s -e %s' % (directory, e), shell=True)
        if 'maximum' not in root[e]['data'].attrs and not threshold:
            print("Determining maximum counts in %s" % f)
            if not dry_run:
                subprocess.call('nxmax -d %s -e %s'
                                % (directory, e), shell=True)
        if 'peaks' not in root[e]:
            print("Finding peaks in %s" % e)
            if not dry_run:
                if threshold:
                    subprocess.call('nxfind -d %s -e %s -t %s -f %s -l %s'
                        % (directory, e, threshold, first, last), shell=True)
                else:
                    subprocess.call('nxfind -d %s -e %s -f %s -l %s'
                                    % (directory, e, first, last), shell=True)

    if parent:
        print("Copying parameters from %s" % parent)
        if not dry_run:
            subprocess.call('nxcopy -i %s -o %s' 
                            % (parent, wrapper_file), shell=True)
    if refine:
        print("Refining %s" % wrapper_file)
        if not dry_run:
            subprocess.call('nxrefine -d %s' % directory, shell=True)
    if parent and 'transform.nxs' not in os.listdir(directory):
        if not dry_run:
            subprocess.call('nxtransform -d %s -p %s' % (directory, parent), shell=True)
            subprocess.call('nxcombine -d %s' % directory, shell=True)


if __name__=="__main__":
    main()
