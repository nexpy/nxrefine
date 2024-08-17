#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse

from nxrefine.nxreduce import NXMultiReduce, NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Copy instrument parameters from a parent file")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be searched')
    parser.add_argument('-p', '--parent',
                        help='file name of file to copy from')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing peaks')
    parser.add_argument('-q', '--queue', action='store_true',
                        help='add to server task queue')

    args = parser.parse_args()

    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(args.directory).entries

    for entry in entries:
        reduce = NXReduce(entry, args.directory, parent=args.parent, copy=True,
                          overwrite=args.overwrite)
        if args.queue:
            reduce.queue('nxcopy', args)
        else:
            reduce.nxcopy()


if __name__ == "__main__":
    main()
