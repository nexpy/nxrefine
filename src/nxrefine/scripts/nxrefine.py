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

    parser = argparse.ArgumentParser(
        description="Refine lattice parameters and goniometer angles")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be processed')
    parser.add_argument('-l', '--lattice', action='store_true',
                        help='refine lattice parameters')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing maximum')
    parser.add_argument('-q', '--queue', nargs="?", default=argparse.SUPPRESS,
                        help='add to server task queue')

    args = parser.parse_args()

    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(args.directory).entries

    for i, entry in enumerate(entries):
        if i == 0:
            lattice = args.lattice
        else:
            lattice = False
        reduce = NXReduce(entry, args.directory, refine=True,
                          lattice=lattice, overwrite=args.overwrite)
        if 'queue' in args:
            reduce.queue('nxrefine', args)
        else:
            reduce.nxrefine()


if __name__ == "__main__":
    main()
