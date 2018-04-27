import argparse
import os
import subprocess

import numpy as np
from nexusformat.nexus import *
from nxrefine.nxrefine import NXRefine
from nexpy.gui.utils import timestamp


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
    
    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    scan = os.path.basename(directory)
    wrapper_file = os.path.join(sample, label, '%s_%s.nxs' % (sample, scan))

    if args.parent:
        parent = nxload(args.parent)
    else:
        parent = None
        Qh = [np.float32(v) for v in args.qh]
        Qk = [np.float32(v) for v in args.qk]
        Ql = [np.float32(v) for v in args.ql]

    entries = args.entries

    root = nxload(wrapper_file, 'rw')

    e = entries[0]
    if parent is not None:
        if e in parent and 'transform' in parent[e]:
            transform = parent[e+'/transform']
            Qh, Qk, Ql = (transform['Qh'].nxvalue,
                          transform['Qk'].nxvalue,
                          transform['Ql'].nxvalue)
            Qh = Qh[0], Qh[1]-Qh[0], Qh[-1]
            Qk = Qk[0], Qk[1]-Qk[0], Qk[-1]
            Ql = Ql[0], Ql[1]-Ql[0], Ql[-1]
        else:
            raise NeXusError('Transform parameters not defined in '+e)

    for e in entries:
        output = os.path.join(scan, e+'_transform.nxs')
        if os.path.exists(os.path.join(sample, label, output)):
            output_file = os.path.join(sample, label, output)
            os.rename(output_file, output_file+'-%s' % timestamp())
        settings = os.path.join(scan, e+'_transform.pars')
        prepare_transform(root[e], Qh, Qk, Ql, output, settings)
        print(root[e].transform.command)
        subprocess.call(root[e].transform.command.nxvalue, shell=True)


if __name__=="__main__":
    main()
