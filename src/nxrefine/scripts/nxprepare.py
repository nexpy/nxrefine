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
from nxrefine.nxreduce import NXMultiReduce, NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Prepare 3D mask around Bragg peaks")
    parser.add_argument('-d', '--directory', required=True, 
                        help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+', 
                        help='names of entries to be processed')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing mask')
    parser.add_argument('-q', '--queue', action='store_true',
                        help='add to server task queue')

    args = parser.parse_args()

    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(args.directory).entries

    for entry in entries:
        reduce = NXReduce(entry, args.directory, prepare=True,
                          overwrite=args.overwrite)
        if args.queue:
            reduce.queue()
        else:
            reduce.nxprepare()


if __name__=="__main__":
    main()
