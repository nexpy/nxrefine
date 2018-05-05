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
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='name of entries to be refined')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing refinement')
    
    args = parser.parse_args()
    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    scan = os.path.basename(directory)
    wrapper_file = os.path.join(sample, label, '%s_%s.nxs' % (sample, scan))
    entries = args.entries
    overwrite = args.overwrite

    if not os.path.exists(wrapper_file):
        print("'%s' does not exist" % wrapper_file)
        sys.exit(1)
    else:
        root = nxload(wrapper_file, 'rw')
    
    print('Refining', wrapper_file)
    
    for i, entry in enumerate(entries):
        if 'nxrefine' in root[entry] and not overwrite:
            print('HKL values already refined for', entry)
        else:
            refine = NXRefine(root[entry])
            if i == 0:
                refine.refine_hkl_parameters(chi=True,omega=True)
                fit_report=refine.fit_report
                refine.refine_hkl_parameters(chi=True, omega=True, gonpitch=True)                
            else:
                refine.refine_hkl_parameters(
                    lattice=False, chi=True, omega=True)
                fit_report=refine.fit_report
                refine.refine_hkl_parameters(
                    lattice=False, chi=True, omega=True, gonpitch=True)
            fit_report = fit_report + '\n' + refine.fit_report
            refine.refine_orientation_matrix()
            fit_report = fit_report + '\n' + refine.fit_report
            if refine.result.success:
                refine.write_parameters()
                note = NXnote('nxrefine '+' '.join(sys.argv[1:]), 
                              ('Current machine: %s\n%s')
                               % (socket.gethostname(), fit_report))
                if 'nxrefine' in root[entry]:
                    del root[entry]['nxrefine']
                root[entry]['nxrefine'] = NXprocess(program='nxrefine', 
                    sequence_index=len(root[entry].NXprocess)+1, 
                    version=__version__, 
                    note=note)
                print('Refined HKL values for', entry)
            else:
                print('HKL refinement not successful in', entry)


if __name__=="__main__":
    main()
