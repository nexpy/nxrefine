#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import argparse

from nxrefine.nxreduce import NXMultiReduce, NXReduce


def main():

    parser = argparse.ArgumentParser(description="Perform CCTW transform")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be processed')
    parser.add_argument('-m', '--mask', action='store_true',
                        help='use 3D mask')
    parser.add_argument('-qh', nargs=3, help='Qh - min, step, max')
    parser.add_argument('-qk', nargs=3, help='Qk - min, step, max')
    parser.add_argument('-ql', nargs=3, help='Ql - min, step, max')
    parser.add_argument('-r', '--radius', default=200,
                        help='radius of mask around each peak (in pixels)')
    parser.add_argument('-w', '--width', default=3,
                        help='width of masked region (in frames)')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing transforms')
    parser.add_argument('-q', '--queue', action='store_true',
                        help='add to server task queue')

    args = parser.parse_args()

    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(args.directory).entries

    for entry in entries:
        reduce = NXReduce(
            entry, args.directory, transform=True, mask=args.mask, Qh=args.qh,
            Qk=args.qk, Ql=args.ql, radius=args.radius, width=args.width,
            overwrite=args.overwrite)
        if args.mask:
            if args.queue:
                reduce.queue()
            else:
                reduce.nxmasked_transform()
        else:
            if args.queue:
                reduce.queue()
            else:
                reduce.nxtransform()


if __name__ == "__main__":
    main()
