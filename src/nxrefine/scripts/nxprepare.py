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
    parser.add_argument('-s', '--subentry', default='',
                        help='subentry to be processed')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing mask')
    parser.add_argument('-q', '--queue', action='store_true',
                        help='add to server task queue')

    args = parser.parse_args()

    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(directory=args.directory).entries

    mask_parameters = {
        'mask_t1': args.t1, 'mask_h1': args.h1,
        'mask_t2': args.t2, 'mask_h2': args.h2,
    }
    for entry in entries:
        reduce = NXReduce(entry, args.subentry, args.directory, prepare=True,
                          overwrite=args.overwrite,
                          mask_parameters=mask_parameters)
        if args.queue:
            reduce.queue('nxprepare', args)
        else:
            reduce.nxprepare()


if __name__ == "__main__":
    main()
