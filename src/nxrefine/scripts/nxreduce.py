#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2018-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import argparse

from nxrefine.nxreduce import NXMultiReduce, NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Perform data reduction on entries")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be processed')
    parser.add_argument('-l', '--link', action='store_true',
                        help='link wrapper file to raw data')
    parser.add_argument('-m', '--max', action='store_true',
                        help='find maximum counts')
    parser.add_argument('-f', '--find', action='store_true',
                        help='find peaks')
    parser.add_argument('-c', '--copy', action='store_true',
                        help='copy parameters')
    parser.add_argument('-r', '--refine', action='store_true',
                        help='refine lattice parameters')
    parser.add_argument('-p', '--prepare', action='store_true',
                        help='prepare 3D masks')
    parser.add_argument('-t', '--transform', action='store_true',
                        help='perform CCTW transforms')
    parser.add_argument('-b', '--combine', action='store_true',
                        help='combine CCTW transforms')
    parser.add_argument('-P', '--pdf', action='store_true',
                        help='perform PDF transforms')
    parser.add_argument('-R', '--regular', action='store_true',
                        help='perform regular CCTW transforms')
    parser.add_argument('-M', '--mask', action='store_true',
                        help='perform CCTW transforms with 3D mask')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing maximum')
    parser.add_argument('-q', '--queue', action='store_true',
                        help='add to server task queue')

    args = parser.parse_args()

    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(args.directory).entries

    for entry in entries:
        reduce = NXReduce(entry, args.directory, link=args.link,
                          maxcount=args.max, find=args.find, copy=args.copy,
                          refine=args.refine, prepare=args.prepare,
                          transform=args.transform, combine=args.combine,
                          pdf=args.pdf, regular=args.regular, mask=args.mask,
                          overwrite=args.overwrite)
        if args.queue:
            reduce.queue('nxreduce', args)
        else:
            reduce.nxreduce()


if __name__ == "__main__":
    main()
