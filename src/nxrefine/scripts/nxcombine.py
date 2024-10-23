#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse

from nxrefine.nxreduce import NXMultiReduce


def main():

    parser = argparse.ArgumentParser(
        description="Combine CCTW transforms")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be combined.')
    parser.add_argument('-R', '--regular', action='store_true',
                        help='combine transforms')
    parser.add_argument('-M', '--mask', action='store_true',
                        help='combine transforms with 3D mask')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing transform')
    parser.add_argument('-q', '--queue', action='store_true',
                        help='add to server task queue')

    args = parser.parse_args()

    reduce = NXMultiReduce(args.directory, entries=args.entries,
                           combine=True, regular=args.regular, mask=args.mask,
                           overwrite=args.overwrite)
    if args.queue:
        reduce.queue('nxcombine', args)
    else:
        if reduce.regular:
            reduce.nxcombine()
        elif reduce.mask:
            reduce.nxcombine(mask=True)


if __name__ == "__main__":
    main()
