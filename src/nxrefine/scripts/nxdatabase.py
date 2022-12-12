#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import argparse
import os
from pathlib import Path

from nxrefine.nxdatabase import NXDatabase


def main():
    parser = argparse.ArgumentParser(description="Populate the database based \
            on local NeXus files")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')

    args = parser.parse_args()

    dir = Path(args.directory)
    print(f'Looking in directory {dir}')
    db_path = dir.parent.parent.joinpath('tasks', 'nxdatabase.db')
    nxdb = NXDatabase(db_path)
    nxdb.sync_db(args.directory)


if __name__ == "__main__":
    main()
