#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse

from nxrefine.nxreduce import NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Set scan file as parent by creating a symbolic link")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')

    args = parser.parse_args()

    reduce = NXReduce(directory=args.directory)
    reduce.make_parent()


if __name__ == "__main__":
    main()
