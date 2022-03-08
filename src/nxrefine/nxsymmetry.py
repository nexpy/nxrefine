# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor, wait

import numpy as np
from nexusformat.nexus import nxload, nxsetlock, NXdata


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


def symmetrize_entries(symm_function, signal, data_file, data_path,
                       result_file):
    nxsetlock(60)
    root = nxload(data_file, 'r')
    for i, entry in enumerate([e for e in data_file if e != 'entry']):
        if i == 0:
            if signal:
                data = root[entry][data_path].nxsignal.nxvalue
            elif root[entry][data_path].nxweights:
                data = root[entry][data_path].nxweights.nxvalue
            else:
                signal = root[entry][data_path].nxsignal.nxvalue
                data = np.zeros(root[entry][data_path].shape,
                                dtype=root[entry][data_path].nxsignal.dtype)
                data[np.where(signal > 0)] = 1
        else:
            if signal:
                data += root[entry][data_path].nxsignal.nxvalue
            elif root[entry][data_path].nxweights:
                data += root[entry][data_path].nxweights.nxvalue
    result = symm_function(np.nan_to_num(data))
    if signal:
        result_file[['data']].nxsignal = result
    else:
        result_file['data'].nxweights = result


def symmetrize_data(symm_function, signal, data_file, data_path, result_file):
    nxsetlock(60)
    root = nxload(data_file, 'r')
    if signal:
        data = root['entry'][data_path].nxsignal.nxvalue
    else:
        signal = root['entry'][data_path].nxsignal.nxvalue
        data = np.zeros(root['entry'][data_path].shape,
                        dtype=root['entry'][data_path].nxsignal.dtype)
        data[np.where(signal > 0)] = 1
    result = symm_function(np.nan_to_num(data))
    if signal:
        result_file[['data']].nxsignal = result
    else:
        result_file['data'].nxweights = result


class NXSymmetry(object):

    def __init__(self, data_file, data_path, symm_file=None, symm_path=None,
                 laue_group=None):
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
        if laue_group and laue_group in laue_functions:
            self.symm_function = laue_functions[laue_group]
        else:
            self.symm_function = triclinic
        self.data_file = data_file
        self.data_path = data_path
        if self.symm_file:
            self.symm_file = symm_file
        else:
            self.symm_file = None
        if self.symm_path:
            self.symm_path = symm_path
        else:
            self.symm_path = None

    def __enter__(self):
        self.result_file = nxload(tempfile.mkstemp(suffix='.nxs')[1], mode='w',
                                  libver='latest')
        self.result_file['data'] = NXdata()
        return self

    def __exit__(self):
        os.remove(self.result_file.nxfilename)

    def symmetrize(self, entries=False):
        if entries:
            symmetrize = symmetrize_entries
        else:
            symmetrize = symmetrize_data
        with ProcessPoolExecutor() as executor:
            futures = []
            for signal in [True, False]:
                futures.append(executor.submit(
                    symmetrize, self.symm_function, signal,
                    self.data_file, self.data_path, self.result_file))
        wait(futures)
        with np.errstate(divide='ignore', invalid='ignore'):
            self.result_file['data'].nxsignal = np.where(
                self.result_file['data'].nxweights.nxvalue > 0,
                self.result_file['data'].nxsignal.nxvalue /
                self.result_file['data'].nxweights.nxvalue,
                0.0)
        return self.result_file['data'].nxsignal.nxvalue
