#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2014-2024, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse
from pathlib import Path

from nxrefine.nxparent import NXParent
from nxrefine.nxsettings import NXSettings


def main():

    parser = argparse.ArgumentParser(
        description="Create a new NXParent file for a sample")
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

    args = parser.parse_args()

    experiment_directory = Path(args.directory).resolve()
    settings = NXSettings(experiment_directory / 'tasks').settings
    analysis_path = settings['instrument'].get('analysis_path', '')
    if analysis_path and experiment_directory.name != analysis_path:
        experiment_directory = experiment_directory / analysis_path

    sample_directory = experiment_directory / args.sample / args.label
    parent_prefix = args.parent if args.parent else args.sample
    parent_file = sample_directory / f'{parent_prefix}_scans.nxs'

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
