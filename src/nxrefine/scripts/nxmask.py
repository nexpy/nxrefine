#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
from __future__ import print_function
import argparse, os, sys, timeit
import numpy as np
from nexusformat.nexus import *


def update_progress(i):
    s = 'Frame %d' % i
    if i > 0:
        s = '\r' + s
    print(s, end='')


def create_mask(entry, radius=200):

    if not os.path.exists(entry['data/data'].nxfilename):
        print("'%s' does not exist" % entry['data/data'].nxfilename)
        return

    if 'data_mask' in entry['data']:
        del entry['data/data_mask']
        
    data_shape = entry['data/data'].shape
    entry['data/data_mask'] = NXfield(shape=data_shape, dtype=np.int8, fillvalue=0)
    mask = entry['data/data_mask']

    tic=timeit.default_timer()
    
    x, y = np.arange(data_shape[2]), np.arange(data_shape[1])
    
    xp, yp, zp = entry['peaks/x'], entry['peaks/y'], entry['peaks/z']
    
    for i in range(len(xp)):
        update_progress(int(zp[i]))
        inside = (x[None,:]-int(xp[i]))**2+(y[:,None]-int(yp[i]))**2 < radius**2
        frame = int(zp[i])
        mask[frame-1:frame+2] = mask[frame-1:frame+2] | inside

    print('\nAll Bragg peaks in %s processed' % entry.nxname)

    toc=timeit.default_timer()
    print(toc-tic, 'seconds for', entry.nxname)


def main():

    parser = argparse.ArgumentParser(
        description="Create 3D mask from the Bragg peak locations")
    parser.add_argument('-d', '--directory', required=True, 
                        help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be processed')
    parser.add_argument('-r', '--radius', default=200, 
                        help='radius of mask around each peak (in pixels)')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing maximum')

    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    scan = os.path.basename(directory)
    wrapper_file = os.path.join(sample, label, '%s_%s.nxs' % (sample, scan))
    entries = args.entries
    radius = args.radius
    overwrite = args.overwrite

    if not os.path.exists(wrapper_file):
        print("'%s' does not exist" % wrapper_file)
        sys.exit(1)
    else:
        root = nxload(wrapper_file, 'rw')

    print('Creating 3D mask in ', wrapper_file)

    for entry in entries:
        print('Processing', entry)
        if 'data_mask' in root[entry]['data'] and not overwrite:
            print('3D mask already created')
        elif 'peaks' not in root[entry]:
            print('No peaks in', entry)
        else:
            create_mask(root[entry], radius)


if __name__=="__main__":
    main()
