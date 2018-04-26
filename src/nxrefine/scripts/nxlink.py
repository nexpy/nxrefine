#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2015, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import argparse
import os
import re
import numpy as np
from nexusformat.nexus import *

def read_logs(directory, entry):
    head_file = os.path.join(directory, entry+'_head.txt')
    meta_file = os.path.join(directory, entry+'_meta.txt')
    if os.path.exists(head_file) or os.path.exists(meta_file):
        logs = NXcollection()
    else:
        return None
    if os.path.exists(head_file):
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
    if os.path.exists(meta_file):
        meta_input = np.genfromtxt(meta_file, delimiter=',', names=True)
        for i, key in enumerate(meta_input.dtype.names):
            logs[key] = [array[i] for array in meta_input]
    return logs


def transfer_logs(entry):
    logs = entry['instrument/logs']
    frame_number = entry['data/frame_number'].size
    if 'MCS1' in logs:
        data = logs['MCS1'][:frame_number]
        entry['monitor1'] = NXmonitor(NXfield(data, name='MCS1'),
                                      NXfield(frame_number, name='frame_number'))
    if 'MCS2' in logs:
        data = logs['MCS2'][:frame_number]
        entry['monitor2'] = NXmonitor(NXfield(data, name='MCS2'),
                                      NXfield(frame_number, name='frame_number'))
    if 'source' not in entry['instrument']:
        entry['instrument/source'] = NXsource()
    entry['instrument/source/name'] = 'Advanced Photon Source'
    entry['instrument/source/type'] = 'Synchrotron X-ray Source'
    entry['instrument/source/probe'] = 'x-ray'
    if 'Storage_Ring_Current' in logs:
        entry['instrument/source/current'] = logs['Storage_Ring_Current']
    if 'UndulatorA_gap' in logs:
        entry['instrument/source/undulator_gap'] = logs['UndulatorA_gap']
    if 'Calculated_filter_transmission' in logs:
        if 'attenuator' not in entry['instrument']:
            entry['instrument/attenuator'] = NXattenuator()
        entry['instrument/attenuator/attenuator_transmission'] = logs['Calculated_filter_transmission']
        
    

def link_data(directory, entry, path):
    files = [f for f in os.listdir(directory) 
             if (os.path.splitext(f)[0] == entry and (f.endswith('.nxs') or 
                                                      f.endswith('.h5')))]
    if len(files) == 1:
        data_directory = os.path.basename(os.path.dirname(directory))
        data_file = os.path.join(data_directory, files[0])
        data_target = path
        data_root = nxload(os.path.join(directory, files[0]))
        if data_target not in data_root:
            print('No data in specified path of the raw data file')
            return
        data_shape = data_root[data_target].shape
        if 'data' not in entry:
            entry['data'] = NXdata()
            entry['data/x_pixel'] = np.arange(data_shape[2], dtype=np.int32)
            entry['data/y_pixel'] = np.arange(data_shape[1], dtype=np.int32)
            entry['data/frame_number'] = np.arange(data_shape[0], dtype=np.int32)
            entry['data/data'] = NXlink(data_target, data_file)
        elif entry['data/frame_number'].shape != data_shape[0]:
            del entry['data/frame_number']
            entry['data/frame_number'] = np.arange(data_shape[0], dtype=np.int32)
            if ('data' in entry['data'] and 
                entry['data/data']._filename != data_file):
                del entry['data/data']
                entry['data/data'] = NXlink(data_target, data_file)
        entry['data'].nxsignal = entry['data/data']
        entry['data'].nxaxes = [entry['data/frame_number'], 
                                entry['data/y_pixel'], 
                                entry['data/x_pixel']] 
    else:
        print('No raw data file found')



def main():

    parser = argparse.ArgumentParser(
        description="Link data and metadata to NeXus file")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries')
    parser.add_argument('-p', '--path', default='entry/data/data', 
        help='Path to data in the raw data file')

    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    scan = os.path.basename(directory)
    wrapper_file = os.path.join(sample, label, '%s_%s.nxs' % (sample, scan))

    entries = args.entries
    path = args.path

    root = nxload(wrapper_file, 'rw')    
    for entry in entries:
        link_data(directory, root[entry], path)
        logs = read_logs(directory, entry)
        if logs:
            if 'logs' in root[entry]['instrument']:
                del root[entry]['instrument/logs']
            entry['instrument/logs'] = logs
            transfer_logs(root[entry])

    print 'Linking to ', root.nxfilename

if __name__ == '__main__':
    main()
