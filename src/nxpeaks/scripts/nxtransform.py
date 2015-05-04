import argparse
import os
import subprocess

import numpy as np
from nexusformat.nexus import *
from nxpeaks.nxrefine import NXRefine


def prepare_transform(entry, Qh, Qk, Ql, output, settings):
    refine = NXRefine(entry)
    refine.output_file = output
    refine.settings_file = settings
    refine.h_start, refine.h_step, refine.h_stop = Qh
    refine.k_start, refine.k_step, refine.k_stop = Qk
    refine.l_start, refine.l_step, refine.l_stop = Ql
    refine.define_grid()
    refine.prepare_transform(output)
    refine.write_settings(settings) 


def main():

    parser = argparse.ArgumentParser(
        description="Prepare files for a CCTW transform")
    parser.add_argument('-s', '--sample', help='sample name')
    parser.add_argument('-l', '--label', help='sample label')
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files to be linked to this file')
    parser.add_argument('-qh', nargs=3, help='Qh - min, step, max')
    parser.add_argument('-qk', nargs=3, help='Qk - min, step, max')
    parser.add_argument('-ql', nargs=3, help='Ql - min, step, max')
    
    args = parser.parse_args()

    sample = args.sample
    label = args.label
    directory = args.directory.rstrip('/')
    if sample is None and label is None:
        sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
        label = os.path.basename(os.path.dirname(directory))
        scan = os.path.basename(directory)

    Qh = [np.float32(v) for v in args.qh]
    Qk = [np.float32(v) for v in args.qk]
    Ql = [np.float32(v) for v in args.ql]

    filenames = args.filenames

    label_path = '%s/%s' % (sample, label)
    wrapper_file = '%s/%s_%s.nxs' % (label_path, sample, scan)

    root = nxload(wrapper_file, 'rw')

    for f in filenames:
        output = os.path.join(directory, f+'_transform.nxs')
        settings = os.path.join(directory, f+'_transform.pars')
        prepare_transform(root[f], Qh, Qk, Ql, output, settings)
        print root[f].transform.command
        subprocess.call(root[f].transform.command.nxdata, shell=True)


if __name__=="__main__":
    main()
