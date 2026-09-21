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


def main():

    parser = argparse.ArgumentParser(
        description="Create a new sample directory")
    parser.add_argument('-d', '--directory', required=True,
                        help='experiment directory')
    parser.add_argument('-s', '--sample', required=True,
                        help='sample name')
    parser.add_argument('-l', '--label', required=True,
                        help='sample label')

    args = parser.parse_args()

    if not Path(args.directory).is_dir():
        raise ValueError(f"'{args.directory}' does not exist")

    sample_path = Path(args.directory / args.sample / args.label)
    sample_path.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    main()
