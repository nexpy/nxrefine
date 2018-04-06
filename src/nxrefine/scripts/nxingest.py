#!/home/beams/USER6IDD/anaconda3/envs/nexpy/bin/python
import argparse, os
import numpy as np
from nexusformat.nexus import *


def read_header(header_file, metadata_file, logs):
    with open(header_file) as f:
        lines = f.readlines()
    for line in lines:
        key, value = line.split(', ')
        value = value.strip('\n')
        try:
            value = np.float(value)
        except:
            pass
        logs[key] = value
    metadata_input = np.genfromtxt(metadata_file, delimiter=',', names=True)
    for i, key in enumerate(metadata_input.dtype.names):
        logs[key] = [array[0] for array in metadata_input]


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
        header_file = os.path.join(directory, f+'_header.txt')
        metadata_file = os.path.join(directory, f+'_metadata.txt')
        entry = root[f]
        if 'logs' in entry['instrument']:
            del entry['instrument/logs']
        entry['instrument/logs'] = NXcollection()
        read_header(f+'_header.txt', f+'_metadata.txt', entry['instrument/logs']))              
                

if __name__=="__main__":
    main()
