#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2015-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault('HDF5_USE_FILE_LOCKING', 'FALSE')

from nxrefine.nxreduce import NXMultiReduce, NXReduce  # noqa: E402


READY = 0
WAITING_FOR_DATA = 1
FAILED = 2
WAITING_FOR_PARENT = 3


def main():

    parser = argparse.ArgumentParser(
        description="Print True if the entries of a scan are ready to be "
                    "analyzed and False if not. The exit code is 0 if "
                    "ready, 1 if waiting for raw data or log files, 3 if "
                    "waiting for the parent file to be set up (orientation "
                    "matrix or transform grid), and 2 if the check fails.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('-f', '--file', help='raw data file, e.g., f1.h5')
    source.add_argument('-d', '--directory', help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+',
                        help='names of entries to be checked')
    parser.add_argument('-q', '--quiet-seconds', type=float, default=30.0,
                        help='minimum time since the raw data and log '
                             'files were last modified (default: 30)')

    args = parser.parse_args()

    try:
        if args.file:
            raw_file = Path(args.file).resolve()
            directory = raw_file.parent
            entries = [raw_file.stem]
        else:
            directory = Path(args.directory).resolve()
            entries = args.entries
        if not directory.is_dir():
            raise ValueError(f"'{directory}' is not a directory")
        if not entries:
            entries = NXMultiReduce(directory=directory).entries
        reasons = []
        for entry in entries:
            ready, entry_reasons = NXReduce(
                entry, directory=directory).link_ready(args.quiet_seconds)
            reasons.extend((kind, f"{entry}: {message}")
                           for kind, message in entry_reasons)
    except Exception as error:
        print(f"nxready: {error}", file=sys.stderr)
        sys.exit(FAILED)

    print(not reasons)
    for kind, message in reasons:
        print(message, file=sys.stderr)
    if not reasons:
        sys.exit(READY)
    elif any(kind == 'data' for kind, message in reasons):
        sys.exit(WAITING_FOR_DATA)
    else:
        sys.exit(WAITING_FOR_PARENT)


if __name__ == "__main__":
    main()
