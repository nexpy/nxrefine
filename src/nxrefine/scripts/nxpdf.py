#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2021-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import argparse

from nxrefine.nxreduce import NXMultiReduce


def main():

    parser = argparse.ArgumentParser(description="Calculate PDF transforms")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-l', '--laue', nargs='?', default=None,
                        help='Laue group to be used if different from file')
    parser.add_argument('-r', '--radius', type=float,
                        help='radius of punched holes in Å-1')
    parser.add_argument('-Q', '--Qmax', type=float,
                        help='Maximum Q in Å-1 used in PDF tapers')
    parser.add_argument('-R', '--regular', action='store_true',
                        help='Calculate using regular transforms')
    parser.add_argument('-M', '--mask', action='store_true',
                        help='Calculate using masked transforms')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing transforms')
    parser.add_argument('-q', '--queue', action='store_true',
                        help='add to server task queue')

    args = parser.parse_args()

    reduce = NXMultiReduce(args.directory, pdf=True,
                           laue=args.laue, radius=args.radius, qmax=args.Qmax,
                           regular=args.regular, mask=args.mask,
                           overwrite=args.overwrite)
    if args.queue:
        reduce.queue('nxpdf', args)
    else:
        if reduce.regular:
            reduce.nxpdf()
        if reduce.mask:
            reduce.nxpdf(mask=True)


if __name__ == "__main__":
    main()
