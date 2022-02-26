# -----------------------------------------------------------------------------
# Copyright (c) 2015-2022, AXMAS Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import logging
import logging.handlers
import operator
import os
import platform
import shutil
import subprocess
import timeit
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime

import h5py as h5
import numpy as np
import scipy
from h5py import is_hdf5
from nexusformat.nexus import (NeXusError, NXattenuator, NXcollection, NXdata,
                               NXentry, NXfield, NXinstrument, NXlink, NXLock,
                               NXmonitor, NXnote, NXparameters, NXprocess,
                               NXreflections, NXroot, NXsource, nxgetmemory,
                               nxload, nxsetlock, nxsetlockexpiry, nxsetmemory)
from qtpy import QtCore

from . import __version__
from .nxdatabase import NXDatabase
from .nxrefine import NXRefine
from .nxserver import NXServer
from .nxsettings import NXSettings
from .nxsymmetry import NXSymmetry
from .nxutils import mask_volume, peak_search


class NXReduce(QtCore.QObject):
    """Data reduction workflow for single crystal diffuse x-ray scattering.

    All the components of the workflow required to reduce data from single
    crystals measured with high-energy synchrotron x-rays on a fast-area
    detector are defined as separate functions. The class is instantiated
    by the entry in the experimental NeXus file corresponding to a single
    360° rotation of the crystal.

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
        data : str, optional
            Path to the data field in the entry, by default 'data/data'
        extension : str, optional
            Extension of the raw data file, by default '.h5'
        path : str, optional
            Path to the raw data, by default '/entry/data/data'
        threshold : float, optional
            Threshold used to in Bragg peak searches, by default None
        min_pixels : int, optional
            Minimum number of pixels required in Bragg peak searches, by
            default 10
        first : int, optional
            First frame included in the data reduction, by default None
        last : int, optional
            Last frame included in the data reduction, by default None
        radius : float, optional
            Radius used in punching holes in inverse Angstroms, by default None
        monitor : str, optional
            Name of monitor used in normalizations, by default None
        norm : float, optional
            Value used to normalize monitor counts, by default None
        mask_parameters : dict, optional
            Thresholds and convolution sizes used to prepare 3D masks, by
            default None.
        Qh : tuple of floats, optional
            Minimum, step size, and maximum value of Qh array, by default None
        Qk : tuple of floats, optional
            Minimum, step size, and maximum value of Qk array, by default None
        Ql : tuple of floats, optional
            Minimum, step size, and maximum value of Ql array, by default None
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
        """

    def __init__(
            self, entry=None, directory=None, parent=None, entries=None,
            data='data/data', extension='.h5', path='/entry/data/data',
            threshold=None, min_pixels=None, first=None, last=None,
            monitor=None, norm=None, radius=None, mask_parameters=None,
            Qh=None, Qk=None, Ql=None,
            link=False, copy=False, maxcount=False, find=False, refine=False,
            prepare=False, transform=False, combine=False, pdf=False,
            lattice=False, regular=False, mask=False, overwrite=False,
            monitor_progress=False, gui=False):

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
                                             f'{self.sample}_{self.scan}.nxs')
            if entry is None:
                self.entry_name = 'entry'
            else:
                self.entry_name = entry
            self._root = None
        self.name = f"{self.sample}_{self.scan}/{self.entry_name}"
        self.base_directory = os.path.dirname(self.wrapper_file)
        self.parent_file = os.path.join(self.base_directory,
                                        self.sample+'_parent.nxs')

        self._data = data
        self._field_root = None
        self._field = None
        self._shape = None
        self._pixel_mask = None
        self._parent_root = None
        self._parent = parent
        self._entries = entries

        if extension.startswith('.'):
            self.extension = extension
        else:
            self.extension = '.' + extension
        self.path = path

        self._threshold = threshold
        self._min_pixels = min_pixels
        self._first = first
        self._last = last
        self._monitor = monitor
        self._norm = norm
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
        self.timer = {}

        self._stopped = False
        self._process_count = None

        self._default = None
        self._server = None
        self._db = None
        self._logger = None

        nxsetlock(600)
        nxsetlockexpiry(28800)

    start = QtCore.Signal(object)
    update = QtCore.Signal(object)
    result = QtCore.Signal(object)
    stop = QtCore.Signal()

    def __repr__(self):
        return f"NXReduce('{self.name}')"

    @property
    def task_directory(self):
        _directory = os.path.join(self.root_directory, 'tasks')
        if not os.path.exists(_directory):
            os.mkdir(_directory)
        return _directory

    @property
    def logger(self):
        if self._logger is None:
            self._logger = logging.getLogger(
                f"{self.label}/{self.sample}_{self.scan}['{self.entry_name}']")
            self._logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                "%(asctime)s %(name)-12s: %(message)s",
                datefmt='%Y-%m-%d %H:%M:%S')
            for handler in self._logger.handlers:
                self._logger.removeHandler(handler)
            if os.path.exists(
                    os.path.join(self.task_directory, 'nxlogger.pid')):
                socketHandler = logging.handlers.SocketHandler(
                    'localhost', logging.handlers.DEFAULT_TCP_LOGGING_PORT)
                self._logger.addHandler(socketHandler)
            else:
                fileHandler = logging.FileHandler(os.path.join(
                    self.task_directory,
                    'nxlogger.log'))
                fileHandler.setFormatter(formatter)
                self._logger.addHandler(fileHandler)
            if not self.gui:
                streamHandler = logging.StreamHandler()
                self._logger.addHandler(streamHandler)
        return self._logger

    @property
    def default(self):
        if self._default is None:
            try:
                self._default = NXSettings().settings['nxreduce']
            except Exception as error:
                self.logger.info(str(error))
        return self._default

    @property
    def server(self):
        if self._server is None:
            try:
                self._server = NXServer()
            except Exception as error:
                self.logger.info(str(error))
        return self._server

    @property
    def db(self):
        if self._db is None:
            try:
                self._db = NXDatabase(os.path.join(self.task_directory,
                                                   'nxdatabase.db'))
            except Exception as error:
                self.logger.info(str(error))
        return self._db

    @property
    def root(self):
        if self._root is None:
            self._root = nxload(self.wrapper_file, 'rw')
        return self._root

    @property
    def entry(self):
        if self.entry_name in self.root:
            return self.root[self.entry_name]
        else:
            return None

    @property
    def entries(self):
        if self._entries:
            return self._entries
        else:
            return [entry for entry in self.root.entries if entry != 'entry']

    @property
    def first_entry(self):
        if self.entries:
            return self.entry_name == self.entries[0]
        else:
            return None

    @property
    def data(self):
        if 'data' in self.entry:
            return self.entry['data']
        elif (self.entry_name == 'entry'
              and 'data' in self.root[self.entries[0]]):
            return self.root[self.entries[0]]['data']
        else:
            return None

    @property
    def field(self):
        if self._field is None:
            self._field = self.data.nxsignal
            self._shape = self._field.shape
        return self._field

    @property
    def shape(self):
        if self._shape is None:
            self._shape = self.field.shape
        return self._shape

    @property
    def nframes(self):
        return self.shape[0]

    @property
    def data_file(self):
        return self.entry[self._data].nxfilename

    def data_exists(self):
        return is_hdf5(self.data_file)

    @property
    def pixel_mask(self):
        if self._pixel_mask is None:
            try:
                self._pixel_mask = (
                    self.entry['instrument/detector/pixel_mask'].nxvalue)
            except Exception as error:
                pass
        return self._pixel_mask

    @pixel_mask.setter
    def pixel_mask(self, mask):
        with self.entry.nxfile:
            self.entry['instrument/detector/pixel_mask'] = mask

    @property
    def parent_root(self):
        if self._parent_root is None:
            self._parent_root = nxload(self.parent_file, 'r')
        return self._parent_root

    @property
    def parent(self):
        if self._parent is None:
            if (not self.is_parent()
                    and os.path.exists(os.path.realpath(self.parent_file))):
                self._parent = os.path.realpath(self.parent_file)
        return self._parent

    def is_parent(self):
        if (os.path.exists(self.parent_file) and
                os.path.realpath(self.parent_file) == self.wrapper_file):
            return True
        else:
            return False

    def make_parent(self):
        if self.is_parent():
            self.logger.info(f"'{self.wrapper_file}' already set as parent")
            return
        elif os.path.exists(self.parent_file):
            if self.overwrite:
                os.remove(self.parent_file)
            else:
                raise NeXusError(f"'{os.path.realpath(self.parent_file)}' "
                                 "already set as parent")
        self.record_start('nxcopy')
        os.symlink(os.path.basename(self.wrapper_file), self.parent_file)
        self.record('nxcopy', parent=self.wrapper_file)
        self.record_end('nxcopy')
        self._parent = None
        self.logger.info(
            f"'{os.path.realpath(self.parent_file)}' set as parent")

    def get_parameter(self, name, field_name=None):
        parameter = self.default[name]
        if field_name is None:
            field_name = name
        if (self.parent and 'nxreduce' in self.parent_root['entry']
                and field_name in self.parent_root['entry/nxreduce']):
            parameter = self.parent_root['entry/nxreduce'][field_name]
        elif ('nxreduce' in self.root['entry']
              and field_name in self.root['entry/nxreduce']):
            parameter = self.root['entry/nxreduce'][field_name]
        return parameter

    def write_parameters(self, threshold=None, first=None, last=None,
                         monitor=None, norm=None, radius=None):
        if not (threshold or first or last or monitor or norm or radius):
            return
        with self.root.nxfile:
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
            if monitor is not None:
                self.monitor = monitor
                self.root['entry/nxreduce/monitor'] = self.monitor
            if norm is not None:
                self.norm = norm
                self.root['entry/nxreduce/norm'] = self.norm
            if radius is not None:
                self.radius = radius
                self.root['entry/nxreduce/radius'] = self.radius

    def clear_parameters(self, parameters):
        """Remove legacy records of parameters."""
        parameters.append('width')
        for p in parameters:
            if 'peaks' in self.entry and p in self.entry['peaks'].attrs:
                del self.entry['peaks'].attrs[p]

    @property
    def first(self):
        if self._first is None:
            self._first = int(self.get_parameter('first', 'first_frame'))
        return self._first

    @first.setter
    def first(self, value):
        try:
            self._first = int(value)
        except ValueError:
            pass

    @property
    def last(self):
        if self._last is None:
            try:
                self.default['last'] = self.shape[0]
            except Exception:
                pass
            self._last = int(self.get_parameter('last', 'last_frame'))
        return self._last

    @last.setter
    def last(self, value):
        try:
            self._last = np.int(value)
        except ValueError:
            pass

    @property
    def threshold(self):
        if self._threshold is None:
            self._threshold = float(self.get_parameter('threshold'))
        return self._threshold

    @threshold.setter
    def threshold(self, value):
        self._threshold = value

    @property
    def min_pixels(self):
        if self._min_pixels is None:
            self._min_pixels = int(self.get_parameter('min_pixels'))
        return self._min_pixels

    @min_pixels.setter
    def min_pixels(self, value):
        self._min_pixels = int(value)

    @property
    def monitor(self):
        if self._monitor is None:
            self._monitor = str(self.get_parameter('monitor'))
        return self._monitor

    @monitor.setter
    def monitor(self, value):
        self._monitor = value

    @property
    def norm(self):
        if self._norm is None:
            self._norm = float(self.get_parameter('norm'))
        return self._norm

    @norm.setter
    def norm(self, value):
        self._norm = value

    @property
    def radius(self):
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

    def complete(self, task):
        if task == 'nxcombine' or task == 'nxmasked_combine':
            return task in self.root['entry']
        else:
            return task in self.entry

    def all_complete(self, task):
        """ Check that all entries for this temperature are done """
        complete = True
        for entry in self.entries:
            if task not in self.root[entry]:
                complete = False
        return complete

    def not_complete(self, task):
        return task not in self.entry or self.overwrite

    def start_progress(self, start, stop):
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
        if self.gui:
            _value = int(i/self._step)
            if _value > self._value:
                self.update.emit(_value)
                self._value = _value
        elif self.monitor_progress:
            print(f'\rFrame {i}', end='')

    def stop_progress(self):
        if self.monitor_progress:
            print('')
        self.stopped = True
        return timeit.default_timer()

    @property
    def stopped(self):
        return self._stopped

    @property
    def process_count(self):
        if self._process_count is None:
            pc = os.cpu_count()
            if pc <= 12:
                self._process_count = pc - 2
            elif pc <= 24:
                self._process_count = pc - 4
            else:
                self._process_count = int(float(pc)/4)
        return self._process_count

    @stopped.setter
    def stopped(self, value):
        self._stopped = value

    def record(self, task, **kwargs):
        """ Record that a task has finished. Update NeXus file and database """
        process = kwargs.pop('process', task)
        parameters = '\n'.join(
            [f"{k.replace('_', ' ').capitalize()}: {v}"
             for (k, v) in kwargs.items()])
        note = NXnote(process, (f'Current machine: {platform.node()}\n' +
                                f'Current directory: {self.directory}\n' +
                                parameters))
        with self.root.nxfile:
            if process in self.entry:
                del self.entry[process]
            self.entry[process] = NXprocess(
                program=f'{process}',
                sequence_index=len(self.entry.NXprocess) + 1,
                version='nxrefine v' + __version__, note=note)
            for key in [k for k in kwargs if k in self.default]:
                self.entry[process][key] = kwargs[key]

    def record_start(self, task):
        """ Record that a task has started. Update database """
        try:
            self.db.start_task(self.wrapper_file, task, self.entry_name)
            self.timer[task] = timeit.default_timer()
            self.logger.info(f"{self.name}: '{task}' started")
        except Exception as error:
            self.logger.info(str(error))

    def record_end(self, task):
        """ Record that a task has ended. Update database """
        try:
            self.db.end_task(self.wrapper_file, task, self.entry_name)
            elapsed_time = timeit.default_timer() - self.timer[task]
            self.logger.info(
                f"{self.name}: '{task}' complete ({elapsed_time:g} seconds)")
        except Exception as error:
            self.logger.info(str(error))

    def record_fail(self, task):
        """ Record that a task has failed. Update database """
        try:
            self.db.fail_task(self.wrapper_file, task, self.entry_name)
            elapsed_time = timeit.default_timer() - self.timer[task]
            self.logger.info(f"'{task}' failed ({elapsed_time:g} seconds)")
        except Exception as error:
            self.logger.info(str(error))

    def nxlink(self):
        if self.not_complete('nxlink') and self.link:
            if not self.data_exists():
                self.logger.info('Data file not available')
                return
            self.record_start('nxlink')
            self.link_data()
            logs = self.read_logs()
            if logs:
                self.transfer_logs(logs)
                self.record('nxlink', logs='Transferred')
                self.logger.info('Entry linked to raw data')
                self.record_end('nxlink')
            else:
                self.record_fail('nxlink')
        elif self.link:
            self.logger.info('Data already linked')

    def link_data(self):
        if self.field:
            with self.root.nxfile:
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
                    data_file = os.path.relpath(
                        self.data_file, os.path.dirname(self.wrapper_file))
                    self.entry['data/data'] = NXlink(self.path, data_file)
                    self.entry['data'].nxsignal = self.entry['data/data']
                    self.logger.info(
                        'Data group created and linked to external data')
                else:
                    if self.entry['data/frame_number'].shape != self.shape[0]:
                        del self.entry['data/frame_number']
                        self.entry['data/frame_number'] = frames
                        if 'frame_time' in self.entry['data']:
                            del self.entry['data/frame_time']
                        self.logger.info('Fixed frame number axis')
                    if 'data/frame_time' not in self.entry:
                        self.entry['data/frame_time'] = frame_time * frames
                        self.entry['data/frame_time'].attrs['units'] = 's'
                self.entry['data'].nxaxes = [self.entry['data/frame_number'],
                                             self.entry['data/y_pixel'],
                                             self.entry['data/x_pixel']]
                with self.field.nxfile as f:
                    time_path = (
                        'entry/instrument/NDAttributes/NDArrayTimeStamp')
                    if time_path in f:
                        start = datetime.fromtimestamp(f[time_path][0])
                        # In EPICS, the epoch started in 1990, not 1970
                        start_time = start.replace(
                            year=start.year+20).isoformat()
                        self.entry['start_time'] = start_time
                        self.entry['data/frame_time'].attrs['start'] = (
                            start_time)
        else:
            self.logger.info('No raw data loaded')

    def read_logs(self):
        head_file = os.path.join(self.directory, self.entry_name+'_head.txt')
        meta_file = os.path.join(self.directory, self.entry_name+'_meta.txt')
        if os.path.exists(head_file) and os.path.exists(meta_file):
            logs = NXcollection()
        else:
            if not os.path.exists(head_file):
                self.logger.info(
                    f"'{self.entry_name}_head.txt' does not exist")
            if not os.path.exists(meta_file):
                self.logger.info(
                    f"'{self.entry_name}_meta.txt' does not exist")
            return None
        with open(head_file) as f:
            lines = f.readlines()
        for line in lines:
            key, value = line.split(', ')
            value = value.strip('\n')
            try:
                value = np.float(value)
            except Exception:
                pass
            logs[key] = value
        meta_input = np.genfromtxt(meta_file, delimiter=',', names=True)
        for i, key in enumerate(meta_input.dtype.names):
            logs[key] = [array[i] for array in meta_input]
        return logs

    def transfer_logs(self, logs):
        with self.root.nxfile:
            if 'instrument' not in self.entry:
                self.entry['instrument'] = NXinstrument()
            if 'logs' in self.entry['instrument']:
                del self.entry['instrument/logs']
            self.entry['instrument/logs'] = logs
            frame_number = self.entry['data/frame_number']
            frames = frame_number.size
            if 'MCS1' in logs:
                if 'monitor1' in self.entry:
                    del self.entry['monitor1']
                data = logs['MCS1'][:frames]
                # Remove outliers at beginning and end of frames
                data[0] = data[1]
                data[-1] = data[-2]
                self.entry['monitor1'] = NXmonitor(NXfield(data, name='MCS1'),
                                                   frame_number)
                if 'data/frame_time' in self.entry:
                    self.entry['monitor1/frame_time'] = (
                        self.entry['data/frame_time'])
            if 'MCS2' in logs:
                if 'monitor2' in self.entry:
                    del self.entry['monitor2']
                data = logs['MCS2'][:frames]
                # Remove outliers at beginning and end of frames
                data[0] = data[1]
                data[-1] = data[-2]
                self.entry['monitor2'] = NXmonitor(NXfield(data, name='MCS2'),
                                                   frame_number)
                if 'data/frame_time' in self.entry:
                    self.entry['monitor2/frame_time'] = (
                        self.entry['data/frame_time'])
            if 'source' not in self.entry['instrument']:
                self.entry['instrument/source'] = NXsource()
            self.entry['instrument/source/name'] = 'Advanced Photon Source'
            self.entry['instrument/source/type'] = 'Synchrotron X-ray Source'
            self.entry['instrument/source/probe'] = 'x-ray'
            if 'Storage_Ring_Current' in logs:
                self.entry['instrument/source/current'] = (
                    logs['Storage_Ring_Current'])
            if 'SCU_Current' in logs:
                self.entry['instrument/source/undulator_current'] = (
                    logs['SCU_Current'])
            if 'UndulatorA_gap' in logs:
                self.entry['instrument/source/undulator_gap'] = (
                    logs['UndulatorA_gap'])
            if 'Calculated_filter_transmission' in logs:
                if 'attenuator' not in self.entry['instrument']:
                    self.entry['instrument/attenuator'] = NXattenuator()
                self.entry['instrument/attenuator/attenuator_transmission'] = (
                    logs['Calculated_filter_transmission'])

    def nxcopy(self):
        if not self.copy:
            return
        elif self.is_parent():
            self.logger.info('Set as parent; no parameters copied')
        elif self.not_complete('nxcopy'):
            self.record_start('nxcopy')
            if self.parent:
                self.copy_parameters()
                self.record('nxcopy', parent=self.parent)
                self.logger.info('Entry parameters copied from parent')
                self.record_end('nxcopy')
            else:
                self.logger.info('No parent defined or accessible')
                self.record_fail('nxcopy')
        else:
            self.logger.info('Parameters already copied')

    def copy_parameters(self):
        parent = self.parent_root
        parent_refine = NXRefine(parent[self.entry_name])
        parent_reduce = NXReduce(parent[self.entry_name])
        refine = NXRefine(self.entry)
        parent_refine.copy_parameters(refine, sample=True, instrument=True)
        self.write_parameters(threshold=parent_reduce.threshold,
                              first=parent_reduce.first,
                              last=parent_reduce.last,
                              monitor=parent_reduce.monitor,
                              norm=parent_reduce.norm,
                              radius=parent_reduce.radius)
        self.logger.info(
            f"Parameters for {self.name} copied from "
            f"'{os.path.basename(os.path.realpath(self.parent))}'")

    def nxmax(self):
        if self.not_complete('nxmax') and self.maxcount:
            if not self.data_exists():
                self.logger.info('Data file not available')
                return
            self.record_start('nxmax')
            maximum = self.find_maximum()
            if self.gui:
                if maximum:
                    self.result.emit(maximum)
                self.stop.emit()
            else:
                self.write_maximum(maximum)
                self.write_parameters(first=self.first, last=self.last)
                self.record('nxmax', maximum=maximum,
                            first_frame=self.first, last_frame=self.last)
                self.record_end('nxmax')
        elif self.maxcount:
            self.logger.info('Maximum counts already found')

    def find_maximum(self):
        self.logger.info('Finding maximum counts')
        with self.field.nxfile:
            maximum = 0.0
            chunk_size = self.field.chunks[0]
            if chunk_size < 20:
                chunk_size = 50
            if self.first is None:
                self.first = 0
            if self.last is None:
                self.last = self.nframes
            data = self.field.nxfile[self.path]
            fsum = np.zeros(self.nframes, dtype=np.float64)
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
            self.pixel_mask = pixel_mask
            # Start looping over the data
            tic = self.start_progress(self.first, self.last)
            for i in range(self.first, self.last, chunk_size):
                if self.stopped:
                    return None
                self.update_progress(i)
                try:
                    v = data[i:i+chunk_size, :, :]
                except IndexError as error:
                    pass
                if i == self.first:
                    vsum = v.sum(0)
                else:
                    vsum += v.sum(0)
                if pixel_mask is not None:
                    v = np.ma.masked_array(v)
                    v.mask = pixel_mask
                fsum[i:i+chunk_size] = v.sum((1, 2))
                if maximum < v.max():
                    maximum = v.max()
                del v
        if pixel_mask is not None:
            vsum = np.ma.masked_array(vsum)
            vsum.mask = pixel_mask
        self.summed_data = NXfield(vsum, name='summed_data')
        self.summed_frames = NXfield(fsum, name='summed_frames')
        toc = self.stop_progress()
        self.logger.info(f'Maximum counts: {maximum} ({(toc-tic):g} seconds)')
        return maximum

    def write_maximum(self, maximum):
        with self.root.nxfile:
            self.entry['data'].attrs['maximum'] = maximum
            self.entry['data'].attrs['first'] = self.first
            self.entry['data'].attrs['last'] = self.last
            if 'summed_data' in self.entry:
                del self.entry['summed_data']
            self.entry['summed_data'] = NXdata(self.summed_data,
                                               self.entry['data'].nxaxes[-2:])
            if 'summed_frames' in self.entry:
                del self.entry['summed_frames']
            self.entry['summed_frames'] = NXdata(self.summed_frames,
                                                 self.entry['data'].nxaxes[0])
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
            polarization = ai.polarization(factor=0.99)
            counts = (self.summed_data.nxvalue.filled(fill_value=0)
                      / polarization)
            polar_angle, intensity = ai.integrate1d(
                counts, 2048, unit='2th_deg', mask=self.pixel_mask,
                correctSolidAngle=True, method=('no', 'histogram', 'cython'))
            Q = (4 * np.pi * np.sin(np.radians(polar_angle) / 2.0)
                 / (ai.wavelength * 1e10))
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
            self.logger.info('Unable to create radial sum')
            self.logger.info(str(error))
            return None

    def nxfind(self):
        if self.not_complete('nxfind') and self.find:
            if not self.data_exists():
                self.logger.info('Data file not available')
                return
            self.record_start('nxfind')
            peaks = self.find_peaks()
            if self.gui:
                if peaks:
                    self.result.emit(peaks)
                self.stop.emit()
            elif peaks:
                self.write_peaks(peaks)
                self.write_parameters(
                    threshold=self.threshold, first=self.first, last=self.last)
                self.record('nxfind', threshold=self.threshold,
                            first=self.first, last=self.last,
                            peak_number=len(peaks))
                self.record_end('nxfind')
            else:
                self.record_fail('nxfind')
        elif self.find:
            self.logger.info('Peaks already found')

    def find_peaks(self):
        self.logger.info("Finding peaks")

        tic = self.start_progress(self.first, self.last)
        self.blobs = []
        with ProcessPoolExecutor(max_workers=self.process_count) as executor:
            futures = []
            for i in range(self.first, self.last+1, 50):
                j, k = i - min(5, i), min(i+55, self.last+5, self.nframes)
                futures.append(executor.submit(
                    peak_search, self.field.nxfilename, self.field.nxfilepath,
                    i, j, k, self.threshold))
            for future in as_completed(futures):
                z, blobs = future.result()
                self.blobs += [b for b in blobs if b.z >= z
                               and b.z < min(z+50, self.last)
                               and b.is_valid(self.pixel_mask, self.min_pixels)
                               ]
                self.update_progress(z)
                futures.remove(future)

        peaks = sorted([b for b in self.blobs], key=operator.attrgetter('z'))

        toc = self.stop_progress()
        self.logger.info(f'{len(peaks)} peaks found ({toc - tic:g} seconds)')
        return peaks

    def write_peaks(self, peaks):
        group = NXreflections()
        group['npixels'] = NXfield([peak.np for peak in peaks], dtype=float)
        group['intensity'] = NXfield([peak.intensity for peak in peaks],
                                     dtype=float)
        group['x'] = NXfield([peak.x for peak in peaks], dtype=float)
        group['y'] = NXfield([peak.y for peak in peaks], dtype=float)
        group['z'] = NXfield([peak.z for peak in peaks], dtype=float)
        group['sigx'] = NXfield([peak.sigx for peak in peaks], dtype=float)
        group['sigy'] = NXfield([peak.sigy for peak in peaks], dtype=float)
        group['sigz'] = NXfield([peak.sigz for peak in peaks], dtype=float)
        group['covxy'] = NXfield([peak.covxy for peak in peaks], dtype=float)
        group['covyz'] = NXfield([peak.covyz for peak in peaks], dtype=float)
        group['covzx'] = NXfield([peak.covzx for peak in peaks], dtype=float)
        group.attrs['first'] = self.first
        group.attrs['last'] = self.last
        group.attrs['threshold'] = self.threshold
        with self.root.nxfile:
            if 'peaks' in self.entry:
                del self.entry['peaks']
            self.entry['peaks'] = group
            refine = NXRefine(self.entry)
            polar_angles, azimuthal_angles = refine.calculate_angles(refine.xp,
                                                                     refine.yp)
            refine.write_angles(polar_angles, azimuthal_angles)
        self.clear_parameters(['threshold', 'first', 'last'])

    def nxrefine(self):
        if self.not_complete('nxrefine') and self.refine:
            if not self.complete('nxfind'):
                self.logger.info(
                    'Cannot refine until peak search is completed')
                return
            self.record_start('nxrefine')
            self.logger.info('Refining orientation')
            if self.lattice or self.first_entry:
                lattice = True
            else:
                lattice = False
            result = self.refine_parameters(lattice=lattice)
            if result:
                if not self.gui:
                    self.write_refinement(result)
                self.record('nxrefine', fit_report=result.fit_report)
                self.record_end('nxrefine')
            else:
                self.record_fail('nxrefine')
        elif self.refine:
            self.logger.info('HKL values already refined')

    def refine_parameters(self, lattice=False):
        with self.root.nxfile:
            refine = NXRefine(self.entry)
            refine.refine_hkls(lattice=lattice, chi=True, omega=True)
            fit_report = refine.fit_report
            refine.refine_hkls(chi=True, omega=True)
            fit_report = fit_report + '\n' + refine.fit_report
            refine.refine_orientation_matrix()
            fit_report = fit_report + '\n' + refine.fit_report
            if refine.result.success:
                refine.fit_report = fit_report
                self.logger.info('Refined HKL values')
                return refine
            else:
                self.logger.info('HKL refinement not successful')
                return None

    def write_refinement(self, refine):
        with self.root.nxfile:
            refine.write_parameters()

    def nxprepare(self):
        if self.not_complete('nxprepare_mask') and self.prepare:
            self.record_start('nxprepare')
            self.logger.info('Preparing 3D mask')
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
        elif self.prepare:
            self.logger.info('3D Mask already prepared')

    def prepare_mask(self):
        """Prepare 3D mask"""
        tic = self.start_progress(self.first, self.last)
        t1 = self.mask_parameters['threshold_1']
        h1 = self.mask_parameters['horizontal_size_1']
        t2 = self.mask_parameters['threshold_2']
        h2 = self.mask_parameters['horizontal_size_2']

        mask_root = nxload(self.mask_file+'.h5', 'w')
        mask_root['entry'] = NXentry()
        mask_root['entry/mask'] = (
            NXfield(shape=self.shape, dtype=np.int8, fillvalue=0))

        with ProcessPoolExecutor(max_workers=self.process_count) as executor:
            futures = []
            for i in range(self.first, self.last+1, 10):
                j, k = i - min(1, i), min(i+11, self.last+1, self.nframes)
                futures.append(executor.submit(
                    mask_volume, self.field.nxfilename, self.field.nxfilepath,
                    mask_root.nxfilename, 'entry/mask', i, j, k,
                    self.pixel_mask, t1, h1, t2, h2))
            for future in as_completed(futures):
                k = future.result()
                self.update_progress(k)
                futures.remove(future)

        frame_mask = np.ones(shape=self.shape[1:], dtype=np.int8)
        with mask_root.nxfile:
            mask_root['entry/mask'][:self.first] = frame_mask
            mask_root['entry/mask'][self.last+1:] = frame_mask

        toc = self.stop_progress()

        self.logger.info(f"3D Mask prepared in {toc-tic:g} seconds")

        return mask_root['entry/mask']

    def write_mask(self, mask):
        """Write mask to file."""
        if os.path.exists(self.mask_file):
            os.remove(self.mask_file)
        shutil.move(mask.nxfilename, self.mask_file)

        if ('data_mask' in self.data
                and self.data['data_mask'].nxfilename != self.mask_file):
            del self.data['data_mask']
        if 'data_mask' not in self.data:
            self.data['data_mask'] = NXlink('entry/mask', self.mask_file)

        self.logger.info(f"3D Mask written to '{self.mask_file}'")

    def nxtransform(self, mask=False):
        if mask:
            task = 'nxmasked_transform'
            process = 'Masked transform'
            self.transform_file = os.path.join(
                self.directory, self.entry_name+'_masked_transform.nxs')
        else:
            task = 'nxtransform'
            process = 'Transform'
            self.transform_file = os.path.join(
                self.directory, self.entry_name+'_transform.nxs')
        if self.not_complete(task) and self.transform:
            if not self.complete('nxrefine'):
                self.logger.info(
                    'Cannot transform until the orientation is complete')
                return
            self.record_start(task)
            cctw_command = self.prepare_transform(mask=mask)
            if cctw_command:
                self.logger.info(f"{process} process launched")
                tic = timeit.default_timer()
                with self.field.nxfile:
                    with NXLock(self.transform_file):
                        process = subprocess.run(cctw_command, shell=True,
                                                 stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE)
                toc = timeit.default_timer()
                if process.returncode == 0:
                    self.logger.info(
                        f'{process} completed ({toc - tic:g} seconds)')
                    self.write_parameters(monitor=self.monitor, norm=self.norm)
                    self.record(task, monitor=self.monitor, norm=self.norm,
                                command=cctw_command,
                                output=process.stdout.decode(),
                                errors=process.stderr.decode())
                    self.record_end(task)
                    self.clear_parameters(['monitor', 'norm'])
                else:
                    self.logger.info(
                        f"{process} completed - errors reported "
                        f"({(toc-tic):g} seconds)")
                    self.record_fail(task)
            else:
                self.logger.info('CCTW command invalid')
                self.record_fail(task)
        elif self.transform:
            self.logger.info(f'{process} already created')

    def get_transform_grid(self, mask=False):
        if self.Qh and self.Qk and self.Ql:
            try:
                self.Qh = [np.float32(v) for v in self.Qh]
                self.Qk = [np.float32(v) for v in self.Qk]
                self.Ql = [np.float32(v) for v in self.Ql]
            except Exception:
                self.Qh = self.Qk = self.Ql = None
        else:
            if mask and 'masked_transform' in self.entry:
                transform = self.entry['masked_transform']
            elif 'transform' in self.entry:
                transform = self.entry['transform']
            elif self.parent:
                root = self.parent_root
                if mask and 'masked_transform' in root[self.entry_name]:
                    transform = root[self.entry_name]['masked_transform']
                elif 'transform' in root[self.entry_name]:
                    transform = root[self.entry_name]['transform']
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
        from scipy.signal import savgol_filter
        with self.root.nxfile:
            if self.norm and self.monitor in self.entry:
                monitor_signal = self.entry[self.monitor].nxsignal / self.norm
                monitor_signal[0] = monitor_signal[1]
                monitor_signal[-1] = monitor_signal[-2]
                self.data['monitor_weight'] = savgol_filter(monitor_signal,
                                                            501, 2)
            else:
                self.data['monitor_weight'] = np.ones(self.nframes,
                                                      dtype=np.float32)
            self.data['monitor_weight'][:self.first] = 0.0
            self.data['monitor_weight'][self.last+1:] = 0.0
            self.data['monitor_weight'].attrs['axes'] = 'frame_number'

    def prepare_transform(self, mask=False):
        settings_file = os.path.join(self.directory,
                                     self.entry_name+'_transform.pars')
        with self.root.nxfile:
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
                return command
            else:
                self.logger.info('Invalid HKL grid')
                return None

    def nxsum(self, scan_list, update=False):
        if os.path.exists(self.data_file) and not (self.overwrite or update):
            self.logger.info('Data already summed')
        elif not os.path.exists(self.directory):
            self.logger.info('Sum directory not created')
        else:
            self.record_start('nxsum')
            self.logger.info('Sum files launched')
            tic = timeit.default_timer()
            if not self.check_files(scan_list):
                self.record_fail('nxsum')
            else:
                self.logger.info('All files and metadata have been checked')
                if not update:
                    self.sum_files(scan_list)
                self.sum_monitors(scan_list)
                toc = timeit.default_timer()
                self.logger.info(f'Sum completed ({toc - tic:g} seconds)')
                self.record('nxsum', scans=','.join(scan_list))
                self.record_end('nxsum')

    def check_sum_files(self, scan_list):
        status = True
        for i, scan in enumerate(scan_list):
            reduce = NXReduce(self.entry_name,
                              os.path.join(self.base_directory, scan))
            if not os.path.exists(reduce.data_file):
                self.logger.info(f"'{reduce.data_file}' does not exist")
                status = False
            elif 'monitor1' not in reduce.entry:
                self.logger.info(
                    f"Monitor1 not present in {reduce.wrapper_file}")
                status = False
        return status

    def sum_files(self, scan_list):

        nframes = 3650
        chunk_size = 500
        for i, scan in enumerate(scan_list):
            reduce = NXReduce(self.entry_name,
                              os.path.join(self.base_directory, scan))
            self.logger.info(
                f"Summing {self.entry_name} in '{reduce.data_file}'")
            if i == 0:
                shutil.copyfile(reduce.data_file, self.data_file)
                new_file = h5.File(self.data_file, 'r+')
                new_field = new_file[self.path]
            else:
                scan_file = h5.File(reduce.data_file, 'r')
                scan_field = scan_file[self.path]
                for i in range(0, nframes, chunk_size):
                    new_slab = new_field[i:i+chunk_size, :, :]
                    scan_slab = scan_field[i:i+chunk_size, :, :]
                    new_field[i:i+chunk_size, :, :] = new_slab + scan_slab
        self.logger.info("Raw data files summed")

    def sum_monitors(self, scan_list, update=False):

        for i, scan in enumerate(scan_list):
            reduce = NXReduce(self.entry_name,
                              os.path.join(self.base_directory, scan))
            self.logger.info(
                f"Adding {self.entry_name} monitors in "
                f"'{reduce.wrapper_file}'")
            if i == 0:
                monitor1 = reduce.entry['monitor1/MCS1'].nxvalue
                monitor2 = reduce.entry['monitor2/MCS2'].nxvalue
                if 'monitor_weight' not in reduce.entry['data']:
                    reduce.get_normalization()
                monitor_weight = reduce.entry['data/monitor_weight'].nxvalue
                if os.path.exists(reduce.mask_file):
                    shutil.copyfile(reduce.mask_file, self.mask_file)
            else:
                monitor1 += reduce.entry['monitor1/MCS1'].nxvalue
                monitor2 += reduce.entry['monitor2/MCS2'].nxvalue
                if 'monitor_weight' not in reduce.entry['data']:
                    reduce.get_normalization()
                monitor_weight += reduce.entry['data/monitor_weight'].nxvalue
        with self.root.nxfile:
            self.entry['monitor1/MCS1'] = monitor1
            self.entry['monitor2/MCS2'] = monitor2
            self.entry['data/monitor_weight'] = monitor_weight

    def nxreduce(self):
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
                self.logger.info('Cannot refine orientation matrix')
                self.record_fail('nxrefine')
        if self.prepare:
            self.nxprepare()
        if self.transform and self.complete('nxrefine'):
            if self.regular:
                self.nxtransform()
            if self.mask:
                self.nxtransform(mask=True)
        elif self.transform:
            self.logger.info('Cannot transform without orientation matrix')
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
            raise NeXusError("NXServer not running")

        tasks = []
        if self.link:
            tasks.append('link')
            self.db.queue_task(self.wrapper_file, 'nxlink', self.entry_name)
        if self.copy:
            tasks.append('copy')
            self.db.queue_task(self.wrapper_file, 'nxcopy', self.entry_name)
        if self.maxcount:
            tasks.append('max')
            self.db.queue_task(self.wrapper_file, 'nxmax', self.entry_name)
        if self.find:
            tasks.append('find')
            self.db.queue_task(self.wrapper_file, 'nxfind', self.entry_name)
        if self.refine:
            tasks.append('refine')
            self.db.queue_task(self.wrapper_file, 'nxrefine', self.entry_name)
        if self.prepare:
            tasks.append('prepare')
            self.db.queue_task(self.wrapper_file, 'nxprepare', self.entry_name)
        if self.transform:
            tasks.append('transform')
            if self.regular:
                self.db.queue_task(self.wrapper_file, 'nxtransform',
                                   self.entry_name)
            if self.mask:
                self.db.queue_task(self.wrapper_file, 'nxmasked_transform',
                                   self.entry_name)
        if self.combine:
            tasks.append('combine')
            if self.regular:
                self.db.queue_task(self.wrapper_file, 'nxcombine',
                                   self.entry_name)
            if self.mask:
                self.db.queue_task(self.wrapper_file, 'nxmasked_combine',
                                   self.entry_name)
        if self.pdf:
            tasks.append('pdf')
            if self.regular:
                self.db.queue_task(self.wrapper_file, 'nxpdf',
                                   self.entry_name)
            if self.mask:
                self.db.queue_task(self.wrapper_file, 'nxmasked_pdf',
                                   self.entry_name)

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
            self.server.add_task(f"{command} {switches(args)}")
        else:
            self.server.add_task(
                f"{command} --directory {self.directory} "
                f"--entries {self.entry_name} --{' --'.join(tasks)}")


class NXMultiReduce(NXReduce):

    def __init__(self, directory, entries=None,
                 combine=False, pdf=False, regular=False, mask=False,
                 laue=None, radius=None, overwrite=False):
        if isinstance(directory, NXroot):
            entry = directory['entry']
        else:
            entry = 'entry'
        super(
            NXMultiReduce, self).__init__(
            entry=entry, directory=directory, entries=entries,
            overwrite=overwrite)
        self.refine = NXRefine(self.root[self.entries[0]])

        if laue:
            if laue in self.refine.laue_groups:
                self.refine.laue_group = laue
            else:
                raise NeXusError('Invalid Laue group specified')
        self._radius = radius

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
        complete = True
        if task == 'nxcombine' or task == 'nxmasked_combine':
            if task not in self.entry:
                complete = False
        elif task == 'nxtransform' or task == 'nxmasked_transform':
            for entry in self.entries:
                if task not in self.root[entry]:
                    complete = False
            if not complete and task == 'nxmasked_transform':
                complete = True
                for entry in self.entries:
                    if 'nxmask' not in self.root[entry]:
                        complete = False
        return complete

    def nxcombine(self, mask=False):
        if mask:
            task = 'nxmasked_combine'
            transform_task = 'nxmasked_transform'
            title = 'Masked Combine'
            self.transform_file = os.path.join(self.directory,
                                               'masked_transform.nxs')
        else:
            task = 'nxcombine'
            transform_task = 'nxtransform'
            title = 'Combine'
            self.transform_file = os.path.join(self.directory, 'transform.nxs')
        if self.not_complete(task) and self.combine:
            if not self.complete(transform_task):
                self.logger.info(
                    f'{title}: Cannot combine until transforms complete')
                return
            self.record_start(task)
            cctw_command = self.prepare_combine()
            if cctw_command:
                if self.mask:
                    self.logger.info("Combining masked transforms "
                                     f"({', '.join(self.entries)})")
                    transform_path = 'masked_transform/data'
                else:
                    self.logger.info("Combining transforms "
                                     f"({', '.join(self.entries)})")
                    transform_path = 'transform/data'
                tic = timeit.default_timer()
                with NXLock(self.transform_file):
                    if os.path.exists(self.transform_file):
                        os.remove(self.transform_file)
                    data_lock = {}
                    for entry in self.entries:
                        data_lock[entry] = NXLock(
                            self.root[entry][transform_path].nxfilename)
                        data_lock[entry].acquire()
                    process = subprocess.run(cctw_command, shell=True,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
                    for entry in self.entries:
                        data_lock[entry].release()
                toc = timeit.default_timer()
                if process.returncode == 0:
                    self.logger.info(
                        f"{title} ({', '.join(self.entries)}) "
                        f"completed ({toc-tic:g} seconds)")
                    self.record(task, command=cctw_command,
                                output=process.stdout.decode(),
                                errors=process.stderr.decode())
                    self.record_end(task)
                else:
                    self.logger.info(
                        f"{title} ({', '.join(self.entries)}) completed "
                        f"- errors reported ({(toc-tic):g} seconds)")
                    self.record_fail('nxcombine')
            else:
                self.logger.info('CCTW command invalid')
        else:
            self.logger.info('Data already combined')

    def prepare_combine(self):
        if self.mask:
            transform = 'masked_transform'
        else:
            transform = 'transform'
        try:
            with self.root.nxfile:
                entry = self.entries[0]
                Qh, Qk, Ql = (self.root[entry][transform]['Qh'],
                              self.root[entry][transform]['Qk'],
                              self.root[entry][transform]['Ql'])
                data = NXlink('/entry/data/v',
                              file=os.path.join(self.scan, transform+'.nxs'),
                              name='data')
                if transform in self.entry:
                    del self.entry[transform]
                self.entry[transform] = NXdata(data, [Ql, Qk, Qh])
                self.entry[transform].attrs['angles'] = (
                    self.root[entry][transform].attrs['angles'])
                self.entry[transform].set_default(over=True)
        except Exception as error:
            self.logger.info('Unable to initialize transform group')
            self.logger.info(str(error))
            return None
        input = ' '.join([os.path.join(
            self.directory,
            fr'{entry}_{transform}.nxs\#/entry/data')
            for entry in self.entries])
        output = os.path.join(self.directory,
                              transform+r'.nxs\#/entry/data/v')
        return f'cctw merge {input} -o {output}'

    def nxpdf(self, mask=False):
        if mask:
            task = 'nxmasked_pdf'
            self.transform = 'masked_transform'
            self.symm_transform = 'symm_masked_transform'
            self.symm_file = os.path.join(self.directory,
                                          'masked_symm_transform.nxs')
            self.total_pdf_file = os.path.join(self.directory,
                                               'masked_total_pdf.nxs')
            self.pdf_file = os.path.join(self.directory, 'masked_pdf.nxs')
        else:
            task = 'nxpdf'
            self.transform = 'transform'
            self.symm_transform = 'symm_transform'
            self.symm_file = os.path.join(self.directory, 'symm_transform.nxs')
            self.total_pdf_file = os.path.join(self.directory, 'total_pdf.nxs')
            self.pdf_file = os.path.join(self.directory, 'pdf.nxs')
        if self.not_complete(task) and self.pdf:
            if mask:
                if not self.complete('nxmasked_combine'):
                    self.logger.info("Cannot calculate PDF until the "
                                     "masked transforms are combined")
                    return
            elif not self.complete('nxcombine'):
                self.logger.info(
                    "Cannot calculate PDF until the transforms are combined")
                return
            elif self.refine.laue_group not in self.refine.laue_groups:
                self.logger.info(
                    "Need to define a valid Laue group before PDF calculation")
                return
            self.record_start('nxpdf')
            self.set_memory()
            self.symmetrize_transform()
            self.total_pdf()
            self.punch_holes()
            self.punch_and_fill()
            self.delta_pdf()
            self.write_parameters(radius=self.radius)
            self.record(task, laue=self.refine.laue_group, radius=self.radius)
            self.record_end(task)
        else:
            self.logger.info('PDF already calculated')

    def set_memory(self):
        total_size = self.entry[self.transform].nxsignal.nbytes / 1e6
        if total_size > nxgetmemory():
            nxsetmemory(total_size + 1000)

    def symmetrize_transform(self):
        if os.path.exists(self.symm_file):
            if self.overwrite:
                os.remove(self.symm_file)
            else:
                self.logger.info('Symmetrized data already exists')
                return
        self.logger.info('Transform being symmetrized')
        tic = timeit.default_timer()
        for i, entry in enumerate(self.entries):
            r = NXReduce(self.root[entry])
            if i == 0:
                summed_data = r.entry[self.transform].nxsignal.nxvalue
                summed_weights = r.entry[self.transform].nxweights.nxvalue
                summed_axes = r.entry[self.transform].nxaxes
            else:
                summed_data += r.entry[self.transform].nxsignal.nxvalue
                summed_weights += r.entry[self.transform].nxweights.nxvalue
        summed_transforms = NXdata(NXfield(summed_data, name='data'),
                                   summed_axes, weights=summed_weights)
        symmetry = NXSymmetry(summed_transforms,
                              laue_group=self.refine.laue_group)
        root = nxload(self.symm_file, 'a')
        root['entry'] = NXentry()
        root['entry/data'] = symmetry.symmetrize()
        root['entry/data'].nxweights = self.fft_weights(
            root['entry/data'].shape)
        if self.symm_transform in self.entry:
            del self.entry[self.symm_transform]
        symm_data = NXlink('/entry/data/data',
                           file=self.symm_file, name='data')
        self.entry[self.symm_transform] = NXdata(
            symm_data, self.entry[self.transform].nxaxes)
        self.entry[self.symm_transform]['data_weights'] = NXlink(
            '/entry/data/data_weights', file=self.symm_file)
        self.logger.info(f"'{self.symm_transform}' added to entry")
        toc = timeit.default_timer()
        self.logger.info(f'Symmetrization completed ({toc-tic:g} seconds)')

    def fft_weights(self, shape, alpha=0.5):
        from scipy.signal import tukey
        x = tukey(shape[2], alpha=alpha)
        y = tukey(shape[1], alpha=alpha)
        z = tukey(shape[0], alpha=alpha)
        return np.einsum('i,j,k->ijk', 1.0/np.where(z > 0, z, z[1]/2),
                         1.0/np.where(y > 0, y, y[1]/2),
                         1.0/np.where(x > 0, x, x[1]/2))

    def fft_taper(self, shape, alpha=0.5):
        from scipy.signal import tukey
        x = tukey(shape[2], alpha=alpha)
        y = tukey(shape[1], alpha=alpha)
        z = tukey(shape[0], alpha=alpha)
        return np.einsum('i,j,k->ijk', z, y, x)

    def total_pdf(self):
        self.logger.info('Calculating total PDF')
        if os.path.exists(self.total_pdf_file):
            if self.overwrite:
                os.remove(self.total_pdf_file)
            else:
                self.logger.info('Total PDF file already exists')
                return
        tic = timeit.default_timer()
        symm_data = self.entry[
            self.symm_transform].nxsignal[:-1, :-1, :-1].nxvalue
        symm_data *= self.fft_taper(symm_data.shape)
        fft = np.real(np.fft.fftshift(
            scipy.fft.fftn(np.fft.fftshift(symm_data),
                           workers=self.process_count)))
        fft *= (1.0 / np.prod(fft.shape))

        root = nxload(self.total_pdf_file, 'a')
        root['entry'] = NXentry()
        root['entry/pdf'] = NXdata(NXfield(fft, name='pdf'))

        if 'total_pdf' in self.entry:
            del self.entry['total_pdf']
        pdf = NXlink('/entry/pdf/pdf', file=self.total_pdf_file, name='pdf')

        dl, dk, dh = [(ax[1]-ax[0]).nxvalue
                      for ax in self.entry[self.symm_transform].nxaxes]
        x = NXfield(np.fft.fftshift(np.fft.fftfreq(
            fft.shape[2], dh)), name='x', scaling_factor=self.refine.a)
        y = NXfield(np.fft.fftshift(np.fft.fftfreq(
            fft.shape[1], dk)), name='y', scaling_factor=self.refine.b)
        z = NXfield(np.fft.fftshift(np.fft.fftfreq(
            fft.shape[0], dl)), name='z', scaling_factor=self.refine.c)
        self.entry['total_pdf'] = NXdata(pdf, (z, y, x))
        self.entry['total_pdf'].attrs['angles'] = (
            self.refine.lattice_parameters[3:])
        self.logger.info("'total_pdf' added to entry")
        toc = timeit.default_timer()
        self.logger.info(f'Total PDF calculated ({toc - tic:g} seconds)')

    def hole_mask(self):
        symm_group = self.entry[self.symm_transform]
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
        self.refine.polar_max = self.refine.two_theta_max()
        if self.refine.laue_group in ['-3', '-3m', '6/m', '6/mmm']:
            _indices = []
            for idx in self.refine.indices:
                _indices += self.refine.indices_hkl(*idx)
            return _indices
        else:
            return self.refine.indices

    def symmetrize(self, data):
        if self.refine.laue_group in ['-3', '-3m', '6/m', '6/mmm']:
            return data
        else:
            symmetry = NXSymmetry(data, laue_group=self.refine.laue_group)
            return symmetry.symmetrize()

    def punch_holes(self):
        self.logger.info('Punching holes')
        if (self.symm_transform in self.entry and
                'punched_data' in self.entry[self.symm_transform]):
            if self.overwrite:
                del self.entry[self.symm_transform]['punched_data']
            else:
                self.logger.info('Punched holes already exists')
                return
        tic = timeit.default_timer()
        symm_group = self.entry[self.symm_transform]
        Qh, Qk, Ql = (symm_group['Qh'], symm_group['Qk'], symm_group['Ql'])

        root = nxload(self.symm_file, 'rw')
        entry = root['entry']

        mask, _ = self.hole_mask()
        ml = int((mask.shape[0]-1)/2)
        mk = int((mask.shape[1]-1)/2)
        mh = int((mask.shape[2]-1)/2)
        symm_data = entry['data/data'].nxdata
        punch_data = np.zeros(shape=symm_data.shape, dtype=symm_data.dtype)
        for h, k, l in self.indices:
            try:
                ih = np.argwhere(np.isclose(Qh, h))[0][0]
                ik = np.argwhere(np.isclose(Qk, k))[0][0]
                il = np.argwhere(np.isclose(Ql, l))[0][0]
                lslice = slice(il-ml, il+ml+1)
                kslice = slice(ik-mk, ik+mk+1)
                hslice = slice(ih-mh, ih+mh+1)
                punch_data[(lslice, kslice, hslice)] = mask
            except Exception:
                pass
        punch_data = self.symmetrize(punch_data)
        changed_idx = np.where(punch_data > 0)
        symm_data[changed_idx] *= 0

        if 'punch' in entry['data']:
            del entry['data/punch']
        entry['data/punch'] = symm_data
        self.entry[self.symm_transform]['punched_data'] = NXlink(
            '/entry/data/punch', file=self.symm_file)
        self.logger.info(f"'punched_data' added to '{self.symm_transform}'")

        toc = timeit.default_timer()
        self.logger.info(f'Punches completed ({toc - tic:g} seconds)')
        self.clear_parameters(['radius'])

    def init_julia(self):
        if self.julia is None:
            try:
                from julia import Julia
                self.julia = Julia(compiled_modules=False)
                import pkg_resources

                from julia import Main
                Main.include(pkg_resources.resource_filename(
                    'nxrefine', 'julia/LaplaceInterpolation.jl'))
            except Exception as error:
                raise NeXusError(str(error))

    def punch_and_fill(self):
        self.logger.info('Performing punch-and-fill')
        if (self.symm_transform in self.entry and
                'filled_data' in self.entry[self.symm_transform]):
            if self.overwrite:
                del self.entry[self.symm_transform]['filled_data']
            else:
                self.logger.info('Data already punched-and-filled')
                return

        self.init_julia()
        from julia import Main
        LaplaceInterpolation = Main.LaplaceInterpolation

        tic = timeit.default_timer()
        symm_group = self.entry[self.symm_transform]
        Qh, Qk, Ql = (symm_group['Qh'], symm_group['Qk'], symm_group['Ql'])

        root = nxload(self.symm_file, 'rw')
        entry = root['entry']

        mask, mask_indices = self.hole_mask()
        idx = [Main.CartesianIndex(int(i[0]+1), int(i[1]+1), int(i[2]+1))
               for i in mask_indices]
        ml = int((mask.shape[0]-1)/2)
        mk = int((mask.shape[1]-1)/2)
        mh = int((mask.shape[2]-1)/2)
        symm_data = entry['data/data'].nxdata
        fill_data = np.zeros(shape=symm_data.shape, dtype=symm_data.dtype)
        self.refine.polar_max = self.refine.two_theta_max()
        for h, k, l in self.indices:
            try:
                ih = np.argwhere(np.isclose(Qh, h))[0][0]
                ik = np.argwhere(np.isclose(Qk, k))[0][0]
                il = np.argwhere(np.isclose(Ql, l))[0][0]
                lslice = slice(il-ml, il+ml+1)
                kslice = slice(ik-mk, ik+mk+1)
                hslice = slice(ih-mh, ih+mh+1)
                v = symm_data[(lslice, kslice, hslice)]
                if v.max() > 0.0:
                    w = LaplaceInterpolation.matern_3d_grid(v, idx)
                    fill_data[(lslice, kslice, hslice)] = w
            except Exception:
                pass
        fill_data = self.symmetrize(fill_data)
        changed_idx = np.where(fill_data > 0)
        symm_data[changed_idx] = fill_data[changed_idx]

        if 'fill' in entry['data']:
            del entry['data/fill']
        entry['data/fill'] = symm_data
        self.entry[self.symm_transform]['filled_data'] = NXlink(
            '/entry/data/fill', file=self.symm_file)
        self.logger.info(f"'filled_data' added to '{self.symm_transform}'")

        toc = timeit.default_timer()
        self.logger.info(f'Punch-and-fill completed ({toc - tic:g} seconds)')

    def delta_pdf(self):
        self.logger.info('Calculating Delta-PDF')
        if os.path.exists(self.pdf_file):
            if self.overwrite:
                os.remove(self.pdf_file)
            else:
                self.logger.info('Delta-PDF file already exists')
                return
        tic = timeit.default_timer()
        symm_data = (self.entry[self.symm_transform]['filled_data']
                     [:-1, :-1, :-1].nxvalue)
        symm_data *= self.fft_taper(symm_data.shape)
        fft = np.real(np.fft.fftshift(
            scipy.fft.fftn(np.fft.fftshift(symm_data),
                           workers=self.process_count)))
        fft *= (1.0 / np.prod(fft.shape))

        root = nxload(self.pdf_file, 'a')
        root['entry'] = NXentry()
        root['entry/pdf'] = NXdata(NXfield(fft, name='pdf'))

        if 'pdf' in self.entry:
            del self.entry['pdf']
        pdf = NXlink('/entry/pdf/pdf', file=self.pdf_file, name='pdf')

        dl, dk, dh = [(ax[1]-ax[0]).nxvalue
                      for ax in self.entry[self.symm_transform].nxaxes]
        x = NXfield(np.fft.fftshift(np.fft.fftfreq(
            fft.shape[2], dh)), name='x', scaling_factor=self.refine.a)
        y = NXfield(np.fft.fftshift(np.fft.fftfreq(
            fft.shape[1], dk)), name='y', scaling_factor=self.refine.b)
        z = NXfield(np.fft.fftshift(np.fft.fftfreq(
            fft.shape[0], dl)), name='z', scaling_factor=self.refine.c)
        self.entry['pdf'] = NXdata(pdf, (z, y, x))
        self.entry['pdf'].attrs['angles'] = self.refine.lattice_parameters[3:]
        self.logger.info("'pdf' added to entry")
        toc = timeit.default_timer()
        self.logger.info(f'Delta-PDF calculated ({toc - tic:g} seconds)')

    def nxsum(self, scan_list):
        if not os.path.exists(self.wrapper_file) or self.overwrite:
            for e in self.entries:
                reduce = NXReduce(self.root[e])
                status = reduce.check_sum_files(scan_list)
                if not status:
                    return status
            if not os.path.exists(self.directory):
                os.mkdir(self.directory)
            self.logger.info('Creating sum file')
            self.configure_sum_file(scan_list)
            self.logger.info('Sum file created')
        else:
            self.logger.info('Sum file already exists')

    def configure_sum_file(self, scan_list):
        shutil.copyfile(os.path.join(self.base_directory,
                                     self.sample+'_'+scan_list[0]+'.nxs'),
                        self.wrapper_file)
        with self.root.nxfile:
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
                self.db.queue_task(self.wrapper_file, 'nxcombine', 'entry')
            if self.mask:
                self.db.queue_task(self.wrapper_file, 'nxmasked_combine',
                                   'entry')
        if self.pdf:
            tasks.append('pdf')
            if self.regular:
                self.db.queue_task(self.wrapper_file, 'nxpdf', 'entry')
            if self.mask:
                self.db.queue_task(self.wrapper_file, 'nxmasked_pdf', 'entry')

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
            self.server.add_task(f"{command} {switches(args)}")
        else:
            self.server.add_task(
                f"{command} --directory {self.directory} "
                f"--{' --'.join(tasks)}")
