# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os

import numpy as np
from nexusformat.nexus import (NeXusError, NXdata, NXdetector, NXfield,
                               NXgoniometer, NXinstrument, NXlink,
                               NXmonochromator, NXsample)
from numpy.linalg import inv, norm
from scipy import optimize

degrees = 180.0 / np.pi
radians = np.pi / 180.0


def find_nearest(array, value):
    """Return array value closest to the requested value."""
    idx = (np.abs(array-value)).argmin()
    return array[idx]


def rotmat(axis, angle):
    """Return a rotation matrix for rotation about the specified axis.

    Parameters
    ----------
    axis : {1, 2, 3}
        Index of the rotation axis.
    angle : float
        Angle of rotation in degrees.

    Returns
    -------
    np.matrix
        The 3x3 rotation matrix
    """
    mat = np.eye(3)
    if angle is None or np.isclose(angle, 0.0):
        return mat
    cang = np.cos(angle*radians)
    sang = np.sin(angle*radians)
    if axis == 1:
        mat = np.array(((1, 0, 0), (0, cang, -sang), (0, sang, cang)))
    elif axis == 2:
        mat = np.array(((cang, 0, sang), (0, 1, 0), (-sang, 0, cang)))
    else:
        mat = np.array(((cang, -sang, 0), (sang, cang, 0), (0, 0, 1)))
    return np.matrix(mat)


def vec(x, y=0.0, z=0.0):
    """Return a 1x3 column vector."""
    return np.matrix((x, y, z)).T


def norm_vec(vec):
    """Return a normalized column vector."""
    return vec / norm(vec)


class NXRefine(object):
    """Crystallographic parameters and methods for single crystal diffraction.

    The parameters are loaded from a NeXus file containing data collected on a
    fast area detector by rotating a single crystal in a monochromatic x-ray
    beam. Each entry in the NeXus file corresponds to a complete 360° rotation,
    and includes a group with the pixel and frame indices of all the Bragg
    peaks identified by the experimental workflow. These peaks are used to
    refine an orientation matrix that depends on the goniometer angles and
    detector orientation defined with respect to the incident beam using a
    scheme defined by Branton Campbell to transform from the experimental
    frame of coordinates to the crystal's reciprocal lattice.

    Functions are provided to derive nominal Bragg peak indices and two-theta
    angles for the defined space group using CCTBX, to define the orientation
    matrix using the Busing and Levy method, and to refine the matrix and
    experimental parameters using the measured Bragg peak positions. Parameters
    are updated in the NeXus file and a settings file is created to be used in
    coordinate transformations from instrumental coordinates to reciprocal
    lattice coordinates, using the CCTW software package
    (https://sourceforge.net/projects/cctw/).

    Parameters
    ----------
    node : NXobject
        NeXus object within the NXentry group containing the experimental
        data and parameters.

    Attributes
    ----------
    a, b, c : float
        Lattice parameters defining the crystallographic unit cell in Å.
    alpha, beta, gamma : float
        Unit cell angles in degrees.
    wavelength : float
        Wavelength of the incident x-ray beam in Å.
    distance : float
        Distance from the sample to the detector in mm.
    yaw, pitch, roll : float
        Yaw, pitch and roll of the area detector in degrees.
    twotheta : float
        Angle of rotation of the detector with respect to the incident beam
        in degrees. This is normally set to 0.
    gonpitch, omega, chi : float
        Goniometer pitch, omega, and chi angles of the sample goniometer
        in degrees.
    phi : array_like
        Phi angles of each measured frame.
    phi_step : float
        Step size of phi angle rotations in degrees.
    xc, yc : float
        Location of the incident beam on the detector in pixel coordinates.
    xd, yd : float
        Translation of the detector along the x and y directions in mm.
    frame_time : float
        Exposure time of each frame in seconds.
    space_group : str
        Crystallographic space group.
    laue_group : str
        Crystallographic Laue group.
    symmetry : str
        Crystallographic symmetry or crystal-class system.
    centring : str
        Lattice centring of the crystallographic space group.
    """

    symmetries = ['cubic', 'tetragonal', 'orthorhombic', 'hexagonal',
                  'monoclinic', 'triclinic']
    """Valid crystal symmetris or families."""
    laue_groups = ['-1', '2/m', 'mmm', '4/m', '4/mmm', '-3', '-3m',
                   '6/m', '6/mmm', 'm-3', 'm-3m']
    """Valid Laue groups."""
    centrings = ['P', 'A', 'B', 'C', 'I', 'F', 'R']
    """Valid lattice centrings."""
    space_groups = {'P': 'P1', 'A': 'Amm2', 'B': 'P1', 'C': 'C121',
                    'I': 'I222', 'F': 'F222', 'R': 'R3'}
    """Space groups with minimal systematic absences for each centring."""

    def __init__(self, node=None):
        if node is not None:
            self.entry = node.nxentry
            if 'data' in self.entry:
                self.data = self.entry['data']
            else:
                self.data = None
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
        self.space_group = ''
        self.laue_group = ''
        self.symmetry = 'triclinic'
        self.centring = 'P'
        self.peaks = None
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
        self.polar_tolerance = 0.1
        self.peak_tolerance = 5.0
        self.hkl_tolerance = 0.05
        self.output_chunks = None
        self.grid_origin = None
        self.grid_basis = None
        self.grid_shape = None
        self.grid_step = None
        self.standard = True

        self.name = ""
        self._idx = None
        self._Dmat_cache = inv(rotmat(1, self.roll) * rotmat(2, self.pitch) *
                               rotmat(3, self.yaw))
        self._Gmat_cache = (rotmat(2, self.gonpitch) * rotmat(3, self.omega) *
                            rotmat(1, self.chi))
        self._julia = None

        self.parameters = None

        if self.entry is not None:
            self.read_parameters()

    def __repr__(self):
        return "NXRefine('" + self.name + "')"

    def read_parameter(self, path, default=None, attr=None):
        """Read the experimental parameter stored at the specfied path.

        If the attr keyword argument is present, the value of the
        specified attribute of the object is returned instead.

        Parameters
        ----------
        path : str
            Path to the parameter relative to the entry group.
        default : float, optional
            Default value of the parameter if the path does not exist,
            by default None.
        attr : str, optional
            Name of attribute, by default None.

        Returns
        -------
        float
            Value of the parameter or attribute.

        Notes
        -----
        The sample groups of each entry are linked to the sample group
        stored in `root[entry]`, so sample parameters are all read from
        `root[entry/sample]`.
        """
        try:
            if path.startswith('sample'):
                entry = self.entry.nxroot['entry']
            else:
                entry = self.entry
            if attr:
                return entry[path].attrs[attr]
            else:
                return entry[path].nxvalue
        except NeXusError:
            return default

    def read_parameters(self, entry=None):
        """Read all the experimental parameters stored in the NeXus file.

        Parameters
        ----------
        entry : NXentry, optional
            Group to be read, if different from `self.entry`, by default None
        """
        if entry:
            self.entry = entry
        with self.entry.nxfile:
            self.name = self.entry.nxroot.nxname + "/" + self.entry.nxname
            self.a = self.read_parameter('sample/unitcell_a', self.a)
            self.b = self.read_parameter('sample/unitcell_b', self.b)
            self.c = self.read_parameter('sample/unitcell_c', self.c)
            self.alpha = self.read_parameter(
                'sample/unitcell_alpha', self.alpha)
            self.beta = self.read_parameter('sample/unitcell_beta', self.beta)
            self.gamma = self.read_parameter(
                'sample/unitcell_gamma', self.gamma)
            self.space_group = self.read_parameter(
                'sample/space_group', self.space_group)
            self.laue_group = self.read_parameter(
                'sample/laue_group', self.laue_group)
            self.wavelength = self.read_parameter(
                'instrument/monochromator/wavelength', self.wavelength)
            self.distance = self.read_parameter('instrument/detector/distance',
                                                self.distance)
            self.yaw = self.read_parameter('instrument/detector/yaw', self.yaw)
            self.pitch = self.read_parameter('instrument/detector/pitch',
                                             self.pitch)
            self.roll = self.read_parameter(
                'instrument/detector/roll', self.roll)
            self.xc = self.read_parameter('instrument/detector/beam_center_x',
                                          self.xc)
            self.yc = self.read_parameter('instrument/detector/beam_center_y',
                                          self.yc)
            self.xd = self.read_parameter('instrument/detector/translation_x',
                                          self.xd)
            self.yd = self.read_parameter('instrument/detector/translation_y',
                                          self.yd)
            self.frame_time = self.read_parameter(
                'instrument/detector/frame_time', self.frame_time)
            self.shape = self.read_parameter(
                'instrument/detector/shape', self.shape)
            phi = self.read_parameter('instrument/goniometer/phi', self.phi)
            if isinstance(phi, np.ndarray) and len(phi) > 1:
                self.phi = phi[0]
                self.phi_step = phi[1] - phi[0]
            else:
                self.phi = phi
                try:
                    self.phi_step = self.read_parameter(
                        'instrument/goniometer/phi', self.phi, attr='step')
                except Exception:
                    pass
            self.chi = self.read_parameter(
                'instrument/goniometer/chi', self.chi)
            self.omega = self.read_parameter('instrument/goniometer/omega',
                                             self.omega)
            self.twotheta = self.read_parameter(
                'instrument/goniometer/two_theta', self.twotheta)
            self.gonpitch = self.read_parameter(
                'instrument/goniometer/goniometer_pitch', self.gonpitch)
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
            self.pixel_size = self.read_parameter(
                'instrument/detector/pixel_size', self.pixel_size)
            self.pixel_mask = self.read_parameter(
                'instrument/detector/pixel_mask')
            self.pixel_mask_applied = self.read_parameter(
                'instrument/detector/pixel_mask_applied')
            self.rotation_angle = self.read_parameter('peaks/rotation_angle')
            self.primary = self.read_parameter('peaks/primary_reflection')
            self.secondary = self.read_parameter('peaks/secondary_reflection')
            self.Umat = self.read_parameter(
                'instrument/detector/orientation_matrix')
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
            self.initialize_peaks()

    def write_parameter(self, path, value, attr=None):
        """Write a value to the NeXus object defined by its path.

        If the `attr` keyword argument is present, the value of the
        specified attribute of the object is returned instead.

        Parameters
        ----------
        path : str
            Path to the parameter relative to the entry group.
        value : float
            Value of the parameter.
        attr : str, optional
            Name of attribute, by default None
        """
        if path.startswith('sample'):
            entry = self.entry.nxroot['entry']
        else:
            entry = self.entry
        if value is not None:
            if attr and path in entry:
                entry[path].attrs[attr] = value
            elif path in entry:
                entry[path].replace(value)
            elif attr is None:
                entry[path] = value

    def write_parameters(self, entry=None, sample=False):
        """Write the stored experimental parameters to the NeXus file.

        Parameters
        ----------
        entry : NXentry, optional
            Group to write to, if different from `self.entry`, by default None.
        sample : bool, optional
            True if only the sample parameters are to be written,
            by default False.
        """
        if entry:
            self.entry = entry
        with self.entry.nxfile:
            if 'sample' not in self.entry:
                self.entry['sample'] = NXsample()
            self.write_parameter('sample/space_group', self.space_group)
            self.write_parameter('sample/laue_group', self.laue_group)
            self.write_parameter('sample/unit_cell_group', self.symmetry)
            self.write_parameter('sample/lattice_centring', self.centring)
            self.write_parameter('sample/unitcell_a', self.a)
            self.write_parameter('sample/unitcell_b', self.b)
            self.write_parameter('sample/unitcell_c', self.c)
            self.write_parameter('sample/unitcell_alpha', self.alpha)
            self.write_parameter('sample/unitcell_beta', self.beta)
            self.write_parameter('sample/unitcell_gamma', self.gamma)
            if sample:
                return
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
            self.write_parameter(
                'instrument/detector/pixel_size', self.pixel_size)
            self.write_parameter(
                'instrument/detector/pixel_mask', self.pixel_mask)
            self.write_parameter('instrument/detector/pixel_mask_applied',
                                 self.pixel_mask_applied)
            self.write_parameter('instrument/detector/translation_x', self.xd)
            self.write_parameter('instrument/detector/translation_y', self.yd)
            self.write_parameter(
                'instrument/detector/frame_time', self.frame_time)
            if self.Umat is not None:
                self.write_parameter('instrument/detector/orientation_matrix',
                                     np.array(self.Umat))
            self.write_parameter('instrument/goniometer/phi', self.phi)
            self.write_parameter('instrument/goniometer/phi', self.phi_step,
                                 attr='step')
            self.write_parameter('instrument/goniometer/chi', self.chi)
            self.write_parameter('instrument/goniometer/omega', self.omega)
            self.write_parameter(
                'instrument/goniometer/two_theta', self.twotheta)
            self.write_parameter('instrument/goniometer/goniometer_pitch',
                                 self.gonpitch)
            self.write_parameter('peaks/primary_reflection', self.primary)
            self.write_parameter('peaks/secondary_reflection', self.secondary)
            if isinstance(self.z, np.ndarray):
                self.rotation_angle = self.phi + (self.phi_step * self.z)

    def copy_parameters(self, other, sample=False, instrument=False):
        """Copy the experimental parameters from another entry.

        Parameters
        ----------
        other : NXRefine
            NXRefine instance containing the other parameters.
        sample : bool, optional
            True if the sample parameters are to be copied, by default False.
        instrument : bool, optional
            True if the instrument parameters are to be copied,
            by default False.
        """
        with other.entry.nxfile:
            if sample:
                if 'sample' not in other.entry.nxroot['entry']:
                    other.entry.nxroot['entry/sample'] = NXsample()
                if 'sample' not in other.entry:
                    other.entry.makelink(other.entry.nxroot['entry/sample'])
                other.write_parameter('sample/space_group', self.space_group)
                other.write_parameter('sample/laue_group', self.laue_group)
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
                other.write_parameter(
                    'instrument/goniometer/phi', self.phi_step, attr='step')
                other.write_parameter('instrument/goniometer/chi', self.chi)
                other.write_parameter(
                    'instrument/goniometer/omega', self.omega)
                other.write_parameter(
                    'instrument/goniometer/two_theta', self.twotheta)
                other.write_parameter('instrument/goniometer/goniometer_pitch',
                                      self.gonpitch)
                other.write_parameter(
                    'instrument/detector/distance', self.distance)
                other.write_parameter('instrument/detector/yaw', self.yaw)
                other.write_parameter('instrument/detector/pitch', self.pitch)
                other.write_parameter('instrument/detector/roll', self.roll)
                other.write_parameter(
                    'instrument/detector/beam_center_x', self.xc)
                other.write_parameter(
                    'instrument/detector/beam_center_y', self.yc)
                other.write_parameter('instrument/detector/pixel_size',
                                      self.pixel_size)
                other.write_parameter('instrument/detector/pixel_mask',
                                      self.pixel_mask)
                other.write_parameter('instrument/detector/pixel_mask_applied',
                                      self.pixel_mask_applied)
                other.write_parameter(
                    'instrument/detector/translation_x', self.xd)
                other.write_parameter(
                    'instrument/detector/translation_y', self.yd)
                other.write_parameter('instrument/detector/frame_time',
                                      self.frame_time)
                if self.Umat is not None:
                    other.write_parameter(
                        'instrument/detector/orientation_matrix',
                        np.array(self.Umat))

    def link_sample(self, other):
        """Link the sample group of this entry to another entry.

        Parameters
        ----------
        other : NXRefine
            NXRefine instance defined by the other entry.
        """
        with other.entry.nxfile:
            if 'sample' in self.entry:
                if 'sample' in other.entry:
                    del other.entry['sample']
                other.entry.makelink(self.entry['sample'])

    def read_settings(self, settings_file):
        """Read the experimental parameters stored in a CCTW settings file.

        Parameters
        ----------
        settings_file : str
            File name of the settings file.
        """
        import configparser
        import itertools
        cfg = configparser.ConfigParser()
        filename = settings_file
        with open(filename) as fp:
            cfg.read_file(itertools.chain(['[global]'], fp), source=filename)
        d = {}
        for c in cfg.items('global'):
            try:
                d[c[0]] = eval(c[1].strip(';'))
            except Exception:
                pass
        self.distance = d['parameters.distance']
        self.a, self.b, self.c, alpha, beta, gamma = d['parameters.unitcell']
        self.alpha, self.beta, self.gamma = (
            alpha*degrees, beta*degrees, gamma*degrees)
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
        self.h_stop, self.k_stop, self.l_stop = [-v
                                                 for v in d
                                                 ['parameters.gridorigin']]
        hs, ks, ls = d['parameters.griddim']
        self.h_step, self.k_step, self.l_step = [1.0/hs, 1.0/ks, 1.0/ls]
        self.h_shape, self.k_shape, self.l_shape = d['outputdata.dimensions']

    def write_settings(self, settings_file):
        """Write experimental parameters to a CCTW settings file.

        Parameters
        ----------
        settings_file : str
            File name of the settings file.
        """
        lines = []
        lines.append(f'parameters.pixelSize = {self.pixel_size};')
        lines.append(f'parameters.wavelength = {self.wavelength};')
        lines.append(f'parameters.distance = {self.distance};')
        lines.append(f'parameters.unitCell = {list(self.lattice_settings)};')
        lines.append(f'parameters.ubMat = {str(self.UBmat.tolist())};')
        lines.append(f'parameters.oMat = {str(self.Omat.tolist())};')
        lines.append('parameters.oVec = [0,0,0];')
        lines.append(f'parameters.det0x = {self.xc};')
        lines.append(f'parameters.det0y = {self.yc};')
        lines.append('parameters.xTrans = [0,0,0];')
        lines.append(
            f'parameters.orientErrorDetPitch = {self.pitch * radians};')
        lines.append(f'parameters.orientErrorDetRoll = {self.roll * radians};')
        lines.append(f'parameters.orientErrorDetYaw = {self.yaw * radians};')
        lines.append(
            f'parameters.orientErrorGonPitch = {self.gonpitch * radians};')
        lines.append('parameters.twoThetaCorrection = 0;')
        lines.append(f'parameters.twoThetaNom = {self.twotheta * radians};')
        lines.append('parameters.omegaCorrection = 0;')
        lines.append(f'parameters.omegaNom = {self.omega * radians};')
        lines.append('parameters.chiCorrection = 0;')
        lines.append(f'parameters.chiNom = {self.chi * radians};')
        lines.append('parameters.phiCorrection = 0;')
        lines.append(f'parameters.phiNom = {self.phi * radians};')
        lines.append(f'parameters.phiStep = {self.phi_step * radians};')
        lines.append(f'parameters.gridOrigin = {self.grid_origin};')
        lines.append(f'parameters.gridBasis = {self.grid_basis};')
        lines.append(f'parameters.gridDim = {self.grid_step};')
        lines.append('parameters.gridOffset = [0,0,0];')
        lines.append('parameters.extraFlip = false;')
        lines.append('inputData.chunkSize = [32,32,32];')
        lines.append(f'outputData.dimensions = {list(self.grid_shape)};')
        lines.append('outputData.chunkSize = [32,32,32];')
        lines.append('outputData.compression = 0;')
        lines.append('outputData.hdfChunkSize = [32,32,32];')
        lines.append('transformer.transformOptions =  0;')
        lines.append('transformer.oversampleX = 1;')
        lines.append('transformer.oversampleY = 1;')
        lines.append('transformer.oversampleZ = 4;')
        with open(settings_file, 'w') as f:
            f.write('\n'.join(lines))

    def write_angles(self, polar_angles, azimuthal_angles):
        """Write the polar and azimuthal angles of the Bragg peaks.

        Parameters
        ----------
        polar_angles : array_like
            Polar angles of the Bragg peaks in degrees.
        azimuthal_angles : array_like
            Azimuthal angles of the Bragg peaks in degrees.
        """
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
        try:
            peaks = list(zip(self.xp,  self.yp, self.zp, self.intensity))
            self.peaks = dict(zip(range(len(peaks)),
                                  [NXPeak(*p) for p in peaks]))
        except Exception:
            self.peaks = None

    def stepsize(self, value):
        import math
        stepsizes = np.array([1, 2, 5, 10])
        digits = math.floor(math.log10(value))
        multiplier = 10**digits
        return find_nearest(stepsizes, value/multiplier) * multiplier

    def initialize_grid(self):
        """Initialize the parameters that define HKL grid."""
        if self.Qh is not None and self.Qk is not None and self.Ql is not None:
            self.h_start, self.h_step, self.h_stop = (
                self.Qh[0], self.Qh[1]-self.Qh[0], self.Qh[-1])
            self.k_start, self.k_step, self.k_stop = (
                self.Qk[0], self.Qk[1]-self.Qk[0], self.Qk[-1])
            self.l_start, self.l_step, self.l_stop = (
                self.Ql[0], self.Ql[1]-self.Ql[0], self.Ql[-1])
        else:

            def round(value):
                import math
                return math.ceil(np.round(value) / 2.) * 2

            self.h_stop = round(0.8 * self.Qmax / self.astar)
            h_range = np.round(2*self.h_stop)
            self.h_start = -self.h_stop
            self.h_step = self.stepsize(h_range/1000)
            self.k_stop = round(0.8 * self.Qmax / self.bstar)
            k_range = np.round(2*self.k_stop)
            self.k_start = -self.k_stop
            self.k_step = self.stepsize(k_range/1000)
            self.l_stop = round(0.8 * self.Qmax / self.cstar)
            l_range = np.round(2*self.l_stop)
            self.l_start = -self.l_stop
            self.l_step = self.stepsize(l_range/1000)
        self.define_grid()

    def define_grid(self):
        """Define the HKL grid for CCTW."""
        self.h_shape = int(
            np.round((self.h_stop - self.h_start) / self.h_step, 2)) + 1
        self.k_shape = int(
            np.round((self.k_stop - self.k_start) / self.k_step, 2)) + 1
        self.l_shape = int(
            np.round((self.l_stop - self.l_start) / self.l_step, 2)) + 1
        self.grid_origin = [self.h_start, self.k_start, self.l_start]
        self.grid_step = [int(np.rint(1.0/self.h_step)),
                          int(np.rint(1.0/self.k_step)),
                          int(np.rint(1.0/self.l_step))]
        self.grid_shape = [self.h_shape, self.k_shape, self.l_shape]
        self.grid_basis = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

    def prepare_transform(self, output_link, mask=False):
        """Prepare the NXdata group for containing the transformed data.

        Parameters
        ----------
        output_link : str
            File name of the external file to contain the transform.
        mask : bool, optional
            True if the NXdata group contains a masked transform,
            by default None.
        """
        command = self.cctw_command(mask)
        H = NXfield(
            np.linspace(self.h_start, self.h_stop, self.h_shape),
            name='Qh', scaling_factor=self.astar, long_name='H (r.l.u.)')
        K = NXfield(
            np.linspace(self.k_start, self.k_stop, self.k_shape),
            name='Qk', scaling_factor=self.bstar, long_name='K (r.l.u.)')
        L = NXfield(
            np.linspace(self.l_start, self.l_stop, self.l_shape),
            name='Ql', scaling_factor=self.cstar, long_name='L (r.l.u.)')
        if mask:
            transform = 'masked_transform'
        else:
            transform = 'transform'

        with self.entry.nxfile:
            if transform in self.entry:
                del self.entry[transform]

            self.entry[transform] = NXdata(NXlink(name='data',
                                           target='/entry/data/v',
                                           file=output_link), [L, K, H])
            self.entry[transform].attrs['angles'] = (self.gamma_star,
                                                     self.beta_star,
                                                     self.alpha_star)
            self.entry[transform+'/weights'] = NXlink(target='/entry/data/n',
                                                      file=output_link)
            self.entry[transform+'/command'] = command
            self.entry[transform].set_default()

    def cctw_command(self, mask=False):
        """Generate the shell command to run CCTW transform.

        Parameters
        ----------
        mask : bool, optional
            True if the transform contains masked data, by default False.

        Returns
        -------
        str
            Command string.
        """
        entry = self.entry.nxname
        if mask:
            name = entry + '_masked_transform'
        else:
            name = entry + '_transform'
        dir = os.path.dirname(self.entry['data'].nxsignal.nxfilename)
        filename = self.entry.nxfilename
        parfile = os.path.join(dir, entry+'_transform.pars')
        command = [f'cctw transform --script {parfile}']
        if 'pixel_mask' in self.entry['instrument/detector']:
            command.append(
                fr'--mask {filename}\#/{entry}/instrument/detector/pixel_mask')
        if mask and 'data_mask' in self.entry['data']:
            command.append(f'--mask3d {filename}\\#/{entry}/data/data_mask')
        if 'monitor_weight' in self.entry['data']:
            command.append(
                fr'--weights {filename}\#/{entry}/data/monitor_weight')
        command.append(fr'{filename}\#/{entry}/data/data')
        command.append(fr'--output {dir}/{name}.nxs\#/entry/data')
        command.append('--normalization 0')
        return ' '.join(command)

    def set_symmetry(self):
        """Use the crystal symmetry to constrain unit cell parameters."""
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
        """Guess the crystal symmetry from the unit cell parameters.

        Returns
        -------
        str
            Crystal symmetry.
        """
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

    def set_polar_max(self, polar_max):
        """Set the maximum polar angle to be used in calculations.

        Parameters
        ----------
        polar_max : float
            Maximum polar angle in degrees.
        """
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

    @property
    def lattice_parameters(self):
        """Lattice parameters with angles in degrees."""
        return self.a, self.b, self.c, self.alpha, self.beta, self.gamma

    @property
    def reciprocal_lattice_parameters(self):
        """Reciprocal lattice parameters."""
        rlp = list(self.unit_cell.reciprocal().parameters())
        rlp[0:3] = [2*np.pi*p for p in rlp[0:3]]
        return rlp

    @property
    def lattice_settings(self):
        """Lattice parameters with angles in radians."""
        return (self.a, self.b, self.c,
                self.alpha*radians, self.beta*radians, self.gamma*radians)

    @property
    def unit_cell(self):
        """CCTBX unit cell."""
        from cctbx import uctbx
        return uctbx.unit_cell(self.lattice_parameters)

    @property
    def reciprocal_cell(self):
        """CCTBX reciprocal unit cell."""
        return self.unit_cell.reciprocal()

    @property
    def astar(self):
        """Reciprocal lattice unit in inverse Å."""
        return self.reciprocal_lattice_parameters[0]

    @property
    def bstar(self):
        """Reciprocal lattice unit in inverse Å."""
        return self.reciprocal_lattice_parameters[1]

    @property
    def cstar(self):
        """Reciprocal lattice unit in inverse Å."""
        return self.reciprocal_lattice_parameters[2]

    @property
    def alpha_star(self):
        """Reciprocal lattice angle in degrees."""
        return self.reciprocal_lattice_parameters[3]

    @property
    def beta_star(self):
        """Reciprocal lattice angle in degrees."""
        return self.reciprocal_lattice_parameters[4]

    @property
    def gamma_star(self):
        """Reciprocal lattice angle in degrees."""
        return self.reciprocal_lattice_parameters[5]

    @property
    def sgi(self):
        """CCTBX space group information."""
        from cctbx import sgtbx
        if self.space_group == '':
            sg = self.space_groups[self.centring]
        else:
            sg = self.space_group
        return sgtbx.space_group_info(sg)

    @sgi.setter
    def sgi(self, value):
        from cctbx import sgtbx
        _sgi = sgtbx.space_group_info(value)
        self.space_group = _sgi.type().lookup_symbol()
        self.symmetry = _sgi.group().crystal_system().lower()
        self.laue_group = _sgi.group().laue_group_type()
        self.centring = self.space_group[0]

    @property
    def sgn(self):
        """Space group symbol."""
        return self.sgi.type().lookup_symbol()

    @property
    def sg(self):
        """CCTBX space group."""
        return self.sgi.group()

    @property
    def miller(self):
        """Set of allowed Miller indices."""
        from cctbx import crystal, miller
        d_min = self.wavelength / (2 * np.sin(self.polar_max*radians/2))
        return miller.build_set(crystal_symmetry=crystal.symmetry(
            space_group_symbol=self.sgn,
            unit_cell=self.lattice_parameters),
            anomalous_flag=False, d_min=d_min).sort()

    @property
    def indices(self):
        """Set of HKL indices allowed by the space group.

        Only a single index is returned when there are a number of
        symmetry-equivalent indices.
        """
        _indices = []
        for h in self.miller.indices():
            _indices.append(self.indices_hkl(*h)[0])
        return _indices

    def indices_hkl(self, H, K, L):
        """Return the symmetry-equivalent HKL indices."""
        from cctbx import miller
        _symm_equiv = miller.sym_equiv_indices(self.sg, (H, K, L))
        _indices = sorted([i.h() for i in _symm_equiv.indices()],
                          reverse=True)
        if len(_indices) < _symm_equiv.multiplicity(False):
            _indices = _indices + [(-hh, -kk, -ll)
                                   for (hh, kk, ll) in _indices]
        return _indices

    @property
    def two_thetas(self):
        """The two-theta angles for all the HKL indices."""
        return list(self.unit_cell.two_theta(self.miller.indices(),
                                             self.wavelength, deg=True))

    def two_theta_hkl(self, H, K, L):
        """Return the two-theta angle for the specified HKL values."""
        return self.unit_cell.two_theta((H, K, L), self.wavelength, deg=True)

    def two_theta_max(self):
        """Return the maximum two-theta measurable on the detector."""
        ym, xm = self.shape
        max_radius = np.sqrt(max(self.xc**2 + self.yc**2,
                                 (xm-self.xc)**2 + self.yc**2,
                                 self.xc**2 + (ym-self.yc**2),
                                 (xm-self.xc)**2 + (ym-self.yc)**2))
        return np.arcsin(
            max_radius * self.pixel_size / self.distance) * degrees

    def make_rings(self):
        """Generate the two-thetas and HKLs for each ring of Bragg peaks.

        Each ring contains the average two-theta value in degrees for all
        Bragg peaks that are within the polar angle tolerance, and all the
        symmetry-equivalent HKLs.

        Returns
        -------
        dict of lists
            Map of ring indices to lists containing their two-theta values
            and symmetry-equivalent HKLs.
        """
        _rings = {}
        _r = 0
        _indices = self.indices
        for i, polar_angle in enumerate(self.two_thetas):
            if i == 0:
                _rings[0] = [polar_angle, [self.indices_hkl(*_indices[i])]]
            elif polar_angle-_rings[_r][0] > self.polar_tolerance:
                _r += 1
                _rings[_r] = [polar_angle, [self.indices_hkl(*_indices[i])]]
            else:
                _rings[_r][1].append(self.indices_hkl(*_indices[i]))
                pa = wa = 0.0
                for j, hkl in enumerate(_rings[_r][1]):
                    pa += self.two_theta_hkl(*hkl[0]) * len(hkl)
                    wa += len(hkl)
                _rings[_r][0] = pa / wa
        return _rings

    def assign_rings(self):
        """Assign all the identified Bragg peaks to rings."""
        rings = self.make_rings()
        ring_angles = [rings[r][0] for r in rings]
        self.rp = np.zeros((self.npks), dtype=int)
        for i in range(self.npks):
            self.rp[i] = (np.abs(self.polar_angle[i] - ring_angles)).argmin()

    def get_ring_list(self):
        """Return the HKL indices for all the rings."""
        hkls = []
        _rings = self.make_rings()
        for r in _rings:
            hkls.append([_rings[r][1][i][0]
                         for i in range(len(_rings[r][1]))])
        return hkls

    @property
    def tilts(self):
        """Detector tilt angles in degrees."""
        return self.yaw, self.pitch, self.roll

    @property
    def centers(self):
        """Position of the incident beam in detector pixel coordinates."""
        return self.xc, self.yc

    @property
    def roll(self):
        """Detector roll angle in degrees."""
        return self._roll

    @roll.setter
    def roll(self, value):
        self._roll = value
        try:
            self._Dmat_cache = inv(rotmat(1, self.roll) *
                                   rotmat(2, self.pitch) *
                                   rotmat(3, self.yaw))

        except Exception:
            pass

    @property
    def pitch(self):
        """Detector pitch angle in degrees."""
        return self._pitch

    @pitch.setter
    def pitch(self, value):
        self._pitch = value
        try:
            self._Dmat_cache = inv(
                rotmat(1, self.roll) * rotmat(2, self.pitch) *
                rotmat(3, self.yaw))

        except Exception:
            pass

    @property
    def yaw(self):
        """Detector yaw angle in degrees."""
        return self._yaw

    @yaw.setter
    def yaw(self, value):
        self._yaw = value
        try:
            self._Dmat_cache = inv(
                rotmat(1, self.roll) * rotmat(2, self.pitch) *
                rotmat(3, self.yaw))

        except Exception:
            pass

    @property
    def chi(self):
        """Goniometer chi angle in degrees."""
        return self._chi

    @chi.setter
    def chi(self, value):
        self._chi = value
        try:
            self._Gmat_cache = (
                rotmat(2, self.gonpitch) * rotmat(3, self.omega) *
                rotmat(1, self.chi))
        except Exception:
            pass

    @property
    def omega(self):
        """Goniometer omega angle in degrees."""
        return self._omega

    @omega.setter
    def omega(self, value):
        self._omega = value
        try:
            self._Gmat_cache = (
                rotmat(2, self.gonpitch) * rotmat(3, self.omega) *
                rotmat(1, self.chi))
        except Exception:
            pass

    @property
    def gonpitch(self):
        """Goniometer pitch angle in degrees."""
        return self._gonpitch

    @gonpitch.setter
    def gonpitch(self, value):
        self._gonpitch = value
        try:
            self._Gmat_cache = (
                rotmat(2, self.gonpitch) * rotmat(3, self.omega) *
                rotmat(1, self.chi))
        except Exception:
            pass

    @property
    def phi_start(self):
        """Starting phi angle in degrees."""
        return self.phi

    @property
    def Qmax(self):
        """Maximum inverse d-spacing measured at the maximum polar angle."""
        return (4 * np.pi * np.sin(self.two_theta_max()*radians/2)
                / self.wavelength)

    def absent(self, H, K, L):
        """Return True if the HKL indices are systematically absent."""
        return self.sg.is_sys_absent((int(H), int(K), int(L)))

    @property
    def npks(self):
        """Number of identified Bragg peaks."""
        try:
            return self.xp.size
        except Exception:
            return 0

    @property
    def UBmat(self):
        """Return the UB matrix."""
        if self.Umat is not None:
            return self.Umat * self.Bmat
        else:
            return np.matrix(np.eye(3))

    @property
    def Bimat(self):
        """Return the inverse B matrix defined by the unit cell."""
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
        """Return the B matrix defined by the unit cell."""
        return inv(self.Bimat)

    @property
    def Omat(self):
        """Return the matrix that rotates detector axes into lab axes.

        When all angles are zero,
            +X(det) = -y(lab), +Y(det) = +z(lab), and +Z(det) = -x(lab)
        """
        if self.standard:
            return np.matrix(((0, -1, 0), (0, 0, 1), (-1, 0, 0)))
        else:
            return np.matrix(((0, 0, 1), (0, 1, 0), (-1, 0, 0)))

    @property
    def Dmat(self):
        """Return the detector orientatioon matrix.

        It also transforms detector coords into lab coordinates.
            Operation order:    yaw -> pitch -> roll
        """
        return self._Dmat_cache

    def Gmat(self, phi):
        """Return the matrix that physically orients the goniometer head.

        It performs the inverse transform of lab coords into head coords.
        """
        return self._Gmat_cache * rotmat(3, phi)

    @property
    def Cvec(self):
        """Return the vector from the sample to detector."""
        return vec(self.xc, self.yc)

    @property
    def Dvec(self):
        """Return the vector from the detector to the sample position."""
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
        self.Gvecs = [self.Gvec(x, y, z) for x, y, z
                      in zip(self.xp[idx], self.yp[idx], self.zp[idx])]
        return self.Gvecs

    def calculate_angles(self, x, y):
        """Return the polar and azimuthal angles of the specified pixels."""
        Oimat = inv(self.Omat)
        Mat = self.pixel_size * inv(self.Dmat) * Oimat
        polar_angles = []
        azimuthal_angles = []
        for i in range(len(x)):
            peak = Oimat * (vec(x[i], y[i]) - self.Cvec)
            v = norm(Mat * peak)
            polar_angle = np.arctan(v / self.distance)
            polar_angles.append(polar_angle)
            azimuthal_angles.append(np.arctan2(-peak[1, 0], peak[2, 0]))
        return (np.array(polar_angles) * degrees,
                np.array(azimuthal_angles) * degrees)

    def angle_peaks(self, i, j):
        """Return the angle between two peaks in degrees.

        Parameters
        ----------
        i, j : int
            Index of the two peaks.

        Returns
        -------
        float
            Angle between the two peaks.
        """
        g1 = norm_vec(self.Gvec(self.xp[i], self.yp[i], self.zp[i]))
        g2 = norm_vec(self.Gvec(self.xp[j], self.yp[j], self.zp[j]))
        return np.around(np.arccos(float(g1.T*g2)) * degrees, 3)

    def angle_hkls(self, h1, h2):
        """Return the angle in degrees between two HKL vectors.

        Parameters
        ----------
        h1, h2 : tuple of ints
            A tuple of the HKL vector indices.

        Returns
        -------
        float
            Angle between two HKL vectors.
        """
        h1v = norm_vec((vec(*h1).T * self.Bmat)).T
        h2v = norm_vec((vec(*h2).T * self.Bmat)).T
        return np.around(np.arccos(h1v.T*h2v)[0, 0] * degrees, 3)

    def unitarity(self):
        """Return the unitarity of the refined orientation matrix."""
        if self.Umat is not None:
            return np.matrix(self.Umat) * np.matrix(self.Umat.T)
        else:
            return None

    def get_UBmat(self, i, j, hi, hj):
        """Return the UBmatrix using the specified peaks.

        This is based on the algorithem described by Busing and Levy in
        Acta Crystallographica 22, 457 (1967). It is an implementation of
        equations (23) to (27).

        Parameters
        ----------
        i, j : int
            Indices of the two Bragg peaks
        hi, hj : tuple of ints
            HKL indices assigned to the respective Bragg peaks.

        Returns
        -------
        np.matrix
            UB matrix
        """
        h1c = (self.Bmat * vec(*hi)).T
        h2c = (self.Bmat * vec(*hj)).T

        t1c = norm_vec(h1c)
        t3c = norm_vec(np.cross(h1c, h2c))
        t2c = norm_vec(np.cross(h1c, t3c))
        Tc = np.concatenate((t1c, t2c, t3c)).T

        g1 = self.Gvec(self.xp[i], self.yp[i], self.zp[i]).T
        g2 = self.Gvec(self.xp[j], self.yp[j], self.zp[j]).T

        t1g = norm_vec(g1)
        t3g = norm_vec(np.cross(g1, g2))
        t2g = norm_vec(np.cross(g1, t3g))
        Tg = np.concatenate((t1g, t2g, t3g)).T

        return Tg * np.linalg.inv(Tc)

    def get_hkl(self, x, y, z):
        """Return the HKL indices for the specified pixel coordinates.

        Parameters
        ----------
        x, y, z : float
            Pixel coordinates

        Returns
        -------
        list
            HKL indices
        """
        if self.Umat is not None:
            v5 = self.Gvec(x, y, z)
#           v6 = inv(self.Umat) * v5
#           v7 = inv(self.Bmat) * v6
            v7 = inv(self.UBmat) * v5
            return list(np.array(v7.T)[0])
        else:
            return [0.0, 0.0, 0.0]

    def get_hkls(self):
        """Return the set of hkls for all the  Bragg peaks as three columns."""
        return zip(*[self.hkl(i) for i in range(self.npks)])

    @property
    def hkls(self):
        """The set of HKLs for all the Bragg peaks."""
        return [self.get_hkl(self.xp[i], self.yp[i], self.zp[i])
                for i in range(self.npks)]

    def hkl(self, i):
        """Return the calculated HKL indices for the specified peak."""
        return self.get_hkl(self.xp[i], self.yp[i], self.zp[i])

    def get_xyz(self, H, K, L):
        """Return a list of the pixel/frame indices for a set of HKL indices.

        Parameters
        ----------
        H, K, L : int
            HKL indices

        Returns
        -------
        list of NXPeaks
            List of NXPeaks containing the pixel/frame coordinates.
        """
        v7 = vec(H, K, L)
        v6 = self.Bmat * v7
        v5 = self.Umat * v6

        def ewald_condition(phi): return (
            norm(self.Evec)**2 - norm(self.Gmat(phi)*v5 + self.Evec)**2)

        phis = []
        if H == 0 and K == 0 and L == 0:
            pass
        elif optimize.fsolve(ewald_condition, 45.0, full_output=1)[2] == 1:
            phis = list(
                np.unique(
                    np.around(
                        [optimize.fsolve(ewald_condition, phi) % 360
                         for phi in np.arange(30, 390, 15)],
                        decimals=4)))

        def get_ij(phi):
            v4 = self.Gmat(phi) * v5
            p = norm_vec(v4 + self.Evec)
            v3 = -(self.Dvec[0, 0] / p[0, 0]) * p
            v2 = self.Dmat * (v3 + self.Dvec)
            v1 = (self.Omat * v2 / self.pixel_size) + self.Cvec
            return v1[0, 0], v1[1, 0]

        peaks = []
        for phi in phis:
            x, y = get_ij(phi)
            z = ((phi - self.phi_start) / self.phi_step) % 3600
            if z < 25:
                z = z + 3600
            elif z > 3625:
                z = z - 3600
            if x > 0 and x < self.shape[1] and y > 0 and y < self.shape[0]:
                peaks.append(NXPeak(x, y, z, H=H, K=K, L=L))

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
        Main.include(pkg_resources.resource_filename('nxrefine',
                                                     'julia/get_xyzs.jl'))
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
                H, K, L = p[3], p[4], p[5]
                if not self.absent(H, K, L):
                    peaks.append(NXPeak(*p[0:3], H=H, K=K, L=L))
            except Exception:
                pass
        return peaks

    def polar(self, i):
        """Return the polar angle in degrees for the specified Bragg peak."""
        Oimat = inv(self.Omat)
        Mat = self.pixel_size * inv(self.Dmat) * Oimat
        peak = Oimat * (vec(self.xp[i], self.yp[i]) - self.Cvec)
        v = norm(Mat * peak)
        return np.arctan(v / self.distance)

    def score(self):
        """Return the goodness of fit of the calculated peak positions."""
        self.set_idx()
        if self.idx:
            diffs = self.diffs()
            weights = self.weights
            return np.sum(weights * diffs) / np.sum(weights)
        else:
            return 0.0

    @property
    def idx(self):
        """List of peaks whose polar angles are less than the maximum."""
        if self._idx is None:
            self._idx = list(np.where(self.polar_angle < self.polar_max)[0])
        return self._idx

    def set_idx(self, hkl_tolerance=None):
        """Define the peaks whose positions are within the HKL tolerance."""
        if hkl_tolerance is None:
            hkl_tolerance = self.hkl_tolerance
        _idx = list(np.where(self.polar_angle < self.polar_max)[0])
        self._idx = [i for i in _idx if self.diff(i) < hkl_tolerance]

    @property
    def weights(self):
        """Peak weights defined by their intensity."""
        return np.array(self.intensity[self.idx])

    def diffs(self):
        """Return all the deviations from the calculated peak positions."""
        return np.array([self.diff(i) for i in self.idx])

    def diff(self, i):
        """Return the deviation from the calculated peak position.

        This is defined as the difference between the peak position and the
        closest HKL vector in reciprocal Å.

        Parameters
        ----------
        i : int
            Peak index

        Returns
        -------
        float
            [description]
        """
        H, K, L = self.hkl(i)
        Q = np.matrix((H, K, L)).T
        Q0 = np.matrix((np.rint(H), np.rint(K), np.rint(L))).T
        return norm(self.Bmat * (Q - Q0))

    def angle_diffs(self):
        """Return the set of polar angle differences for all the peaks"""
        return np.array([self.angle_diff(i) for i in self.idx])

    def angle_diff(self, i):
        """Return the deviation from the calculated peak position in degrees.

        Parameters
        ----------
        i : int
            Peak index.

        Returns
        -------
        float
            Difference in degrees.
        """
        (h0, k0, l0) = [int(np.rint(x)) for x in self.hkl(i)]
        polar0 = self.unit_cell.two_theta((h0, k0, l0), self.wavelength)
        return np.abs(self.polar(i) - polar0)

    def xyz(self, i):
        """Return the pixel coordinates of the specified peak."""
        return self.xp[i], self.yp[i], self.zp[i]

    def get_peaks(self):
        """Return tuples containing the peaks and their parameters."""
        peaks = np.array([i for i in range(self.npks)
                          if self.polar_angle[i] < self.polar_max])
        x, y, z = (np.rint(self.xp[peaks]).astype(np.int16),
                   np.rint(self.yp[peaks]).astype(np.int16),
                   np.rint(self.zp[peaks]).astype(np.int16))
        polar, azi = self.polar_angle[peaks], self.azimuthal_angle[peaks]
        intensity = self.intensity[peaks]
        if self.Umat is not None:
            H, K, L = self.get_hkls()
            H = np.array(H)[peaks]
            K = np.array(K)[peaks]
            L = np.array(L)[peaks]
            diffs = np.array([self.diff(i) for i in peaks])
        else:
            H = K = L = diffs = np.zeros(peaks.shape, dtype=float)
        return list(zip(peaks, x, y, z, polar, azi, intensity, H, K, L, diffs))

    def define_parameters(self, **opts):
        """Return LMFIT parameters defined by the keyword arguments.

        Returns
        -------
        lmfit.Parameters
            The set of parameters to be optimized by LMFIT.
        """
        from lmfit import Parameters
        self.parameters = Parameters()
        if 'lattice' in opts:
            self.define_lattice_parameters()
            del opts['lattice']
        for opt in opts:
            self.parameters.add(opt, getattr(self, opt), vary=opts[opt])
        return self.parameters

    def define_lattice_parameters(self, lattice=True):
        """Define LMFIT parameters for refining lattice parameters.

        The added parameters depend on the crystal symmetry.

        Parameters
        ----------
        lattice : bool, optional
            True if the lattice parameters ar to be varied, by default True.
        """
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
        """Update the NXRefine attributes using the LMFIT Parameters.

        Parameters
        ----------
        parameters : lmfit.Parameters
            The set of parameters optimized by LMFIT.
        """
        for p in parameters:
            setattr(self, p, parameters[p].value)
        self.set_symmetry()

    def restore_parameters(self):
        """Restore the NXRefine attributes to the values before refinement."""
        for p in self.parameters:
            setattr(self, p, self.parameters[p].init_value)
        self.set_symmetry()

    def refine_hkls(self, method='leastsq', **opts):
        """Refine parameters based on the calculated HKL values.

        The parameters to be refined are defined by the keyword arguments,
        which are typically set using the Refine Lattice plugin.

        Parameters
        ----------
        method : str, optional
            LMFIT minimizer method, by default 'leastsq'
        """
        self.set_idx()
        from lmfit import fit_report, minimize
        if self.Umat is None:
            raise NeXusError('No orientation matrix defined')
        p0 = self.define_parameters(**opts)
        if len(p0) == 0:
            raise NeXusError('No parameters selected for refinement')
        self.result = minimize(self.hkl_residuals, p0, method=method)
        self.fit_report = fit_report(self.result)
        if self.result.success:
            self.get_parameters(self.result.params)

    def hkl_residuals(self, parameters):
        """Return the residuals of the calculated HKL values.

        Parameters
        ----------
        parameters : lmfit.Parameters
            The set of parameters to be optimized by LMFIT.

        Returns
        -------
        array_like
            An array of differences between calculated and nominal HKL values.
        """
        self.get_parameters(parameters)
        return self.diffs()

    def refine_angles(self, method='nelder', **opts):
        """Refine parameters based on the calculated polar angles.

        Parameters
        ----------
        method : str, optional
            LMFIT minimizer method, by default 'nelder'
        """
        self.set_idx()
        from lmfit import fit_report, minimize
        p0 = self.define_parameters(lattice=True, **opts)
        self.result = minimize(self.angle_residuals, p0, method=method)
        self.fit_report = fit_report(self.result)
        if self.result.success:
            self.get_parameters(self.result.params)

    def angle_residuals(self, parameters):
        """Return the residuals of the calculated polar angles.

        Parameters
        ----------
        parameters : lmfit.Parameters
            The set of parameters to be optimized by LMFIT.

        Returns
        -------
        array_like
            An array of differences between calculated and nominal polar
            angles.
        """
        self.get_parameters(parameters)
        return self.angle_diffs()

    def define_orientation_matrix(self):
        """Return the elements of the orientation matrix as LMFIT parameters.

        Returns
        -------
        lmfit.Parameters
            The set of parameters to be optimized by LMFIT.

        Notes
        -----
        This is usually run after optimizing all the other crystallographic
        and experimental parameters. This fit will break the unitarity of the
        orientation matrix, but it is usually minor, and can be checked with
        the `unitarity` function.
        """
        from lmfit import Parameters
        p = Parameters()
        for i in range(3):
            for j in range(3):
                p.add('U%d%d' % (i, j), self.Umat[i, j])
        self.init_p = self.Umat
        return p

    def get_orientation_matrix(self, p):
        """Update the orientation matrix using the LMFIT Parameters.

        Parameters
        ----------
        parameters : lmfit.Parameters
            The set of parameters optimized by LMFIT.
        """
        for i in range(3):
            for j in range(3):
                self.Umat[i, j] = p['U%d%d' % (i, j)].value

    def refine_orientation_matrix(self, method='leastsq'):
        """Refine the orientatoin matrix based on the calculated HKL values.

        Parameters
        ----------
        method : str, optional
            LMFIT minimizer method, by default 'leastsq'
        """
        self.set_idx()
        from lmfit import fit_report, minimize
        p0 = self.define_orientation_matrix()
        self.result = minimize(self.orient_residuals, p0, method=method)
        self.fit_report = fit_report(self.result)
        if self.result.success:
            self.get_orientation_matrix(self.result.params)

    def restore_orientation_matrix(self):
        """Restore the orientation matrix to the values before refinement."""
        self.Umat = self.init_p

    def orient_residuals(self, p):
        """Return the residuals of the calculated HKL values.

        Parameters
        ----------
        parameters : lmfit.Parameters
            The set of parameters to be optimized by LMFIT.

        Returns
        -------
        array_like
            An array of differences between calculated and nominal HKL values.
        """
        self.get_orientation_matrix(p)
        return self.diffs()

    def get_polarization(self, beam_polarization=0.99):
        """Return the synchrotron x-ray polarization across the detector.

        Parameters
        ----------
        beam_polarization : float, optional
            [description], by default 0.99

        Returns
        -------
        array_like
            A 2D array of the polarization correction for the detector pixels.
        """
        if 'polarization' in self.entry['instrument/detector']:
            return self.entry['instrument/detector/polarization'].nxvalue
        elif 'calibration' in self.entry['instrument']:
            from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
            parameters = (
                self.entry['instrument/calibration/refinement/parameters'])
            ai = AzimuthalIntegrator(
                dist=parameters['Distance'].nxvalue,
                poni1=parameters['Poni1'].nxvalue,
                poni2=parameters['Poni2'].nxvalue,
                rot1=parameters['Rot1'].nxvalue,
                rot2=parameters['Rot2'].nxvalue,
                rot3=parameters['Rot3'].nxvalue,
                pixel1=parameters['PixelSize1'].nxvalue,
                pixel2=parameters['PixelSize2'].nxvalue,
                wavelength=parameters['Wavelength'].nxvalue)
            return ai.polarization(shape=self.shape, factor=beam_polarization)
        else:
            return 1


class NXPeak(object):
    """Parameters defining Bragg peaks identified in the data volumes.

    Parameters
    ----------
    x, y : float
        Pixel numbers of the optimized peak position
    z : float
        Frame number of the peak position
    intensity : float, optional
        Peak intensity, by default None
    pixel_count : int, optional
        Maximum counts in the peak, by default None
    H, K, L : float, optional
        HKL indices of the peak, by default None
    radius : float, optional
        Mask radius, by default None
    polar_angle : float, optional
        Peak polar angle, by default None
    azimuthal_angle : float, optional
        Peak azimuthal angle, by default None
    rotation_angle : float, optional
        Peak rotation angle, by default None
    """

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
        return f"NXPeak(x={self.x:.2f}, y={self.y:.2f}, z={self.z:.2f})"
