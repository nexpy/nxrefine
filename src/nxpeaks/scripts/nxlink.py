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
import subprocess
from nexusformat.nexus import *


def link_files(nexus_file, scan_dir, filenames, mask=None):    
    for f in filenames:
        if f+'.nxs' in os.listdir(scan_dir):
            if f not in nexus_file:
                nexus_file[f] = NXentry()
            scan_file = os.path.join(scan_dir, f+'.nxs')
            make_data(nexus_file[f], scan_file, mask)
    

def make_data(entry, scan_file, mask=None):
    root = nxload(scan_file)
    entry.filename = root.entry.filename
    entry.start_time = root.entry.start_time
    if 'instrument' not in entry:
        entry.instrument = root.entry.instrument
    if 'detector' not in entry.instrument:
        entry.instrument.detector = NXdetector()
    entry.instrument.detector.frame_start = root.entry.instrument.detector.frame_start
    entry.instrument.detector.frame_time = root.entry.instrument.detector.frame_time
    if mask is not None:
        entry.instrument.detector.pixel_mask = mask
        entry.instrument.detector.pixel_mask_applied = False
    if 'data' not in entry:
        entry.data = NXdata()
    entry.data.x_pixel = root.entry.data.x_pixel
    entry.data.y_pixel = root.entry.data.y_pixel
    entry.data.frame_number = root.entry.data.frame_number
    scan_parent = os.path.basename(os.path.dirname(scan_file))
    scan_link = os.path.join(scan_parent, os.path.basename(scan_file))
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
    parser.add_argument('-m', '--maskfile', help='name of the pixel mask file')

    args = parser.parse_args()

    sample_name = args.sample
    sample_label = args.label
    directory = args.directory
    filenames = args.filenames
    if args.maskfile is not None:
        mask = nxload(args.maskfile)['entry/mask']
    else:
        mask = None

    scan_dir = os.path.join(sample_name, sample_label, directory)
    scan = os.path.basename(scan_dir)
    if scan:
        nexus_file = nxload(os.path.join(sample_name, sample_label, sample_name+'_'+scan+'.nxs'), 'rw')
    else:
        nexus_file = nxload(os.path.join(sample_name, sample_label, sample_name+'.nxs'), 'rw')
    link_files(nexus_file, scan_dir, filenames, mask)
    print 'Linking to ', nexus_file.nxfilename

if __name__ == '__main__':
    main()

