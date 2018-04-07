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


def link_files(nexus_file, scan_dir, filenames):    
    for f in filenames:
        if f+'.nxs' in os.listdir(scan_dir):
            if f not in nexus_file:
                nexus_file[f] = NXentry()
            scan_file = os.path.join(scan_dir, f+'.nxs')
            make_data(nexus_file[f], scan_file)
    

def make_data(entry, scan_file):
    root = nxload(scan_file)
    if 'filename' in root.entry:
        entry.filename = root.entry.filename
    if 'start_time' in root.entry:
        entry.start_time = root.entry.start_time
    if 'instrument' not in entry:
        entry.instrument = root.entry.instrument
    if 'detector' not in entry.instrument:
        entry.instrument.detector = NXdetector()
    entry.instrument.detector.frame_start = root.entry.instrument.detector.frame_start
    entry.instrument.detector.frame_time = root.entry.instrument.detector.frame_time
    if 'data' not in entry:
        entry.data = NXdata()
    entry.data.x_pixel = root.entry.data.x_pixel
    entry.data.y_pixel = root.entry.data.y_pixel
    entry.data.frame_number = root.entry.data.frame_number
    scan_parent = os.path.basename(os.path.dirname(scan_file))
    scan_link = os.path.join(scan_parent, os.path.basename(scan_file))
    if 'data' in entry.data:
        del entry.data['data']
    entry.data.data = NXlink(target='/entry/data/data', file=scan_link)
    entry.data.nxsignal = entry.data.data
    entry.data.nxaxes = [entry.data.frame_number, entry.data.y_pixel, 
                         entry.data.x_pixel]
    for subentry in root.entry.NXsubentry:
        entry[subentry.nxname] = subentry
    for process in root.entry.NXprocess:
        entry[process.nxname] = process 
    return entry


def main():

    parser = argparse.ArgumentParser(
        description="Link image stack to wrapper NeXus file")
    parser.add_argument('-s', '--sample', help='sample name')
    parser.add_argument('-l', '--label', default='', help='sample label')
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2'], nargs='+',
        help='names of NeXus files to be linked to this file')

    args = parser.parse_args()

    sample = args.sample
    label = args.label
    directory = args.directory.rstrip('/')
    if sample is None and label == '':
        sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
        label = os.path.basename(os.path.dirname(directory))
        directory = os.path.basename(directory)
    filenames = args.filenames

    scan_dir = os.path.join(sample, label, directory)
    scan = os.path.basename(scan_dir)
    if scan:
        nexus_file = nxload(os.path.join(sample, label, sample+'_'+scan+'.nxs'), 'rw')
    else:
        nexus_file = nxload(os.path.join(sample, label, name+'.nxs'), 'rw')
    link_files(nexus_file, scan_dir, filenames)
    print('Linking to ', nexus_file.nxfilename)

if __name__ == '__main__':
    main()

