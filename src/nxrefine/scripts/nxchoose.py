#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2018-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import argparse

from nxrefine.nxreduce import NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Choose parameters for NXReduce operations")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-t', '--threshold', type=float,
                        help='peak threshold')
    parser.add_argument('-f', '--first', type=int, help='first frame')
    parser.add_argument('-l', '--last', type=int, help='last frame')
    parser.add_argument('-p', '--polar_max', type=float,
                        help='maximum polar angle in degrees')
    parser.add_argument('-m', '--monitor',
                        help='monitor to use in normalizations')
    parser.add_argument('-n', '--norm', type=float,
                        help='normalization to monitor')
    parser.add_argument('-r', '--radius', type=float,
                        help='radius of punched holes in Å-1')
    parser.add_argument('-q', '--Qmin', type=float,
                        help='minimum Q in Å-1 used in transmission estimates')
    parser.add_argument('-Q', '--Qmax', type=float,
                        help='maximum Q in Å-1 used in PDF tapers')
    parser.add_argument('-r', '--radius', type=float,
                        help='radius of punched holes in Å-1')
    parser.add_argument('-o', '--output', action='store_true',
                        help='print current parameters')

    args = parser.parse_args()

    reduce = NXReduce(directory=args.directory)
    if args.output:
        print('Current NXReduce parameters\n---------------------------')
        print(f"Threshold = {reduce.threshold:g}")
        print(f"First Frame = {reduce.first}")
        print(f"Last Frame = {reduce.last}")
        print(f"Maximum Polar Angle = {reduce.polar_max:g}")
        print(f"Monitor = {reduce.monitor}")
        print(f"Normalization = {reduce.norm:g}")
        print(f"Qmin = {reduce.qmin:g}")
        print(f"Qmax = {reduce.qmax:g}")
        print(f"Radius = {reduce.radius:g}")
    else:
        reduce.write_parameters(threshold=args.threshold,
                                first=args.first, last=args.last,
                                polar_max=args.polar_max,
                                monitor=args.monitor, norm=args.norm,
                                qmin=args.Qmin, qmax=args.Qmax,
                                radius=args.radius)


if __name__ == "__main__":
    main()
