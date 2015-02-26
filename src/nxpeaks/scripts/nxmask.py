#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2015, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import os, getopt, sys, timeit
import numpy as np
from nexusformat.nexus import *

def apply_mask(root, entry, mask):
    if entry is None:
        entries = root.NXentry
    else:
        entries = [root[entry]]
    for entry in entries:
        if 'instrument/detector' in entry:
            entry['instrument/detector/pixel_mask'] = mask
            entry['instrument/detector/pixel_mask_applied'] = False
            print 'Mask applied to %s' % entry

def main():
    help = "nxmask -d <directory> -f <filename> -e <entry> -m <maskfile> -p <path>"
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hd:f:e:m:p:",
                                   ["directory=", "filename=", "entry=", 
                                    "mask=", "path="])
    except getopt.GetoptError:
        print help
        sys.exit(2)
    directory = './'
    filename = None
    entry = None
    maskfile = 'pilatus_mask.nxs'
    path = 'entry/mask'
    for opt, arg in opts:
        if opt == '-h':
            print help
            sys.exit()
        elif opt in ('-f', '--filename'):
            filename = arg
        elif opt in ('-d', '--directory'):
            directory = arg
        elif opt in ('-e', '--entry'):
            entry= arg
        elif opt in ('-m', '--mask'):
            maskfile= arg
        elif opt in ('-p', '--path'):
            path= arg
    if filename is None:
        print help
        sys.exit(2)
    tic=timeit.default_timer()
    root = nxload(os.path.join(directory, filename), 'rw')
    mask = nxload(maskfile)[path]
    apply_mask(root, entry, mask)
    toc=timeit.default_timer()
    print toc-tic, 'seconds for', filename


if __name__=="__main__":
    main()
