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
        description="Prepare files for a CCTW transform")
    parser.add_argument('-s', '--sample', help='sample name')
    parser.add_argument('-l', '--label', help='sample label')
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files to be merged')
    
    args = parser.parse_args()

    sample = args.sample
    label = args.label
    directory = args.directory.rstrip('/')
    if sample is None and label is None:
        sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
        label = os.path.basename(os.path.dirname(directory))
        scan = os.path.basename(directory)
    else:
        scan = directory

    filenames = args.filenames

    label_path = '%s/%s' % (sample, label)
    wrapper_file = '%s/%s_%s.nxs' % (label_path, sample, scan)

    root = nxload(wrapper_file, 'rw')
    entry = root['entry']

    output = os.path.join(scan, 'transform.nxs')
    input = ' '.join([os.path.join(directory, '%s_transform.nxs\#/entry/data'
                      % f) for f in filenames])
    output = os.path.join(directory, 'transform.nxs\#/entry/data/v')
    command = 'cctw merge %s -o %s' % (input, output)
    subprocess.call(command, shell=True)

    Qh = root['%s/transform/Qh' % filenames[0]]
    Qk = root['%s/transform/Qk' % filenames[0]]
    Ql = root['%s/transform/Ql' % filenames[0]]
    data = NXlink('/entry/data/v', file=os.path.join(scan, 'transform.nxs'),
                  name='data')
    if 'transform' not in entry:
        entry['transform'] = NXdata(data, [Ql,Qk,Qh])
    else:
        entry['transform_1'] = NXdata(data, [Ql,Qk,Qh])

    note = NXnote('nxcombine '+' '.join(sys.argv[1:]), 
                  ('Current machine: %s\n'
                   'Current working directory: %s')
                    % (socket.gethostname(), os.getcwd()))
    entry['nxcombine'] = NXprocess(program='nxcombine', 
                                   sequence_index=len(entry.NXprocess)+1, 
                                   version=__version__, 
                                   note=note)



if __name__=="__main__":
    main()
