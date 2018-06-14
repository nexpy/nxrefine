import argparse
import os
import socket
import subprocess
import sys

import numpy as np
from nexusformat.nexus import *
from nxrefine.nxrefine import NXRefine
from nxrefine import __version__


def main():

    parser = argparse.ArgumentParser(
        description="Combine CCTW transforms")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
                        nargs='+', help='names of data entries to be merged')
    parser.add_argument('-m', '--mask', action='store_true', 
                        help='transform with 3D mask')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing transform')
    
    args = parser.parse_args()

    reduce = NXReduce(args.directory, combine=True, entries=args.entries,
                      overwrite=args.overwrite)
    reduce.nxcombine()


if __name__=="__main__":
    main()
