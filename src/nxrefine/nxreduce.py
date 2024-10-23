# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import logging
import logging.handlers
import operator
import os
import platform
import shutil
import subprocess
import timeit

import h5py as h5
import numpy as np
import scipy.fft
from h5py import is_hdf5
from nexusformat.nexus import (NeXusError, NXcollection, NXdata, NXentry,
                               NXfield, NXlink, NXLock, NXnote, NXparameters,
                               NXprocess, NXreflections, NXroot, nxgetconfig,
                               nxopen, nxsetconfig)
from qtpy import QtCore

from . import __version__
from .nxbeamline import get_beamline
from .nxdatabase import NXDatabase
from .nxrefine import NXRefine
from .nxserver import NXServer
from .nxsettings import NXSettings
from .nxsymmetry import NXSymmetry
from .nxutils import init_julia, load_julia, mask_volume, peak_search


class NXReduce(QtCore.QObject):
    """Data reduction workflow for single crystal diffuse x-ray scattering.

    All the components of the workflow required to reduce data from single
    crystals measured with high-energy synchrotron x-rays on a fast-area
    detector are defined as separate functions that start with 'nx'. The class
    is instantiated by the entry in the experimental NeXus file corresponding
    to a single 360° rotation of the crystal.

        Parameters
        ----------
        entry : NXentry or str, optional
            Entry containing the rotation scan, by default None
        directory : str, optional
            Path to the directory containing the raw data, by default None
        parent : str, optional
            File path to the parent NeXus file, by default None
        entries : list of str, optional
            List of all the rotation scan entries in the file, by default None
        threshold : float, optional
            Threshold used to in Bragg peak searches, by default None
        min_pixels : int, optional
            Minimum number of pixels required in Bragg peak searches, by
            default 10
        first : int, optional
            First frame included in the data reduction, by default None
        last : int, optional
            Last frame included in the data reduction, by default None
        polar_max : float, optional
            Maximum polar angle in peak refinements, by default None
        hkl_tolerance : float, optional
            Q-tolerance in Å-1 for including a peak in a refinement,
            by default None
        monitor : str, optional
            Name of monitor used in normalizations, by default None
        norm : float, optional
            Value used to normalize monitor counts, by default None
        polarization : float, optional
            Value of beam polarization, by default None
        qmin : float, optional
            Minimum Q used in calculating transmissions, by default None
        qmax : float, optional
            Maximum Q used in PDF taper function, by default None
        radius : float, optional
            Radius used in punching holes in inverse Angstroms, by default None
        mask_parameters : dict, optional
            Thresholds and convolution sizes used to prepare 3D masks, by
            default None.
        Qh : tuple of floats, optional
            Minimum, step size, and maximum value of Qh array, by default None
        Qk : tuple of floats, optional
            Minimum, step size, and maximum value of Qk array, by default None
        Ql : tuple of floats, optional
            Minimum, step size, and maximum value of Ql array, by default None
        load : bool, optional
            Load raw data files, by default False
        link : bool, optional
            Link metadata, by default False
        copy : bool, optional
            Copy refinement and transform parameters, by default False
        maxcount : bool, optional
            Determine maximum counts, by default False
        find : bool, optional
            Find Bragg peaks, by default False
        refine : bool, optional
            Refine lattice parameters and orientation matrix, by default False
        prepare : bool, optional
            Prepare the 3D data mask, by default False
        transform : bool, optional
            Transform the data into Q, by default False
        combine: bool, optional
            Combine transformed data
        pdf: bool, optional
            Create PDF transforms
        lattice : bool, optional
            Refine the lattice parameters, by default False
        mask : bool, optional
            Use mask in performing transforms, by default False
        overwrite : bool, optional
            Overwrite previous analyses, by default False
        monitor_progress : bool, optional
            Monitor progress at the command line, by default False
        gui : bool, optional
            Use PyQt signals to monitor progress, by default False
        server : NXServer
            NXServer instance if available, by default None
        """

    def __init__(
            self, entry=None, directory=None, parent=None, entries=None,
            threshold=None, min_pixels=None, first=None, last=None,
            polar_max=None, hkl_tolerance=None, monitor=None, norm=None,
            polarization=None, qmin=None, qmax=None,
            radius=None, mask_parameters=None,
            Qh=None, Qk=None, Ql=None,
            load=False, link=False, copy=False,
            maxcount=False, find=False, refine=False, prepare=False,
            transform=False, combine=False, pdf=False,
            lattice=False, regular=False, mask=False, overwrite=False,
            monitor_progress=False, gui=False, server=None):

        super(NXReduce, self).__init__()

        if isinstance(entry, NXentry):
            self.entry_name = entry.nxname
            self.wrapper_file = entry.nxfilename
            self.sample = os.path.basename(
                os.path.dirname(
                    os.path.dirname(self.wrapper_file)))
            self.label = os.path.basename(os.path.dirname(self.wrapper_file))
            base_name = os.path.basename(
                os.path.splitext(self.wrapper_file)[0])
            self.scan = base_name.replace(self.sample+'_', '')
            self.directory = os.path.realpath(
                os.path.join(
                    os.path.dirname(self.wrapper_file), self.scan))
            self.root_directory = os.path.realpath(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(self.directory))))
            self._root = entry.nxroot
        elif directory is None:
            raise NeXusError('Directory not specified')
        else:
            self.directory = os.path.realpath(directory.rstrip('/'))
            self.root_directory = os.path.dirname(
                os.path.dirname(
                    os.path.dirname(self.directory)))
            self.sample = os.path.basename(
                os.path.dirname(
                    os.path.dirname(self.directory)))
            self.label = os.path.basename(os.path.dirname(self.directory))
            self.scan = os.path.basename(self.directory)
            self.wrapper_file = os.path.join(self.root_directory,
                                             self.sample, self.label,
                                             f"{self.sample}_{self.scan}.nxs")
            if entry is None:
                self.entry_name = 'entry'
            else:
                self.entry_name = entry
            self._root = None
        self.name = f"{self.sample}_{self.scan}/{self.entry_name}"
        self.base_directory = os.path.dirname(self.wrapper_file)

        self._settings = None
        self._beamline = None
        self._field = None
        self._shape = None
        self._pixel_mask = None
        self._parent = parent
        self._parent_root = None
        self._parent_entry = None
        self._entries = entries
        self._mode = 'r'

        self._threshold = threshold
        self._min_pixels = min_pixels
        self._first = first
        self._last = last
        self._polar_max = polar_max
        self._hkl_tolerance = hkl_tolerance
        self._monitor = monitor
        self._norm = norm
        self._polarization = polarization
        self._qmin = qmin
        self._qmax = qmax
        self._radius = radius
        if mask_parameters is None:
            self.mask_parameters = {
                'threshold_1': 2, 'horizontal_size_1': 11,
                'threshold_2': 0.8, 'horizontal_size_2': 51}
        else:
            self.mask_parameters = mask_parameters

        self._maximum = None
        self.summed_data = None
        self.Qh = Qh
        self.Qk = Qk
        self.Ql = Ql

        self.load = load
        self.link = link
        self.copy = copy
        self.maxcount = maxcount
        self.find = find
        self.refine = refine
        self.lattice = lattice
        self.prepare = prepare
        self.transform = transform
        self.combine = combine
        self.pdf = pdf
        self.regular = regular
        self.mask = mask
        if not self.mask:
            self.regular = True
        self.overwrite = overwrite
        self.monitor_progress = monitor_progress
        self.gui = gui
        self._server = server
        self.server_settings = NXSettings().settings['server']
        self.log_file = os.path.join(self.task_directory, 'nxlogger.log')

        self.timer = {}

        self.summed_frames = None
        self.partial_frames = None
        self.summed_data = None

        self._stopped = False
        self._process_count = None

        self._default = None
        self._db = None
        self._logger = None
        self._concurrent = None
        self._cctw = None

        nxsetconfig(lock=3600, lockexpiry=28800)

    start = QtCore.Signal(object)
    update = QtCore.Signal(object)
    result = QtCore.Signal(object)
    stop = QtCore.Signal()

    def __repr__(self):
        return f"NXReduce('{self.name}')"

    def __enter__(self):
        self._mode = self.root.nxfilemode
        self.root.reload()
        self.root.unlock()
        return self.root.__enter__()

    def __exit__(self, *args):
        self.root.__exit__()
        if self._mode == 'r':
            self.root.lock()

    @property
    def task_directory(self):
        """Directory containing log files and the reduction database."""
        _directory = os.path.join(self.root_directory, 'tasks')
        if not os.path.exists(_directory):
            os.mkdir(_directory)
        return _directory

    @property
    def logger(self):
        """Log file handler."""
        if self._logger is None:
            self._logger = logging.getLogger(
                f"{self.label}/{self.sample}_{self.scan}['{self.entry_name}']")
            self._logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                "%(asctime)s %(name)-12s: %(message)s",
                datefmt='%Y-%m-%d %H:%M:%S')
            for handler in self._logger.handlers:
                self._logger.removeHandler(handler)
            fileHandler = logging.FileHandler(self.log_file)
            fileHandler.setFormatter(formatter)
            self._logger.addHandler(fileHandler)
            if not self.gui:
                streamHandler = logging.StreamHandler()
                self._logger.addHandler(streamHandler)
        return self._logger

    def log(self, message):
        with NXLock(self.log_file, timeout=60, expiry=60):
            self.logger.info(message)

    @property
    def settings(self):
        if self._settings is None:
            self._settings = NXSettings(self.task_directory).settings
        return self._settings

    @property
    def default(self):
        """Dictionary containing default reduction parameters."""
        if self._default is None:
            try:
                self._default = self.settings['nxreduce']
            except Exception as error:
                self.log(str(error))
        return self._default

    @property
    def server(self):
        """Front-end to interface with the reduction workflow server."""
        if self._server is None:
            try:
                self._server = NXServer()
            except Exception as error:
                self.log(str(error))
        return self._server

    @property
    def db(self):
        """Database for recording the data reduction status."""
        if self._db is None:
            try:
                self._db = NXDatabase(os.path.join(self.task_directory,
                                                   'nxdatabase.db'))
            except Exception as error:
                self.log(str(error))
        return self._db

    @property
    def beamline(self):
        """NXBeamLine class for importing data and logs."""
        if self._beamline is None:
            instrument = self.settings['instrument']['instrument']
            self._beamline = get_beamline(instrument=instrument)(reduce=self)
        return self._beamline

    @property
    def root(self):
        """NXroot group containing the complete wrapper file tree."""
        if self._root is None:
            self._root = nxopen(self.wrapper_file, 'r')
        return self._root

    @property
    def entry(self):
        """NXentry group containing the current entry being reduced."""
        if self.entry_name in self.root:
            return self.root[self.entry_name]
        else:
            return None

    @property
    def entries(self):
        """List of entries in the wrapper file excluding 'entry'."""
        if self._entries:
            return self._entries
        else:
            entries = [entry for entry in self.root.entries
                       if entry[-1].isdigit()]
            try:
                f = self.db.get_file(self.wrapper_file)
                if len(f.get_entries()) != len(entries):
                    f.set_entries(entries)
                    self.db.session.commit()
            except Exception:
                pass
            return entries

    @property
    def first_entry(self):
        """NXentry group containing the first raw data scan.

        The lattice parameters are only refined for the first entry.
        """
        return self.root[self.entries[0]]

    def is_first_entry(self):
        """True if the current entry is the first in the file."""
        return self.entry_name == self.entries[0]

    @property
    def data(self):
        """NXdata group containing the raw data for the current entry."""
        if 'data' in self.entry:
            return self.entry['data']
        elif (self.entry_name == 'entry'
              and 'data' in self.root[self.entries[0]]):
            return self.root[self.entries[0]]['data']
        else:
            return None

    @property
    def field(self):
        """NXfield containing the raw data."""
        if self._field is None:
            self._field = self.data.nxsignal
        return self._field

    @property
    def shape(self):
        """Shape of the raw data."""
        if self._shape is None:
            if self.raw_data_exists():
                self._shape = self.field.shape
            else:
                try:
                    self._shape = tuple(
                        [axis.shape[0] for axis in self.entry['data'].nxaxes])
                except NeXusError:
                    self._shape = None
        return self._shape

    @property
    def nframes(self):
        """Number of frames stored in the raw data."""
        try:
            return self.entry['data/frame_number'].shape[0]
        except NeXusError:
            return self.shape[0]

    @property
    def raw_file(self):
        """Absolute file path to the externally linked raw data file."""
        return self.entry['data/data'].nxfilename

    @property
    def raw_path(self):
        """Path to the raw data in the externally linked raw data file."""
        return self.entry['data/data'].nxtarget

    def raw_data_exists(self):
        """True if the externally linked raw data file exists."""
        return is_hdf5(self.raw_file)

    @property
    def pixel_mask(self):
        """Detector pixel mask defined in the current entry."""
        if self._pixel_mask is None:
            try:
                self._pixel_mask = (
                    self.entry['instrument/detector/pixel_mask'].nxvalue)
            except Exception:
                self._pixel_mask = np.zeros((self.shape[1], self.shape[2]),
                                            dtype=np.int8)
        return self._pixel_mask

    @pixel_mask.setter
    def pixel_mask(self, value):
        self._pixel_mask = value

    @property
    def parent(self):
        """Wrapper file selected to be the parent.

        Data reduction parameters are copied from the parent unless they
        are explicitly set as keyword arguments when initializing the
        NXReduce instance.
        """
        if self._parent is None:
            if os.path.exists(self.parent_file) and not self.is_parent():
                self._parent = self.parent_file
            else:
                self._parent = None
        return self._parent

    @property
    def parent_root(self):
        """NXroot group of the parent file."""
        if self._parent_root is None and self.parent:
            self._parent_root = nxopen(self.parent, 'r')
        return self._parent_root

    @property
    def parent_entry(self):
        """NXentry group of the parent file."""
        if self._parent_entry is None and self.parent:
            self._parent_entry = self.parent_root[self.entry_name]
        return self._parent_entry

    @property
    def parent_file(self):
        """Absolute file path to the parent file."""
        return os.path.join(self.base_directory, self.sample+'_parent.nxs')

    def is_parent(self):
        """True if the current entry is in the selected parent."""
        if (os.path.exists(self.parent_file)
                and os.path.realpath(self.parent_file) == self.wrapper_file):
            return True
        else:
            return False

    def make_parent(self):
        """Set the current wrapper file as the parent."""
        if self.is_parent():
            self.log(f"'{self.wrapper_file}' already set as parent")
            return
        elif os.path.exists(self.parent_file):
            if self.overwrite:
                os.remove(self.parent_file)
                self.db.update_file(os.path.realpath(self.parent_file))
            else:
                raise NeXusError(f"'{os.path.realpath(self.parent_file)}' "
                                 "already set as parent")
        self.record_start('nxcopy')
        os.symlink(os.path.basename(self.wrapper_file), self.parent_file)
        self.db.update_file(self.wrapper_file)
        self.record('nxcopy', parent=self.wrapper_file)
        self.record_end('nxcopy')
        self._parent = None
        self.log(
            f"'{os.path.realpath(self.parent_file)}' set as parent")

    def get_parameter(self, name, field_name=None):
        """Return the requested data reduction parameter.

        If a parent has been selected, the parameter is read from the
        '/entry/nxreduce' group stored in the parent. Otherwise, the
        parameter is read from the current wrapper file.

        Parameters
        ----------
        name : str
            Name of the requested parameter.
        field_name : str, optional
            Name of the field containing the requested parameter,
            by default None. In most cases, this is the same as the
            name of the requested parameter.

        Returns
        -------
        int, float, or str
            Value of the requested parameter.
        """
        parameter = self.default[name]
        if field_name is None:
            field_name = name
        if (self.parent and 'nxreduce' in self.parent_root['entry']
                and field_name in self.parent_root['entry/nxreduce']):
            parameter = self.parent_root['entry/nxreduce'][field_name].nxvalue
        elif ('nxreduce' in self.root['entry']
              and field_name in self.root['entry/nxreduce']):
            parameter = self.root['entry/nxreduce'][field_name].nxvalue
        return parameter

    def write_parameters(self, threshold=None, first=None, last=None,
                         polar_max=None, hkl_tolerance=None,
                         monitor=None, norm=None,
                         qmin=None, qmax=None, radius=None):
        """Store the specified data reduction parameters.

        If the parameter was read from the parent, this updates the
        local copy in the current wrapper file's '/entry/nxreduce'
        group.
        """
        with self:
            if 'nxreduce' not in self.root['entry']:
                self.root['entry/nxreduce'] = NXparameters()
            if threshold is not None:
                self.threshold = threshold
                self.root['entry/nxreduce/threshold'] = self.threshold
            if first is not None:
                self.first = first
                self.root['entry/nxreduce/first_frame'] = self.first
            if last is not None:
                self.last = last
                self.root['entry/nxreduce/last_frame'] = self.last
            if polar_max is not None:
                self.polar_max = polar_max
                self.root['entry/nxreduce/polar_max'] = self.polar_max
            if hkl_tolerance is not None:
                self.hkl_tolerance = hkl_tolerance
                self.root['entry/nxreduce/hkl_tolerance'] = self.hkl_tolerance
            if monitor is not None:
                self.monitor = monitor
                self.root['entry/nxreduce/monitor'] = self.monitor
            if norm is not None:
                self.norm = norm
                self.root['entry/nxreduce/norm'] = self.norm
            if qmin is not None:
                self.qmin = qmin
                self.root['entry/nxreduce/qmin'] = self.qmin
            if qmax is not None:
                self.qmax = qmax
                self.root['entry/nxreduce/qmax'] = self.qmax
            if radius is not None:
                self.radius = radius
                self.root['entry/nxreduce/radius'] = self.radius

    def clear_parameters(self, parameters):
        """Remove legacy records of parameters in the 'peaks' group."""
        with self:
            parameters.append('width')
            for p in parameters:
                if 'peaks' in self.entry and p in self.entry['peaks'].attrs:
                    del self.entry['peaks'].attrs[p]

    @property
    def first(self):
        """First frame of the raw data to be used in the reduction."""
        if self._first is None:
            self._first = int(self.get_parameter('first', 'first_frame'))
        if self._first is None or self._first < 0:
            self._first = 10
        return self._first

    @first.setter
    def first(self, value):
        try:
            self._first = int(value)
        except ValueError:
            pass

    @property
    def last(self):
        """Last frame of the raw data to be used in the reduction."""
        if self._last is None:
            try:
                self.default['last'] = self.nframes - 10
            except Exception:
                pass
            self._last = int(self.get_parameter('last', 'last_frame'))
        if self._last is None or self._last > self.nframes:
            self._last = self.nframes - 10
        return self._last

    @last.setter
    def last(self, value):
        try:
            self._last = int(value)
            if self._last > self.nframes:
                self._last = self.nframes - 10
        except ValueError:
            pass

    @property
    def polar_max(self):
        """Maximum polar angle of peaks to be used in refinements."""
        if self._polar_max is None:
            self._polar_max = float(self.get_parameter('polar_max'))
        return self._polar_max

    @polar_max.setter
    def polar_max(self, value):
        self._polar_max = float(value)

    @property
    def hkl_tolerance(self):
        """Q-tolerance for peaks to be used in refinements."""
        if self._hkl_tolerance is None:
            self._hkl_tolerance = float(self.get_parameter('hkl_tolerance'))
        return self._hkl_tolerance

    @hkl_tolerance.setter
    def hkl_tolerance(self, value):
        self._hkl_tolerance = float(value)

    @property
    def threshold(self):
        """Threshold for selecting peaks for refinements.

        If all the pixels within a peak fall below this threshold, the
        peak will not be used in refinements.
        """
        if self._threshold is None:
            self._threshold = float(self.get_parameter('threshold'))
        return self._threshold

    @threshold.setter
    def threshold(self, value):
        self._threshold = value

    @property
    def min_pixels(self):
        """Minimum number of pixels separating different peaks."""
        if self._min_pixels is None:
            self._min_pixels = int(self.get_parameter('min_pixels'))
        return self._min_pixels

    @min_pixels.setter
    def min_pixels(self, value):
        self._min_pixels = int(value)

    @property
    def monitor(self):
        """Name of the field to be used to correct for the incident flux."""
        if self._monitor is None:
            self._monitor = str(self.get_parameter('monitor'))
        return self._monitor

    @monitor.setter
    def monitor(self, value):
        self._monitor = value

    @property
    def norm(self):
        """Factor used to normalize the monitor counts."""
        if self._norm is None:
            self._norm = float(self.get_parameter('norm'))
        return self._norm

    @norm.setter
    def norm(self, value):
        self._norm = value

    @property
    def polarization(self):
        """Beam polarization."""
        if self._polarization is None:
            self._polarization = float(self.get_parameter('polarization'))
        return self._polarization

    @polarization.setter
    def polarization(self, value):
        self._polarization = value

    @property
    def qmin(self):
        """Minimum Q used in estimating the sample transmission."""
        if self._qmin is None:
            self._qmin = float(self.get_parameter('qmin'))
        return self._qmin

    @qmin.setter
    def qmin(self, value):
        self._qmin = value

    @property
    def qmax(self):
        """Maximum Q used in the PDF taper function.

        This parameter is also used define the maximum Q used in
        estimating the sample transmission.
        """
        if self._qmax is None:
            self._qmax = float(self.get_parameter('qmax'))
        return self._qmax

    @qmax.setter
    def qmax(self, value):
        self._qmax = value

    @property
    def radius(self):
        """Q-radius used to define the punch size."""
        if self._radius is None:
            self._radius = float(self.get_parameter('radius'))
        return self._radius

    @radius.setter
    def radius(self, value):
        self._radius = value

    @property
    def maximum(self):
        if self._maximum is None:
            if 'data' in self.entry and 'maximum' in self.entry['data'].attrs:
                self._maximum = self.entry['data'].attrs['maximum']
        return self._maximum

    @maximum.setter
    def maximum(self, value):
        self._maximum = value

    @property
    def concurrent(self):
        if self._concurrent is None:
            if ('concurrent' in self.server_settings and
                    self.server_settings['concurrent']):
                value = self.server_settings['concurrent']
                if value in ['True', 'true', 'Yes', 'yes', 'Y', 'y']:
                    self._concurrent = 'spawn'
                elif value in ['False', 'false', 'No', 'no', 'N', 'n']:
                    self._concurrent = False
                else:
                    self._concurrent = value
            else:
                self._concurrent = False
        return self._concurrent
            
    @property
    def cctw(self):
        if self._cctw is None:
            if ('cctw' in self.server_settings and 
                    self.server_settings['cctw']):
                self._cctw = self.server_settings['cctw']
            else:
                self._cctw = 'cctw'
        return self._cctw

    def complete(self, task):
        """True if the task for this entry in the wrapper file is done """
        return task in self.entry

    def all_complete(self, task):
        """True if the task for all entries in this wrapper file are done."""
        for entry in self.entries:
            if task not in self.root[entry]:
                return False
        return True

    def not_processed(self, task):
        """True if the NXprocess group for this task has not been created.

        This is used to prevent existing analyses from being overwritten,
        unless `overwrite` is set to True.
        """
        return task not in self.entry or self.overwrite

    @property
    def oriented(self):
        """True if an orientation matrix has been determined."""
        return ('instrument' in self.entry and
                'detector' in self.entry['instrument'] and
                'orientation_matrix' in self.entry['instrument/detector'])

    def start_progress(self, start, stop):
        """Initialize a counter to monitor progress completing a task.

        Parameters
        ----------
        start : int
            Start value of the counter.
        stop : int
            Stop value of the counter.

        Returns
        -------
        float
            Timer value for calculating the completion time.
        """
        self._start = start
        if self.gui:
            self._step = (stop - start) / 100
            self._value = int(start)
            self.start.emit((0, 100))
        elif self.monitor_progress:
            print('Frame', end='')
        self.stopped = False
        return timeit.default_timer()

    def update_progress(self, i):
        """Update the progress counter."""
        if self.gui:
            _value = int(i/self._step)
            if _value > self._value:
                self.update.emit(_value)
                self._value = _value
        elif self.monitor_progress:
            print(f"\rFrame {i}", end="")

    def stop_progress(self):
        """Stop the progress counter and return the timer value."""
        if self.monitor_progress:
            print('')
        self.stopped = True
        return timeit.default_timer()

    @property
    def stopped(self):
        """True if the progress counter has stopped."""
        return self._stopped

    @stopped.setter
    def stopped(self, value):
        self._stopped = value

    @property
    def process_count(self):
        """Number of CPUs to be used in concurrent tasks."""
        if self._process_count is None:
            pc = os.cpu_count()
            if pc > 8:
                self._process_count = pc // 2
            else:
                self._process_count = 4
        return self._process_count

    def record(self, task, **kwargs):
        """Record the completion of a task in the current entry.

        A NXprocess group is created to record the results of the task,
        along with the reduction parameters.

        Parameters
        ----------
        task : str
            Name of the task.
        kwargs : dict
            Parameters used in the task.
        """
        process = kwargs.pop('process', task)
        parameters = '\n'.join(
            [f"{k.replace('_', ' ').capitalize()}: {v}"
             for (k, v) in kwargs.items()])
        note = NXnote(process, (f"Current machine: {platform.node()}\n" +
                                f"Current directory: {self.directory}\n" +
                                parameters))
        with self:
            if process in self.entry:
                del self.entry[process]
            self.entry[process] = NXprocess(
                program=f'{process}',
                sequence_index=len(self.entry.NXprocess) + 1,
                version='nxrefine v' + __version__, note=note)
            for key in [k for k in kwargs if k in self.default]:
                self.entry[process][key] = kwargs[key]

    def record_start(self, task):
        """ Record that a task has started in the database """
        try:
            self.db.start_task(self.wrapper_file, task, self.entry_name)
            self.timer[task] = timeit.default_timer()
            self.log(f"{self.name}: '{task}' started")
        except Exception as error:
            self.log(str(error))

    def record_end(self, task):
        """ Record that a task has ended in the database """
        try:
            self.db.end_task(self.wrapper_file, task, self.entry_name)
            elapsed_time = timeit.default_timer() - self.timer[task]
            self.log(
                f"{self.name}: '{task}' complete ({elapsed_time:g} seconds)")
        except Exception as error:
            self.log(str(error))

    def record_fail(self, task):
        """ Record that a task has failed in the database """
        try:
            self.db.fail_task(self.wrapper_file, task, self.entry_name)
            elapsed_time = timeit.default_timer() - self.timer[task]
            self.log(f"'{task}' failed ({elapsed_time:g} seconds)")
        except Exception as error:
            self.log(str(error))

    def nxload(self):
        """Perform nxload operation in the workflow.

        This checks for the presence of raw data files and, on some beamlines,
        loads them if necessary.
        """
        if not self.raw_data_exists() or self.overwrite:
            self.record_start('nxload')
            try:
                status = self.beamline.load_data(overwrite=self.overwrite)
                if status:
                    self.log("Raw data file loaded")
                    self.record('nxload', logs='Loaded')
                    self.record_end('nxload')
                else:
                    self.log("Raw data file not loaded")
                    self.record_fail('nxload')
            except Exception as error:
                self.log(str(error))
                self.record_fail('nxload')
                raise
        else:
            self.log("Raw data file already exists")

    def nxlink(self):
        """Perform nxlink operation in the workflow.

        This reads external metadata from the beamline into the current entry.
        """
        if self.not_processed('nxlink') and self.link:
            if not self.raw_data_exists():
                self.log("Data file not available")
                return
            self.record_start('nxlink')
            try:
                self.link_data()
                self.log("Entry linked to raw data")
                try:
                    self.beamline.read_logs()
                    self.log("Scan logs imported")
                    self.record('nxlink', logs='Transferred')
                    self.record_end('nxlink')
                except NeXusError as error:
                    self.log(str(error))
                    self.record_fail('nxlink')
            except Exception as error:
                self.log(str(error))
                self.record_fail('nxlink')
                raise
        elif self.link:
            self.log("Data already linked")

    def link_data(self):
        if self.field:
            with self:
                frames = np.arange(self.shape[0], dtype=np.int32)
                if 'instrument/detector/frame_time' in self.entry:
                    frame_time = self.entry['instrument/detector/frame_time']
                else:
                    frame_time = 0.1
                if 'data' not in self.entry:
                    self.entry['data'] = NXdata()
                    self.entry['data/x_pixel'] = np.arange(
                        self.shape[2], dtype=np.int32)
                    self.entry['data/y_pixel'] = np.arange(
                        self.shape[1], dtype=np.int32)
                    self.entry['data/frame_number'] = frames
                    self.entry['data/frame_time'] = frame_time * frames
                    self.entry['data/frame_time'].attrs['units'] = 's'
                    raw_file = os.path.relpath(
                        self.raw_file, os.path.dirname(self.wrapper_file))
                    self.entry['data/data'] = NXlink(self.raw_path, raw_file)
                    self.entry['data'].nxsignal = self.entry['data/data']
                    self.log(
                        'Data group created and linked to external data')
                else:
                    if self.entry['data/frame_number'].shape != self.shape[0]:
                        del self.entry['data/frame_number']
                        self.entry['data/frame_number'] = frames
                        if 'frame_time' in self.entry['data']:
                            del self.entry['data/frame_time']
                        self.log("Fixed frame number axis")
                    if 'data/frame_time' not in self.entry:
                        self.entry['data/frame_time'] = frame_time * frames
                        self.entry['data/frame_time'].attrs['units'] = 's'
                self.entry['data'].nxaxes = [self.entry['data/frame_number'],
                                             self.entry['data/y_pixel'],
                                             self.entry['data/x_pixel']]
        else:
            self.log("No raw data loaded")

    def nxcopy(self):
        if not self.copy:
            return
        elif self.is_parent():
            self.log("Set as parent; no parameters copied")
        elif self.not_processed('nxcopy'):
            self.record_start('nxcopy')
            try:
                if self.parent:
                    self.copy_parameters()
                    self.record('nxcopy', parent=self.parent)
                    self.log("Entry parameters copied from parent")
                    self.record_end('nxcopy')
                else:
                    self.log("No parent defined or accessible")
                    self.record_fail('nxcopy')
            except Exception as error:
                self.log(str(error))
                self.record_fail('nxcopy')
                raise
        else:
            self.log("Parameters already copied")

    def copy_parameters(self):
        parent = self.parent_root
        parent_refine = NXRefine(parent[self.entry_name])
        parent_reduce = NXReduce(parent[self.entry_name])
        refine = NXRefine(self.entry)
        parent_refine.copy_parameters(refine, sample=True, instrument=True)
        self.write_parameters(threshold=parent_reduce.threshold,
                              first=parent_reduce.first,
                              last=parent_reduce.last,
                              polar_max=parent_reduce.polar_max,
                              hkl_tolerance=parent_reduce.hkl_tolerance,
                              monitor=parent_reduce.monitor,
                              norm=parent_reduce.norm,
                              qmin=parent_reduce.qmin,
                              qmax=parent_reduce.qmax,
                              radius=parent_reduce.radius)
        self.log(
            f"Parameters for {self.name} copied from "
            f"'{os.path.basename(os.path.realpath(self.parent))}'")

    def nxmax(self):
        if self.not_processed('nxmax') and self.maxcount:
            if not self.raw_data_exists():
                self.log("Data file not available")
                return
            self.record_start('nxmax')
            try:
                result = self.find_maximum()
                if self.gui:
                    if result:
                        self.result.emit(result)
                    self.stop.emit()
                else:
                    self.write_maximum()
                    self.write_parameters(first=self.first, last=self.last)
                    self.record('nxmax', maximum=self.maximum,
                                first_frame=self.first, last_frame=self.last,
                                qmin=self.qmin)
                    self.record_end('nxmax')
            except Exception as error:
                self.log(str(error))
                self.record_fail('nxmax')
                raise
        elif self.maxcount:
            self.log("Maximum counts already found")

    def find_maximum(self):
        self.log("Finding maximum counts")
        with self.field.nxfile:
            maximum = 0.0
            chunk_size = self.field.chunks[0]
            if chunk_size < 20:
                chunk_size = 50
            data = self.field.nxfile[self.raw_path]
            fsum = np.zeros(self.nframes, dtype=np.float64)
            psum = np.zeros(self.nframes, dtype=np.float64)
            pixel_mask = self.pixel_mask
            # Add constantly firing pixels to the mask
            pixel_max = np.zeros((self.shape[1], self.shape[2]))
            v = data[0:10, :, :]
            for i in range(10):
                pixel_max = np.maximum(v[i, :, :], pixel_max)
            pixel_mean = v.sum(0) / 10.
            mask = np.zeros((self.shape[1], self.shape[2]), dtype=np.int8)
            mask[np.where(pixel_max == pixel_mean)] = 1
            mask[np.where(pixel_mean < 100)] = 0
            pixel_mask = pixel_mask | mask
            transmission_mask = self.transmission_coordinates()
            # Start looping over the data
            tic = self.start_progress(self.first, self.last)
            for i in range(self.first, self.last, chunk_size):
                if self.stopped:
                    return None
                self.update_progress(i)
                try:
                    v = data[i:i+chunk_size, :, :]
                except IndexError:
                    pass
                if i == self.first:
                    vsum = v.sum(0)
                else:
                    vsum += v.sum(0)
                v = np.ma.masked_array(v)
                v.mask = pixel_mask
                fsum[i:i+chunk_size] = v.sum((1, 2))
                v.mask = pixel_mask | transmission_mask
                psum[i:i+chunk_size] = v.sum((1, 2))
                if maximum < v.max():
                    maximum = v.max()
                del v
        self.pixel_mask = pixel_mask
        vsum = np.ma.masked_array(vsum)
        vsum.mask = pixel_mask
        self.maximum = maximum
        self.summed_data = NXfield(vsum, name='summed_data')
        self.summed_frames = NXfield(fsum, name='summed_frames')
        self.partial_frames = NXfield(psum, name='partial_frames')
        toc = self.stop_progress()
        self.log(f"Maximum counts: {maximum} ({(toc-tic):g} seconds)")
        result = NXcollection(NXfield(maximum, name='maximum'),
                              self.summed_data, self.summed_frames,
                              self.partial_frames)
        return result

    def write_maximum(self):
        with self:
            self.entry['data'].attrs['maximum'] = self.maximum
            self.entry['data'].attrs['first'] = self.first
            self.entry['data'].attrs['last'] = self.last
            self.entry['instrument/detector/pixel_mask'] = self.pixel_mask
            if 'summed_data' in self.entry:
                del self.entry['summed_data']
            self.entry['summed_data'] = NXdata(self.summed_data,
                                               self.entry['data'].nxaxes[-2:])
            if 'summed_frames' in self.entry:
                del self.entry['summed_frames']
            self.entry['summed_frames'] = NXdata(self.summed_frames,
                                                 self.entry['data'].nxaxes[0])
            self.entry['summed_frames/partial_frames'] = self.partial_frames
            self.calculate_radial_sums()
        self.clear_parameters(['first', 'last'])

    def calculate_radial_sums(self):
        try:
            from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
            parameters = (
                self.entry['instrument/calibration/refinement/parameters'])
            ai = AzimuthalIntegrator(
                dist=parameters['Distance'].nxvalue,
                detector=parameters['Detector'].nxvalue,
                poni1=parameters['Poni1'].nxvalue,
                poni2=parameters['Poni2'].nxvalue,
                rot1=parameters['Rot1'].nxvalue,
                rot2=parameters['Rot2'].nxvalue,
                rot3=parameters['Rot3'].nxvalue,
                pixel1=parameters['PixelSize1'].nxvalue,
                pixel2=parameters['PixelSize2'].nxvalue,
                wavelength=parameters['Wavelength'].nxvalue)
            polarization = ai.polarization(factor=self.polarization)
            counts = (self.summed_data.nxvalue.filled(fill_value=0)
                      / polarization)
            polar_angle, intensity = ai.integrate1d(
                counts, 2048, unit='2th_deg', mask=self.pixel_mask,
                correctSolidAngle=True, method=('no', 'histogram', 'cython'))
            Q = (4 * np.pi * np.sin(np.radians(polar_angle) / 2.0)
                 / (ai.wavelength * 1e10))
            with self:
                if 'radial_sum' in self.entry:
                    del self.entry['radial_sum']
                self.entry['radial_sum'] = NXdata(
                    NXfield(intensity, name='radial_sum'),
                    NXfield(polar_angle, name='polar_angle', units='degrees'),
                    Q=NXfield(Q, name='Q', units='Ang-1'))
                if 'polarization' in self.entry['instrument/detector']:
                    del self.entry['instrument/detector/polarization']
                self.entry['instrument/detector/polarization'] = polarization
        except Exception as error:
            self.log("Unable to create radial sum")
            self.log(str(error))
            return None

    def sample_transmission(self):
        """Field containing the estimated sample transmission."""
        path = 'instrument/sample/transmission'
        if (self.parent and path in self.parent_entry):
            transmission = self.parent_entry[path].nxsignal
        elif path in self.entry:
            transmission = self.entry[path].nxsignal
        else:
            return np.ones(shape=(self.nframes,), dtype=np.float32)
        if self.is_first_entry():
            return transmission
        else:
            first_reduce = NXReduce(self.first_entry)
            first_transmission = first_reduce.sample_transmission()
            if ('maximum' in transmission.attrs and
                    'maximum' in first_transmission.attrs):
                correction = (transmission.attrs['maximum'] /
                              first_transmission.attrs['maximum'])
                transmission *= correction
            return transmission

    def calculate_transmission(self, frame_window=5, filter_size=20):
        if self.partial_frames is None:
            if ('summed_frames' in self.entry
                    and 'partial_frames' in self.entry['summed_frames']):
                y = self.entry['summed_frames/partial_frames'].nxvalue
            else:
                raise NeXusError('Partial frames not available')
        else:
            y = self.partial_frames.nxvalue

        from scipy.interpolate import interp1d
        from scipy.ndimage.filters import median_filter

        y = y / self.read_monitor()
        x = np.arange(self.nframes)
        dx = frame_window
        ms = filter_size
        xmin = x[self.first+dx:self.last-dx:2*dx]
        ymin = median_filter(np.array([min(y[i-dx:i+dx]) for i in xmin]),
                             size=ms)
        yabs = np.ones(shape=x.shape, dtype=np.float32)
        yabs[xmin[0]:xmin[-1]] = interp1d(
            xmin, ymin, kind='cubic')(x[xmin[0]:xmin[-1]])
        yabs[0:xmin[0]] = yabs[xmin[0]]
        yabs[xmin[-1]:] = yabs[xmin[-1]-1]
        xout = list(x[::100])
        yout = list(yabs[::100])
        if max(xout) < x.max():
            xout = xout + [x[-1]]
            yout = yout + [yabs[-1]]
        yabs = interp1d(xout, yout, kind='cubic')(x)
        transmission = NXfield(yabs / yabs.max(), name='transmission',
                               long_name='Sample Transmission')
        transmission.attrs['maximum'] = yabs.max()
        frames = NXfield(np.arange(self.nframes), name='nframes',
                         long_title='Frame No.')
        group = NXdata(transmission, frames, title='Sample Transmission')
        group.attrs['frame_window'] = frame_window
        group.attrs['filter_size'] = filter_size
        return group

    def transmission_coordinates(self):
        refine = NXRefine(self.entry)
        min_radius = (self.qmin * refine.wavelength * refine.distance
                      / (2 * np.pi * refine.pixel_size))
        max_radius = (self.qmax * refine.wavelength * refine.distance
                      / (2 * np.pi * refine.pixel_size))
        x = np.arange(self.shape[2])
        y = np.arange(self.shape[1])
        min_mask = ((x[np.newaxis, :]-refine.xc)**2
                    + (y[:, np.newaxis]-refine.yc)**2 < min_radius**2)
        max_mask = ((x[np.newaxis, :]-refine.xc)**2
                    + (y[:, np.newaxis]-refine.yc)**2 > max_radius**2)
        return min_mask | max_mask

    def read_monitor(self):
        try:
            return self.beamline.read_monitor(self.monitor)
        except Exception:
            return np.ones(shape=(self.nframes), dtype=float)

    def nxfind(self):
        if self.not_processed('nxfind') and self.find:
            if not self.raw_data_exists():
                self.log("Data file not available")
                return
            self.record_start('nxfind')
            try:
                peaks = self.find_peaks()
                if self.gui:
                    if peaks:
                        self.result.emit(peaks)
                    self.stop.emit()
                elif peaks:
                    self.write_peaks(peaks)
                    self.write_parameters(threshold=self.threshold,
                                          first=self.first, last=self.last)
                    self.record('nxfind', threshold=self.threshold,
                                first=self.first, last=self.last,
                                peak_number=len(peaks))
                    self.record_end('nxfind')
                else:
                    self.record_fail('nxfind')
            except Exception as error:
                self.log(str(error))
                self.record_fail('nxfind')
                raise
        elif self.find:
            self.log("Peaks already found")

    def find_peaks(self):
        self.log("Finding peaks")
        tic = self.start_progress(self.first, self.last)
        self.blobs = []
        if self.concurrent:
            from nxrefine.nxutils import NXExecutor, as_completed
            with NXExecutor(max_workers=self.process_count,
                            mp_context=self.concurrent) as executor:
                futures = []
                for i in range(self.first, self.last+1, 50):
                    j, k = i - min(5, i), min(i+55, self.last+5, self.nframes)
                    futures.append(executor.submit(
                        peak_search,
                        self.field.nxfilename, self.field.nxfilepath,
                        i, j, k, self.threshold, mask=self.pixel_mask,
                        min_pixels=self.min_pixels))
                for future in as_completed(futures):
                    z, blobs = future.result()
                    self.blobs += [b for b in blobs if b.z >= z
                                   and b.z < min(z+50, self.last)]
                    self.update_progress(z)
                    futures.remove(future)
        else:
            for i in range(self.first, self.last+1, 50):
                j, k = i - min(5, i), min(i+55, self.last+5, self.nframes)
                z, blobs = peak_search(
                    self.field.nxfilename, self.field.nxfilepath,
                    i, j, k, self.threshold, mask=self.pixel_mask,
                    min_pixels=self.min_pixels)
                self.blobs += [b for b in blobs if b.z >= z
                               and b.z < min(z+50, self.last)]
                self.update_progress(z)

        peaks = sorted([b for b in self.blobs], key=operator.attrgetter('z'))

        toc = self.stop_progress()
        self.log(f"{len(peaks)} peaks found ({toc - tic:g} seconds)")
        return peaks

    def write_peaks(self, peaks):
        group = NXreflections()
        group['intensity'] = NXfield([peak.intensity for peak in peaks],
                                     dtype=float)
        group['x'] = NXfield([peak.x for peak in peaks], dtype=float)
        group['y'] = NXfield([peak.y for peak in peaks], dtype=float)
        group['z'] = NXfield([peak.z for peak in peaks], dtype=float)
        group['sigx'] = NXfield([peak.sigx for peak in peaks], dtype=float)
        group['sigy'] = NXfield([peak.sigy for peak in peaks], dtype=float)
        group['sigz'] = NXfield([peak.sigz for peak in peaks], dtype=float)
        group.attrs['first'] = self.first
        group.attrs['last'] = self.last
        group.attrs['threshold'] = self.threshold
        with self:
            if 'peaks' in self.entry:
                del self.entry['peaks']
            self.entry['peaks'] = group
        refine = NXRefine(self.entry)
        polar_angles, azimuthal_angles = refine.calculate_angles(refine.xp,
                                                                 refine.yp)
        refine.write_angles(polar_angles, azimuthal_angles)
        self.clear_parameters(['threshold', 'first', 'last'])

    def nxrefine(self):
        if self.not_processed('nxrefine') and self.refine:
            if not self.complete('nxfind'):
                self.log(
                    'Cannot refine until peak search is completed')
                return
            self.record_start('nxrefine')
            try:
                self.log("Refining orientation")
                if self.lattice or self.is_first_entry():
                    lattice = True
                else:
                    lattice = False
                refine = self.refine_parameters(lattice=lattice)
                if refine:
                    if not self.gui:
                        refine.write_parameters()
                    self.write_parameters(polar_max=self.polar_max,
                                          hkl_tolerance=self.hkl_tolerance)
                    self.record('nxrefine', polar_max=self.polar_max,
                                hkl_tolerance=self.hkl_tolerance,
                                fit_report=refine.fit_report)
                    self.record_end('nxrefine')
                else:
                    self.record_fail('nxrefine')
            except Exception as error:
                self.log(str(error))
                self.record_fail('nxrefine')
                raise
        elif self.refine:
            self.log("HKL values already refined")

    def refine_parameters(self, lattice=False):
        refine = NXRefine(self.entry)
        refine.polar_max = self.polar_max
        refine.hkl_tolerance = self.hkl_tolerance
        refine.refine_hkls(lattice=lattice, chi=True, omega=True, theta=True)
        fit_report = refine.fit_report
        refine.refine_hkls(chi=True, omega=True, theta=True)
        fit_report = fit_report + '\n' + refine.fit_report
        refine.refine_orientation_matrix()
        fit_report = fit_report + '\n' + refine.fit_report
        if refine.result.success:
            refine.fit_report = fit_report
            self.log("Refined HKL values")
            return refine
        else:
            self.log("HKL refinement not successful")
            return None

    def nxprepare(self):
        if self.not_processed('nxprepare_mask') and self.prepare:
            try:
                self.record_start('nxprepare')
                self.log("Preparing 3D mask")
                self.mask_file = os.path.join(self.directory,
                                              self.entry_name+'_mask.nxs')
                mask = self.prepare_mask()
                if self.gui:
                    if mask:
                        self.result.emit(mask)
                    self.stop.emit()
                elif mask:
                    self.write_mask(mask)
                    self.write_parameters(first=self.first, last=self.last)
                    self.record(
                        'nxprepare', masked_file=self.mask_file,
                        first=self.first, last=self.last,
                        threshold1=self.mask_parameters['threshold_1'],
                        horizontal1=self.mask_parameters['horizontal_size_1'],
                        threshold2=self.mask_parameters['threshold_2'],
                        horizontal2=self.mask_parameters['horizontal_size_2'],
                        process='nxprepare_mask')
                    self.record_end('nxprepare')
                else:
                    self.record_fail('nxprepare')
            except Exception as error:
                self.log(str(error))
                self.record_fail('nxprepare')
                raise
        elif self.prepare:
            self.log("3D Mask already prepared")

    def prepare_mask(self):
        """Prepare 3D mask"""
        tic = self.start_progress(self.first, self.last)
        t1 = self.mask_parameters['threshold_1']
        h1 = self.mask_parameters['horizontal_size_1']
        t2 = self.mask_parameters['threshold_2']
        h2 = self.mask_parameters['horizontal_size_2']

        mask_root = nxopen(self.mask_file+'.h5', 'w')
        mask_root['entry'] = NXentry()
        mask_root['entry/mask'] = (
            NXfield(shape=self.shape, dtype=np.int8, fillvalue=0))

        if self.concurrent:
            from nxrefine.nxutils import NXExecutor, as_completed
            with NXExecutor(max_workers=self.process_count,
                            mp_context=self.concurrent) as executor:
                futures = []
                for i in range(self.first, self.last+1, 10):
                    j, k = i - min(1, i), min(i+11, self.last+1, self.nframes)
                    futures.append(executor.submit(
                        mask_volume,
                        self.field.nxfilename, self.field.nxfilepath,
                        mask_root.nxfilename, 'entry/mask', i, j, k,
                        self.pixel_mask, t1, h1, t2, h2))
                for future in as_completed(futures):
                    k = future.result()
                    self.update_progress(k)
                    futures.remove(future)
        else:
            for i in range(self.first, self.last+1, 10):
                j, k = i - min(1, i), min(i+11, self.last+1, self.nframes)
                k = mask_volume(self.field.nxfilename, self.field.nxfilepath,
                                mask_root.nxfilename, 'entry/mask', i, j, k,
                                self.pixel_mask, t1, h1, t2, h2)
                self.update_progress(k)

        frame_mask = np.ones(shape=self.shape[1:], dtype=np.int8)
        with mask_root.nxfile:
            mask_root['entry/mask'][:self.first] = frame_mask
            mask_root['entry/mask'][self.last+1:] = frame_mask

        toc = self.stop_progress()

        self.log(f"3D Mask prepared in {toc-tic:g} seconds")

        return mask_root['entry/mask']

    def write_mask(self, mask):
        """Write mask to file."""
        if os.path.exists(self.mask_file):
            os.remove(self.mask_file)
        shutil.move(mask.nxfilename, self.mask_file)
        with self:
            if ('data_mask' in self.data
                    and self.data['data_mask'].nxfilename != self.mask_file):
                del self.data['data_mask']
            if 'data_mask' not in self.data:
                self.data['data_mask'] = NXlink('entry/mask', self.mask_file)
        self.log(f"3D Mask written to '{self.mask_file}'")

    def nxtransform(self, mask=False):
        if mask:
            task = 'nxmasked_transform'
            task_name = 'Masked transform'
            self.transform_file = os.path.join(
                self.directory, self.entry_name+'_masked_transform.nxs')
        else:
            task = 'nxtransform'
            task_name = 'Transform'
            self.transform_file = os.path.join(
                self.directory, self.entry_name+'_transform.nxs')
        if self.not_processed(task) and self.transform:
            if not self.oriented:
                self.log(
                    'Cannot transform until the orientation is complete')
                return
            self.record_start(task)
            try:
                cctw_command = self.prepare_transform(mask=mask)
                if cctw_command:
                    self.log(f"{task_name} process launched")
                    tic = timeit.default_timer()
                    with self.field.nxfile:
                        with NXLock(self.transform_file):
                            process = subprocess.run(cctw_command, shell=True,
                                                     stdout=subprocess.PIPE,
                                                     stderr=subprocess.PIPE)
                    cctw_output = process.stdout.decode()
                    cctw_errors = process.stderr.decode()
                    self.log('CCTW Output\n' + cctw_output)
                    if cctw_errors:
                        self.log('CCTW Errors\n' + cctw_errors)
                    toc = timeit.default_timer()
                    if process.returncode == 0:
                        self.log(
                            f"{task_name} completed ({toc - tic:g} seconds)")
                        self.write_parameters(monitor=self.monitor,
                                              norm=self.norm)
                        self.record(task, monitor=self.monitor, norm=self.norm,
                                    command=cctw_command,
                                    output=cctw_output,
                                    errors=cctw_errors)
                        self.record_end(task)
                        self.clear_parameters(['monitor', 'norm'])
                    else:
                        self.log(
                            f"{task_name} completed - errors reported "
                            f"({(toc-tic):g} seconds)")
                        self.record_fail(task)
                else:
                    self.log("CCTW command invalid")
                    self.record_fail(task)
            except Exception as error:
                self.log(str(error))
                self.record_fail(task)
                raise
        elif self.transform:
            self.log(f"{task_name} already created")

    def get_transform_grid(self, mask=False):
        if self.Qh and self.Qk and self.Ql:
            try:
                self.Qh = [np.float32(v) for v in self.Qh]
                self.Qk = [np.float32(v) for v in self.Qk]
                self.Ql = [np.float32(v) for v in self.Ql]
            except Exception:
                self.Qh = self.Qk = self.Ql = None
        else:
            if self.parent:
                root = self.parent_root
                if mask and 'masked_transform' in root[self.entry_name]:
                    transform = root[self.entry_name]['masked_transform']
                elif 'transform' in root[self.entry_name]:
                    transform = root[self.entry_name]['transform']
            elif mask and 'masked_transform' in self.entry:
                transform = self.entry['masked_transform']
            elif 'transform' in self.entry:
                transform = self.entry['transform']
            try:
                Qh, Qk, Ql = (transform['Qh'].nxvalue,
                              transform['Qk'].nxvalue,
                              transform['Ql'].nxvalue)
                self.Qh = Qh[0], Qh[1]-Qh[0], Qh[-1]
                self.Qk = Qk[0], Qk[1]-Qk[0], Qk[-1]
                self.Ql = Ql[0], Ql[1]-Ql[0], Ql[-1]
            except Exception:
                self.Qh = self.Qk = self.Ql = None

    def get_normalization(self):
        with self:
            try:
                monitor_weight = self.read_monitor()
                inst = self.entry['instrument']
                transmission = np.ones(self.nframes, dtype=np.float32)
                try:
                    transmission *= inst['attenuator/attenuator_transmission']
                except Exception:
                    pass
                try:
                    transmission *= inst['filter/transmission'].nxsignal
                except Exception:
                    pass
                try:
                    transmission *= self.sample_transmission()
                except Exception:
                    pass
                monitor_weight *= transmission
            except Exception:
                self.log('Unable to determine monitor weights')
                monitor_weight = np.ones(self.nframes, dtype=np.float32)
            monitor_weight[:self.first] = 0.0
            monitor_weight[self.last+1:] = 0.0
            if 'monitor_weight' in self.data:
                del self.data['monitor_weight']
            self.data['monitor_weight'] = monitor_weight
            self.data['monitor_weight'].attrs['axes'] = 'frame_number'

    def prepare_transform(self, mask=False):
        settings_file = os.path.join(self.directory,
                                     self.entry_name+'_transform.pars')
        self.get_transform_grid(mask=mask)
        if self.norm:
            self.get_normalization()
        if self.Qh and self.Qk and self.Ql:
            refine = NXRefine(self.entry)
            refine.read_parameters()
            refine.h_start, refine.h_step, refine.h_stop = self.Qh
            refine.k_start, refine.k_step, refine.k_stop = self.Qk
            refine.l_start, refine.l_step, refine.l_stop = self.Ql
            refine.define_grid()
            refine.prepare_transform(self.transform_file, mask=mask)
            refine.write_settings(settings_file)
            command = refine.cctw_command(mask)
            if command and os.path.exists(self.transform_file):
                with NXLock(self.transform_file):
                    os.remove(self.transform_file)
            command = command.replace('cctw', self.cctw)
            return command
        else:
            self.log("Invalid HKL grid")
            return None

    def nxsum(self, scan_list, update=False):
        if os.path.exists(self.raw_file) and not (self.overwrite or update):
            self.log("Data already summed")
        elif not os.path.exists(self.directory):
            self.log("Sum directory not created")
        else:
            self.record_start('nxsum')
            try:
                self.log("Sum files launched")
                tic = timeit.default_timer()
                if not self.check_files(scan_list):
                    self.record_fail('nxsum')
                else:
                    self.log(
                        "All files and metadata have been checked")
                    if not update:
                        self.sum_files(scan_list)
                    self.sum_monitors(scan_list)
                    toc = timeit.default_timer()
                    self.log(f"Sum completed ({toc - tic:g} seconds)")
                    self.record('nxsum', scans=','.join(scan_list))
                    self.record_end('nxsum')
            except Exception as error:
                self.log(str(error))
                self.record_fail('nxsum')
                raise

    def check_sum_files(self, scan_list):
        status = True
        for i, scan in enumerate(scan_list):
            reduce = NXReduce(self.entry_name,
                              os.path.join(self.base_directory, scan))
            if not os.path.exists(reduce.raw_file):
                self.log(f"'{reduce.raw_file}' does not exist")
                status = False
            elif 'monitor1' not in reduce.entry:
                self.log(
                    f"Monitor1 not present in {reduce.wrapper_file}")
                status = False
        return status

    def sum_files(self, scan_list):

        nframes = 3650
        chunk_size = 500
        for i, scan in enumerate(scan_list):
            reduce = NXReduce(self.entry_name,
                              os.path.join(self.base_directory, scan))
            self.log(
                f"Summing {self.entry_name} in '{reduce.raw_file}'")
            if i == 0:
                shutil.copyfile(reduce.raw_file, self.raw_file)
                new_file = h5.File(self.raw_file, 'r+')
                new_field = new_file[self.raw_path]
            else:
                scan_file = h5.File(reduce.raw_file, 'r')
                scan_field = scan_file[reduce.raw_path]
                for i in range(0, nframes, chunk_size):
                    new_slab = new_field[i:i+chunk_size, :, :]
                    scan_slab = scan_field[i:i+chunk_size, :, :]
                    new_field[i:i+chunk_size, :, :] = new_slab + scan_slab
        self.log("Raw data files summed")

    def sum_monitors(self, scan_list, update=False):

        for i, scan in enumerate(scan_list):
            reduce = NXReduce(self.entry_name,
                              os.path.join(self.base_directory, scan))
            self.log(
                f"Adding {self.entry_name} monitors in "
                f"'{reduce.wrapper_file}'")
            monitors = []
            if i == 0:
                for monitor in reduce.entry.NXmonitor:
                    monitors.append(monitor.nxsignal.nxvalue)
                if 'monitor_weight' not in reduce.entry['data']:
                    reduce.get_normalization()
                monitor_weight = reduce.entry['data/monitor_weight'].nxvalue
                if os.path.exists(reduce.mask_file):
                    shutil.copyfile(reduce.mask_file, self.mask_file)
            else:
                for i, monitor in enumerate(reduce.entry.NXmonitor):
                    monitors[i] += monitor.nxsignal.nxvalue
                if 'monitor_weight' not in reduce.entry['data']:
                    reduce.get_normalization()
                monitor_weight += reduce.entry['data/monitor_weight'].nxvalue
        with self:
            for i, monitor in enumerate(self.entry.NXmonitor):
                self.entry[monitor.nxname].nxsignal = monitors[i]
            self.entry['data/monitor_weight'] = monitor_weight

    def nxreduce(self):
        if self.load:
            self.nxload()
        if self.link:
            self.nxlink()
        if self.copy:
            self.nxcopy()
        if self.maxcount:
            self.nxmax()
        if self.find:
            self.nxfind()
        if self.refine:
            if self.complete('nxcopy') and self.complete('nxfind'):
                self.nxrefine()
            else:
                self.log("Cannot refine orientation matrix")
                self.record_fail('nxrefine')
        if self.prepare:
            self.nxprepare()
        if self.transform:
            if self.oriented:
                if self.regular:
                    self.nxtransform()
                if self.mask:
                    self.nxtransform(mask=True)
            else:
                self.log("Cannot transform without orientation matrix")
                if self.regular:
                    self.record_fail('nxtransform')
                if self.mask:
                    self.record_fail('nxmasked_transform')
        if self.combine or self.pdf:
            reduce = NXMultiReduce(self.directory, entries=self.entries,
                                   combine=self.combine, pdf=self.pdf,
                                   regular=self.regular, mask=self.mask,
                                   overwrite=self.overwrite)
            if self.combine:
                if self.regular and self.all_complete('nxtransform'):
                    reduce.nxcombine()
                if self.mask and self.all_complete('nxmasked_transform'):
                    reduce.nxcombine(mask=True)
            if self.pdf:
                if self.regular and self.complete('nxcombine'):
                    reduce.nxpdf()
                if self.mask and self.complete('nxmasked_combine'):
                    reduce.nxpdf(mask=True)

    def queue(self, command, args=None):
        """ Add tasks to the server's fifo, and log this in the database """

        if self.server is None:
            raise NeXusError("NXServer not configured")

        tasks = []
        if self.load:
            tasks.append('load')
            self.queue_task('nxload')
        if self.link:
            tasks.append('link')
            self.queue_task('nxlink')
        if self.copy:
            tasks.append('copy')
            self.queue_task('nxcopy')
        if self.maxcount:
            tasks.append('max')
            self.queue_task('nxmax')
        if self.find:
            tasks.append('find')
            self.queue_task('nxfind')
        if self.refine:
            tasks.append('refine')
            self.queue_task('nxrefine')
        if self.prepare:
            tasks.append('prepare')
            self.queue_task('nxprepare')
        if self.transform:
            tasks.append('transform')
            if self.regular:
                self.queue_task('nxtransform')
            if self.mask:
                self.queue_task('nxmasked_transform')
        if self.combine:
            tasks.append('combine')
            if self.regular:
                self.queue_task('nxcombine', entry='entry')
            if self.mask:
                self.queue_task('nxmasked_combine', entry='entry')
        if self.pdf:
            tasks.append('pdf')
            if self.regular:
                self.queue_task('nxpdf', entry='entry')
            if self.mask:
                self.queue_task('nxmasked_pdf', entry='entry')

        if not tasks:
            return

        if set(tasks).intersection(['transform', 'combine', 'pdf']):
            if self.regular:
                tasks.append('regular')
            if self.mask:
                tasks.append('mask')
        if self.overwrite:
            tasks.append('overwrite')

        def switches(args):
            d = vars(args)
            s = [f"--{k} {d[k]}" if d[k] is not True else f"--{k}"
                 for k in d if d[k] and k != 'entries' and k != 'queue']
            s.insert(1, f"--entries {self.entry_name}")
            return ' '.join(s)

        if args:
            if 'directory' in args:
                args.directory = os.path.realpath(args.directory)
            self.server.add_task(f"{command} {switches(args)}")
        else:
            self.server.add_task(
                f"{command} --directory {self.directory} "
                f"--entries {self.entry_name} --{' --'.join(tasks)}")

    def queue_task(self, task, entry=None):
        if entry is None:
            entry = self.entry_name
        if self.not_processed(task):
            self.db.queue_task(self.wrapper_file, task, entry)


class NXMultiReduce(NXReduce):

    def __init__(self, directory, entries=None,
                 combine=False, pdf=False, regular=False, mask=False,
                 laue=None, radius=None, qmax=None, overwrite=False):
        if isinstance(directory, NXroot):
            entry = directory['entry']
        else:
            entry = 'entry'
        super().__init__(entry=entry, directory=directory, entries=entries,
                         overwrite=overwrite)
        self.refine = NXRefine(self.root)

        if laue:
            if laue in self.refine.laue_groups:
                self.refine.laue_group = laue
            else:
                raise NeXusError('Invalid Laue group specified')
        self._radius = radius
        self._qmax = qmax

        self.combine = combine
        self.pdf = pdf
        self.regular = regular
        self.mask = mask
        if not self.mask:
            self.regular = True
        self.julia = None

    def __repr__(self):
        return f"NXMultiReduce('{self.sample}_{self.scan}')"

    def complete(self, task):
        if task in ['nxcombine', 'nxmasked_combine', 'nxpdf', 'nxmasked_pdf']:
            return task in self.entry
        return self.all_complete(task)

    def nxcombine(self, mask=False):
        if mask:
            task = 'nxmasked_combine'
            transform_task = 'nxmasked_transform'
            self.title = 'Masked Combine'
            self.transform_path = 'masked_transform'
            self.transform_file = os.path.join(self.directory,
                                               'masked_transform.nxs')
        else:
            task = 'nxcombine'
            transform_task = 'nxtransform'
            self.title = 'Combine'
            self.transform_path = 'transform'
            self.transform_file = os.path.join(self.directory, 'transform.nxs')
        if self.not_processed(task) and self.combine:
            if not self.complete(transform_task):
                self.log(
                    f"{self.title}: Cannot combine until transforms complete")
                return
            self.record_start(task)
            try:
                cctw_command = self.prepare_combine()
                if cctw_command:
                    if mask:
                        self.log("Combining masked transforms "
                                         f"({', '.join(self.entries)})")
                        transform_data = 'masked_transform/data'
                    else:
                        self.log("Combining transforms "
                                         f"({', '.join(self.entries)})")
                        transform_data = 'transform/data'
                    tic = timeit.default_timer()
                    with NXLock(self.transform_file):
                        if os.path.exists(self.transform_file):
                            os.remove(self.transform_file)
                        data_lock = {}
                        for entry in self.entries:
                            data_lock[entry] = NXLock(
                                self.root[entry][transform_data].nxfilename)
                            data_lock[entry].acquire()
                        process = subprocess.run(cctw_command, shell=True,
                                                 stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE)
                        for entry in self.entries:
                            data_lock[entry].release()
                    cctw_output = process.stdout.decode()
                    cctw_errors = process.stderr.decode()
                    self.log('CCTW Output\n' + cctw_output)
                    if cctw_errors:
                        self.log('CCTW Errors\n' + cctw_errors)
                    toc = timeit.default_timer()
                    if process.returncode == 0:
                        self.log(
                            f"{self.title} ({', '.join(self.entries)}) "
                            f"completed ({toc-tic:g} seconds)")
                        self.record(task, command=cctw_command,
                                    output=cctw_output,
                                    errors=cctw_errors)
                        self.record_end(task)
                    else:
                        self.log(
                            f"{self.title} "
                            f"({', '.join(self.entries)}) completed "
                            f"- errors reported ({(toc-tic):g} seconds)")
                        self.record_fail('nxcombine')
                else:
                    self.log("CCTW command invalid")
            except Exception as error:
                self.log(str(error))
                self.record_fail(transform_task)
                raise
        else:
            self.log(f"{self.title}: Data already combined")

    def prepare_combine(self):
        try:
            with self:
                entry = self.entries[0]
                Qh, Qk, Ql = (self.root[entry][self.transform_path]['Qh'],
                              self.root[entry][self.transform_path]['Qk'],
                              self.root[entry][self.transform_path]['Ql'])
                if 'scaling_factor' not in Qh.attrs:
                    Qh.attrs['scaling_factor'] = self.refine.astar
                if 'scaling_factor' not in Qk.attrs:
                    Qk.attrs['scaling_factor'] = self.refine.bstar
                if 'scaling_factor' not in Ql.attrs:
                    Ql.attrs['scaling_factor'] = self.refine.cstar
                data = NXlink('/entry/data/v', self.transform_file,
                              name='data')
                if self.transform_path in self.entry:
                    del self.entry[self.transform_path]
                self.entry[self.transform_path] = NXdata(data, [Ql, Qk, Qh])
                self.entry[self.transform_path].attrs['angles'] = (
                    self.refine.gamma_star,
                    self.refine.beta_star,
                    self.refine.alpha_star)
                self.add_title(self.entry[self.transform_path])
                self.entry[self.transform_path].set_default(over=True)
        except Exception as error:
            self.log("Unable to initialize transform group")
            self.log(str(error))
            return None
        input = ' '.join([os.path.join(
            self.directory,
            fr'{entry}_{self.transform_path}.nxs\#/entry/data')
            for entry in self.entries])
        output = os.path.join(self.directory,
                              fr'{self.transform_path}.nxs\#/entry/data/v')
        return f"{self.cctw} merge {input} --normalization 1 -o {output}"

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

    def nxpdf(self, mask=False):
        if mask:
            task = 'nxmasked_pdf'
        else:
            task = 'nxpdf'
        if self.not_processed(task) and self.pdf:
            if mask:
                if not self.complete('nxmasked_combine'):
                    self.log("Cannot calculate PDF until the "
                                     "masked transforms are combined")
                    return
            elif not self.complete('nxcombine'):
                self.log(
                    "Cannot calculate PDF until the transforms are combined")
                return
            elif self.refine.laue_group not in self.refine.laue_groups:
                self.log(
                    "Need to define a valid Laue group before PDF calculation")
                return
            if self.julia is None:
                try:
                    self.julia = init_julia()
                except Exception as error:
                    self.log(f"Cannot initialize Julia: {error}")
                    self.julia = None
                    return
            load_julia(['LaplaceInterpolation.jl'])
            self.record_start(task)
            self.init_pdf(mask)
            try:
                self.symmetrize_transform()
                self.total_pdf()
                self.punch_and_fill()
                self.delta_pdf()
                self.write_parameters(radius=self.radius, qmax=self.qmax)
                self.record(task, laue=self.refine.laue_group,
                            radius=self.radius, qmax=self.qmax)
                self.record_end(task)
            except Exception as error:
                self.log(str(error))
                self.record_fail(task)
                raise
        else:
            self.log(f"{self.title} already calculated")

    def init_pdf(self, mask=False):
        if mask:
            self.title = 'Masked PDF'
            self.transform_path = 'masked_transform'
            self.symm_data = 'symm_masked_transform'
            self.total_pdf_data = 'total_masked_pdf'
            self.pdf_data = 'masked_pdf'
            self.symm_file = os.path.join(self.directory,
                                          'masked_symm_transform.nxs')
            self.total_pdf_file = os.path.join(self.directory,
                                               'masked_total_pdf.nxs')
            self.pdf_file = os.path.join(self.directory, 'masked_pdf.nxs')
            self.Qh, self.Qk, self.Ql = (self.entry['masked_transform/Qh'],
                                         self.entry['masked_transform/Qk'],
                                         self.entry['masked_transform/Ql'])
        else:
            self.title = 'PDF'
            self.transform_path = 'transform'
            self.symm_data = 'symm_transform'
            self.total_pdf_data = 'total_pdf'
            self.pdf_data = 'pdf'
            self.symm_file = os.path.join(self.directory, 'symm_transform.nxs')
            self.total_pdf_file = os.path.join(self.directory, 'total_pdf.nxs')
            self.pdf_file = os.path.join(self.directory, 'pdf.nxs')
            self.Qh, self.Qk, self.Ql = (self.entry['transform/Qh'],
                                         self.entry['transform/Qk'],
                                         self.entry['transform/Ql'])
        total_size = self.entry[self.transform_path].nxsignal.nbytes / 1e6
        if total_size > nxgetconfig('memory'):
            nxsetconfig(memory=total_size+1000)
        self.taper = self.fft_taper()

    def symmetrize_transform(self):
        self.log(f"{self.title}: Transform being symmetrized")
        tic = timeit.default_timer()
        symm_root = nxopen(self.symm_file, 'w')
        symm_root['entry'] = NXentry()
        symm_root['entry/data'] = NXdata()
        symmetry = NXSymmetry(self.entry[self.transform_path],
                              laue_group=self.refine.laue_group)
        symm_root['entry/data/data'] = symmetry.symmetrize(entries=True)
        symm_root['entry/data'].nxsignal = symm_root['entry/data/data']
        symm_root['entry/data'].nxweights = 1.0 / self.taper
        symm_root['entry/data'].nxaxes = self.entry[self.transform_path].nxaxes
        with self:
            if self.symm_data in self.entry:
                del self.entry[self.symm_data]
            symm_data = NXlink('/entry/data/data', file=self.symm_file,
                               name='data')
            self.entry[self.symm_data] = NXdata(
                symm_data, self.entry[self.transform_path].nxaxes)
            self.entry[self.symm_data].nxweights = NXlink(
                '/entry/data/data_weights', file=self.symm_file)
            self.add_title(self.entry[self.symm_data])
        self.log(f"'{self.symm_data}' added to entry")
        toc = timeit.default_timer()
        self.log(f"{self.title}: Symmetrization completed "
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
        if self.parent:
            entry = self.parent_root['entry']
            if ('symm_transform' in entry
                    and entry['symm_transform'].nxweights):
                return 1.0 / entry['symm_transform'].nxweights.nxvalue
            elif ('symm_masked_transform' in entry
                    and entry['symm_masked_transform'].nxweights):
                return 1.0 / entry['symm_masked_transform'].nxweights.nxvalue
        self.log(f"{self.title}: Calculating taper function")
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
        self.log(f"{self.title}: Taper function calculated "
                         f"({toc-tic:g} seconds)")
        return taper

    def total_pdf(self):
        if os.path.exists(self.total_pdf_file):
            if self.overwrite:
                os.remove(self.total_pdf_file)
            else:
                self.log(
                    f"{self.title}: Total PDF file already exists")
                return
        self.log(f"{self.title}: Calculating total PDF")
        tic = timeit.default_timer()
        symm_data = self.entry[self.symm_data].nxsignal.nxvalue
        symm_data *= self.taper
        fft = np.real(scipy.fft.fftshift(
            scipy.fft.fftn(scipy.fft.fftshift(symm_data[:-1, :-1, :-1]),
                           workers=self.process_count)))
        fft *= (1.0 / np.prod(fft.shape))

        with nxopen(self.total_pdf_file, 'a') as root:
            root['entry'] = NXentry()
            root['entry/pdf'] = NXdata(NXfield(fft, name='pdf'))

        with self:
            if self.total_pdf_data in self.entry:
                del self.entry[self.total_pdf_data]
            pdf = NXlink('/entry/pdf/pdf', file=self.total_pdf_file,
                         name='pdf')

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
        self.log(f"'{self.total_pdf_data}' added to entry")
        toc = timeit.default_timer()
        self.log(f"{self.title}: Total PDF calculated "
                         f"({toc - tic:g} seconds)")

    def hole_mask(self):
        symm_group = self.entry[self.symm_data]
        dl, dk, dh = [(ax[1]-ax[0]).nxvalue for ax in symm_group.nxaxes]
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
        self.refine.polar_max = max([NXRefine(self.root[e]).two_theta_max()
                                     for e in self.entries])
        if self.refine.laue_group in ['-3', '-3m', '6/m', '6/mmm']:
            _indices = []
            for idx in self.refine.indices:
                _indices += self.refine.indices_hkl(*idx)
            return _indices
        else:
            return self.refine.indices

    def symmetrize(self, data):
        if self.refine.laue_group not in ['-3', '-3m', '6/m', '6/mmm']:
            import tempfile
            with nxopen(tempfile.mkstemp(suffix='.nxs')[1], mode='w') as root:
                root['data'] = data
                symmetry = NXSymmetry(root['data'],
                                      laue_group=self.refine.laue_group)
            result = symmetry.symmetrize()
            os.remove(root.nxfilename)
            return result
        else:
            return data

    def punch_and_fill(self):
        self.log(f"{self.title}: Performing punch-and-fill")

        from julia import Main
        LaplaceInterpolation = Main.LaplaceInterpolation

        tic = timeit.default_timer()
        symm_group = self.entry[self.symm_data]
        Qh, Qk, Ql = (symm_group['Qh'], symm_group['Qk'], symm_group['Ql'])

        symm_root = nxopen(self.symm_file, 'rw')
        symm_data = symm_root['entry/data/data']

        mask, mask_indices = self.hole_mask()
        idx = [Main.CartesianIndex(int(i[0]+1), int(i[1]+1), int(i[2]+1))
               for i in mask_indices]
        ml = int((mask.shape[0]-1)/2)
        mk = int((mask.shape[1]-1)/2)
        mh = int((mask.shape[2]-1)/2)
        fill_data = np.zeros(shape=symm_data.shape, dtype=symm_data.dtype)
        self.refine.polar_max = max([NXRefine(self.root[e]).two_theta_max()
                                     for e in self.entries])
        for h, k, l in self.indices:
            try:
                ih = np.argwhere(np.isclose(Qh, h))[0][0]
                ik = np.argwhere(np.isclose(Qk, k))[0][0]
                il = np.argwhere(np.isclose(Ql, l))[0][0]
                lslice = slice(il-ml, il+ml+1)
                kslice = slice(ik-mk, ik+mk+1)
                hslice = slice(ih-mh, ih+mh+1)
                v = symm_data[(lslice, kslice, hslice)].nxvalue
                if v.max() > 0.0:
                    w = LaplaceInterpolation.matern_3d_grid(v, idx)
                    fill_data[(lslice, kslice, hslice)] += np.where(mask, w, 0)
            except Exception:
                pass

        self.log(f"{self.title}: Symmetrizing punch-and-fill")

        fill_data = self.symmetrize(fill_data)
        changed_idx = np.where(fill_data > 0)
        buffer = symm_data.nxvalue
        buffer[changed_idx] = fill_data[changed_idx]
        if 'fill' in symm_root['entry/data']:
            del symm_root['entry/data/fill']
        symm_root['entry/data/fill'] = buffer
        with self:
            if 'filled_data' in self.entry[self.symm_data]:
                del self.entry[self.symm_data]['filled_data']
            self.entry[self.symm_data]['filled_data'] = NXlink(
                '/entry/data/fill', file=self.symm_file)

        buffer[changed_idx] *= 0
        if 'punch' in symm_root['entry/data']:
            del symm_root['entry/data/punch']
        symm_root['entry/data/punch'] = buffer
        with self:
            if 'punched_data' in self.entry[self.symm_data]:
                del self.entry[self.symm_data]['punched_data']
            self.entry[self.symm_data]['punched_data'] = NXlink(
                '/entry/data/punch', file=self.symm_file)

        toc = timeit.default_timer()
        self.log(f"{self.title}: Punch-and-fill completed "
                         f"({toc - tic:g} seconds)")

    def delta_pdf(self):
        self.log(f"{self.title}: Calculating Delta-PDF")
        if os.path.exists(self.pdf_file):
            if self.overwrite:
                os.remove(self.pdf_file)
            else:
                self.log(
                    f"{self.title}: Delta-PDF file already exists")
                return
        tic = timeit.default_timer()
        symm_data = self.entry[self.symm_data]['filled_data'].nxvalue
        symm_data *= self.taper
        fft = np.real(scipy.fft.fftshift(
            scipy.fft.fftn(scipy.fft.fftshift(symm_data[:-1, :-1, :-1]),
                           workers=self.process_count)))
        fft *= (1.0 / np.prod(fft.shape))

        root = nxopen(self.pdf_file, 'a')
        root['entry'] = NXentry()
        root['entry/pdf'] = NXdata(NXfield(fft, name='pdf'))

        if self.pdf_data in self.entry:
            with self:
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
        with self:
            self.entry[self.pdf_data] = NXdata(pdf, (z, y, x))
            self.entry[self.pdf_data].attrs['angles'] = (
                self.refine.lattice_parameters[3:])
            self.add_title(self.entry[self.pdf_data])
        self.log(f"'{self.pdf_data}' added to entry")
        toc = timeit.default_timer()
        self.log(f"{self.title}: Delta-PDF calculated "
                         f"({toc - tic:g} seconds)")

    def nxsum(self, scan_list):
        if not os.path.exists(self.wrapper_file) or self.overwrite:
            for e in self.entries:
                reduce = NXReduce(self.root[e])
                status = reduce.check_sum_files(scan_list)
                if not status:
                    return status
            if not os.path.exists(self.directory):
                os.mkdir(self.directory)
            self.log("Creating sum file")
            self.configure_sum_file(scan_list)
            self.log("Sum file created")
        else:
            self.log("Sum file already exists")

    def configure_sum_file(self, scan_list):
        shutil.copyfile(os.path.join(self.base_directory,
                                     self.sample+'_'+scan_list[0]+'.nxs'),
                        self.wrapper_file)
        with self:
            if 'nxcombine' in self.root['entry']:
                del self.root['entry/nxcombine']
            if 'nxmasked_combine' in self.root['entry']:
                del self.root['entry/nxmasked_combine']
            for e in self.entries:
                entry = self.root[e]
                if 'data' in entry:
                    if 'data' in entry['data']:
                        del entry['data/data']
                    entry['data/data'] = NXlink(
                        '/entry/data/data',
                        os.path.join(self.directory, entry.nxname+'.h5'))
                    if 'data_mask' in entry['data']:
                        mask_file = os.path.join(self.directory,
                                                 entry.nxname+'_mask.nxs')
                        del entry['data/data_mask']
                        entry['data/data_mask'] = NXlink('/entry/mask',
                                                         mask_file)
                if 'nxtransform' in entry:
                    del entry['nxtransform']
                if 'nxmasked_transform' in entry:
                    del entry['nxmasked_transform']
        self.db.update_file(self.wrapper_file)

    def nxreduce(self):
        if self.combine:
            if self.regular:
                self.nxcombine()
            if self.mask:
                self.nxcombine(mask=True)
        if self.pdf:
            if self.regular:
                self.nxpdf()
            if self.mask:
                self.nxpdf(mask=True)

    def queue(self, command, args=None):
        """ Add tasks to the server's fifo, and log this in the database """

        tasks = []
        if self.combine:
            tasks.append('combine')
            if self.regular:
                self.queue_task('nxcombine')
            if self.mask:
                self.queue_task('nxmasked_combine')
        if self.pdf:
            tasks.append('pdf')
            if self.regular:
                self.queue_task('nxpdf')
            if self.mask:
                self.queue_task('nxmasked_pdf')

        if not tasks:
            return

        if self.regular:
            tasks.append('regular')
        if self.mask:
            tasks.append('mask')
        if self.overwrite:
            tasks.append('overwrite')

        def switches(args):
            d = vars(args)
            s = [f"--{k} {d[k]}" if d[k] is not True else f"--{k}"
                 for k in d if d[k] and k != 'queue']
            return ' '.join(s)

        if args:
            if 'directory' in args:
                args.directory = os.path.realpath(args.directory)
            self.server.add_task(f"{command} {switches(args)}")
        else:
            self.server.add_task(
                f"{command} --directory {self.directory} "
                f"--{' --'.join(tasks)}")
