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
        chunk_size = field.chunks[0]
        for i in range(0, field.shape[0], chunk_size):
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
    parser.add_argument('-d', '--directory', default='./',
                        help='directory containing the NeXus file')
    parser.add_argument('-f', '--filename', required=True,
                         help='NeXus file name')
    parser.add_argument('-p', '--path', default='/entry/data',
                        help='path of the NXdata group within the NeXus file')
    args = parser.parse_args()
    tic=timeit.default_timer()
    name, ext = os.path.splitext(args.filename)
    if ext == '':
        args.filename = args.filename + '.nxs'
    root = nxload(os.path.join(args.directory, args.filename), 'rw')
    maximum = find_maximum(root[args.path].nxsignal)
    print('Maximum counts are ', maximum)
    save_maximum(root[args.path], maximum)
    toc=timeit.default_timer()
    print(toc-tic, 'seconds for', args.filename)


if __name__=="__main__":
    main()
