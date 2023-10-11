#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, AXMAS Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import argparse
import sys

from nxrefine.nxreduce import NXMultiReduce, NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Prepare 3D mask around Bragg peaks")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be processed')
    parser.add_argument('--t1', type=float, default=2,
                        help='threshold for smaller convolution')
    parser.add_argument('--h1', type=int, default=11,
                        help='size of smaller convolution')
    parser.add_argument('--t2', type=float, default=0.8,
                        help='threshold for larger convolution')
    parser.add_argument('--h2', type=int, default=51,
                        help='size of larger convolution')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing mask')
    parser.add_argument('-m', '--monitor', action='store_true',
                        help='monitor progress in the command line')
    parser.add_argument('-q', '--queue', action='store_true',
                        help='add to server task queue')

    args = parser.parse_args()

    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(args.directory).entries

    for entry in entries:
        reduce = NXReduce(entry, args.directory, prepare=True,
                          overwrite=args.overwrite,
                          monitor_progress=args.monitor)
        reduce.mask_parameters['threshold_1'] = args.t1
        reduce.mask_parameters['horizontal_size_1'] = args.h1
        reduce.mask_parameters['threshold_2'] = args.t2
        reduce.mask_parameters['horizontal_size_2'] = args.h2
        if args.queue:
            reduce.queue('nxprepare', args)
        else:
            reduce.nxprepare()


if __name__ == "__main__":
    main()
