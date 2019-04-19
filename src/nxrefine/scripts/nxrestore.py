import argparse
import os
import subprocess
import sys

import numpy as np
from nexusformat.nexus import *
from nxrefine.nxreduce import NXReduce, NXMultiReduce
from nxrefine.nxrefine import NXRefine


def main():

    parser = argparse.ArgumentParser(
        description="Restore orientation from CCTW parameter file")
    parser.add_argument('-d', '--directory', required=True, 
                        help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be processed')
    
    args = parser.parse_args()

    files = os.listdir(args.directory)
    
    for entry in args.entries:
        reduce = NXReduce(entry, args.directory)
        r = NXRefine(reduce.entry)
        settings_file = entry+'_transform.pars'
        if settings_file in files:
            r.read_settings(os.path.join(args.directory, settings_file))
            r.write_parameters()
        transform_file = entry+'_transform.nxs'
        if transform_file in files:
            r.prepare_transform(os.path.join(os.path.basename(args.directory[:-1]), 
                                             transform_file))
        masked_transform_file = entry+'_masked_transform.nxs'
        if masked_transform_file in files:
            r.prepare_transform(os.path.join(os.path.basename(args.directory[:-1]), 
                                             args.directory, masked_transform_file))
    if 'transform.nxs' in files:
        reduce = NXMultiReduce(args.directory)
        reduce.prepare_combine()
    if 'masked_transform.nxs' in files:
        reduce = NXMultiReduce(args.directory, mask=True)
        reduce.prepare_combine()


if __name__=="__main__":
    main()
