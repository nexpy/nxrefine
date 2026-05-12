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

from nxrefine.nxparent import NXParent


def main():

    parser = argparse.ArgumentParser(
        description="Choose parameters for NXReduce operations")
    parser.add_argument('-p', '--parent', required=True,
                        help='parent scans file (*_scans.nxs)')
    parser.add_argument('-t', '--threshold', type=float,
                        help='peak threshold')
    parser.add_argument('--first-frame', type=int, dest='first_frame',
                        help='first frame')
    parser.add_argument('--last-frame', type=int, dest='last_frame',
                        help='last frame')
    parser.add_argument('-P', '--polar-max', type=float, dest='polar_max',
                        help='maximum polar angle in degrees')
    parser.add_argument('-T', '--hkl-tolerance', type=float,
                        dest='hkl_tolerance',
                        help='tolerance for including peak in Å-1')
    parser.add_argument('-m', '--monitor',
                        help='monitor to use in normalizations')
    parser.add_argument('-n', '--norm', type=float,
                        help='normalization to monitor')
    parser.add_argument('-q', '--qmin', type=float,
                        help='minimum Q in Å-1 used in transmission estimates')
    parser.add_argument('-Q', '--qmax', type=float,
                        help='maximum Q in Å-1 used in PDF tapers')
    parser.add_argument('-r', '--radius', type=float,
                        help='radius of punched holes in Å-1')
    parser.add_argument('--scan-path', dest='scan_path',
                        help='path to scan variable within scan files')
    parser.add_argument('--scan-units', dest='scan_units',
                        help='units for scan variable')
    parser.add_argument('-o', '--output', action='store_true',
                        help='print current parameters')

    args = parser.parse_args()

    parent = NXParent(Path(args.parent).resolve())
    if args.output:
        print('Current NXParent settings\n-------------------------')
        fields = [
            ('Threshold', 'threshold'),
            ('First Frame', 'first_frame'),
            ('Last Frame', 'last_frame'),
            ('Maximum Polar Angle', 'polar_max'),
            ('HKL Tolerance', 'hkl_tolerance'),
            ('Monitor', 'monitor'),
            ('Normalization', 'norm'),
            ('Qmin', 'qmin'),
            ('Qmax', 'qmax'),
            ('Radius', 'radius'),
            ('Scan Path', 'scan_path'),
            ('Scan Units', 'scan_units'),
        ]
        for label, key in fields:
            value = parent.get_setting(key)
            print(f"{label} = {value if value is not None else 'not set'}")
    else:
        params = {
            'threshold':     args.threshold,
            'first_frame':   args.first_frame,
            'last_frame':    args.last_frame,
            'polar_max':     args.polar_max,
            'hkl_tolerance': args.hkl_tolerance,
            'monitor':       args.monitor,
            'norm':          args.norm,
            'qmin':          args.qmin,
            'qmax':          args.qmax,
            'radius':        args.radius,
            'scan_path':     args.scan_path,
            'scan_units':    args.scan_units,
        }
        parent.write_settings(**{k: v for k, v in params.items()
                                 if v is not None})


if __name__ == "__main__":
    main()
