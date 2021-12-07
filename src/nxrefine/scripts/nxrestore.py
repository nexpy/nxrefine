# -----------------------------------------------------------------------------
# Copyright (c) 2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import argparse
import os

from nxrefine.nxreduce import NXMultiReduce, NXReduce
from nxrefine.nxrefine import NXRefine


def main():

    parser = argparse.ArgumentParser(
        description="Restore orientation from CCTW parameter file")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be processed')

    args = parser.parse_args()

    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(args.directory).entries

    for entry in entries:
        reduce = NXReduce(entry, args.directory)
        if os.path.exists(reduce.settings_file):
            refine = NXRefine(reduce.entry)
            refine.read_settings(reduce.settings_file)
            refine.write_parameters()
            if os.path.exists(reduce.transform_file):
                refine.prepare_transform(reduce.transform_file)
            if os.path.exists(reduce.masked_transform_file):
                refine.prepare_transform(reduce.masked_transform_file,
                                         mask=True)
        reduce = NXMultiReduce(args.directory)
        if os.path.exists(reduce.transform_file):
            reduce.prepare_combine()
        if os.path.exists(reduce.masked_transform_file):
            reduce.mask = True
            reduce.prepare_combine()


if __name__ == "__main__":
    main()
