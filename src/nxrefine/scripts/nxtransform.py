import argparse
import os
import subprocess

import numpy as np
from nexusformat.nexus import *
from nxrefine.nxrefine import NXRefine
from nexpy.gui.utils import timestamp


def read_transform(entry):
    try:
        transform = entry['transform']
        Qh, Qk, Ql = (transform['Qh'].nxvalue,
                      transform['Qk'].nxvalue,
                      transform['Ql'].nxvalue)
        Qh = Qh[0], Qh[1]-Qh[0], Qh[-1]
        Qk = Qk[0], Qk[1]-Qk[0], Qk[-1]
        Ql = Ql[0], Ql[1]-Ql[0], Ql[-1]
        return Qh, Qk, Ql
    except Exception:
        print('Transform parameters not defined in', entry)
        sys.exit(1)


def prepare_transform(entry, Qh, Qk, Ql, output, settings):
    refine = NXRefine(entry)
    refine.read_parameters()
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
        description="Perform CCTW transform")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be transformed')
    parser.add_argument('-p', '--parent', help='file name of file to copy from')
    parser.add_argument('-qh', nargs=3, help='Qh - min, step, max')
    parser.add_argument('-qk', nargs=3, help='Qk - min, step, max')
    parser.add_argument('-ql', nargs=3, help='Ql - min, step, max')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing transforms')
    
    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    scan = os.path.basename(directory)
    wrapper_file = os.path.join(sample, label, '%s_%s.nxs' % (sample, scan))
    entries = args.entries
    parent = args.parent
    overwrite = args.overwrite

    if not os.path.exists(wrapper_file):
        print("'%s' does not exist" % wrapper_file)
        sys.exit(1)
    else:
        root = nxload(wrapper_file, 'rw')

    if args.qh or args.qk or args.ql:
        try:
            Qh = [np.float32(v) for v in args.qh]
            Qk = [np.float32(v) for v in args.qk]
            Ql = [np.float32(v) for v in args.ql]
        except Exception:
            print('Invalid HKL values')
            sys.exit(1)
    elif parent:
        if not os.path.exists(parent):
            print("'%s' does not exist" % parent)
            sys.exit(1)
        else:    
            parent = nxload(args.parent)
            Qh, Qk, Ql = read_transform(parent[entries[0]])
    else:
        parent = None
        Qh, Qk, Ql = read_transform(root[entries[0]])

    print('Transforming', wrapper_file)

    for entry in entries:
        print('Processing', entry)
        output_file = os.path.join(directory, entry+'_transform.nxs')
        if os.path.exists(output_file):
            if overwrite:
                os.rename(output_file, output_file+'-%s' % timestamp())
            else:
                print('Transform already exists')
                continue
        output = os.path.join(scan, entry+'_transform.nxs')
        settings = os.path.join(directory, entry+'_transform.pars')
        if os.path.exists(settings):
            os.rename(settings, settings+'-%s' % timestamp())
        prepare_transform(root[entry], Qh, Qk, Ql, output, settings)
        if not os.path.exists(root[entry]['data/data'].nxfilename):
            print("'%s' does not exist" % root[entry]['data/data'].nxfilename)
            return
        print(root[entry].transform.command)
        subprocess.call(root[entry].transform.command.nxvalue, shell=True)


if __name__=="__main__":
    main()
