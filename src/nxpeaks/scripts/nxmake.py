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


def make_nexus_file(sample_name, sample_label, scan_dir, parameter, unit, 
                    filenames, pattern,  mask=None):    
    root = NXroot()
    sample = NXsample()
    sample.name = sample_name
    if sample_label:
        sample.label = sample_label
    if parameter is not None:
        try:
            scan = os.path.basename(scan_dir)
            sample[parameter] = np.float32(re.match(pattern, scan).group(1))
            sample[parameter].attrs['units'] = unit
        except ValueError:
            pass
    root.entry = NXentry(sample)
    for f in filenames:
        if f+'.nxs' in os.listdir(scan_dir):
            root[f] = make_entry(os.path.join(scan_dir, f+'.nxs'), mask)
            root[f].makelink(root.entry.sample)
    return root
    

def make_entry(scan_file, mask=None):
    root = nxload(scan_file)
    entry = NXentry(NXdata())
    entry.filename = root.entry.filename
    entry.start_time = root.entry.start_time
    entry.instrument = root.entry.instrument
    if mask is not None:
        entry.instrument.detector.pixel_mask = mask
        entry.instrument.detector.pixel_mask_applied = False
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
        description="Create composite NeXus files")
    parser.add_argument('-s', '--sample', help='sample name')
    parser.add_argument('-l', '--label', default='', help='sample label')
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-r', '--regular', default='(.*)[kK]',
        help=('regular expression pattern for extracting the parameter value '
              'from the scan directory'))
    parser.add_argument('-p', '--parameter',
        help='name of the varying parameter (assumed to be a sample parameter)')
    parser.add_argument('-u', '--unit', default='K', help='parameter units')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2'], nargs='+',
        help='names of NeXus files to be linked to this file')
    parser.add_argument('-m', '--maskfile', default='pilatus_mask.nxs',
        help='name of the pixel mask file')

    args = parser.parse_args()

    sample_name = args.sample
    sample_label = args.label
    directory = args.directory
    pattern = re.compile(args.regular)
    parameter = args.parameter
    unit = args.unit
    filenames = args.filenames
    if args.maskfile is not None:
        mask = nxload(args.maskfile)['entry/mask']
    else:
        mask = None

    scan_dir = os.path.join(sample_name, sample_label, directory)
    scan = os.path.basename(scan_dir)
    if scan:
        nexus_file = os.path.join(sample_name, sample_label, sample_name + '_' + scan + '.nxs')
    else:
        nexus_file = os.path.join(sample_name, sample_label, sample_name + '.nxs')
    root = make_nexus_file(sample_name, sample_label, scan_dir, 
                           parameter, unit, filenames, pattern, mask)
    root.save(nexus_file, 'w')
    print 'Saving ', nexus_file

if __name__ == '__main__':
    main()

