# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
from nexusformat.nexus import nxload, nxsetlock


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


def symmetrize_entries(symm_function, data_type, data_file, data_path):
    nxsetlock(60)
    data_root = nxload(data_file, 'r')
    data_path = os.path.basename(data_path)
    for i, entry in enumerate([e for e in data_root if e != 'entry']):
        if i == 0:
            if data_type == 'signal':
                data = data_root[entry][data_path].nxsignal.nxvalue
            elif data_root[entry][data_path].nxweights:
                data = data_root[entry][data_path].nxweights.nxvalue
            else:
                signal = data_root[entry][data_path].nxsignal.nxvalue
                data = np.zeros(signal.shape, dtype=signal.dtype)
                data[np.where(signal > 0)] = 1
        else:
            if data_type == 'signal':
                data += data_root[entry][data_path].nxsignal.nxvalue
            elif data_root[entry][data_path].nxweights:
                data += data_root[entry][data_path].nxweights.nxvalue
    result = symm_function(data)
    root = nxload(tempfile.mkstemp(suffix='.nxs')[1], mode='w')
    root['data'] = result
    return data_type, root.nxfilename


def symmetrize_data(symm_function, data_type, data_file, data_path):
    nxsetlock(60)
    data_root = nxload(data_file, 'r')
    if data_type == 'signal':
        data = data_root[data_path].nxvalue
    else:
        signal = data_root[data_path].nxvalue
        data = np.zeros(signal.shape, signal.dtype)
        data[np.where(signal > 0)] = 1
    result = symm_function(data)
    root = nxload(tempfile.mkstemp(suffix='.nxs')[1], mode='w')
    root['data'] = result
    return data_type, root.nxfilename


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


class NXSymmetry:

    def __init__(self, data, laue_group=None):
        if laue_group and laue_group in laue_functions:
            self.symm_function = laue_functions[laue_group]
        else:
            self.symm_function = triclinic
        self.data_file = data.nxfilename
        self.data_path = data.nxpath

    def symmetrize(self, entries=False):
        if entries:
            symmetrize = symmetrize_entries
        else:
            symmetrize = symmetrize_data
        with ProcessPoolExecutor(max_workers=2) as executor:
            futures = []
            for data_type in ['signal', 'weights']:
                futures.append(executor.submit(
                    symmetrize, self.symm_function, data_type,
                    self.data_file, self.data_path))
        for future in as_completed(futures):
            data_type, result_file = future.result()
            result_root = nxload(result_file, 'r')
            if data_type == 'signal':
                signal = result_root['data'].nxvalue
            else:
                weights = result_root['data'].nxvalue
            os.remove(result_file)
        with np.errstate(divide='ignore', invalid='ignore'):
            result = np.where(weights > 0, signal / weights, 0.0)
        return result
