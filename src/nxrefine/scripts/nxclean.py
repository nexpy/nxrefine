#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse

from nxrefine.nxparent import NXParent


def main():

    parser = argparse.ArgumentParser(
        description="Remove old scan-file backups created during restructuring")
    parser.add_argument('-d', '--directory', required=True,
                        help='experiment directory containing the parent file')
    parser.add_argument('-p', '--parent', required=True,
                        help='parent file name (must end with _scans.nxs)')
    parser.add_argument('--days', type=int, default=30,
                        help='delete backups older than this many days '
                             '(default: 30; use 0 to remove all backups)')

    args = parser.parse_args()

    from pathlib import Path
    parent_file = Path(args.directory) / args.parent
    parent = NXParent(parent_file)
    parent.clean_backups(days=args.days)


if __name__ == "__main__":
    main()
