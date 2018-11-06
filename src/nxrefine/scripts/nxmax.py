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
        description="Find maximum counts of the signal in the specified path")
    parser.add_argument('-d', '--directory', required=True, 
                        help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be processed')
    parser.add_argument('-f', '--first', type=int, help='first frame')
    parser.add_argument('-l', '--last', type=int, help='last frame')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing maximum')
    parser.add_argument('-q', '--queue', action='store_true',
                        help='add to server task queue')

    args = parser.parse_args()

    for entry in args.entries:
        reduce = NXReduce(entry, args.directory, maxcount=True,
                          first=args.first, last=args.last, 
                          overwrite=args.overwrite)
        if args.queue:
            reduce.queue()
        else:
            reduce.nxmax()


if __name__=="__main__":
    main()
