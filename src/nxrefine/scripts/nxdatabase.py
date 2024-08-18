#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse
from pathlib import Path

from nxrefine.nxdatabase import NXDatabase


def main():
    parser = argparse.ArgumentParser(
        description="Populate the database based on local NeXus files")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')

    args = parser.parse_args()

    directory = Path(args.directory).resolve()
    print(f'Looking in directory {directory}')
    db_path = directory.parent.parent / 'tasks' / 'nxdatabase.db'
    nxdb = NXDatabase(db_path)
    nxdb.sync_db(args.directory)


if __name__ == "__main__":
    main()
