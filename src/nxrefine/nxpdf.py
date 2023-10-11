import logging
import os
import timeit
from pathlib import Path

import numpy as np
import scipy.fft
from nexusformat.nexus import (NeXusError, NXdata, NXentry, NXfield, NXlink,
                               nxgetconfig, nxopen, nxsetconfig)

from .nxrefine import NXRefine
from .nxsymmetry import NXSymmetry
from .nxutils import init_julia, load_julia


class NXPDF:

    def __init__(self, root, laue=None, radius=0.2, qmax=12.0,
                 symmetrize=False, overwrite=False):
        self.root = root
        self.entry = root['entry']
        self.directory = Path(
            self.entry['transform'].nxsignal.nxfilename).parent
        self.task_directory = self.directory.parent.parent / 'tasks'
        self.sample = self.directory.parent.name
        self.scan = self.directory.name
        self.symmetrize_data = symmetrize
        self.overwrite = overwrite

        self.refine = NXRefine(self.root)
        if laue:
            if laue in self.refine.laue_groups:
                self.refine.laue_group = laue
            else:
                raise NeXusError('Invalid Laue group specified')
        self.radius = radius
        self.qmax = qmax

        self._logger = None
        self.julia = None

    def __repr__(self):
        return f"NXPDF('{self.root.nxname}')"

    @property
    def logger(self):
        """Log file handler."""
        if self._logger is None:
            self._logger = logging.getLogger(
                f"{self.sample}_{self.scan}['entry']")
            self._logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                "%(asctime)s %(name)-12s: %(message)s",
                datefmt='%Y-%m-%d %H:%M:%S')
            fileHandler = logging.FileHandler(
                self.task_directory.joinpath('nxlogger.log'))
            fileHandler.setFormatter(formatter)
            self._logger.addHandler(fileHandler)
        return self._logger

    def add_title(self, data):
        title = []
        if 'chemical_formula' in self.entry['sample']:
            title.append(str(self.entry['sample/chemical_formula']))
        elif 'name' in self.entry['sample']:
            title.append(str(self.entry['sample/name']))
        else:
            title.append(self.root.nxname)
        if 'temperature' in self.entry['sample']:
            if 'units' in self.entry['sample/temperature'].attrs:
                units = self.entry['sample/temperature'].attrs['units']
                title.append(f"{self.entry['sample/temperature']:g}{units}")
            else:
                title.append('T=' + str(self.entry['sample/temperature']))
        name = data.nxname.replace('symm', 'symmetrized').replace('_', ' ')
        title.append(name.title().replace('Pdf', 'PDF'))
        data['title'] = ' '.join(title)

    def nxpdf(self):
        task = 'nxpdf'
        if self.julia is None:
            try:
                self.julia = init_julia()
            except Exception as error:
                self.logger.info(f"Cannot initialize Julia: {error}")
                self.julia = None
                return
        load_julia(['LaplaceInterpolation.jl'])
        # self.record_start(task)
        self.init_pdf()
        try:
            self.symmetrize_transform()
            self.total_pdf()
            self.punch_and_fill()
            self.delta_pdf()
            # self.write_parameters(radius=self.radius, qmax=self.qmax)
            # self.record(task, laue=self.refine.laue_group,
            #             radius=self.radius, qmax=self.qmax)
            # self.record_end(task)
        except Exception as error:
            self.logger.info(str(error))
            # self.record_fail(task)
            raise

    def init_pdf(self, mask=False):
        self.title = 'PDF'
        self.symm_data = 'symm_transform'
        self.total_pdf_data = 'total_pdf'
        self.pdf_data = 'pdf'
        self.symm_file = self.directory / 'symm_transform.nxs'
        self.total_pdf_file = self.directory / 'total_pdf.nxs'
        self.pdf_file = self.directory / 'pdf.nxs'
        self.Qh, self.Qk, self.Ql = (self.entry['transform/Qh'].centers(),
                                     self.entry['transform/Qk'].centers(),
                                     self.entry['transform/Ql'].centers())
        total_size = self.entry['transform'].nxsignal.nbytes / 1e6
        if total_size > nxgetconfig('memory'):
            nxsetconfig(memory=total_size+1000)
        self.taper = self.fft_taper()

    def symmetrize_transform(self):
        self.logger.info(f"{self.title}: Transform being symmetrized")
        tic = timeit.default_timer()
        symm_root = nxopen(self.symm_file, 'w')
        symm_root['entry'] = NXentry()
        symm_root['entry/data'] = NXdata()
        if self.symmetrize_data:
            symmetry = NXSymmetry(self.entry['transform'],
                                  laue_group=self.refine.laue_group)
            symm_root['entry/data/data'] = symmetry.symmetrize(entries=True)
        else:
            symm_root['entry/data/data'] = np.nan_to_num(
                self.entry['transform'].nxsignal.nxvalue,
                posinf=0.0, neginf=0.0)
        symm_root['entry/data'].nxsignal = symm_root['entry/data/data']
        symm_root['entry/data'].nxweights = 1.0 / self.taper
        symm_root['entry/data'].nxaxes = self.entry['transform'].nxaxes
        if self.symm_data in self.entry:
            del self.entry[self.symm_data]
        symm_data = NXlink('/entry/data/data', file=self.symm_file,
                           name='data')
        self.entry[self.symm_data] = NXdata(
            symm_data, self.entry['transform'].nxaxes)
        self.entry[self.symm_data].nxweights = NXlink(
            '/entry/data/data_weights', file=self.symm_file)
        self.add_title(self.entry[self.symm_data])
        self.logger.info(f"'{self.symm_data}' added to entry")
        toc = timeit.default_timer()
        self.logger.info(f"{self.title}: Symmetrization completed "
                         f"({toc-tic:g} seconds)")

    def fft_taper(self, qmax=None):
        """Calculate spherical Tukey taper function.

        The taper function values are read from the parent if they are
        available.

        Parameters
        ----------
        qmax : float, optional
            Maximum Q value in Å-1, by default None.

        Returns
        -------
        array-like
            An array containing the 3D taper function values.
        """
        self.logger.info(f"{self.title}: Calculating taper function")
        tic = timeit.default_timer()
        if qmax is None:
            qmax = self.qmax
        Z, Y, X = np.meshgrid(self.Ql * self.refine.cstar,
                              self.Qk * self.refine.bstar,
                              self.Qh * self.refine.astar,
                              indexing='ij')
        taper = np.ones(X.shape, dtype=np.float32)
        R = 2 * np.sqrt(X**2 + Y**2 + Z**2) / qmax
        idx = (R > 1.0) & (R < 2.0)
        taper[idx] = 0.5 * (1 - np.cos(R[idx] * np.pi))
        taper[R >= 2.0] = taper.min()
        toc = timeit.default_timer()
        self.logger.info(f"{self.title}: Taper function calculated "
                         f"({toc-tic:g} seconds)")
        return taper

    def total_pdf(self):
        if self.total_pdf_file.exists():
            if self.overwrite:
                self.total_pdf_file.unlink()
            else:
                self.logger.info(
                    f"{self.title}: Total PDF file already exists")
                return
        self.logger.info(f"{self.title}: Calculating total PDF")
        tic = timeit.default_timer()
        symm_data = self.entry[self.symm_data].nxsignal.nxvalue
        symm_data *= self.taper
        fft = np.real(scipy.fft.fftshift(
            scipy.fft.fftn(scipy.fft.fftshift(symm_data[:-1, :-1, :-1]),
                           workers=os.cpu_count())))
        fft *= (1.0 / np.prod(fft.shape))

        root = nxopen(self.total_pdf_file, 'a')
        root['entry'] = NXentry()
        root['entry/pdf'] = NXdata(NXfield(fft, name='pdf'))

        if self.total_pdf_data in self.entry:
            del self.entry[self.total_pdf_data]
        pdf = NXlink('/entry/pdf/pdf', file=self.total_pdf_file, name='pdf')

        dl, dk, dh = [(ax[1]-ax[0]).nxvalue
                      for ax in self.entry[self.symm_data].nxaxes]
        x = NXfield(scipy.fft.fftshift(scipy.fft.fftfreq(
            fft.shape[2], dh)), name='x', scaling_factor=self.refine.a)
        y = NXfield(scipy.fft.fftshift(scipy.fft.fftfreq(
            fft.shape[1], dk)), name='y', scaling_factor=self.refine.b)
        z = NXfield(scipy.fft.fftshift(scipy.fft.fftfreq(
            fft.shape[0], dl)), name='z', scaling_factor=self.refine.c)
        self.entry[self.total_pdf_data] = NXdata(pdf, (z, y, x))
        self.entry[self.total_pdf_data].attrs['angles'] = (
            self.refine.lattice_parameters[3:])
        self.add_title(self.entry[self.total_pdf_data])
        self.logger.info(f"'{self.total_pdf_data}' added to entry")
        toc = timeit.default_timer()
        self.logger.info(f"{self.title}: Total PDF calculated "
                         f"({toc - tic:g} seconds)")

    def hole_mask(self, data_group):
        data_group = self.entry[self.symm_data]
        dl, dk, dh = [(ax[1]-ax[0]).nxvalue for ax in data_group.nxaxes]
        dhp = np.rint(self.radius / (dh * self.refine.astar))
        dkp = np.rint(self.radius / (dk * self.refine.bstar))
        dlp = np.rint(self.radius / (dl * self.refine.cstar))
        ml, mk, mh = np.ogrid[0:4*int(dlp)+1, 0:4*int(dkp)+1, 0:4*int(dhp)+1]
        mask = ((((ml-2*dlp)/dlp)**2+((mk-2*dkp)/dkp)
                ** 2+((mh-2*dhp)/dhp)**2) <= 1)
        mask_array = np.where(mask == 0, 0, 1)
        mask_indices = [list(idx) for idx in list(np.argwhere(mask == 1))]
        return mask_array, mask_indices

    @property
    def indices(self):
        self.refine.wavelength = 0.1
        self.refine.polar_max = 10.0
        if self.refine.laue_group in ['-3', '-3m', '6/m', '6/mmm']:
            _indices = []
            for idx in self.refine.indices:
                _indices += self.refine.indices_hkl(*idx)
            return _indices
        else:
            ids = []
            for h, k, l in self.refine.indices:
                ids += self.refine.indices_hkl(h, k, l)
            return ids

    def symmetrize(self, data):
        if self.refine.laue_group not in ['-3', '-3m', '6/m', '6/mmm']:
            import tempfile
            root = nxopen(tempfile.mkstemp(suffix='.nxs')[1], mode='w')
            root['data'] = data
            symmetry = NXSymmetry(root['data'],
                                  laue_group=self.refine.laue_group)
            result = symmetry.symmetrize()
            Path(root.nxfilename).unlink()
            return result
        else:
            return data

    def punch_and_fill(self):
        self.logger.info(f"{self.title}: Performing punch-and-fill")

        from julia import Main
        LaplaceInterpolation = Main.LaplaceInterpolation

        tic = timeit.default_timer()

        symm_root = nxopen(self.symm_file, 'rw')
        symm_data = symm_root['entry/data/data']

        mask, mask_indices = self.hole_mask()
        idx = [Main.CartesianIndex(int(i[0]+1), int(i[1]+1), int(i[2]+1))
               for i in mask_indices]
        ml = int((mask.shape[0]-1)/2)
        mk = int((mask.shape[1]-1)/2)
        mh = int((mask.shape[2]-1)/2)
        fill_data = np.zeros(shape=symm_data.shape, dtype=symm_data.dtype)
        for h, k, l in self.indices:
            try:
                ih = np.argwhere(np.isclose(self.Qh, h, atol=0.001))[0][0]
                ik = np.argwhere(np.isclose(self.Qk, k, atol=0.001))[0][0]
                il = np.argwhere(np.isclose(self.Ql, l, atol=0.001))[0][0]
                lslice = slice(il-ml, il+ml+1)
                kslice = slice(ik-mk, ik+mk+1)
                hslice = slice(ih-mh, ih+mh+1)
                v = symm_data[(lslice, kslice, hslice)].nxvalue
                if v.max() > 0.0:
                    w = LaplaceInterpolation.matern_3d_grid(v, idx)
                    fill_data[(lslice, kslice, hslice)] += np.where(mask, w, 0)
            except Exception as error:
                raise

        self.logger.info(f"{self.title}: Symmetrizing punch-and-fill")

        # fill_data = self.symmetrize(fill_data)
        self.changed_idx = np.where(fill_data > 0)
        buffer = symm_data.nxvalue
        buffer[self.changed_idx] = fill_data[self.changed_idx]
        if 'fill' in symm_root['entry/data']:
            del symm_root['entry/data/fill']
        symm_root['entry/data/fill'] = buffer
        if 'filled_data' in self.entry[self.symm_data]:
            del self.entry[self.symm_data]['filled_data']
        self.entry[self.symm_data]['filled_data'] = NXlink(
            '/entry/data/fill', file=self.symm_file)

        buffer[self.changed_idx] *= 0
        if 'punch' in symm_root['entry/data']:
            del symm_root['entry/data/punch']
        symm_root['entry/data/punch'] = buffer
        if 'punched_data' in self.entry[self.symm_data]:
            del self.entry[self.symm_data]['punched_data']
        self.entry[self.symm_data]['punched_data'] = NXlink(
            '/entry/data/punch', file=self.symm_file)

        toc = timeit.default_timer()
        self.logger.info(f"{self.title}: Punch-and-fill completed "
                         f"({toc - tic:g} seconds)")

    def delta_pdf(self):
        self.logger.info(f"{self.title}: Calculating Delta-PDF")
        if self.pdf_file.exists():
            if self.overwrite:
                self.pdf_file.unlink()
            else:
                self.logger.info(
                    f"{self.title}: Delta-PDF file already exists")
                return
        tic = timeit.default_timer()
        symm_data = self.entry[self.symm_data]['filled_data'].nxvalue
        symm_data *= self.taper
        fft = np.real(scipy.fft.fftshift(
            scipy.fft.fftn(scipy.fft.fftshift(symm_data[:-1, :-1, :-1]),
                           workers=os.cpu_count())))
        fft *= (1.0 / np.prod(fft.shape))

        root = nxopen(self.pdf_file, 'a')
        root['entry'] = NXentry()
        root['entry/pdf'] = NXdata(NXfield(fft, name='pdf'))

        if self.pdf_data in self.entry:
            del self.entry[self.pdf_data]
        pdf = NXlink('/entry/pdf/pdf', file=self.pdf_file, name='pdf')

        dl, dk, dh = [(ax[1]-ax[0]).nxvalue
                      for ax in self.entry[self.symm_data].nxaxes]
        x = NXfield(scipy.fft.fftshift(scipy.fft.fftfreq(
            fft.shape[2], dh)), name='x', scaling_factor=self.refine.a)
        y = NXfield(scipy.fft.fftshift(scipy.fft.fftfreq(
            fft.shape[1], dk)), name='y', scaling_factor=self.refine.b)
        z = NXfield(scipy.fft.fftshift(scipy.fft.fftfreq(
            fft.shape[0], dl)), name='z', scaling_factor=self.refine.c)
        self.entry[self.pdf_data] = NXdata(pdf, (z, y, x))
        self.entry[self.pdf_data].attrs['angles'] = (
            self.refine.lattice_parameters[3:])
        self.add_title(self.entry[self.pdf_data])
        self.logger.info(f"'{self.pdf_data}' added to entry")
        toc = timeit.default_timer()
        self.logger.info(f"{self.title}: Delta-PDF calculated "
                         f"({toc - tic:g} seconds)")
