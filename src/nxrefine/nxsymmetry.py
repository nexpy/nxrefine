class NXSymmetry(object):

    laue_functions = {'-1': self.triclinic,
                      '2/m': self.monoclinic,
                      'mmm': self.orthorhombic,
                      '4/m': self.tetragonal1,
                      '4/mmm': self.tetragonal2,
                      '-3': self.triclinic,
                      '-3m': self.triclinic,
                      '6/m': self.monoclinic,
                      '6/mmm': self.orthorhombic,
                      'm-3': self.cubic,
                      'm-3m': self.cubic}

    def __init__(self, data, laue_group='-1'):
        if laue_group in laue_functions:
            self._function = self.laue_functions[laue_group]
        else:
            self._function = self.triclinic
        self._data = data.nxsignal.nxvalue            

    def triclinic(self):
        """Laue group: -1"""
        self._data += np.flip(self._data)
        return outarr

    def monoclinic(self):
        """Laue group: 2/m"""
        outarr = self._data
        outarr += np.rot90(outarr, 2, (0,2))
        outarr += np.flip(outarr, 0)
        return outarr

    def orthorhombic(self):
        """Laue group: mmm"""
        outarr = self._data
        outarr += np.flip(outarr, 0)
        outarr += np.flip(outarr, 1)
        outarr += np.flip(outarr, 2)
        return outarr

    def tetragonal1(self):
        """Laue group: 4/m"""
        outarr = self._data
        outarr += np.rot90(outarr, 1, (1,2))
        outarr += np.rot90(outarr, 2, (1,2))
        outarr += np.flip(outarr, 0)
        return outarr

    def tetragonal2(self):
        """Laue group: 4/mmm"""
        outarr = self._data
        outarr += np.rot90(outarr, 1, (1,2))
        outarr += np.rot90(outarr, 2, (1,2))
        outarr += np.rot90(outarr, 2, (0,1))
        outarr += np.flip(outarr, 0)
        return outarr

    def cubic(arr):
        """Laue group: m-3 or m-3m"""
        outarr = self._data
        outarr += np.transpose(arr,axes=(1,2,0))+np.transpose(arr,axes=(2,0,1))
        outarr += np.transpose(outarr,axes=(0,2,1))
        outarr += np.flip(outarr, 0)
        outarr += np.flip(outarr, 1)
        outarr += np.flip(outarr, 2)
        return outarr

    def symmetrize(self):
        result = NXfield(func(arr) / func(wts), name='data')
        return NXData(result, self._data.nxaxes)

