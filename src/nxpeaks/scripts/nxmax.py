#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import argparse, os, sys, timeit
import numpy as np
from nexusformat.nexus import *

def find_maximum(node):
    maximum = 0.0
    try:
        mask = node.nxentry['instrument/detector/pixel_mask'].nxdata
        if len(mask.shape) > 2:
            mask = mask[0]
    except Exception:
        mask = None
    if len(node.shape) == 2:
        maximum = node[:,:].max()
    else:
        chunk_size = node.nxfile[node.nxpath].chunks[0]
        for i in range(0, node.shape[0], chunk_size):
            try:
                print 'Processing', i
                v = node[i:i+chunk_size,:,:]
            except IndexError as error:
                pass
            if mask is not None:
                v = np.ma.masked_array(v)
                v.mask = mask
            if maximum < v.max():
                maximum = v.max()
    return maximum


def save_maximum(node, maximum):
    node.nxgroup.attrs['maximum'] = maximum


def main():

    parser = argparse.ArgumentParser(
        description="Find maximum counts in the specified path")
    parser.add_argument('-d', '--directory', default='./')
    parser.add_argument('-f', '--filename', required=True)
    parser.add_argument('-p', '--path', default='/entry/data/data')
    args = parser.parse_args()
    tic=timeit.default_timer()
    root = nxload(os.path.join(args.directory, args.filename), 'rw')
    maximum = find_maximum(root[args.path])
    print 'Maximum counts are ', maximum
    save_maximum(root[args.path], maximum)
    toc=timeit.default_timer()
    print toc-tic, 'seconds for', args.filename


if __name__=="__main__":
    main()
