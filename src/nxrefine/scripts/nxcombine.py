import argparse
import os
import socket
import subprocess
import sys

import numpy as np
from nexusformat.nexus import *
from nxrefine.nxrefine import NXRefine
from nxrefine import __version__


def prepare_transform(entry, Qh, Qk, Ql, output, settings):
    refine = NXRefine(entry)
    refine.refine_lattice_parameters()
    refine.output_file = output
    refine.settings_file = settings
    refine.h_start, refine.h_step, refine.h_stop = Qh
    refine.k_start, refine.k_step, refine.k_stop = Qk
    refine.l_start, refine.l_step, refine.l_stop = Ql
    refine.define_grid()
    refine.prepare_transform(output)
    refine.write_settings(settings)
    refine.write_parameters()


def main():

    parser = argparse.ArgumentParser(
        description="Combine CCTW transforms")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
                        nargs='+', help='names of data entries to be merged')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing transform')
    
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
        entry = root['entry']

    print('Combining entries in', wrapper_file)
    
    if os.path.exists(os.path.join(directory, 'transform.nxs')) and not overwrite:
        print('Transforms already combined')
        sys.exit()
    else:
        input_files = [os.path.join(directory, '%s_transform.nxs' % e)
                       for e in entries]
        missing = [f for f in input_files if not os.path.exists(f)]
        if missing:
            for f in missing:
                print("'%s' does not exist" % f)
            sys.exit(1)

    input = ' '.join([os.path.join(directory, '%s_transform.nxs\#/entry/data'
                      % e) for e in entries])
    output = os.path.join(directory, 'transform.nxs\#/entry/data/v')
    command = 'cctw merge %s -o %s' % (input, output)
    subprocess.call(command, shell=True)

    Qh = root['%s/transform/Qh' % entries[0]]
    Qk = root['%s/transform/Qk' % entries[0]]
    Ql = root['%s/transform/Ql' % entries[0]]
    data = NXlink('/entry/data/v', file=os.path.join(scan, 'transform.nxs'),
                  name='data')
    if 'transform' in entry:
        del entry['transform']
    entry['transform'] = NXdata(data, [Ql,Qk,Qh])

    note = NXnote('nxcombine '+' '.join(sys.argv[1:]), 
                  ('Current machine: %s\n'
                   'Current working directory: %s')
                    % (socket.gethostname(), os.getcwd()))
    if 'nxcombine' in entry:
        del entry['nxcombine']
    entry['nxcombine'] = NXprocess(program='nxcombine', 
                                   sequence_index=len(entry.NXprocess)+1, 
                                   version=__version__, 
                                   note=note)


if __name__=="__main__":
    main()
