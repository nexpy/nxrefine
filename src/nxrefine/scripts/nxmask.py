#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2015, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import argparse, os, socket, sys, timeit
import numpy as np
from nexusformat.nexus import *
from nxpeaks import __version__

def apply_mask(entries, mask):
    for entry in entries:
        try:
            entry['instrument/detector/pixel_mask'] = mask
            entry['instrument/detector/pixel_mask_applied'] = False
            print 'Mask applied to %s' % entry
            note = NXnote('nxmask '+' '.join(sys.argv[1:]), 
                          ('Current machine: %s\n'
                           'Current working directory: %s\n'
                           'Mask file: %s')
                         % (socket.gethostname(), os.getcwd(), mask.nxfilename))
            entry['nxmask'] = NXprocess(program='nxmask', 
                                        sequence_index=len(entry.NXprocess)+1, 
                                        version=__version__, 
                                        note=note)
        except KeyError:
            pass

def main():

    parser = argparse.ArgumentParser(
        description="Add mask to the specified NeXus file")
    parser.add_argument('-f', '--filename', required=True)
    parser.add_argument('-e', '--entry', nargs='+')
    parser.add_argument('-m', '--maskfile', default='pilatus_mask.nxs')
    parser.add_argument('-p', '--path', default='entry/mask')

    args = parser.parse_args()

    name, ext = os.path.splitext(args.filename)
    if ext == '':
        args.filename = args.filename + '.nxs'
    name, ext = os.path.splitext(args.maskfile)
    if ext == '':
        args.maskfile = args.maskfile + '.nxs.'
    root = nxload(args.filename, 'rw')
    if args.entry is not None:
        entries = [root[entry] for entry in args.entry]
    else:
        entries = root.NXentry
    mask = nxload(args.maskfile)[args.path]
    apply_mask(entries, mask)


if __name__=="__main__":
    main()
