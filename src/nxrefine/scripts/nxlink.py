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
        description="Link data and metadata to NeXus file")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be searched')
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
        reduce = NXReduce(entry, args.directory, link=True,
                          overwrite=args.overwrite)
        if args.queue:
            reduce.queue('nxlink', args)
        else:
            reduce.nxlink()


if __name__ == "__main__":
    main()
