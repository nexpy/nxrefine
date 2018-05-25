#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
from __future__ import print_function
import argparse, os, sys, timeit
import numpy as np
from nexusformat.nexus import *
from nxrefine.nxreduce import NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Find maximum counts of the signal in the specified path")
    parser.add_argument('-d', '--directory', required=True, 
                        help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be processed')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing maximum')

    args = parser.parse_args()

    for entry in args.entries:
        reduce = NXReduce(entry, args.directory, overwrite=args.overwrite)
        reduce.nxmax()


if __name__=="__main__":
    main()
