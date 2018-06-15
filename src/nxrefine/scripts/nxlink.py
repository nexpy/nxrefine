#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2015, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import argparse
from nxrefine.nxreduce import NXReduce

def main():

    parser = argparse.ArgumentParser(
        description="Link data and metadata to NeXus file")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'],
        nargs='+', help='names of entries to be searched')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing peaks')

    args = parser.parse_args()

    for entry in args.entries:
        reduce = NXReduce(entry, args.directory, link=True,
                          overwrite=args.overwrite)
        reduce.nxlink()


if __name__=="__main__":
    main()
