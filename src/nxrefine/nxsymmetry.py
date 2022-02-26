# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
from nexusformat.nexus import nxsetlock


def triclinic(data):
    """Laue group: -1"""
    outarr = np.nan_to_num(data)
    outarr += np.flip(outarr)
    return outarr


def monoclinic(data):
    """Laue group: 2/m"""
    outarr = np.nan_to_num(data)
    outarr += np.rot90(outarr, 2, (0, 2))
    outarr += np.flip(outarr, 0)
    return outarr


def orthorhombic(data):
    """Laue group: mmm"""
    outarr = np.nan_to_num(data)
    outarr += np.flip(outarr, 0)
    outarr += np.flip(outarr, 1)
    outarr += np.flip(outarr, 2)
    return outarr


def tetragonal1(data):
    """Laue group: 4/m"""
    outarr = np.nan_to_num(data)
    outarr += np.rot90(outarr, 1, (1, 2))
    outarr += np.rot90(outarr, 2, (1, 2))
    outarr += np.flip(outarr, 0)
    return outarr


def tetragonal2(data):
    """Laue group: 4/mmm"""
    outarr = np.nan_to_num(data)
    outarr += np.rot90(outarr, 1, (1, 2))
    outarr += np.rot90(outarr, 2, (1, 2))
    outarr += np.rot90(outarr, 2, (0, 1))
    outarr += np.flip(outarr, 0)
    return outarr


def hexagonal(data):
    """Laue group: 6/m, 6/mmm (modeled as 2/m along the c-axis)"""
    outarr = np.nan_to_num(data)
    outarr += np.rot90(outarr, 2, (1, 2))
    outarr += np.flip(outarr, 0)
    return outarr


def cubic(data):
    """Laue group: m-3 or m-3m"""
    outarr = np.nan_to_num(data)
    outarr += (np.transpose(outarr, axes=(1, 2, 0)) +
               np.transpose(outarr, axes=(2, 0, 1)))
    outarr += np.transpose(outarr, axes=(0, 2, 1))
    outarr += np.flip(outarr, 0)
    outarr += np.flip(outarr, 1)
    outarr += np.flip(outarr, 2)
    return outarr


def symmetrize_data(symm_function, signal, data_file, data_path,
                    symm_file, symm_path):
    nxsetlock(60)
    from .nxreduce import NXReduce
    for i, entry in enumerate([e for e in data_file if e != 'entry']):
        r = NXReduce(data_file[entry])
        if i == 0:
            if signal:
                data = r.entry[data_path].nxsignal.nxvalue
            else:
                data = r.entry[data_path].nxweights.nxvalue
        else:
            if signal:
                data += r.entry[data_path].nxsignal.nxvalue
            else:
                data += r.entry[data_path].nxweights.nxvalue
    result = symm_function(np.nan_to_num(data))
    if signal:
        symm_file[symm_path].nxsignal = result
    else:
        symm_file[symm_path].nxweights = result


class NXSymmetry(object):

    def __init__(self, data_file, data_path, symm_file, laue_group):
        laue_functions = {'-1': triclinic,
                          '2/m': monoclinic,
                          'mmm': orthorhombic,
                          '4/m': tetragonal1,
                          '4/mmm': tetragonal2,
                          '-3': triclinic,
                          '-3m': triclinic,
                          '6/m': hexagonal,
                          '6/mmm': hexagonal,
                          'm-3': cubic,
                          'm-3m': cubic}
        if laue_group in laue_functions:
            self.symm_function = laue_functions[laue_group]
        else:
            self.symm_function = triclinic
        self.data_file = data_file
        self.data_path = data_path
        self.symm_file = symm_file
        self.symm_path = 'entry/data'

    def symmetrize(self):
        with ProcessPoolExecutor() as executor:
            for signal in [True, False]:
                executor.submit(symmetrize_data, self.symm_function, signal,
                                self.data_file, self.data_path,
                                self.symm_file, self.symm_path)
        with np.errstate(divide='ignore', invalid='ignore'):
            self.symm_file[self.symm_path].nxsignal = np.where(
                self.symm_file[self.symm_path].nxweights.nxvalue > 0,
                self.symm_file[self.symm_path].nxsignal.nxvalue /
                self.symm_file[self.symm_path].nxweights.nxvalue,
                0.0)
