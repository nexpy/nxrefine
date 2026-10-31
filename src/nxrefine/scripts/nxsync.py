#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse
import sys
from pathlib import Path

from nxrefine.nxdatabase import FAILED, IN_PROGRESS, QUEUED, NXDatabase

STATUS_NAMES = {QUEUED: 'queued', IN_PROGRESS: 'in progress',
                FAILED: 'failed'}


def scan_file(directory):
    """Return the path of the scan file of a scan directory."""
    sample = directory.parent.parent.name
    return directory.parent / f"{sample}_{directory.name}.nxs"


def main():
    parser = argparse.ArgumentParser(
        description="Update the workflow database from the contents of the "
                    "scan files, as the Sync button does in the Manage "
                    "Workflows dialog. The exit code is 0 if all the scans "
                    "are synchronized and 1 if any fail.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('-d', '--directory', nargs='+',
                        help='scan directories, e.g., sample/label/scan')
    source.add_argument('-f', '--file', nargs='+',
                        help='scan files, e.g., sample/label/sample_scan.nxs')

    args = parser.parse_args()

    if args.directory:
        scan_files = [scan_file(Path(directory).resolve())
                      for directory in args.directory]
    else:
        scan_files = [Path(file).resolve() for file in args.file]

    databases = {}
    failed = False
    for wrapper_file in scan_files:
        try:
            task_directory = wrapper_file.parent.parent.parent / 'tasks'
            if task_directory not in databases:
                task_directory.mkdir(exist_ok=True)
                databases[task_directory] = NXDatabase(
                    task_directory / 'nxdatabase.db')
            database = databases[task_directory]
            before = database.unfinished_tasks(wrapper_file)
            database.update_file(wrapper_file)
            after = database.unfinished_tasks(wrapper_file)
            print(f"Synchronized {wrapper_file}")
            reset = [f"{task} ({STATUS_NAMES[status]})"
                     for task, status in before.items()
                     if after.get(task) != status]
            if reset:
                print(f"  Reset to match the file: {', '.join(reset)}")
        except Exception as error:
            failed = True
            print(f"nxsync: {wrapper_file.name}: {error}", file=sys.stderr)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
