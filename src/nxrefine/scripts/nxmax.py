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


def find_maximum(entry):

    field = entry['data'].nxsignal
    if not os.path.exists(field.nxfilename):
        print("'%s' does not exist" % field.nxfilename)
        return

    tic=timeit.default_timer()

    maximum = 0.0
    try:
        mask = entry['instrument/detector/pixel_mask'].nxdata
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

    entry['data'].attrs['maximum'] = maximum
    
    print('\nMaximum counts in %s are' % entry.nxname, maximum)

    toc=timeit.default_timer()
    print(toc-tic, 'seconds for', entry.nxname)


def main():

    parser = argparse.ArgumentParser(
        description="Find maximum counts of the signal in the specified path")
    parser.add_argument('-d', '--directory', required=True, 
                        help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be processed')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing maximum')

    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    scan = os.path.basename(directory)
    wrapper_file = os.path.join(sample, label, '%s_%s.nxs' % (sample, scan))
    entries = args.entries
    overwrite = args.overwrite

    if not os.path.exists(wrapper_file):
        print("'%s' does not exist" % wrapper_file)
        sys.exit(1)
    else:
        root = nxload(wrapper_file, 'rw')

    print('Finding maximum in ', wrapper_file)

    for entry in entries:
        print('Processing', entry)
        if 'maximum' in root[entry]['data'].attrs and not overwrite:
            print('Maximum value already determined')
        else:
            find_maximum(root[entry])


if __name__=="__main__":
    main()
