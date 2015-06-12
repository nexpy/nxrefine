import numpy as np
import os
import random
from scipy.optimize import minimize
from nexusformat.nexus import *
from nxpeaks.unitcell import unitcell
from nxpeaks import closest


degrees = 180.0 / np.pi
radians = np.pi / 180.0


def find_nearest(array, value):
    idx = (np.abs(array-value)).argmin()
    return array[idx]
 

def rotmat(axis, angle):
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


def norm(vec):
    return vec / np.linalg.norm(vec)


class NXRefine(object):

    symmetries = ['cubic', 'tetragonal', 'orthorhombic', 'hexagonal', 
                  'monoclinic', 'triclinic']
    centrings = ['P', 'A', 'B', 'C', 'I', 'F', 'R']

    def __init__(self, node=None, 
                 a=None, b=None, c=None, alpha=None, beta=None, gamma=None,
                 wavelength=None, distance=None, 
                 yaw=None, pitch=None, roll=None,
                 xc=None, yc=None, symmetry=None, centring=None,
                 polar_max=None):
        if node is not None:
            self.entry = node.nxentry
        self.a = a
        self.b = b
        self.c = c
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.wavelength = wavelength
        self.distance = distance
        self.yaw = yaw
        self.pitch = pitch
        self.roll = roll
        self.gonpitch = 0.0
        self.twotheta = 0.0
        self.phi = 0.0
        self.chi = 0.0
        self.xc = xc
        self.yc = yc
        self.symmetry = symmetry
        self.centring = centring
        self.omega_start = 0.0
        self.omega_step = 0.1
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
        
        self.grains = None
        
        if self.entry:
            self.read_parameters()

    def read_parameter(self, path):
        try:
            field = self.entry[path]
            if field.shape == () and not isinstance(field.nxdata, basestring):
                return np.asscalar(field.nxdata)
            else:
                return field.nxdata
        except NeXusError:
            pass 

    def read_parameters(self, entry=None):
        if entry:
            self.entry = entry
        self.a = self.read_parameter('sample/unitcell_a')
        self.b = self.read_parameter('sample/unitcell_b')
        self.c = self.read_parameter('sample/unitcell_c')
        self.alpha = self.read_parameter('sample/unitcell_alpha')
        self.beta = self.read_parameter('sample/unitcell_beta')
        self.gamma = self.read_parameter('sample/unitcell_gamma')
        self.wavelength = self.read_parameter('instrument/monochromator/wavelength')
        self.distance = self.read_parameter('instrument/detector/distance')
        self.yaw = self.read_parameter('instrument/detector/yaw')
        if self.yaw is None:
            self.yaw = 0.0
        self.pitch = self.read_parameter('instrument/detector/pitch')
        if self.pitch is None:
            self.pitch = 0.0
        self.roll = self.read_parameter('instrument/detector/roll')
        if self.roll is None:
            self.roll = 0.0
        self.xc = self.read_parameter('instrument/detector/beam_center_x')
        self.yc = self.read_parameter('instrument/detector/beam_center_y')
        self.symmetry = self.read_parameter('sample/unit_cell_group')
        self.centring = self.read_parameter('sample/lattice_centring')
        self.xp = self.read_parameter('peaks/x')
        self.yp = self.read_parameter('peaks/y')
        self.zp = self.read_parameter('peaks/z')
        self.polar_angle = self.read_parameter('peaks/polar_angle')
        self.azimuthal_angle = self.read_parameter('peaks/azimuthal_angle')
        self.intensity = self.read_parameter('peaks/intensity')
        self.pixel_size = self.read_parameter('instrument/detector/pixel_size')
        self.pixel_mask = self.read_parameter('instrument/detector/pixel_mask')
        self.pixel_mask_applied = self.read_parameter('instrument/detector/pixel_mask_applied')
        self.rotation_angle = self.read_parameter('peaks/rotation_angle')
        self.primary = self.read_parameter('peaks/primary_reflection')
        self.secondary = self.read_parameter('peaks/secondary_reflection')
        self.Umat = self.read_parameter('instrument/detector/orientation_matrix')
        if isinstance(self.polar_angle, np.ndarray):
            try:
                self.set_polar_max(np.sort(self.polar_angle)[20] + 0.1)
            except IndexError:
                self.set_polar_max(self.polar_angle.max())
        else:
            self.set_polar_max(20.0)

    def write_parameter(self, path, value):
        if value is not None:
            if isinstance(value, basestring):
                try:
                    del self.entry[path]
                except NeXusError:
                    pass
            self.entry[path] = value

    def write_parameters(self, entry=None):
        if entry:
            self.entry = entry
        if 'sample' not in self.entry.entries:
            self.entry.sample = NXsample()
        self.write_parameter('sample/unit_cell_group', self.symmetry)
        self.write_parameter('sample/lattice_centring', self.centring)
        self.write_parameter('sample/unitcell_a', self.a)
        self.write_parameter('sample/unitcell_b', self.b)
        self.write_parameter('sample/unitcell_c', self.c)
        self.write_parameter('sample/unitcell_alpha', self.alpha)
        self.write_parameter('sample/unitcell_beta', self.beta)
        self.write_parameter('sample/unitcell_gamma', self.gamma)
        if 'instrument' not in self.entry.entries:
            self.entry.instrument = NXinstrument()
        if 'detector' not in self.entry.instrument.entries:
            self.entry.instrument.detector = NXdetector()
        if 'monochromator' not in self.entry.instrument.entries:
            self.entry.instrument.monochromator = NXmonochromator()
        self.write_parameter('instrument/monochromator/wavelength', self.wavelength)
        self.write_parameter('instrument/detector/distance', self.distance)
        self.write_parameter('instrument/detector/yaw', self.yaw)
        self.write_parameter('instrument/detector/pitch', self.pitch)
        self.write_parameter('instrument/detector/roll', self.roll)
        self.write_parameter('instrument/detector/beam_center_x', self.xc)
        self.write_parameter('instrument/detector/beam_center_y', self.yc)
        self.write_parameter('instrument/detector/pixel_size', self.pixel_size)
        self.write_parameter('instrument/detector/pixel_mask', self.pixel_mask)
        self.write_parameter('instrument/detector/pixel_mask_applied', self.pixel_mask_applied)
        if self.Umat is not None:
            self.write_parameter('instrument/detector/orientation_matrix', np.array(self.Umat))
        self.write_parameter('peaks/primary_reflection', self.primary)
        self.write_parameter('peaks/secondary_reflection', self.secondary)        
        if self.omega_start is not None and self.omega_step is not None:
            if isinstance(self.z, np.ndarray):
                self.rotation_angle = self.z * self.omega_step + self.omega_start

    def copy_parameters(self, other, sample=False, instrument=False):
        if sample:
            if 'sample' not in other.entry.entries:
                other.entry.sample = NXsample()
            other.write_parameter('sample/unit_cell_group', self.symmetry)
            other.write_parameter('sample/lattice_centring', self.centring)
            other.write_parameter('sample/unitcell_a', self.a)
            other.write_parameter('sample/unitcell_b', self.b)
            other.write_parameter('sample/unitcell_c', self.c)
            other.write_parameter('sample/unitcell_alpha', self.alpha)
            other.write_parameter('sample/unitcell_beta', self.beta)
            other.write_parameter('sample/unitcell_gamma', self.gamma)
        if instrument:
            if 'instrument' not in other.entry.entries:
                other.entry.instrument = NXinstrument()
            if 'detector' not in other.entry.instrument.entries:
                other.entry.instrument.detector = NXdetector()
            if 'monochromator' not in other.entry.instrument.entries:
                other.entry.instrument.monochromator = NXmonochromator()
            other.write_parameter('instrument/monochromator/wavelength', self.wavelength)
            other.write_parameter('instrument/detector/distance', self.distance)
            other.write_parameter('instrument/detector/yaw', self.yaw)
            other.write_parameter('instrument/detector/pitch', self.pitch)
            other.write_parameter('instrument/detector/roll', self.roll)
            other.write_parameter('instrument/detector/beam_center_x', self.xc)
            other.write_parameter('instrument/detector/beam_center_y', self.yc)
            other.write_parameter('instrument/detector/pixel_size', self.pixel_size)
            other.write_parameter('instrument/detector/pixel_mask', self.pixel_mask)
            other.write_parameter('instrument/detector/pixel_mask_applied', self.pixel_mask_applied)
            if self.Umat is not None:
                other.write_parameter('instrument/detector/orientation_matrix', np.array(self.Umat))

    def link_sample(self, other):
        if 'sample' in self.entry:
            if 'sample' in other.entry:
                del other.entry['sample']
            other.entry.makelink(self.entry['sample'])

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
        lines.append('parameters.orientErrorDetPitch = %s;' % (self.pitch*radians))
        lines.append('parameters.orientErrorDetRoll = %s;' % (self.roll*radians))
        lines.append('parameters.orientErrorDetYaw = %s;' % (self.yaw*radians))
        lines.append('parameters.orientErrorGonPitch = %s;' % (self.gonpitch*radians))
        lines.append('parameters.twoThetaCorrection = 0;')
        lines.append('parameters.twoThetaNom = %s;' % (self.twotheta*radians))
        lines.append('parameters.omegaCorrection = 0;')
        lines.append('parameters.omegaStep = %s;' % (self.omega_step*radians))
        lines.append('parameters.chiCorrection = 0;')
        lines.append('parameters.chiNom = %s;' % (self.chi*radians))
        lines.append('parameters.phiCorrection = 0;')
        lines.append('parameters.phiNom = %s;' % (self.phi*radians))
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
        if 'sample' not in self.entry.entries:
            self.entry.sample = NXsample()
        if 'peaks' not in self.entry.entries:
            self.entry.peaks = NXdata()
        if 'polar_angle' in self.entry.peaks.entries:
            del self.entry.peaks['polar_angle']
        if 'azimuthal_angle' in self.entry.peaks.entries:
            del self.entry.peaks['azimuthal_angle']
        self.write_parameter('peaks/polar_angle', polar_angles)
        self.write_parameter('peaks/azimuthal_angle', azimuthal_angles)
        self.entry.peaks.nxsignal = self.entry.peaks.azimuthal_angle
        self.entry.peaks.nxaxes = self.entry.peaks.polar_angle

    def initialize_peaks(self):
        peaks=zip(self.xp,  self.yp, self.zp, self.intensity)
        self.peak = dict(zip(range(len(peaks)),[NXpeak(*args) for args in peaks]))

    def initialize_grid(self):
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

    def prepare_transform(self, output_file):
        command = self.cctw_command()
        h = NXfield(np.linspace(self.h_start, self.h_stop, self.h_shape), name='Qh')
        k = NXfield(np.linspace(self.k_start, self.k_stop, self.k_shape), name='Qk')
        l = NXfield(np.linspace(self.l_start, self.l_stop, self.l_shape), name='Ql')
        self.entry['transform'] = NXdata(NXlink(name = 'data', 
                                         target='/entry/data/v',
                                         file=output_file), [l, k, h])
        self.entry['transform/command'] = command

    def cctw_command(self):
        name = self.entry.nxname + '_transform'
        dir = os.path.dirname(self.entry['data'].nxsignal.nxfilename)
        filename = self.entry.nxfilename
        mask_file = '%s/mask_%s.nxs' % (dir, self.entry.nxname)
        if not os.path.exists(mask_file):
            mask = self.entry['instrument/detector/pixel_mask']
            mask.nxname = 'mask'
            NXroot(NXentry(mask)).save(mask_file)
        return (('cctw transform '
                 '--script %s/%s.pars '
                 '--mask %s\#/entry/mask '
                 '%s\#/%s/data/data ' 
                 '-o %s/%s.nxs\#/entry/data '
                 '--normalization 0')
                 % (dir, name, 
                    mask_file,
                    self.entry.nxfilename, self.entry.nxname, 
                    dir, name))

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
    def ds_max(self):
        return 2 * np.sin(self.polar_max*radians/2) / self.wavelength

    @property
    def unitcell(self):
        if self._unitcell is None or \
           not np.allclose(self._unitcell.lattice_parameters,
                           np.array(self.lattice_parameters)):
           self._unitcell = unitcell(self.lattice_parameters, self.centring)
        self._unitcell.makerings(self.ds_max)
        return self._unitcell

    @property
    def npks(self):
        try:
            return self.xp.size
        except:
            return 0

    @property
    def rings(self):
        return 2*np.arcsin(np.array(self.unitcell.ringds)*self.wavelength/2)*degrees

    @property
    def UBmat(self):
        """Determine the U matrix using the defined UB matrix and B matrix
        calculated from the lattice parameters
        """
        return self.Umat * self.Bmat

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
        return np.linalg.inv(self.Bimat)

    @property
    def Omat(self):
        """Define the transform that rotates detector axes into lab axes.

        The inverse transforms detector coords into lab coords.
        When all angles are zero,
            +X(det) = -y(lab), +Y(det) = +z(lab), and +Z(det) = -x(lab)
        """
        return np.matrix(((0,0,1), (0,1,0), (-1,0,0)))

    @property
    def Dmat(self):
        """Define the matrix, whose inverse physically orients the detector.

        It also transforms detector coords into lab coords.
        Operation order:    yaw -> pitch -> roll -> twotheta -> gonpitch
        """
        return np.linalg.inv(rotmat(3, self.yaw) *
                             rotmat(2, self.pitch) *
                             rotmat(1, self.roll) *
                             rotmat(3, self.twotheta) *
                             rotmat(2, self.gonpitch))

    def Gmat(self, omega):
        """Define the matrix that physically orients the goniometer head into place
    
        Its inverse transforms lab coords into head coords.
        """
        return (rotmat(3, self.phi) * rotmat(1, self.chi) * rotmat(3, omega) * 
                rotmat(2,self.gonpitch))

    @property
    def Cvec(self):
        return vec(self.xc, self.yc)

    def Dvec(self, omega):
        Svec = vec(0.0)
        return (self.Gmat(omega) * Svec - 
            (rotmat(2,self.gonpitch) * rotmat(3,self.twotheta) * vec(self.distance)))

    @property
    def Evec(self):
        return vec(1.0 / self.wavelength)

    def Gvec(self, x, y, z):
        omega = self.omega_start + self.omega_step * z
        v1 = vec(x, y)
        v2 = self.pixel_size * np.linalg.inv(self.Omat) * (v1 - self.Cvec)
        v3 = np.linalg.inv(self.Dmat) * v2 - self.Dvec(omega)
        return (np.linalg.inv(self.Gmat(omega)) * 
               (((v3/np.linalg.norm(v3)) / self.wavelength) - self.Evec))

    def set_polar_max(self, polar_max):
        try:
            if not isinstance(self.polar_angle, np.ndarray):
                self.polar_angle, self.azimuthal_angle = self.calculate_angles(self.xp, self.yp)
            self.x = []
            self.y = []
            for i in range(self.npks):
                if self.polar_angle[i] <= polar_max:
                    self.x.append(self.xp[i])
                    self.y.append(self.yp[i])
        except Exception:
            pass
        self.polar_max = polar_max

    def polar(self, x, y):
        Oimat = np.linalg.inv(self.Omat)
        Mat = self.pixel_size * np.linalg.inv(self.Dmat) * Oimat
        peak = Oimat * (vec(x, y) - self.Cvec)
        v = np.linalg.norm(Mat * peak)
        return np.arctan(v / self.distance) * degrees

    def calculate_angles(self, x, y):
        """Calculate the polar and azimuthal angles of the specified pixels"""
        Oimat = np.linalg.inv(self.Omat)
        Mat = self.pixel_size * np.linalg.inv(self.Dmat) * Oimat
        polar_angles = []
        azimuthal_angles = []
        for i in range(len(x)):
            peak = Oimat * (vec(x[i], y[i]) - self.Cvec)
            v = np.linalg.norm(Mat * peak)
            polar_angle = np.arctan(v / self.distance)
            polar_angles.append(polar_angle)
            azimuthal_angles.append(np.arctan2(-peak[1,0], peak[2,0]))
        return np.array(polar_angles)*degrees, np.array(azimuthal_angles)*degrees

    def calculate_rings(self, polar_max=None):
        """Calculate the polar angles of the Bragg peak rings"""
        if polar_max is None:
            polar_max = self.polar_max
        ds_max = 2 * np.sin(polar_max*radians/2) / self.wavelength
        dss = set(sorted([np.around(x[0],3) for x in self.unitcell.gethkls(ds_max)]))
        peaks = []
        for ds in dss:
            peaks.append(2*np.arcsin(self.wavelength*ds/2)*degrees)
        return sorted(peaks)

    def angle_peaks(self, i, j):
        """Calculate the angle (in degrees) between two peaks"""
        g1 = norm(self.Gvec(self.xp[i], self.yp[i], self.zp[i]))
        g2 = norm(self.Gvec(self.xp[j], self.yp[j], self.zp[j]))
        return np.around(np.arccos(float(g1.T*g2)) * degrees, 3)

    def angle_hkls(self, h1, h2):
        """Calculate the angle (in degrees) between two (hkl) tuples"""
        return self.unitcell.anglehkls(h1, h2)[0]
        
    def angle_rings(self, ring1, ring2):
        """Calculate the set of angles allowed between peaks in two rings"""
        return set(np.around(np.arccos(self.unitcell.getanglehkls(ring1, ring2)[1])
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
        peaks = [i for i in range(self.npks) if self.polar_angle[i] < self.polar_max]
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
        self.grains = sorted([NXgrain(grain) for grain in grains if len(grain) > 2])
        for grain in self.grains:
            self.orient(grain)
            grain.peaks = [i for i in range(self.npks) 
                           if self.diff(i) < self.hkl_tolerance]
            grain.score = self.score(grain)            
        
    def orient(self, grain=None):
        """Determine the UB matrix (optionally for the specified grain)"""
        if grain:
            for (i, j) in [(i,j) for i in grain.peaks for j in grain.peaks if j > i]:
                angle = self.angle_peaks(i, j)
                if abs(angle) > 20.0 and abs(angle-180.0) > 20.0:
                    break
            grain.primary, grain.secondary = i, j
            self.Umat = grain.Umat = self.get_UBmat(i, j) * self.Bimat
        else:
            self.Umat = self.get_UBmat(self.primary, self.secondary) * self.Bimat

    @property
    def idx(self):
        return list(np.where(self.diffs < self.hkl_tolerance)[0])

    def score(self, grain=None):
        diffs = self.diffs
        if grain:
            idx = grain.peaks
        else:
            idx = list(np.where(diffs < self.hkl_tolerance)[0])
        diffs = diffs[idx]
        weights = self.intensity[idx]
        return np.sum(weights * diffs) / np.sum(weights)

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
#            v6 = np.linalg.inv(self.Umat) * v5
#            v7 = np.linalg.inv(self.Bmat) * v6
            v7 = np.linalg.inv(self.UBmat) * v5
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

    @property
    def diffs(self):
        """Return the set of reciproal space differences for all the peaks"""
        return np.array([self.diff(i) for i in range(self.npks)])

    def diff(self, i):
        """Determine the reciprocal space difference between the calculated 
        (hkl) and the closest integer (hkl) of the specified peak"""
        h, k, l = self.hkl(i)
        Q = np.matrix((h, k, l)).T
        Q0 = np.matrix((np.rint(h), np.rint(k), np.rint(l))).T
        return np.linalg.norm(self.Bmat * (Q - Q0))

    def xyz(self, i):
        """Return the pixel coordinates of the specified peak"""
        return self.xp[i], self.yp[i], self.zp[i]

    def get_peaks(self, polar_max=None):
        """Return tuples containing the peaks and their respective parameters"""
        if polar_max is not None:
            peaks = np.array([i for i in range(self.npks) 
                              if self.polar_angle[i] < polar_max])
        else:
            peaks = np.arange(self.npks)
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
            diffs = self.diffs[peaks]
        else:
            h = k = l = diffs = np.zeros((peaks), dtype=np.float32)
        return zip(peaks, x, y, z, polar, azi, intensity, h, k, l, diffs)

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
#        less = list(np.where(self.polar_angle>self.rings[ring]-self.polar_tolerance)[0])
#        more = list(np.where(self.polar_angle<self.rings[ring]+self.polar_tolerance)[0])
#        return [idx for idx in less if idx in more]
#    def Gvs(self, polar_max=None):
#        if self.polar_max is None:
#            self.polar_max = polar_max
#        result = np.array([self.Gvec(self.xp[i], self.yp[i], self.zp[i]) 
#                         for i in self.idx])
#        result.shape = (len(self.idx),3)
#        return result

    def define_lattice_parameters(self):
        if self.symmetry == 'cubic':
            self.p = [self.a]
        elif self.symmetry == 'tetragonal':
            self.p = [self.a, self.c]
        else:
            self.p = [self.a, self.b, self.c]
        self.init_p = self.a, self.b, self.c

    def get_lattice_parameters(self, p):
        if self.symmetry == 'cubic':
            self.a = self.b = self.c = p[0]
        elif self.symmetry == 'tetragonal':
            self.a, self.c = p
            self.b = self.a
        else:
            self.a, self.b, self.c = p

    def refine_lattice_parameters(self, method='nelder-mead', **opts):
        self.define_lattice_parameters()
        p0 = np.array(self.p)
        result = minimize(self.lattice_residuals, p0, method='nelder-mead',
                          options={'xtol': 1e-5, 'disp': True})
        if result.success:
            self.get_lattice_parameters(result.x)

    def restore_lattice_parameters(self):
        self.a, self.b, self.c = self.init_p

    def lattice_residuals(self, p):
        self.get_lattice_parameters(p)
        polar_angles, _ = self.calculate_angles(self.x, self.y)
        rings = self.calculate_rings()
        residuals = np.array([find_nearest(rings, polar_angle) - polar_angle 
                              for polar_angle in polar_angles])
        return np.sum(residuals**2)

    def refine_orient_parameters(self, method='nelder-mead', **opts):
        idx = self.idx
        random.shuffle(idx)
        self.fit_idx = idx[0:20]
        p0 = np.ravel(self.Umat)
        self.fit_intensity = self.intensity[self.fit_idx]
        result = minimize(self.orient_residuals, p0, method=method,
                          options={'xtol': 1e-5, 'disp': True})
        if result.success:
            self.Umat = np.matrix(result.x).reshape(3,3)

    def orient_residuals(self, p):
        self.Umat = np.matrix(p).reshape(3,3)
        diffs = np.array([self.diff(i) for i in self.fit_idx])
        score = np.sum(diffs * self.fit_intensity)
        return score


class NXpeak(object):

    def __init__(self, x, y, z, intensity, 
                 polar_angle=None, azimuthal_angle=None, rotation_angle=None):
        self.x = x
        self.y = y
        self.z = z
        self.intensity = intensity
        self.polar_angle = polar_angle
        self.azimuthal_angle = azimuthal_angle
        self.rotation_angle = rotation_angle
        self.ring = None
        self.H = None
        self.K = None
        self.L = None
        self.Umat = None

    def __repr__(self):
        return "NXpeak(x=%.2f y=%.2f z=%.2f)" % (self.x, self.y, self.z)


class NXgrain(object):

    def __init__(self, peaks, Umat=None, primary=None, secondary=None):
        self.peaks = sorted(list(set(sorted(peaks))))
        self.primary = primary
        self.secondary = secondary
        self.Umat = Umat
        self.score = 0

    def __repr__(self):
        return "NXgrain(%s)" % self.peaks

    def __cmp__(self, other):
        if len(self.peaks) == len(other.peaks):
            return 0
        if len(self.peaks) < len(other.peaks):
            return 1
        if len(self.peaks) > len(other.peaks):
            return -1

    def __contains__(self, peak):
        return peak in self.peaks

    def __len__(self):
        return len(self.peaks)

