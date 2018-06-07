#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2018, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
import argparse
from nxrefine.nxreduce import NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Set scan file as parent by creating a symbolic link")
    parser.add_argument('-d', '--directory', required=True, 
                        help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be searched')
    parser.add_argument('-t', '--threshold', type=float,
                        help='peak threshold - defaults to maximum counts/10')
    parser.add_argument('-f', '--first', type=int, help='first frame')
    parser.add_argument('-l', '--last', type=int, help='last frame')
    parser.add_argument('-r', '--radius', type=int, default=200, 
                        help='radius of mask around each peak (in pixels)')
    parser.add_argument('-w', '--width', type=int, default=3, 
                        help='width of masked region (in frames)')
    parser.add_argument('-s', '--start', action='store_true',
                        help='start data reduction')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing parent')

    args = parser.parse_args()

    reduce = NXReduce(directory=args.directory, overwrite=args.overwrite)
    reduce.make_parent()
    if args.start:
        for entry in args.entries:
            reduce = NXReduce(entry, args.directory, 
                              link=True, maxcount=True, find=True, mask3D=True,
                              threshold=args.threshold, 
                              first=args.first, last=args.last,
                              radius=args.radius, width=args.width,
                              overwrite=args.overwrite)
            reduce.nxlink()
            reduce.nxmax()
            reduce.nxfind()
            reduce.nxmask()


if __name__=="__main__":
    main()
