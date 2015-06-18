import argparse
import os
import subprocess

import numpy as np
from scipy.optimize import leastsq
from nexusformat.nexus import *
from nxpeaks.nxrefine import NXRefine


def refine_orientation(ref):
    idx = ref.idx
    intensities = ref.intensity[idx]
    sigma = np.average(intensities) / intensities
    p0 = set_parameters(idx)
    def diffs(p):
        get_parameters(p)
        UBimat = np.linalg.inv(ref.UBmat)
        Q = [UBimat * Gvec[i] for i in idx]
        dQ = Q - np.rint(Q)
        return np.array([np.linalg.norm(ref.Bmat*np.matrix(dQ[i])) 
                         for i in idx]) / sigma
    popt, C, info, msg, success = leastsq(diffs, p0, full_output=1)
    get_parameters(popt)


def set_parameters(ref, idx):
    global Gvec, Umat
    x, y, z = ref.xp[idx], ref.yp[idx], ref.zp[idx]
    Gvec = [ref.Gvec(xx,yy,zz) for xx,yy,zz in zip(x,y,z)]
    if ref.symmetry == 'cubic':
        pars = [ref.a]
    elif ref.symmetry == 'tetragonal' or ref.symmetry == 'hexagonal':
        pars = [ref.a, ref.c]
    elif ref.symmetry == 'orthorhombic':
        pars = [ref.a, ref.b, ref.c] 
    elif ref.symmetry == 'monoclinic':
        pars = [ref.a, ref.b, ref.c. ref.beta]
    else:
        pars = [ref.a, ref.b, ref.c, ref.alpha, ref.beta, ref.gamma]  
    p0 = np.zeros(shape=(len(pars)+9), dtype=np.float32)
    p0[:len(pars)] = pars
    p0[len(pars):] = np.ravel(ref.Umat)
    return p0


def get_parameters(ref, p):
    if ref.symmetry == 'cubic':
        ref.a = p[0]
        i = 1
    elif ref.symmetry == 'tetragonal' or ref.symmetry == 'hexagonal':
        ref.a, ref.c = p[0:2]
        i = 2
    elif ref.symmetry == 'orthorhombic':
        ref.a, ref.b, ref.c = p[0:3]
        i = 3
    elif ref.symmetry == 'monoclinic':
        ref.a, ref.b, ref.c. ref.beta = p[0:4]
        i = 4
    else:
        ref.a, ref.b, ref.c, ref.alpha, ref.beta, ref.gamma = p[0:6]
        i = 6
    ref.set_symmetry()
    ref.Umat = np.matrix(p[i:]).reshape(3,3)


def write_parameters(ref):
    ref.write_parameters()


def main():

    parser = argparse.ArgumentParser(
        description="Refine orientation matrix")
    parser.add_argument('-s', '--sample', help='sample name')
    parser.add_argument('-l', '--label', help='sample label')
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be oriented')
    parser.add_argument('-o', '--omega', default='0.0', help='omega start')
    
    args = parser.parse_args()

    sample = args.sample
    label = args.label
    directory = args.directory.rstrip('/')
    if sample is None and label is None:
        sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
        label = os.path.basename(os.path.dirname(directory))
        scan = os.path.basename(directory)

    label_path = '%s/%s' % (sample, label)
    wrapper_file = '%s/%s_%s.nxs' % (label_path, sample, scan)

    root = nxload(wrapper_file, 'rw')

    entries = args.entries

    omega = 
    for e in entries:
        ref = NXrefine(root[e])
        ref.read_parameters()
        ref.refine_orientation()
        ref.write_parameters()


if __name__=="__main__":
    main()
