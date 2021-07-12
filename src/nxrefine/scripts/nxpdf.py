import argparse
import os
import subprocess
import sys

import numpy as np
from nexusformat.nexus import *
from nxrefine.nxrefine import NXRefine
from nxrefine.nxreduce import NXMultiReduce, NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Create delta-PDF")
    parser.add_argument('-d', '--directory', required=True, 
                        help='scan directory')
    parser.add_argument('-e', '--entries', nargs='+', 
                        help='names of entries to be processed')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing transforms')
    
    args = parser.parse_args()
    
    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(args.directory).entries

    for entry in entries:
        reduce = NXMultiReduce(entry, args.directory, pdf=True,
                               overwrite=args.overwrite)
        reduce.nxpdf()


if __name__=="__main__":
    main()
