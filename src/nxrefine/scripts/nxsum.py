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

    parser = argparse.ArgumentParser(description="Sum raw data files")
    parser.add_argument('-d', '--directory', required=True,
                        help='directory containing summed files')
    parser.add_argument('-c', '--create', action='store_true',
                        help='create the sum file and directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be summed')
    parser.add_argument('-s', '--scans', nargs='+', required=True,
                        help='list of scan directories to be summed')
    parser.add_argument('-u', '--update', action='store_true',
                        help='update links to existing summed files')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing summed files')

    args = parser.parse_args()

    if args.create:
        reduce = NXMultiReduce(args.directory, overwrite=True)
        reduce.nxsum(args.scans)
    else:
        for entry in args.entries:
            reduce = NXReduce(entry, args.directory, overwrite=args.overwrite)
            reduce.nxsum(args.scans, update=args.update)


if __name__ == "__main__":
    main()
