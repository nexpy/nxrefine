#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2015-2024, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse

import numpy as np

from nxrefine.nxreduce import NXMultiReduce, NXReduce


def to_array(triple):
    if triple is None:
        return None
    qmin, qstep, qmax = (np.float32(v) for v in triple)
    shape = int(np.round((qmax - qmin) / qstep, 2)) + 1
    return np.linspace(qmin, qmax, shape)


def main():

    parser = argparse.ArgumentParser(description="Perform CCTW transform")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be processed')
    parser.add_argument('-qh', nargs=3, help='Qh - min, step, max')
    parser.add_argument('-qk', nargs=3, help='Qk - min, step, max')
    parser.add_argument('-ql', nargs=3, help='Ql - min, step, max')
    parser.add_argument('-R', '--regular', action='store_true',
                        help='perform regular transform')
    parser.add_argument('-M', '--mask', action='store_true',
                        help='perform transform with 3D mask')
    parser.add_argument('-s', '--subentry', default='',
                        help='subentry to be processed')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing transforms')
    parser.add_argument('-q', '--queue', action='store_true',
                        help='add to server task queue')

    args = parser.parse_args()

    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(directory=args.directory).entries

    for entry in entries:
        reduce = NXReduce(
            entry, args.subentry, args.directory, transform=True,
            Qh=to_array(args.qh), Qk=to_array(args.qk), Ql=to_array(args.ql),
            regular=args.regular, mask=args.mask, overwrite=args.overwrite)
        if args.queue:
            reduce.queue('nxtransform', args)
        else:
            if reduce.regular:
                reduce.nxtransform()
            if reduce.mask:
                reduce.nxtransform(mask=True)


if __name__ == "__main__":
    main()
