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


def link_files(nexus_file, scan_dir, filenames, extension):
    for f in filenames:
        if f+extension in os.listdir(scan_dir):
            scan_file = os.path.join(scan_dir, f+extension)
            make_data(nexus_file[f], scan_file)
    

def make_data(entry, scan_file):
    root = nxload(scan_file)
    if 'data' not in entry:
        entry.data = NXdata()
    scan_data = root['entry/data']
    entry.data.x_pixel = np.arange(scan_data.data.shape[2], dtype=np.int32)
    entry.data.y_pixel = np.arange(scan_data.data.shape[1], dtype=np.int32)
    entry.data.frame_number = np.arange(scan_data.data.shape[0], dtype=np.int32)
    scan_parent = os.path.basename(os.path.dirname(scan_file))
    scan_link = os.path.join(scan_parent, os.path.basename(scan_file))
    if 'data' in entry.data:
        del entry.data['data']
    entry.data.data = NXlink(target='/entry/data/data', file=scan_link)
    entry.data.nxsignal = entry.data.data
    entry.data.nxaxes = [entry.data.frame_number, entry.data.y_pixel, 
                         entry.data.x_pixel]
    return entry


def main():

    parser = argparse.ArgumentParser(
        description="Retroactively initialize data in wrapper NeXus file")
    parser.add_argument('-s', '--sample', help='sample name')
    parser.add_argument('-l', '--label', default='', help='sample label')
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-f', '--filenames', 
        default=['f1', 'f2', 'f3'], nargs='+',
        help='names of NeXus files to be linked to this file')
    parser.add_argument('-e', '--extension', default='.h5', 
        help='extension of raw data files')

    args = parser.parse_args()

    sample = args.sample
    label = args.label
    directory = args.directory.rstrip('/')
    if sample is None and label == '':
        sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
        label = os.path.basename(os.path.dirname(directory))
        directory = os.path.basename(directory)
    filenames = args.filenames
    extension = args.extension
    id not extension.startswith('.'):
        extension = '.' + extension

    scan_dir = os.path.join(sample, label, directory)
    scan = os.path.basename(scan_dir)
    if scan:
        nexus_file = nxload(os.path.join(sample, label, sample+'_'+scan+'.nxs'), 'rw')
    else:
        nexus_file = nxload(os.path.join(sample, label, name+'.nxs'), 'rw')
    link_files(nexus_file, scan_dir, filenames, extension)
    print('Linking to ', nexus_file.nxfilename)

if __name__ == '__main__':
    main()

