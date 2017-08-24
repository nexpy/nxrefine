import argparse
import os
import socket
import subprocess
import sys
import timeit

import numpy as np
from scipy.optimize import leastsq
from nexusformat.nexus import *
from nxpeaks.nxrefine import NXRefine
from nxpeaks import __version__


def refine_orientation(ref):
    idx = ref.idx
    intensities = ref.intensity[idx]
    sigma = np.average(intensities) / intensities
    p0 = set_parameters(ref, idx)
    def diffs(p):
        get_parameters(ref, p)
        UBimat = np.linalg.inv(ref.UBmat)
        Q = np.array([UBimat * ref.Gvecs[i] for i in idx])
        dQ = Q - np.rint(Q)
        return np.array([np.linalg.norm(ref.Bmat*np.matrix(dQ[i])) 
                         for i in idx]) / sigma
    popt, C, info, msg, success = leastsq(diffs, p0, epsfcn=1e-6, full_output=1)
    get_parameters(ref, popt)
    return success, info, msg


def set_parameters(ref, idx):
    ref.get_Gvecs(idx)
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
        ref.a = ref.b = ref.c = p[0]
        i = 1
    elif ref.symmetry == 'tetragonal' or ref.symmetry == 'hexagonal':
        ref.a = ref.b = p[0]
        ref.c = p[1]
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
    ref.Umat = np.matrix(p[i:]).reshape(3,3)


def write_parameters(ref):
    ref.write_parameters()


def main():

    parser = argparse.ArgumentParser(
        description="Refine orientation matrix")
    parser.add_argument('-d', '--directory', default='./',
                        help='directory containing the NeXus file')
    parser.add_argument('-f', '--filename', required=True,
                         help='NeXus file name')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be oriented')
    parser.add_argument('-o', '--omega', default='0.0', help='omega start')
    
    args = parser.parse_args()

    name, ext = os.path.splitext(args.filename)
    if ext == '':
        args.filename = args.filename + '.nxs'
    root = nxload(os.path.join(args.directory, args.filename), 'rw')

    entries = args.entries

    tic=timeit.default_timer()
    for e in entries:
        entry = root[e]
        ref = NXRefine(entry)
        old_score = ref.score()
        print 'Current lattice parameters: ', ref.a, ref.b, ref.c
        print '%s peaks; Old score: %.4f' % (len(ref.idx), old_score)
        success, info, msg = refine_orientation(ref)
        new_score = ref.score()
        print 'Success:', success, ' ', msg
        print 'No. of function calls:', info['nfev']
        print 'New lattice parameters: ', ref.a, ref.b, ref.c
        print '%s peaks; New score: %.4f' % (len(ref.idx), new_score)
        if new_score <= old_score and success > 0 and success < 5:
            write_parameters(ref)
            note = NXnote('nxorient '+' '.join(sys.argv[1:]), 
                          ('Current machine: %s\n'
                           'Current working directory: %s')
                            % (socket.gethostname(), os.getcwd()))
            entry['nxorient'] = NXprocess(program='nxorient', 
                                          sequence_index=len(entry.NXprocess)+1, 
                                          version=__version__, 
                                          note=note)

    toc=timeit.default_timer()
    print toc-tic, 'seconds for', args.filename


if __name__=="__main__":
    main()
