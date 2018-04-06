#!/home/beams/USER6IDD/anaconda3/envs/nexpy/bin/python
import argparse, os
import numpy as np
from nexusformat.nexus import *


def read_metadata(head_file, meta_file, logs):
    with open(head_file) as f:
        lines = f.readlines()
    for line in lines:
        key, value = line.split(', ')
        value = value.strip('\n')
        try:
            value = np.float(value)
        except:
            pass
        logs[key] = value
    meta_input = np.genfromtxt(meta_file, delimiter=',', names=True)
    for i, key in enumerate(meta_input.dtype.names):
        logs[key] = [array[0] for array in meta_input]


def main():

    parser = argparse.ArgumentParser(
        description="Read metadata from Sector 6 scan")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files to be linked to this file')

    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    scan = os.path.basename(directory)
    files = args.filenames

    label_path = '%s/%s' % (sample, label)
    wrapper_file = '%s/%s_%s.nxs' % (label_path, sample, scan)

    root = nxload(wrapper_file, 'rw')    
    for f in files:
        head_file = os.path.join(directory, f+'_head.txt')
        meta_file = os.path.join(directory, f+'_meta.txt')
        entry = root[f]
        if 'logs' in entry['instrument']:
            del entry['instrument/logs']
        entry['instrument/logs'] = NXcollection()
        read_metadata(head_file, meta_file, entry['instrument/logs']))              
                

if __name__=="__main__":
    main()
