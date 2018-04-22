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
        description="Refine lattice parameter")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-e', '--entry', default='f1', 
                        help='name of entry to be refined')
    
    args = parser.parse_args()
    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    scan = os.path.basename(directory)
    wrapper_file = os.path.join(sample, label, '%s_%s.nxs' % (sample, scan))

    root = nxload(wrapper_file, 'rw')
    entry = root[args.entry]
    
    refine = NXRefine(entry)

    refine.refine_hkl_parameters()
    if refine.result.success:
        refine.write_parameters()
        note = NXnote('nxrefine '+' '.join(sys.argv[1:]), 
                      ('Current machine: %s\n%s')
                       % (socket.gethostname(), refine.fit_report))
        entry['nxrefine'] = NXprocess(program='nxrefine', 
                                sequence_index=len(entry.NXprocess)+1, 
                                version=__version__, 
                                note=note)


if __name__=="__main__":
    main()
