#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2015, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import argparse, os, sys, timeit
import numpy as np
from nexusformat.nexus import *

def apply_mask(root, entries, mask):
    for entry in entries:
        if 'instrument/detector' in root[entry]:
            entry['instrument/detector/pixel_mask'] = mask
            entry['instrument/detector/pixel_mask_applied'] = False
            print 'Mask applied to %s' % entry

def main():

    parser = argparse.ArgumentParser(
        description="Add mask to the specified NeXus file")
    parser.add_argument('-d', '--directory', default='./')
    parser.add_argument('-f', '--filename', required=True)
    parser.add_argument('-e', '--entry', nargs='+')
    parser.add_argument('-m', '--maskfile', default='pilatus_mask.nxs')
    parser.add_argument('-p', '--path', default='/entry/mask')

    args = parser.parse_args()

    root = nxload(os.path.join(args.directory, args.filename), 'rw')
    if arg.entry is not None:
        entries = [root[entry] for entry in arg.entry]
    else:
        entries = root.NXentry
    mask = nxload(args.maskfile)[args.path]
    apply_mask(root, entries, mask)


if __name__=="__main__":
    main()
