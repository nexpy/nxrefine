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
from nexusformat.nexus import *

def find_maximum(node):
    maximum = 0.0
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
            if maximum < v.max():
                maximum = v.max()
    return maximum

def save_maximum(node, maximum):
    node.nxgroup.attrs['maximum'] = maximum

def main():
    help = "nxmax -d <directory> -f <filename> -p <path>"
    try:
        opts, args = getopt.getopt(sys.argv[1:],"hd:f:p:",["directory=","filename=","path="])
    except getopt.GetoptError:
        print help
        sys.exit(2)
    directory = './'
    filename = None
    path = '/entry/data/v'
    for opt, arg in opts:
        if opt == '-h':
            print help
            sys.exit()
        elif opt in ('-f', '--filename'):
            filename = arg
        elif opt in ('-d', '--directory'):
            directory = arg
        elif opt in ('-p', '--path'):
            path = arg
    if filename is None:
        print help
        sys.exit(2)
    tic=timeit.default_timer()
    root = nxload(os.path.join(directory, filename), 'rw')
    maximum = find_maximum(root[path])
    print 'Maximum counts are ', maximum
    save_maximum(root[path], maximum)
    toc=timeit.default_timer()
    print toc-tic, 'seconds for', filename


if __name__=="__main__":
    main()
