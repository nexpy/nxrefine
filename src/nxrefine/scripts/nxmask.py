#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
from __future__ import print_function
import argparse
from nxrefine.nxreduce import NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Calculate 3D mask from the Bragg peak locations")
    parser.add_argument('-d', '--directory', required=True, 
                        help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be processed')
    parser.add_argument('-r', '--radius', default=200, 
                        help='radius of mask around each peak (in pixels)')
    parser.add_argument('-w', '--width', default=3, 
                        help='width of masked region (in frames)')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing maximum')

    args = parser.parse_args()

    for entry in args.entries:
        reduce = NXReduce(entry, args.directory, mask3D=True,
                          radius=args.radius, width=args.width,
                          overwrite=args.overwrite)
        reduce.nxmask()


if __name__=="__main__":
    main()
