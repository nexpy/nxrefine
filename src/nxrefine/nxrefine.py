from __future__ import absolute_import, unicode_literals

import numpy as np
import os
import random
import six
from scipy import optimize

from nexusformat.nexus import *
from .unitcell import unitcell, outif
from . import closest

from numpy.linalg import inv, norm


degrees = 180.0 / np.pi
radians = np.pi / 180.0


def find_nearest(array, value):
    """Return array value closest to the requested value."""
    idx = (np.abs(array-value)).argmin()
    return array[idx]
 

def rotmat(axis, angle):
    """Return a rotation matrix for rotation about the specified axis."""
    mat = np.eye(3) 
    if angle is None or np.isclose(angle, 0.0):
        return mat
    cang = np.cos(angle*radians)
    sang = np.sin(angle*radians)
    if axis == 1:
        mat = np.array(((1,0,0), (0,cang,-sang), (0, sang, cang)))
    elif axis == 2:
        mat = np.array(((cang,0,sang), (0,1,0), (-sang,0,cang)))
    else:
        mat = np.array(((cang,-sang,0), (sang,cang,0), (0,0,1)))
    return np.matrix(mat)


def vec(x, y=0.0, z=0.0):
    return np.matrix((x, y, z)).T


def norm_vec(vec):
    return vec / norm(vec)


class NXRefine(object):

    symmetries = ['cubic', 'tetragonal', 'orthorhombic', 'hexagonal', 
                  'monoclinic', 'triclinic']
    centrings = ['P', 'A', 'B', 'C', 'I', 'F', 'R']

    def __init__(self, node=None):
        if node is not None:
            self.entry = node.nxentry
            self.data = self.entry['data']
        else:
            self.entry = None
            self.data = None
        self.a = 4.0
        self.b = 4.0
        self.c = 4.0
        self.alpha = 90.0
        self.beta = 90.0
        self.gamma = 90.0
        self.wavelength = 1.0
        self.distance = 100.0
        self._yaw = 0.0
        self._pitch = 0.0
        self._roll = 0.0
        self.twotheta = 0.0
        self._gonpitch = 0.0
        self._omega = 0.0
        self._chi = 0.0
        self.phi = 0.0
        self.phi_step = 0.1
        self.xc = 256.0
        self.yc = 256.0
        self.xd = 0.0
        self.yd = 0.0
        self.frame_time = 0.1
        self.symmetry = 'cubic'
        self.centring = 'P'
        self.peak = None
        self.xp = None
        self.yp = None
        self.zp = None
        self.x = None
        self.y = None
        self.z = None
        self.polar_angle = None
        self.azimuthal_angle = None
        self.rotation_angle = None
        self.intensity = None
        self.pixel_size = 0.1
        self.shape = [1679, 1475]
        self.polar_max = None
        self.Umat = None
        self.primary = None
        self.secondary = None
        self._unitcell = None
        self.polar_tolerance = 0.1
        self.peak_tolerance = 5.0
        self.hkl_tolerance = 0.05
        self.output_chunks = None
        self.grid_origin = None
        self.grid_basis = None
        self.grid_shape = None
        self.grid_step = None
        self.standard = True

        self._name = ""
        self._idx = None
        self._Dmat_cache = inv(rotmat(1, self.roll) * rotmat(2, self.pitch) *
                               rotmat(3, self.yaw))
        self._Gmat_cache = (rotmat(2,self.gonpitch) * rotmat(3, self.omega) * 
                            rotmat(1, self.chi))
        self._julia = None
        
        self.parameters = None
        
        self.grains = None
        
        if self.entry is not None:
            self.read_parameters()

    def __repr__(self):
        return "NXRefine('" + self._name + "')"

    def read_parameter(self, path, default=None, attr=None):
        try:
            if attr:
                return self.entry[path].attrs[attr]
            else:
                # return self.entry[path].nxvalue
                return self.entry[path].nxdata
        except NeXusError:
            return default

    def read_parameters(self, entry=None):
        if entry:
            self.entry = entry
        with self.entry.nxfile:
            self._name = self.entry.nxroot.nxname + "/" + self.entry.nxname
            self.a = self.read_parameter('sample/unitcell_a', self.a)
            self.b = self.read_parameter('sample/unitcell_b', self.b)
            self.c = self.read_parameter('sample/unitcell_c', self.c)
            self.alpha = self.read_parameter('sample/unitcell_alpha', self.alpha)
            self.beta = self.read_parameter('sample/unitcell_beta', self.beta)
            self.gamma = self.read_parameter('sample/unitcell_gamma', self.gamma)
            self.wavelength = self.read_parameter('instrument/monochromator/wavelength', 
                                                  self.wavelength)
            self.distance = self.read_parameter('instrument/detector/distance', 
                                                self.distance)
            self.yaw = self.read_parameter('instrument/detector/yaw', self.yaw)
            self.pitch = self.read_parameter('instrument/detector/pitch', 
                                             self.pitch)
            self.roll = self.read_parameter('instrument/detector/roll', self.roll)
            self.xc = self.read_parameter('instrument/detector/beam_center_x', 
                                          self.xc)
            self.yc = self.read_parameter('instrument/detector/beam_center_y', 
                                          self.yc)
            self.xd = self.read_parameter('instrument/detector/translation_x', 
                                          self.xd)
            self.yd = self.read_parameter('instrument/detector/translation_y', 
                                          self.yd)
            self.frame_time = self.read_parameter('instrument/detector/frame_time', 
                                                  self.frame_time)
            self.shape = self.read_parameter('instrument/detector/shape', self.shape)
            phi = self.read_parameter('instrument/goniometer/phi', self.phi)
            if isinstance(phi, np.ndarray) and len(phi) > 1:
                self.phi = phi[0]
                self.phi_step = phi[1] - phi[0]
            else:
                self.phi = phi
                try:
                    self.phi_step = self.read_parameter('instrument/goniometer/phi', 
                                                        self.phi, attr='step')
                except Exception:
                    pass
            self.chi = self.read_parameter('instrument/goniometer/chi', self.chi)
            self.omega = self.read_parameter('instrument/goniometer/omega', 
                                             self.omega)
            self.twotheta = self.read_parameter('instrument/goniometer/two_theta', 
                                                self.twotheta)
            self.gonpitch = self.read_parameter('instrument/goniometer/goniometer_pitch', 
                                                self.gonpitch)
            self.symmetry = self.read_parameter('sample/unit_cell_group', 
                                                self.symmetry)
            self.centring = self.read_parameter('sample/lattice_centring', 
                                                self.centring)
            self.xp = self.read_parameter('peaks/x')
            self.yp = self.read_parameter('peaks/y')
            self.zp = self.read_parameter('peaks/z')
            self.polar_angle = self.read_parameter('peaks/polar_angle')
            self.azimuthal_angle = self.read_parameter('peaks/azimuthal_angle')
            self.intensity = self.read_parameter('peaks/intensity')
            self.pixel_size = self.read_parameter('instrument/detector/pixel_size', 
                                                  self.pixel_size)
            self.pixel_mask = self.read_parameter('instrument/detector/pixel_mask')
            self.pixel_mask_applied = self.read_parameter(
                                          'instrument/detector/pixel_mask_applied')
            self.rotation_angle = self.read_parameter('peaks/rotation_angle')
            self.primary = self.read_parameter('peaks/primary_reflection')
            self.secondary = self.read_parameter('peaks/secondary_reflection')
            self.Umat = self.read_parameter('instrument/detector/orientation_matrix')
            if isinstance(self.polar_angle, np.ndarray):
                try:
                    self.set_polar_max(np.sort(self.polar_angle)[200] + 0.1)
                except IndexError:
                    self.set_polar_max(self.polar_angle.max())
            else:
                self.set_polar_max(10.0)
            self.Qh = self.read_parameter('transform/Qh')
            self.Qk = self.read_parameter('transform/Qk')
            self.Ql = self.read_parameter('transform/Ql')

    def write_parameter(self, path, value, attr=None):
        if value is not None:
            if attr and path in self.entry:
                self.entry[path].attrs[attr] = value
            elif path in self.entry:
                self.entry[path].replace(value)
            elif attr is None:
                self.entry[path] = value

    def write_parameters(self, entry=None):
        if entry:
            self.entry = entry
        with self.entry.nxfile:
            if 'sample' not in self.entry:
                self.entry['sample'] = NXsample()
            self.write_parameter('sample/unit_cell_group', self.symmetry)
            self.write_parameter('sample/lattice_centring', self.centring)
            self.write_parameter('sample/unitcell_a', self.a)
            self.write_parameter('sample/unitcell_b', self.b)
            self.write_parameter('sample/unitcell_c', self.c)
            self.write_parameter('sample/unitcell_alpha', self.alpha)
            self.write_parameter('sample/unitcell_beta', self.beta)
            self.write_parameter('sample/unitcell_gamma', self.gamma)
            if 'instrument' not in self.entry:
                self.entry['instrument'] = NXinstrument()
            if 'detector' not in self.entry['instrument']:
                self.entry['instrument/detector'] = NXdetector()
            if 'monochromator' not in self.entry['instrument']:
                self.entry['instrument/monochromator'] = NXmonochromator()
            if 'goniometer' not in self.entry['instrument']:
                self.entry['instrument/goniometer'] = NXgoniometer()
            self.write_parameter('instrument/monochromator/wavelength', 
                                 self.wavelength)
            self.write_parameter('instrument/detector/distance', self.distance)
            self.write_parameter('instrument/detector/yaw', self.yaw)
            self.write_parameter('instrument/detector/pitch', self.pitch)
            self.write_parameter('instrument/detector/roll', self.roll)
            self.write_parameter('instrument/detector/beam_center_x', self.xc)
            self.write_parameter('instrument/detector/beam_center_y', self.yc)
            self.write_parameter('instrument/detector/pixel_size', self.pixel_size)
            self.write_parameter('instrument/detector/pixel_mask', self.pixel_mask)
            self.write_parameter('instrument/detector/pixel_mask_applied', 
                                 self.pixel_mask_applied)
            self.write_parameter('instrument/detector/translation_x', self.xd)
            self.write_parameter('instrument/detector/translation_y', self.yd)
            self.write_parameter('instrument/detector/frame_time', self.frame_time)
            if self.Umat is not None:
                self.write_parameter('instrument/detector/orientation_matrix', 
                                     np.array(self.Umat))
            self.write_parameter('instrument/goniometer/phi', self.phi)
            self.write_parameter('instrument/goniometer/phi', self.phi_step, 
                                 attr='step')
            self.write_parameter('instrument/goniometer/chi', self.chi)
            self.write_parameter('instrument/goniometer/omega', self.omega)
            self.write_parameter('instrument/goniometer/two_theta', self.twotheta)
            self.write_parameter('instrument/goniometer/goniometer_pitch', 
                                 self.gonpitch)
            self.write_parameter('peaks/primary_reflection', self.primary)
            self.write_parameter('peaks/secondary_reflection', self.secondary)        
            if isinstance(self.z, np.ndarray):
                self.rotation_angle = self.phi + (self.phi_step * self.z)

    def copy_parameters(self, other, sample=False, instrument=False):
        with other.entry.nxfile:
            if sample:
                if 'sample' not in other.entry:
                    other.entry['sample'] = NXsample()
                other.write_parameter('sample/unit_cell_group', self.symmetry)
                other.write_parameter('sample/lattice_centring', self.centring)
                other.write_parameter('sample/unitcell_a', self.a)
                other.write_parameter('sample/unitcell_b', self.b)
                other.write_parameter('sample/unitcell_c', self.c)
                other.write_parameter('sample/unitcell_alpha', self.alpha)
                other.write_parameter('sample/unitcell_beta', self.beta)
                other.write_parameter('sample/unitcell_gamma', self.gamma)
            if instrument:
                if 'instrument' not in other.entry:
                    other.entry['instrument'] = NXinstrument()
                if 'detector' not in other.entry['instrument']:
                    other.entry['instrument/detector'] = NXdetector()
                if 'monochromator' not in other.entry['instrument']:
                    other.entry['instrument/monochromator'] = NXmonochromator()
                if 'goniometer' not in other.entry['instrument']:
                    other.entry['instrument/goniometer'] = NXgoniometer()
                other.write_parameter('instrument/monochromator/wavelength', 
                                      self.wavelength)
                other.write_parameter('instrument/goniometer/phi', self.phi)
                other.write_parameter('instrument/goniometer/phi', self.phi_step,
                                      attr='step')
                other.write_parameter('instrument/goniometer/chi', self.chi)
                other.write_parameter('instrument/goniometer/omega', self.omega)
                other.write_parameter('instrument/goniometer/two_theta', self.twotheta)
                other.write_parameter('instrument/goniometer/goniometer_pitch', 
                                      self.gonpitch)
                other.write_parameter('instrument/detector/distance', self.distance)
                other.write_parameter('instrument/detector/yaw', self.yaw)
                other.write_parameter('instrument/detector/pitch', self.pitch)
                other.write_parameter('instrument/detector/roll', self.roll)
                other.write_parameter('instrument/detector/beam_center_x', self.xc)
                other.write_parameter('instrument/detector/beam_center_y', self.yc)
                other.write_parameter('instrument/detector/pixel_size', 
                                      self.pixel_size)
                other.write_parameter('instrument/detector/pixel_mask', 
                                      self.pixel_mask)
                other.write_parameter('instrument/detector/pixel_mask_applied', 
                                      self.pixel_mask_applied)
                other.write_parameter('instrument/detector/translation_x', self.xd)
                other.write_parameter('instrument/detector/translation_y', self.yd)
                other.write_parameter('instrument/detector/frame_time', 
                                      self.frame_time)
                if self.Umat is not None:
                    other.write_parameter('instrument/detector/orientation_matrix', 
                                          np.array(self.Umat))        

    def link_sample(self, other):
        with other.entry.nxfile:
            if 'sample' in self.entry:
                if 'sample' in other.entry:
                    del other.entry['sample']
                other.entry.makelink(self.entry['sample'])

    def read_settings(self, settings_file):
        import configparser, itertools
        cfg = configparser.ConfigParser()
        filename = settings_file
        with open(filename) as fp:
            cfg.read_file(itertools.chain(['[global]'], fp), source=filename)
        d = {}
        for c in cfg.items('global'):
            try:
                d[c[0]]=eval(c[1].strip(';'))
            except Exception:
                pass
        self.distance = d['parameters.distance']
        self.a, self.b, self.c, alpha, beta, gamma = d['parameters.unitcell']
        self.alpha, self.beta, self.gamma = alpha*degrees, beta*degrees, gamma*degrees
        ubmat = np.matrix(d['parameters.ubmat'])
        self.Umat = ubmat * self.Bimat
        self.xc = d['parameters.det0x']
        self.yc = d['parameters.det0y']
        self.pitch = d['parameters.orienterrordetpitch'] * degrees
        self.roll = d['parameters.orienterrordetroll'] * degrees
        self.yaw = d['parameters.orienterrordetyaw'] * degrees
        self.gonpitch = d['parameters.orienterrorgonpitch'] * degrees
        self.twotheta = d['parameters.twothetanom'] * degrees
        self.omega = d['parameters.omeganom'] * degrees
        self.chi = d['parameters.chinom'] * degrees
        self.phi = d['parameters.phinom'] * degrees
        self.phi_step = d['parameters.phistep'] * degrees
        self.h_start, self.k_start, self.l_start = d['parameters.gridorigin']
        self.h_stop, self.k_stop, self.l_stop = [-v for v in d['parameters.gridorigin']]
        hs, ks, ls = d['parameters.griddim']
        self.h_step, self.k_step, self.l_step = [1.0/hs, 1.0/ks, 1.0/ls]
        self.h_shape, self.k_shape, self.l_shape = d['outputdata.dimensions']

    def write_settings(self, settings_file):
        lines = []
        lines.append('parameters.pixelSize = %s;' % self.pixel_size)
        lines.append('parameters.wavelength = %s;'% self.wavelength)
        lines.append('parameters.distance = %s;' % self.distance)
        lines.append('parameters.unitCell = %s;' % list(self.lattice_settings))
        lines.append('parameters.ubMat = %s;' % str(self.UBmat.tolist()))
        lines.append('parameters.oMat = %s;' % str(self.Omat.tolist()))
        lines.append('parameters.oVec = [0,0,0];')
        lines.append('parameters.det0x = %s;' % self.xc)
        lines.append('parameters.det0y = %s;' % self.yc)
        lines.append('parameters.xTrans = [0,0,0];')
        lines.append('parameters.orientErrorDetPitch = %s;' 
                     % (self.pitch*radians))
        lines.append('parameters.orientErrorDetRoll = %s;' 
                     % (self.roll*radians))
        lines.append('parameters.orientErrorDetYaw = %s;' % (self.yaw*radians))
        lines.append('parameters.orientErrorGonPitch = %s;' 
                     % (self.gonpitch*radians))
        lines.append('parameters.twoThetaCorrection = 0;')
        lines.append('parameters.twoThetaNom = %s;' % (self.twotheta*radians))
        lines.append('parameters.omegaCorrection = 0;')
        lines.append('parameters.omegaNom = %s;' % (self.omega*radians))
        lines.append('parameters.chiCorrection = 0;')
        lines.append('parameters.chiNom = %s;' % (self.chi*radians))
        lines.append('parameters.phiCorrection = 0;')
        lines.append('parameters.phiNom = %s;' % (self.phi*radians))
        lines.append('parameters.phiStep = %s;' % (self.phi_step*radians))
        lines.append('parameters.gridOrigin = %s;' % self.grid_origin)
        lines.append('parameters.gridBasis = %s;' % self.grid_basis)
        lines.append('parameters.gridDim = %s;' % self.grid_step)
        lines.append('parameters.gridOffset =  [0,0,0];')
        lines.append('parameters.extraFlip =  false;')
        lines.append('inputData.chunkSize =  [32,32,32];')
        lines.append('outputData.dimensions = %s;' % list(self.grid_shape))
        lines.append('outputData.chunkSize =  [32,32,32];')
        lines.append('outputData.compression = %s;' % 0)
        lines.append('outputData.hdfChunkSize = [32,32,32];')
        lines.append('transformer.transformOptions =  0;')
        lines.append('transformer.oversampleX = 1;')
        lines.append('transformer.oversampleY =  1;')
        lines.append('transformer.oversampleZ =  4;')
        f = open(settings_file, 'w')
        f.write('\n'.join(lines))
        f.close()

    def write_angles(self, polar_angles, azimuthal_angles):
        with self.entry.nxfile:
            if 'sample' not in self.entry:
                self.entry['sample'] = NXsample()
            if 'peaks' not in self.entry:
                self.entry['peaks'] = NXdata()
            else:
                if 'polar_angle' in self.entry['peaks']:
                    del self.entry['peaks/polar_angle']
                if 'azimuthal_angle' in self.entry['peaks']:
                    del self.entry['peaks/azimuthal_angle']
            self.write_parameter('peaks/polar_angle', polar_angles)
            self.write_parameter('peaks/azimuthal_angle', azimuthal_angles)

    def initialize_peaks(self):
        peaks=list(zip(self.xp,  self.yp, self.zp, self.intensity))
        self.peak = dict(zip(range(len(peaks)),[NXPeak(*args) for args in peaks]))

    def initialize_grid(self):
        if self.Qh is not None and self.Qk is not None and self.Ql is not None:
            self.h_start, self.h_step, self.h_stop = (
                self.Qh[0], self.Qh[1]-self.Qh[0], self.Qh[-1])
            self.k_start, self.k_step, self.k_stop = (
                self.Qk[0], self.Qk[1]-self.Qk[0], self.Qk[-1])
            self.l_start, self.l_step, self.l_stop = (
                self.Ql[0], self.Ql[1]-self.Ql[0], self.Ql[-1])
        else:
            polar_max = self.polar_max
            try:
                self.set_polar_max(self.polar_angle.max())
            except:
                pass
            self.h_stop = np.round(self.ds_max * self.a)
            h_range = np.round(2*self.h_stop)
            self.h_start = -self.h_stop
            self.h_step = np.round(h_range/1000, 2)
            self.k_stop = np.round(self.ds_max * self.b)
            k_range = np.round(2*self.k_stop)
            self.k_start = -self.k_stop
            self.k_step = np.round(k_range/1000, 2)
            self.l_stop = np.round(self.ds_max * self.c)
            l_range = np.round(2*self.l_stop)
            self.l_start = -self.l_stop
            self.l_step = np.round(l_range/1000, 2)
            self.polar_max = polar_max
        self.define_grid()

    def define_grid(self):
        self.h_shape = np.int32(np.round((self.h_stop - self.h_start) / 
                                          self.h_step, 2)) + 1
        self.k_shape = np.int32(np.round((self.k_stop - self.k_start) / 
                                          self.k_step, 2)) + 1
        self.l_shape = np.int32(np.round((self.l_stop - self.l_start) / 
                                          self.l_step, 2)) + 1
        self.grid_origin = [self.h_start, self.k_start, self.l_start]
        self.grid_step = [np.int32(np.rint(1.0/self.h_step)),    
                          np.int32(np.rint(1.0/self.k_step)),
                          np.int32(np.rint(1.0/self.l_step))]
        self.grid_shape = [self.h_shape, self.k_shape, self.l_shape]
        self.grid_basis = [[1,0,0],[0,1,0],[0,0,1]]

    def prepare_transform(self, output_link, mask=None):
        command = self.cctw_command(mask)
        h = NXfield(np.linspace(self.h_start, self.h_stop, self.h_shape), 
                    name='Qh')
        k = NXfield(np.linspace(self.k_start, self.k_stop, self.k_shape), 
                    name='Qk')
        l = NXfield(np.linspace(self.l_start, self.l_stop, self.l_shape), 
                    name='Ql')
        if mask:
            transform = 'masked_transform'
        else:
            transform = 'transform'
        
        with self.entry.nxfile:
            if transform in self.entry:
                del self.entry[transform]            
        
            self.entry[transform] = NXdata(NXlink(name = 'data', 
                                           target='/entry/data/v',
                                           file=output_link), [l, k, h])
            self.entry[transform+'/weights'] = NXlink(target='/entry/data/n',
                                                      file=output_link)
            self.entry[transform+'/command'] = command

    def cctw_command(self, mask=False):
        entry = self.entry.nxname
        if mask:
            name = entry + '_masked_transform'
        else:
            name = entry + '_transform'
        dir = os.path.dirname(self.entry['data'].nxsignal.nxfilename)
        filename = self.entry.nxfilename
        parfile = os.path.join(dir, entry+'_transform.pars')
        command = ['cctw transform --script %s' % parfile]
        if 'pixel_mask' in self.entry['instrument/detector']:
            command.append('--mask %s\#/%s/instrument/detector/pixel_mask' 
                           % (filename, entry))
        if mask and 'data_mask' in self.entry['data']:
            command.append('--mask3d %s\#/%s/data/data_mask' 
                           % (filename, entry))
        if 'monitor_weight' in self.entry['data']:
            command.append('--weights %s\#/%s/data/monitor_weight' 
                           % (filename, entry))
        command.append('%s\#/%s/data/data' % (filename, entry))
        command.append('--output %s/%s.nxs\#/entry/data' % (dir, name))
        command.append('--normalization 0')
        return ' '.join(command)
 
    def set_symmetry(self):
        if self.symmetry == 'cubic':
            self.c = self.b = self.a
            self.alpha = self.beta = self.gamma = 90.0 
        elif self.symmetry == 'tetragonal':
            self.b = self.a       
            self.alpha = self.beta = self.gamma = 90.0
        elif self.symmetry == 'orthorhombic':
            self.alpha = self.beta = self.gamma = 90.0 
        elif self.symmetry == 'hexagonal':
            self.b = self.a
            self.alpha = self.beta = 90.0 
            self.gamma = 120.0
        elif self.symmetry == 'monoclinic':
            self.alpha = self.gamma = 90.0

    def guess_symmetry(self):
        if self.lattice_parameters.count(None) > 0:
            return 'monoclinic'
        if np.isclose(self.alpha, 90.0) and np.isclose(self.beta, 90.0):
            if np.isclose(self.gamma, 90.0):
                if np.isclose(self.a, self.b) and np.isclose(self.a, self.c):
                    return 'cubic'
                elif np.isclose(self.a, self.b):
                    return 'tetragonal'
                else:
                    return 'orthorhombic'
            elif np.isclose(self.gamma, 120.0):
                if np.isclose(self.a, self.b):
                    return 'hexagonal'
                else:
                    return 'triclinic'
        elif np.isclose(self.alpha, 90.0) and np.isclose(self.gamma, 90.0):
            return 'monoclinic'
        else:
            return 'triclinic'

    @property
    def lattice_parameters(self):
        return self.a, self.b, self.c, self.alpha, self.beta, self.gamma

    @property
    def lattice_settings(self):
        return (self.a, self.b, self.c, 
                self.alpha*radians, self.beta*radians, self.gamma*radians)

    @property
    def tilts(self):
        return self.yaw, self.pitch, self.roll

    @property
    def centers(self):
        return self.xc, self.yc

    @property
    def roll(self):
        return self._roll

    @roll.setter
    def roll(self, value):
        self._roll = value
        try:
            self._Dmat_cache = inv(rotmat(1, self.roll) * rotmat(2, self.pitch) *
                                   rotmat(3, self.yaw))

        except:
            pass
        
    @property
    def pitch(self):
        return self._pitch

    @pitch.setter
    def pitch(self, value):
        self._pitch = value
        try:
            self._Dmat_cache = inv(rotmat(1, self.roll) * rotmat(2, self.pitch) *
                                   rotmat(3, self.yaw))

        except:
            pass
        
    @property
    def yaw(self):
        return self._yaw

    @yaw.setter
    def yaw(self, value):
        self._yaw = value
        try:
            self._Dmat_cache = inv(rotmat(1, self.roll) * rotmat(2, self.pitch) *
                                   rotmat(3, self.yaw))

        except:
            pass
        
    @property
    def chi(self):
        return self._chi

    @chi.setter
    def chi(self, value):
        self._chi = value
        try:
            self._Gmat_cache = (rotmat(2,self.gonpitch) * rotmat(3, self.omega) * 
                                rotmat(1, self.chi))
        except:
            pass
        
    @property
    def omega(self):
        return self._omega

    @omega.setter
    def omega(self, value):
        self._omega = value
        try:
            self._Gmat_cache = (rotmat(2,self.gonpitch) * rotmat(3, self.omega) * 
                                rotmat(1, self.chi))
        except:
            pass

    @property
    def gonpitch(self):
        return self._gonpitch

    @gonpitch.setter
    def gonpitch(self, value):
        self._gonpitch = value
        try:
            self._Gmat_cache = (rotmat(2,self.gonpitch) * rotmat(3, self.omega) * 
                                rotmat(1, self.chi))
        except:
            pass

    @property
    def phi_start(self):
        return self.phi

    @property
    def ds_max(self):
        return 2 * np.sin(self.polar_max*radians/2) / self.wavelength

    @property
    def unitcell(self):
        if (self._unitcell is None or
            not np.allclose(self._unitcell.lattice_parameters,
                            np.array(self.lattice_parameters))):
           self._unitcell = unitcell(self.lattice_parameters, self.centring)
        self._unitcell.makerings(self.ds_max)
        return self._unitcell

    def absent(self, h, k, l):
        return outif[self.centring](h, k, l)

    @property
    def npks(self):
        try:
            return self.xp.size
        except Exception:
            return 0

    @property
    def rings(self):
        return 2 * np.arcsin(np.array(self.unitcell.ringds) * 
                             self.wavelength/2) * degrees

    @property
    def UBmat(self):
        """Determine the U matrix using the defined UB matrix and B matrix
        calculated from the lattice parameters
        """
        if self.Umat is not None:
            return self.Umat * self.Bmat
        else:
            return np.matrix(np.eye(3))

    @property
    def Bimat(self):
        """Create a B matrix containing the column basis vectors of the direct 
        unit cell.
        """
        a, b, c, alpha, beta, gamma = self.lattice_parameters
        alpha = alpha * radians
        beta = beta * radians
        gamma = gamma * radians
        B23 = c*(np.cos(alpha)-np.cos(beta)*np.cos(gamma))/np.sin(gamma)
        B33 = np.sqrt(c**2-(c*np.cos(beta))**2-B23**2)
        return np.matrix(((a, b*np.cos(gamma), c*np.cos(beta)),
                         (0, b*np.sin(gamma),  B23),
                         (0, 0, B33)))

    @property
    def Bmat(self):
        """Create a B matrix containing the column basis vectors of the direct 
        unit cell.
        """
        return inv(self.Bimat)

    @property
    def Omat(self):
        """Define the transform that rotates detector axes into lab axes.

        The inverse transforms detector coords into lab coords.
        When all angles are zero,
            +X(det) = -y(lab), +Y(det) = +z(lab), and +Z(det) = -x(lab)
        """
        if self.standard:
            return np.matrix(((0,-1,0), (0,0,1), (-1,0,0)))
        else:
            return np.matrix(((0,0,1), (0,1,0), (-1,0,0)))

    @property
    def Dmat(self):
        """Define the matrix, whose inverse physically orients the detector.

        It also transforms detector coords into lab coords.
        Operation order:    yaw -> pitch -> roll
        """
        return self._Dmat_cache

    def Gmat(self, phi):
        """Define the matrix that physically orients the goniometer head.
    
        It performs the inverse transform of lab coords into head coords.
        """
        return self._Gmat_cache * rotmat(3, phi)

    @property
    def Cvec(self):
        return vec(self.xc, self.yc)

    @property
    def Dvec(self):
        """Define the vector from the detector center to the sample position.
        
        Svec is the vector from the goniometer center to the sample position, 
        i.e., t_gs. From this is subtracted the vector from the goniometer 
        center to the detector center, i.e., t_gd
        """
        return vec(-self.distance)

    @property
    def Evec(self):
        return vec(1.0 / self.wavelength)

    def Gvec(self, x, y, z):
        phi = self.phi + self.phi_step * z
        v1 = vec(x, y)
        v2 = self.pixel_size * inv(self.Omat) * (v1 - self.Cvec)
        v3 = inv(self.Dmat) * v2 - self.Dvec
        return (inv(self.Gmat(phi)) * 
                ((norm_vec(v3) / self.wavelength) - self.Evec))

    def get_Gvecs(self, idx):
        self.Gvecs = [self.Gvec(x,y,z) for x,y,z 
                      in zip(self.xp[idx], self.yp[idx], self.zp[idx])]
        return self.Gvecs

    def set_polar_max(self, polar_max):
        try:
            if not isinstance(self.polar_angle, np.ndarray):
                self.polar_angle, self.azimuthal_angle = \
                    self.calculate_angles(self.xp, self.yp)
            self.x = []
            self.y = []
            for i in range(self.npks):
                if self.polar_angle[i] <= polar_max:
                    self.x.append(self.xp[i])
                    self.y.append(self.yp[i])
        except Exception:
            pass
        self.polar_max = polar_max
        self._idx = None

    def calculate_angles(self, x, y):
        """Calculate the polar and azimuthal angles of the specified pixels"""
        Oimat = inv(self.Omat)
        Mat = self.pixel_size * inv(self.Dmat) * Oimat
        polar_angles = []
        azimuthal_angles = []
        for i in range(len(x)):
            peak = Oimat * (vec(x[i], y[i]) - self.Cvec)
            v = norm(Mat * peak)
            polar_angle = np.arctan(v / self.distance)
            polar_angles.append(polar_angle)
            azimuthal_angles.append(np.arctan2(-peak[1,0], peak[2,0]))
        return (np.array(polar_angles) * degrees, 
                np.array(azimuthal_angles) * degrees)

    def calculate_rings(self, polar_max=None):
        """Calculate the polar angles of the Bragg peak rings"""
        if polar_max is None:
            polar_max = self.polar_max
        ds_max = 2 * np.sin(polar_max*radians/2) / self.wavelength
        dss = set(sorted([np.around(x[0],3) 
                          for x in self.unitcell.gethkls(ds_max)]))
        peaks = []
        for ds in dss:
            peaks.append(2*np.arcsin(self.wavelength*ds/2)*degrees)
        return sorted(peaks)

    def angle_peaks(self, i, j):
        """Calculate the angle (in degrees) between two peaks"""
        g1 = norm_vec(self.Gvec(self.xp[i], self.yp[i], self.zp[i]))
        g2 = norm_vec(self.Gvec(self.xp[j], self.yp[j], self.zp[j]))
        return np.around(np.arccos(float(g1.T*g2)) * degrees, 3)

    def angle_hkls(self, h1, h2):
        """Calculate the angle (in degrees) between two (hkl) tuples"""
        return self.unitcell.anglehkls(h1, h2)[0]
        
    def angle_rings(self, ring1, ring2):
        """Calculate the set of angles allowed between peaks in two rings"""
        return set(np.around(np.arccos(
                                 self.unitcell.getanglehkls(ring1, ring2)[1])
                             * degrees, 3))

    def assign_rings(self):
        """Assign all the peaks to rings (stored in 'rp')"""
        polar_max = self.polar_max
        self.set_polar_max(max(self.polar_angle))
        rings = self.rings
        self.rp = np.zeros((self.npks), np.int16)
        for i in range(self.npks):
            self.rp[i] = (np.abs(self.polar_angle[i] - rings)).argmin()
        self.set_polar_max(polar_max)

    def compatible(self, i, j):
        """Determine if the angle between two peaks is contained in the set of
        angles between their respective rings"""
        if i == j:
            return False
        angle = self.angle_peaks(i, j)
        angles = self.angle_rings(self.rp[i], self.rp[j])
        close = [a for a in angles if abs(a-angle) < self.peak_tolerance]
        if close:
            return True
        else:
            return False
        
    def generate_grains(self):
        self.assign_rings()
        grains = []
        peaks = [i for i in range(self.npks) 
                 if self.polar_angle[i] < self.polar_max]
        assigned = set()
        for (i, j) in [(i, j) for i in peaks for j in peaks if j > i]:
            if self.compatible(i,j):
                if i not in assigned and j not in assigned:
                    grains.append([i,j])
                    assigned.add(i)
                    assigned.add(j)
                else:
                    for grain in grains:
                        if i not in grain:
                            bad = [k for k in grain if not self.compatible(i,k)]
                            if not bad:
                                grain.append(i)
                                assigned.add(i)
                        if j not in grain:
                            bad = [k for k in grain if not self.compatible(j,k)]
                            if not bad:
                                grain.append(j)
                                assigned.add(j)
        self.grains = sorted([NXgrain(grain) 
                              for grain in grains if len(grain) > 2])
        for grain in self.grains:
            self.orient(grain)
            grain.peaks = [i for i in range(self.npks) 
                           if self.diff(i) < self.hkl_tolerance]
            grain.score = self.score(grain)            
        
    def orient(self, grain=None):
        """Determine the UB matrix (optionally for the specified grain)"""
        if grain:
            for (i, j) in [(i,j) for i in grain.peaks 
                           for j in grain.peaks if j > i]:
                angle = self.angle_peaks(i, j)
                if abs(angle) > 20.0 and abs(angle-180.0) > 20.0:
                    break
            grain.primary, grain.secondary = i, j
            self.Umat = grain.Umat = self.get_UBmat(i, j) * self.Bimat
        else:
            self.Umat = (self.get_UBmat(self.primary, self.secondary) 
                         * self.Bimat)

    def unitarity(self):
        if self.Umat is not None:
            return np.matrix(self.Umat) * np.matrix(self.Umat.T)
        else:
            return None

    def get_UBmat(self, i, j):
        """Determine a UBmatrix using the specified peaks"""
        ring1 = np.abs(self.polar_angle[i] - self.rings).argmin()
        g1 = np.array(self.Gvec(self.xp[i], self.yp[i], self.zp[i]).T)[0]
        ring2 = np.abs(self.polar_angle[j] - self.rings).argmin()
        g2 = np.array(self.Gvec(self.xp[j], self.yp[j], self.zp[j]).T)[0]
        self.unitcell.orient(ring1, g1, ring2, g2, verbose=1)
        return np.matrix(self.unitcell.UB)

    def get_hkl(self, x, y, z):
        """Determine hkl for the specified pixel coordinates"""
        if self.Umat is not None:
            v5 = self.Gvec(x, y, z)
#            v6 = inv(self.Umat) * v5
#            v7 = inv(self.Bmat) * v6
            v7 = inv(self.UBmat) * v5
            return list(np.array(v7.T)[0])
        else:
            return [0.0, 0.0, 0.0]

    def get_hkls(self):
        """Determine the set of hkls for all the peaks as three columns"""
        return zip(*[self.hkl(i) for i in range(self.npks)])

    @property
    def hkls(self):
        """Determine the set of hkls for all the peaks"""
        return [self.get_hkl(self.xp[i], self.yp[i], self.zp[i]) 
                for i in range(self.npks)]

    def hkl(self, i):
        """Return the calculated (hkl) for the specified peak"""
        return self.get_hkl(self.xp[i], self.yp[i], self.zp[i])

    def get_xyz(self, h, k, l):

        v7 = vec(h, k, l)
        v6 = self.Bmat * v7
        v5 = self.Umat * v6
        
        ewald_condition = lambda phi: (norm(self.Evec)**2 - norm(self.Gmat(phi)*v5 +
                                       self.Evec)**2)

        phis = []
        if h == 0 and k == 0 and l == 0:
            pass
        elif optimize.fsolve(ewald_condition, 45.0, full_output=1)[2] == 1:
            phis = list(np.unique(np.around([optimize.fsolve(ewald_condition, phi) % 360 
                                             for phi in np.arange(30, 390, 15)], 
                                            decimals=4)))

        def get_ij(phi):
            v4 = self.Gmat(phi) * v5
            p = norm_vec(v4 + self.Evec)
            v3 = -(self.Dvec[0,0] / p[0,0]) * p
            v2 = self.Dmat * (v3 + self.Dvec)
            v1 = (self.Omat * v2 / self.pixel_size) + self.Cvec
            return v1[0,0], v1[1,0]

        peaks = []
        for phi in phis:
            x, y = get_ij(phi)
            z = ((phi - self.phi_start) / self.phi_step) % 3600
            if z < 25:
                z = z + 3600
            elif z > 3625:
                z = z - 3600
            if x > 0 and x < self.shape[1] and y > 0 and y < self.shape[0]:
                peaks.append(NXPeak(x, y, z, H=h, K=k, L=l))

        peaks = [peak for peak in peaks if peak.z > 0 and peak.z < 3648]

        return peaks

    def get_xyzs(self, Qh=None, Qk=None, Ql=None):
        if self._julia is None:
            try:
                from julia import Julia
                self._julia = Julia(compiled_modules=False)
                self._julia.eval("@eval Main import Base.MainInclude: include")
            except Exception as error:
                raise NeXusError(str(error))
        import pkg_resources
        from julia import Main, Pkg
        Pkg.add("Roots")
        Main.Gmat0 = np.array(self.Gmat(0.0))
        Main.UBmat = np.array(self.UBmat)
        Main.Dmat = np.array(self.Dmat)
        Main.Omat = np.array(self.Omat) / self.pixel_size
        Main.Cvec = list(np.array(self.Cvec.T).reshape((3)))
        Main.Dvec = list(np.array(self.Dvec.T).reshape((3)))
        Main.Evec = list(np.array(self.Evec.T).reshape((3)))
        Main.shape = self.shape
        Main.include(pkg_resources.resource_filename('nxrefine', 'get_xyzs.jl'))
        if Qh is None:
            Qh = int(self.Qh[-1])
        if Qk is None:
            Qk = int(self.Qk[-1])
        if Ql is None:
            Ql = int(self.Ql[-1])
        ps = self._julia.get_xyzs(Qh, Qk, Ql)
        peaks = []
        for p in ps:
            try:
                h, k, l = p[3], p[4], p[5]
                if not self.absent(h, k, l):
                    peaks.append(NXPeak(*p[0:3], H=h, K=k, L=l)))
            except Exception:
                pass
        return peaks                       

    def polar(self, i):
        """Return the polar angle for the specified peak"""
        Oimat = inv(self.Omat)
        Mat = self.pixel_size * inv(self.Dmat) * Oimat
        peak = Oimat * (vec(self.xp[i], self.yp[i]) - self.Cvec)
        v = norm(Mat * peak)
        return np.arctan(v / self.distance)

    def score(self, grain=None):
        self.set_idx()
        if self.idx:
            diffs = self.diffs()
            weights = self.weights
            return np.sum(weights * diffs) / np.sum(weights)
        else:
            return 0.0

    @property
    def idx(self):
        if self._idx is None:
            self._idx = list(np.where(self.polar_angle < self.polar_max)[0])
        return self._idx
        
    def set_idx(self, hkl_tolerance=None):
        if hkl_tolerance is None:
            hkl_tolerance = self.hkl_tolerance
        _idx = list(np.where(self.polar_angle < self.polar_max)[0])
        self._idx = [i for i in _idx if self.diff(i) < hkl_tolerance]

    @property
    def weights(self):
        return np.array(self.intensity[self.idx])

    def diffs(self):
        """Return the set of reciproal space differences for all the peaks"""
        return np.array([self.diff(i) for i in self.idx])

    def diff(self, i):
        """Determine the reciprocal space difference between the calculated 
        (hkl) and the closest integer (hkl) of the specified peak"""
        h, k, l = self.hkl(i)
        Q = np.matrix((h, k, l)).T
        Q0 = np.matrix((np.rint(h), np.rint(k), np.rint(l))).T
        return norm(self.Bmat * (Q - Q0))

    def angle_diffs(self):
        """Return the set of polar angle differences for all the peaks"""
        return np.array([self.angle_diff(i) for i in self.idx])

    def angle_diff(self, i):
        """Determine the polar angle difference between the calculated 
        (hkl) and the closest integer (hkl) of the specified peak"""
        h, k, l = self.hkl(i)
        (h0, k0, l0) = (np.rint(h), np.rint(k), np.rint(l))
        polar0 = 2 * np.arcsin(self.unitcell.ds((h0,k0,l0))*self.wavelength/2)
        return np.abs(self.polar(i) - polar0)

    def xyz(self, i):
        """Return the pixel coordinates of the specified peak"""
        return self.xp[i], self.yp[i], self.zp[i]

    def get_peaks(self, polar_max=None):
        """Return tuples containing the peaks and their respective parameters"""
        peaks = np.array([i for i in range(self.npks) 
                          if self.polar_angle[i] < self.polar_max])
        x, y, z = (np.rint(self.xp[peaks]).astype(np.int16), 
                   np.rint(self.yp[peaks]).astype(np.int16), 
                   np.rint(self.zp[peaks]).astype(np.int16))
        polar, azi = self.polar_angle[peaks], self.azimuthal_angle[peaks]
        intensity = self.intensity[peaks]
        if self.Umat is not None:
            h, k, l = self.get_hkls()
            h = np.array(h)[peaks]
            k = np.array(k)[peaks]
            l = np.array(l)[peaks]
            diffs = np.array([self.diff(i) for i in peaks])
        else:
            h = k = l = diffs = np.zeros(peaks.shape, dtype=np.float32)
        return list(zip(peaks, x, y, z, polar, azi, intensity, h, k, l, diffs))

    def get_ring_hkls(self):
        polar_max = self.polar_max
        self.set_polar_max(max(self.polar_angle))
        dss = sorted([ringds for ringds in self.unitcell.ringds])
        hkls=[self.unitcell.ringhkls[ds] for ds in dss]
        self.set_polar_max(polar_max)
        return hkls
#
#    def find_ring(self, h, k, l):
#        hkl_list = self.unitcell.gethkls(self.ds_max)
#        try:
#            idx = [x[1] for x in hkl_list].index((h,k,l))
#            return self.unitcell.ringds.index(hkl_list[idx][0])
#        except ValueError:
#            return None
#
#    def find_ring_indices(self, ring):
#        if ring is None:
#            return []
#        less = list(np.where(self.polar_angle>self.rings[ring]
#                             - self.polar_tolerance)[0])
#        more = list(np.where(self.polar_angle<self.rings[ring]
#                             + self.polar_tolerance)[0])
#        return [idx for idx in less if idx in more]
#    def Gvs(self, polar_max=None):
#        if self.polar_max is None:
#            self.polar_max = polar_max
#        result = np.array([self.Gvec(self.xp[i], self.yp[i], self.zp[i]) 
#                         for i in self.idx])
#        result.shape = (len(self.idx),3)
#        return result

    def define_parameters(self, **opts):
        from lmfit import Parameters
        self.parameters = Parameters()
        if 'lattice' in opts:
            self.define_lattice_parameters()
            del opts['lattice']
        for opt in opts:
            self.parameters.add(opt, getattr(self, opt), vary=opts[opt])
        return self.parameters

    def define_lattice_parameters(self, lattice=True):
        if self.symmetry == 'cubic':
            self.parameters.add('a', self.a, vary=lattice)
        elif self.symmetry == 'tetragonal' or self.symmetry == 'hexagonal':
            self.parameters.add('a', self.a, vary=lattice)
            self.parameters.add('c', self.c, vary=lattice)
        elif self.symmetry == 'orthorhombic':
            self.parameters.add('a', self.a, vary=lattice)
            self.parameters.add('b', self.b, vary=lattice)
            self.parameters.add('c', self.c, vary=lattice)
        elif self.symmetry == 'monoclinic':
            self.parameters.add('a', self.a, vary=lattice)
            self.parameters.add('b', self.b, vary=lattice)
            self.parameters.add('c', self.c, vary=lattice)
            self.parameters.add('beta', self.beta, vary=lattice)
        else:
            self.parameters.add('a', self.a, vary=lattice)
            self.parameters.add('b', self.b, vary=lattice)
            self.parameters.add('c', self.c, vary=lattice)
            self.parameters.add('alpha', self.alpha, vary=lattice)
            self.parameters.add('beta', self.beta, vary=lattice)
            self.parameters.add('gamma', self.gamma, vary=lattice)

    def get_parameters(self, parameters):
        for p in parameters:
            vars(self)[p] = parameters[p].value
        self.set_symmetry()
        
    def restore_parameters(self):
        for p in self.parameters:
            vars(self)[p] = self.parameters[p].init_value
        self.set_symmetry()

    def refine_hkls(self, method='leastsq', **opts):
        self.set_idx()
        from lmfit import minimize, fit_report
        if self.Umat is None:
            raise NeXusError('No orientation matrix defined')
        p0 = self.define_parameters(**opts)
        self.result = minimize(self.hkl_residuals, p0, method=method)
        self.fit_report = fit_report(self.result)
        if self.result.success:
            self.get_parameters(self.result.params)

    def hkl_residuals(self, parameters):
        self.get_parameters(parameters)
        return self.diffs()

    def refine_angles(self, method='nelder', **opts):
        self.set_idx()
        from lmfit import minimize, fit_report
        p0 = self.define_parameters(lattice=True, **opts)
        self.result = minimize(self.angle_residuals, p0, method=method)
        self.fit_report = fit_report(self.result)
        if self.result.success:
            self.get_parameters(self.result.params)

    def angle_residuals(self, parameters):
        self.get_parameters(parameters)
        return self.angle_diffs()

    def define_orientation_matrix(self):
        from lmfit import Parameters
        p = Parameters()
        for i in range(3):
            for j in range(3):
                p.add('U%d%d' % (i,j), self.Umat[i,j])
        self.init_p = self.Umat
        return p

    def get_orientation_matrix(self, p):
        for i in range(3):
            for j in range(3):
                self.Umat[i,j] = p['U%d%d' % (i,j)].value

    def refine_orientation_matrix(self, **opts):
        self.set_idx()
        from lmfit import minimize, fit_report
        p0 = self.define_orientation_matrix()
        self.result = minimize(self.orient_residuals, p0, **opts)
        self.fit_report = fit_report(self.result)
        if self.result.success:
            self.get_orientation_matrix(self.result.params)

    def restore_orientation_matrix(self):
        self.Umat = self.init_p

    def orient_residuals(self, p):
        self.get_orientation_matrix(p)
        return self.diffs()


class NXPeak(object):

    def __init__(self, x, y, z, intensity=None, pixel_count=None, 
                 H=None, K=None, L=None, radius=None, 
                 polar_angle=None, azimuthal_angle=None, rotation_angle=None):
        self.x = x
        self.y = y
        self.z = z
        self.intensity = intensity
        self.pixel_count = pixel_count
        self.H = H
        self.K = K
        self.L = L
        self.radius = radius
        self.polar_angle = polar_angle
        self.azimuthal_angle = azimuthal_angle
        self.rotation_angle = rotation_angle
        self.ring = None
        self.Umat = None

    def __repr__(self):
        return "NXPeak(x=%.2f, y=%.2f, z=%.2f)" % (self.x, self.y, self.z)


class NXgrain(object):

    def __init__(self, peaks, Umat=None, primary=None, secondary=None):
        self.peaks = sorted(list(set(sorted(peaks))))
        self.primary = primary
        self.secondary = secondary
        self.Umat = Umat
        self.score = 0

    def __repr__(self):
        return "NXgrain(%s)" % self.peaks

    def __lt__(self, other):
        return len(self.peaks) < len(other.peaks)

    def __contains__(self, peak):
        return peak in self.peaks

    def __len__(self):
        return len(self.peaks)
