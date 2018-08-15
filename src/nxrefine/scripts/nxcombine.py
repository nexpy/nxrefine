import argparse
import os
import socket
import subprocess
import sys

import numpy as np
from nexusformat.nexus import *
from nxrefine.nxreduce import NXMultiReduce
from nxrefine import __version__


def main():

    parser = argparse.ArgumentParser(
        description="Combine CCTW transforms")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be searched')
    parser.add_argument('-m', '--mask', action='store_true', 
                        help='combine transforms with 3D mask')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing transform')
    
    args = parser.parse_args()

    reduce = NXMultiReduce(args.directory, entries=args.entries, mask=args.mask,
                           overwrite=args.overwrite)
    reduce.nxcombine()


if __name__=="__main__":
    main()
