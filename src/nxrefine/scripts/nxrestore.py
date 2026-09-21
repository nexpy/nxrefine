#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse
from pathlib import Path

from nxrefine.nxparent import NXParent


def main():

    parser = argparse.ArgumentParser(
        description="Restore scan files from backups created during "
                    "restructuring")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory (e.g., sample/label/scan) or '
                             'label directory when using -a')
    parser.add_argument('-a', '--all', action='store_true',
                        help='restore all scan files in the label directory')
    args = parser.parse_args()

    directory = Path(args.directory).resolve()

    if args.all:
        label_dir = directory
        parent_files = list(label_dir.glob('*_scans.nxs'))
        if not parent_files:
            raise FileNotFoundError(
                f"No parent file found in '{label_dir}'")
        parent = NXParent(parent_files[0])
        for scan in parent.scans:
            try:
                src = parent.restore_scan(scan)
                print(f"Restored '{Path(scan).stem}.nxs' from '{src.name}'")
            except FileNotFoundError as e:
                print(f"Skipped '{scan}': {e}")
    else:
        label_dir = directory.parent
        parent_files = list(label_dir.glob('*_scans.nxs'))
        if not parent_files:
            raise FileNotFoundError(
                f"No parent file found in '{label_dir}'")
        parent = NXParent(parent_files[0])
        sample = label_dir.parent.name
        scan_stem = f'{sample}_{directory.name}'
        src = parent.restore_scan(scan_stem)
        print(f"Restored '{scan_stem}.nxs' from '{src.name}'")


if __name__ == "__main__":
    main()
