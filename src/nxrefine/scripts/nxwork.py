import argparse, os, subprocess
import numpy as np
from nexusformat.nexus import nxload
from nexpy.gui.utils import natural_sort


def main():

    parser = argparse.ArgumentParser(
        description="Perform workflow for scan")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files linked to this file')
    parser.add_argument('-t', '--threshold', type=float,
                        help='peak threshold - defaults to maximum counts/20')
    parser.add_argument('-s', '--start', default=20, type=int, 
                        help='starting frame')
    parser.add_argument('-e', '--end', default=3630, type=int, 
                        help='ending frame')
    parser.add_argument('-p', '--parent', help='file name of file to copy from')
    
    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(directory))  
    label = os.path.basename(directory)

    print("Processing directory '%s'" % directory)
    
    files = args.filenames
    parent = args.parent
    threshold = args.threshold
    start = args.start
    end = args.end

    label_path = '%s/%s' % (sample, label)

    wrapper_files = sorted([os.path.join(directory, filename) 
                             for filename in os.listdir(label_path) 
                             if filename.endswith('.nxs')], key=natural_sort)

    for wrapper_file in wrapper_files:
        print("Processing %s" % wrapper_file)
        root = nxload(wrapper_file)
        scan_label = os.path.splitext(os.path.basename(wrapper_file))[0][len(sample)+1:]
        path = os.path.join(sample, label, scan_label)        
        for f in files:
            print("Processing %s" % f)
            if 'logs' not in root[f]['instrument']:
                print("Reading in metadata in %s" % f)
                subprocess.call('nxingest -d %s -f %s' % (path, f), shell=True)
            if 'maximum' not in root[f]['data'].attrs and not threshold:
                print("Determining maximum counts in %s" % f)
                subprocess.call('nxmax -f %s -p %s/data'
                                % (wrapper_file, f), shell=True)
            if 'peaks' not in root[f]:
                print("Finding peaks in %s" % f)
                if threshold:
                    subprocess.call('nxfind -f %s -p %s/data -t %s -s %s -e %s'
                        % (wrapper_file, f, threshold, start, end), shell=True)
                else:
                    subprocess.call('nxfind -f %s -p %s/data -s %s -e %s'
                                    % (wrapper_file, f, start, end), shell=True)

        if parent:
            print("Copying parameters from %s" % parent)
            subprocess.call('nxcopy -f %s -o %s' 
                            % (parent, wrapper_file), shell=True)
    

if __name__=="__main__":
    main()
