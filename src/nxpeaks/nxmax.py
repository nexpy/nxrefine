#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import os, getopt, sys, timeit
import numpy as np
from nexpy.api.nexus import *

def write_maximum(root):
    maximum = 0.0
    if len(root.entry.data.v.shape) == 2:
        v = root.entry.data.v[:,:]
        maximum = v.max()
    else:
        chunk_size = root.nxfile['/entry/data/v'].chunks[0]
        for i in range(0, root.entry.data.v.shape[0], chunk_size):
            try:
                print 'Processing', i
                v = root.entry.data.v[i:i+chunk_size,:,:]
            except IndexError as error:
                pass
            if maximum < v.max():
                maximum = v.max()
    root.entry.data.v.maximum = maximum
    print 'Maximum counts are ', maximum

def main():
    help = "nxmax -d <directory> -f <filename>"
    try:
        opts, args = getopt.getopt(sys.argv[1:],"hd:f:",["directory=","filename="])
    except getopt.GetoptError:
        print help
        sys.exit(2)
    directory = './'
    filename = None
    for opt, arg in opts:
        if opt == '-h':
            print help
            sys.exit()
        elif opt in ('-f', '--filename'):
            filename = arg
        elif opt in ('-d', '--directory'):
            directory = arg
    if filename is None:
        print help
        sys.exit(2)
    tic=timeit.default_timer()
    root = nxload(os.path.join(directory, filename), 'rw')
    write_maximum(root)
    toc=timeit.default_timer()
    print toc-tic, 'seconds for', filename


if __name__=="__main__":
    main()
