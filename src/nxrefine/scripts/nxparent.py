#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2014-2024, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse
import os
from pathlib import Path

os.environ.setdefault('HDF5_USE_FILE_LOCKING', 'FALSE')

from nexusformat.nexus import nxsetconfig  # noqa: E402

from nxrefine.nxparent import NXParent  # noqa: E402
from nxrefine.nxsettings import NXSettings  # noqa: E402


def main():

    parser = argparse.ArgumentParser(
        description="Create a new NXParent file for a sample, or update an "
                    "existing one")
    parser.add_argument('-d', '--directory', required=True,
                        help='experiment directory')
    parser.add_argument('-s', '--sample', required=True,
                        help='sample name')
    parser.add_argument('-l', '--label', required=True,
                        help='label (sublabel/scan set)')
    parser.add_argument('-p', '--parent', default=None,
                        help='parent prefix (default: sample name)')
    parser.add_argument('-c', '--configuration', default=None,
                        help='configuration file to copy instrument/sample '
                             'info from')
    parser.add_argument('-f', '--file', default=None,
                        help='NeXus file to copy instrument/sample info from')
    parser.add_argument('-m', '--merge', default=None,
                        help='parent file whose scans, settings, transform '
                             'grid, sample and instrument are added to the '
                             'parent file, which is created if necessary; '
                             'existing content and consolidated datasets are '
                             'not changed')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='with --merge, also replace content in the '
                             'parent file that differs from the one being '
                             'merged')
    parser.add_argument('-u', '--update', action='store_true',
                        help='rebuild the consolidated datasets in the '
                             'parent file from the scan files')

    args = parser.parse_args()

    experiment_directory = Path(args.directory).resolve()
    settings = NXSettings(experiment_directory / 'tasks').settings
    analysis_path = settings['instrument'].get('analysis_path', '')
    if analysis_path and experiment_directory.name != analysis_path:
        experiment_directory = experiment_directory / analysis_path

    sample_directory = experiment_directory / args.sample / args.label
    parent_prefix = args.parent if args.parent else args.sample
    parent_file = sample_directory / f'{parent_prefix}_scans.nxs'

    if args.merge or args.update:
        nxsetconfig(lock=3600, lockexpiry=28800)
        parent = NXParent(parent_file)
        if args.merge:
            for change in parent.merge_authored(
                    args.merge, overwrite=args.overwrite):
                print(change)
        if args.update:
            if not parent_file.is_file():
                parser.error(f"'{parent_file}' does not exist")
            parent.update_scan_data()
        return

    source_file = None
    if args.file:
        source_file = Path(args.file).resolve()
    elif args.configuration:
        source_file = Path(args.configuration).resolve()
    else:
        config_dir = experiment_directory / 'configurations'
        configs = sorted(config_dir.glob('*.nxs')) if config_dir.exists() else []
        if configs:
            source_file = configs[0]

    parent = NXParent(parent_file)
    with parent.root:
        parent.initialize()
        if source_file:
            parent.copy_file(source_file)
    if parent.root.nxfile is None:
        parent.root.save(parent_file, 'w')


if __name__ == "__main__":
    main()
