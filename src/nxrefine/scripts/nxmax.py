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
    s = 'Processing %d' % i
    if i > 0:
        s = '\r' + s
    print(s, end='')


def find_maximum(field):
    maximum = 0.0
    try:
        mask = field.nxentry['instrument/detector/pixel_mask'].nxdata
        if len(mask.shape) > 2:
            mask = mask[0]
    except Exception:
        mask = None
    if len(field.shape) == 2:
        maximum = field[:,:].max()
    else:
        nframes = field.shape[0]
        chunk_size = field.chunks[0]
        for i in range(0, nframes, chunk_size):
            try:
                update_progress(i)
                v = field[i:i+chunk_size,:,:]
            except IndexError as error:
                pass
            if mask is not None:
                v = np.ma.masked_array(v)
                v.mask = mask
            if maximum < v.max():
                maximum = v.max()
            del v
    return maximum


def save_maximum(group, maximum):
    group.attrs['maximum'] = maximum


def main():

    parser = argparse.ArgumentParser(
        description="Find maximum counts of the signal in the specified path")
    parser.add_argument('-d', '--directory', required=True, 
                        help='scan directory')
    parser.add_argument('-e', '--entry', help='entry to be processed')

    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    scan = os.path.basename(directory)
    wrapper_file = os.path.join(sample, label, '%s_%s.nxs' % (sample, scan))
    entry = args.entry

    tic=timeit.default_timer()
    name, ext = os.path.splitext(wrapper_file)
    root = nxload(wrapper_file, 'rw')
    entry = root[entry]
    maximum = find_maximum(entry['data'].nxsignal)
    print('\nMaximum counts are ', maximum)
    save_maximum(entry['data'], maximum)
    toc=timeit.default_timer()
    print(toc-tic, 'seconds for', wrapper_file)


if __name__=="__main__":
    main()
