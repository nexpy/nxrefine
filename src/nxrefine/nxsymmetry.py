import numpy as np
from nexusformat.nexus import *

class NXSymmetry(object):

    def __init__(self, data, laue_group='-1'):
        laue_functions = {'-1': self.triclinic,
                          '2/m': self.monoclinic,
                          'mmm': self.orthorhombic,
                          '4/m': self.tetragonal1,
                          '4/mmm': self.tetragonal2,
                          '-3': self.triclinic,
                          '-3m': self.triclinic,
                          '6/m': self.monoclinic,
                          '6/mmm': self.monoclinic,
                          'm-3': self.cubic,
                          'm-3m': self.cubic}
        if laue_group in laue_functions:
            self._function = laue_functions[laue_group]
        else:
            self._function = self.triclinic
        self._data = data
        self._signal = data.nxsignal.nxvalue
        self._wts = data.nxweights.nxvalue

    def triclinic(self, data):
        """Laue group: -1"""
        outarr = data
        outarr += np.flip(outarr)
        return outarr

    def monoclinic(self, data):
        """Laue group: 2/m"""
        outarr = data
        outarr += np.rot90(outarr, 2, (0,2))
        outarr += np.flip(outarr, 0)
        return outarr

    def orthorhombic(self, data):
        """Laue group: mmm"""
        outarr = data
        outarr += np.flip(outarr, 0)
        outarr += np.flip(outarr, 1)
        outarr += np.flip(outarr, 2)
        return outarr

    def tetragonal1(self, data):
        """Laue group: 4/m"""
        outarr = data
        outarr += np.rot90(outarr, 1, (1,2))
        outarr += np.rot90(outarr, 2, (1,2))
        outarr += np.flip(outarr, 0)
        return outarr

    def tetragonal2(self, data):
        """Laue group: 4/mmm"""
        outarr = data
        outarr += np.rot90(outarr, 1, (1,2))
        outarr += np.rot90(outarr, 2, (1,2))
        outarr += np.rot90(outarr, 2, (0,1))
        outarr += np.flip(outarr, 0)
        return outarr

    def cubic(self, data):
        """Laue group: m-3 or m-3m"""
        outarr = data
        outarr += np.transpose(outarr,axes=(1,2,0))+np.transpose(outarr,axes=(2,0,1))
        outarr += np.transpose(outarr,axes=(0,2,1))
        outarr += np.flip(outarr, 0)
        outarr += np.flip(outarr, 1)
        outarr += np.flip(outarr, 2)
        return outarr

    def symmetrize(self):
        result = NXfield(self._function(self._signal)/self._function(self._wts), 
                         name='data')
        return NXdata(result, self._data.nxaxes)

