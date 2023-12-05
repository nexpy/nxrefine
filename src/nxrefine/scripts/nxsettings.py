#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2018-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import argparse
from pathlib import Path

from nxrefine.nxsettings import NXSettings


def main():

    parser = argparse.ArgumentParser(
        description="Set default settings")
    parser.add_argument('-d', '--directory', nargs='?',
                        help='Directory containing the settings file')
    parser.add_argument('-c', '--create', action='store_true',
                        help='Create settings file if necessary')
    parser.add_argument('-i', '--input', action='store_true',
                        help='Input parameters')

    args = parser.parse_args()

    if args.directory:
        settings = NXSettings(directory=Path(args.directory).resolve(),
                              create=args.create)
    else:
        settings = NXSettings()
    print(f'Default settings stored in {settings.directory}')
    if args.input:
        settings.input_defaults()


if __name__ == "__main__":
    main()
