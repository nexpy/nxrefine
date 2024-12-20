# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import os

import dask.array as da
import numpy as np
from dask.distributed import Client
from nexusformat.nexus import nxopen, nxsetconfig


def triclinic(data):
    """Laue group: -1"""
    outarr = da.nan_to_num(data)
    outarr += da.flip(outarr)
    return outarr


def monoclinic(data):
    """Laue group: 2/m"""
    outarr = da.nan_to_num(data)
    outarr += da.rot90(outarr, 2, (0, 2))
    outarr += da.flip(outarr, 1)
    return outarr


def orthorhombic(data):
    """Laue group: mmm"""
    outarr = da.nan_to_num(data)
    outarr += da.flip(outarr, 0)
    outarr += da.flip(outarr, 1)
    outarr += da.flip(outarr, 2)
    return outarr


def tetragonal1(data):
    """Laue group: 4/m"""
    outarr = da.nan_to_num(data)
    outarr += da.rot90(outarr, 1, (1, 2))
    outarr += da.rot90(outarr, 2, (1, 2))
    outarr += da.flip(outarr, 0)
    return outarr


def tetragonal2(data):
    """Laue group: 4/mmm"""
    outarr = da.nan_to_num(data)
    outarr += da.rot90(outarr, 1, (1, 2))
    outarr += da.rot90(outarr, 2, (1, 2))
    outarr += da.rot90(outarr, 2, (0, 1))
    outarr += da.flip(outarr, 0)
    return outarr


def hexagonal(data):
    """Laue group: 6/m, 6/mmm (modeled as 2/m along the c-axis)"""
    outarr = da.nan_to_num(data)
    outarr += da.rot90(outarr, 2, (1, 2))
    outarr += da.flip(outarr, 0)
    return outarr


def cubic(data):
    """Laue group: m-3 or m-3m"""
    outarr = da.nan_to_num(data)
    outarr += da.transpose(outarr, axes=(1, 2, 0))
    outarr += da.transpose(outarr, axes=(2, 0, 1))
    outarr += da.transpose(outarr, axes=(0, 2, 1))
    outarr += da.flip(outarr, 0)
    outarr += da.flip(outarr, 1)
    outarr += da.flip(outarr, 2)
    return outarr

def symmetrize_entries(symm_function, data_type, data_file, data_path):
    """
    Symmetrize data from multiple entries in a file.

    Parameters
    ----------
    symm_function : function
        The function to use for symmetrizing the data.
    data_type : str
        The type of data to symmetrize; either 'signal' or 'weights'.
    data_file : str
        The name of the file containing the data to symmetrize.
    data_path : str
        The path to the data in the file.

    Returns
    -------
    data_type : str
        The type of data that was symmetrized.
    filename : str
        The name of the file containing the symmetrized data.
    """
    nxsetconfig(lock=3600, lockexpiry=28800)
    with nxopen(data_file, 'r') as data_root:
        data_path = os.path.basename(data_path)
        for i, entry in enumerate([e for e in data_root if e[-1].isdigit()]):
            data_size = int(
                data_root[entry][data_path].nxsignal.nbytes / 1e6) + 1000
            nxsetconfig(memory=data_size)
            if i == 0:
                if data_type == 'signal':
                    signal_path = data_root[entry][data_path].nxsignal.nxpath
                    data = da.from_array(data_root.nxfile[signal_path])
                elif data_root[entry][data_path].nxweights:
                    weights_path = data_root[entry][data_path].nxweights.nxpath
                    data = da.from_array(data_root.nxfile[weights_path])
                else:
                    signal_path = data_root[entry][data_path].nxsignal.nxpath
                    signal = da.from_array(data_root.nxfile[signal_path])
                    data = da.zeros(signal.shape, dtype=signal.dtype)
                    data[da.where(signal > 0)] = 1
            else:
                if data_type == 'signal':
                    signal_path = data_root[entry][data_path].nxsignal.nxpath
                    data += da.from_array(data_root.nxfile[signal_path])
                elif data_root[entry][data_path].nxweights:
                    weights_path = data_root[entry][data_path].nxweights.nxpath
                    data += da.from_array(data_root.nxfile[weights_path])
    result = symm_function(data)
    return data_type, result


def symmetrize_data(symm_function, data_type, data_file, data_path):
    """
    Symmetrize data from a single entry in a file.

    Parameters
    ----------
    symm_function : function
        The function to use for symmetrizing the data.
    data_type : str
        The type of data to symmetrize; either 'signal' or 'weights'.
    data_file : str
        The name of the file containing the data to symmetrize.
    data_path : str
        The path to the data in the file.

    Returns
    -------
    data_type : str
        The type of data that was symmetrized.
    filename : str
        The name of the file containing the symmetrized data.
    """
    nxsetconfig(lock=3600, lockexpiry=28800)
    with nxopen(data_file, 'r') as data_root:
        data_size = int(data_root[data_path].nbytes / 1e6) + 1000
        nxsetconfig(memory=data_size)
        if data_type == 'signal':
            data = da.from_array(data_root.nxfile[data_path])
        else:
            signal = da.from_array(data_root.nxfile[data_path])
            data = da.zeros(signal.shape, signal.dtype)
            data[da.where(signal > 0)] = 1
    result = symm_function(data)
    return data_type, result


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
        """
        Parameters
        ----------
        data : NXdata
            The data to be symmetrized.
        laue_group : str, optional
            The Laue group of the crystal structure of the sample. If not
            specified, a triclinic crystal structure is assumed.

        Attributes
        ----------
        symm_function : function
            The function to use for symmetrizing the data.
        data_file : str
            The name of the file containing the data to symmetrize.
        data_path : str
            The path to the data in the file.
        """
        if laue_group and laue_group in laue_functions:
            self.symm_function = laue_functions[laue_group]
        else:
            self.symm_function = triclinic
        self.data_file = data.nxfilename
        self.data_path = data.nxpath

    def symmetrize(self, entries=False):
        """
        Symmetrize the data.

        Parameters
        ----------
        entries : bool, optional
            Flag to indicate whether to symmetrize multiple entries in a file,
            by default False.

        Returns
        -------
        array-like
            The symmetrized data.
        """
        if entries:
            symmetrize = symmetrize_entries
        else:
            symmetrize = symmetrize_data
        client = Client(n_workers=6)
        signal = symmetrize(self.symm_function, 'signal',
                            self.data_file, self.data_path)
        weights = symmetrize(self.symm_function, 'weights',
                            self.data_file, self.data_path)
        with np.errstate(divide='ignore', invalid='ignore'):
            result = da.where(weights[1] > 0, signal[1] / weights[1], 0.0)
        result = client.persist(result)
        return result
