#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2014-2024, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse

from nxrefine.nxreduce import NXMultiReduce, NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Find peaks within the NeXus data")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be searched')
    parser.add_argument('-t', '--threshold', type=float, help='peak threshold')
    parser.add_argument('-f', '--first', type=int, help='first frame')
    parser.add_argument('-l', '--last', type=int, help='last frame')
    parser.add_argument('-P', '--pixels', type=int,
                        help='minimum pixels between peaks')
    parser.add_argument('-s', '--subentry', default='',
                        help='subentry to be processed')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing peaks')
    parser.add_argument('-p', '--parent', default=None,
                        help='The parent .nxs file to use')
    parser.add_argument('-q', '--queue', action='store_true',
                        help='add to server task queue')

    args = parser.parse_args()

    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(directory=args.directory).entries

    for entry in entries:
        reduce = NXReduce(entry, args.subentry, args.directory, find=True,
                          threshold=args.threshold,
                          first=args.first, last=args.last,
                          min_pixels=args.pixels,
                          overwrite=args.overwrite)
        if args.queue:
            reduce.queue('nxfind', args)
        else:
            reduce.nxfind()


if __name__ == "__main__":
    main()
