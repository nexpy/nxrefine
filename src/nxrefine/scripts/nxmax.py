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
        description="Find maximum counts of the signal in the specified path")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be processed')
    parser.add_argument('-f', '--first', type=int, help='first frame')
    parser.add_argument('-l', '--last', type=int, help='last frame')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing maximum')
    parser.add_argument('-m', '--monitor', action='store_true',
                        help='monitor progress in the command line')
    parser.add_argument('-q', '--queue', nargs="?", default=argparse.SUPPRESS,
                        help='add to server task queue')

    args = parser.parse_args()

    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(args.directory).entries

    for entry in entries:
        reduce = NXReduce(entry, args.directory, maxcount=True,
                          first=args.first, last=args.last,
                          overwrite=args.overwrite,
                          monitor_progress=args.monitor)
        if 'queue' in args:
            reduce.queue('nxmax', args)
        else:
            reduce.nxmax()


if __name__ == "__main__":
    main()
