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
        logs[key] = [array[i] for array in meta_input]


def main():

    parser = argparse.ArgumentParser(
        description="Read metadata from Sector 6 scan")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+', help='names of entries')

    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    scan = os.path.basename(directory)
    wrapper_file = os.path.join(sample, label, '%s_%s.nxs' % (sample, scan))

    entries = args.entries

    root = nxload(wrapper_file, 'rw')    
    for e in entries:
        head_file = os.path.join(directory, e+'_head.txt')
        meta_file = os.path.join(directory, e+'_meta.txt')
        entry = root[e]
        if 'logs' in entry['instrument']:
            del entry['instrument/logs']
        entry['instrument/logs'] = NXcollection()
        read_metadata(head_file, meta_file, entry['instrument/logs'])             
                

if __name__=="__main__":
    main()
