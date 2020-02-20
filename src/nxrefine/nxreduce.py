import logging, logging.handlers
import operator
import os
import errno
import platform
import shutil
import subprocess
import sys
import time
import timeit
import datetime
from copy import deepcopy

import numpy as np
import h5py as h5
from h5py import is_hdf5

from nexusformat.nexus import *

from nexpy.gui.pyqt import QtCore
from nexpy.gui.utils import clamp, timestamp

from .nxdatabase import NXDatabase
from .nxrefine import NXRefine, NXPeak
from .nxserver import NXServer
from . import blobcorrector, __version__
from .connectedpixels import blob_moments
from .labelimage import labelimage, flip1


class NXReduce(QtCore.QObject):

    def __init__(self, entry='f1', directory=None, parent=None, entries=None,
                 data='data/data', extension='.h5', path='/entry/data/data',
                 threshold=None, first=None, last=None, radius=None, width=None,
                 norm=None, Qh=None, Qk=None, Ql=None, 
                 link=False, maxcount=False, find=False, copy=False,
                 refine=False, lattice=False, transform=False, prepare=False, mask=False,
                 overwrite=False, gui=False):

        super(NXReduce, self).__init__()

        if isinstance(entry, NXentry):
            self.entry_name = entry.nxname
            self.wrapper_file = entry.nxfilename
            self.sample = os.path.basename(
                            os.path.dirname(
                              os.path.dirname(self.wrapper_file)))
            self.label = os.path.basename(os.path.dirname(self.wrapper_file))
            base_name = os.path.basename(os.path.splitext(self.wrapper_file)[0])
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
                                             '%s_%s.nxs' %
                                             (self.sample, self.scan))
            self.entry_name = entry
            self._root = None
        self.base_directory = os.path.dirname(self.wrapper_file)
        self.task_directory = os.path.join(self.root_directory, 'tasks')
        if parent is None:
            self.parent_file = os.path.join(self.base_directory,
                                            self.sample+'_parent.nxs')
        else:
            self.parent_file = os.path.realpath(parent)
        
        self.mask_file = os.path.join(self.directory,
                                      self.entry_name+'_mask.nxs')
        self.log_file = os.path.join(self.task_directory, 'nxlogger.log')
        self.transform_file = os.path.join(self.directory,
                                           self.entry_name+'_transform.nxs')
        self.masked_transform_file = os.path.join(self.directory,
                                        self.entry_name+'_masked_transform.nxs')
        self.settings_file = os.path.join(self.directory,
                                           self.entry_name+'_transform.pars')

        self._data = data
        self._field_root = None
        self._field = None
        self._shape = None
        self._mask_root = None
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
        self._maximum = None
        self.summed_data = None
        self._first = first
        self._last = last
        self._radius = radius
        self._width = width
        self._norm = norm
        self.Qh = Qh
        self.Qk = Qk
        self.Ql = Ql

        self.link = link
        self.maxcount = maxcount
        self.find = find
        self.copy = copy
        self.refine = refine
        self.lattice = lattice
        self.transform = transform
        self.prepare = prepare
        self.mask = mask
        self.overwrite = overwrite
        self.gui = gui

        self._stopped = False

        self.init_logs()
        db_file = os.path.join(self.task_directory, 'nxdatabase.db')
        try:
            self.db = NXDatabase(db_file)
        except Exception:
            pass
        try:
            self.server = NXServer(self.root_directory)
        except Exception as error:
            self.server = None

        nxsetlock(600)

    start = QtCore.Signal(object)
    update = QtCore.Signal(object)
    result = QtCore.Signal(object)
    stop = QtCore.Signal()

    def __repr__(self):
        return "NXReduce('"+self.sample+"_"+self.scan+"/"+self.entry_name+"')"

    def init_logs(self):
        self.logger = logging.getLogger("%s/%s_%s['%s']"
                      % (self.label, self.sample, self.scan, self.entry_name))
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
                        '%(asctime)s %(name)-12s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
        for handler in self.logger.handlers:
            self.logger.removeHandler(handler)
        if os.path.exists(self.task_directory):
            if os.path.exists(os.path.join(self.task_directory, 'nxlogger.pid')):
                socketHandler = logging.handlers.SocketHandler('localhost',
                                    logging.handlers.DEFAULT_TCP_LOGGING_PORT)
                self.logger.addHandler(socketHandler)
            else:
                fileHandler = logging.FileHandler(self.log_file)
                fileHandler.setFormatter(formatter)
                self.logger.addHandler(fileHandler)
        if not self.gui:
            streamHandler = logging.StreamHandler()
            self.logger.addHandler(streamHandler)

    @property
    def root(self):
        if self._root is None:
            self._root = nxload(self.wrapper_file, 'rw')
        return self._root

    @property
    def entry(self):
        return self.root[self.entry_name]

    @property
    def entries(self):
        if self._entries:
            return self._entries
        else:
            return [entry for entry in self.root.entries if entry != 'entry']

    @property
    def first_entry(self):
        return self.entry_name == self.entries[0]

    @property
    def data(self):
        return self.entry['data']

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
    def data_file(self):
        return self.entry[self._data].nxfilename

    def data_exists(self):
        return is_hdf5(self.data_file)

    @property
    def mask_root(self):
        if self._mask_root is None:
            self._mask_root = nxload(self.mask_file, 'a')
            if 'entry' not in self.mask_root:
                self.mask_root['entry'] = NXentry()
        return self._mask_root

    @property
    def pixel_mask(self):
        if self._pixel_mask is None:
            try:
                self._pixel_mask = self.entry['instrument/detector/pixel_mask'].nxvalue
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
            if not self.is_parent() and os.path.exists(self.parent_file):
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
            self.logger.info("'%s' already set as parent" % self.wrapper_file)
            return
        elif os.path.exists(self.parent_file):
            if self.overwrite:
                os.remove(self.parent_file)
            else:
                raise NeXusError("'%s' already set as parent"
                                 % os.path.realpath(self.parent_file))
        os.symlink(os.path.basename(self.wrapper_file), self.parent_file)
        self._parent = None
        self.logger.info("'%s' set as parent" % os.path.realpath(self.parent_file))

    @property
    def first(self):
        _first = self._first
        if _first is None:
            if 'peaks' in self.entry and 'first' in self.entry['peaks'].attrs:
                _first = np.int32(self.entry['peaks'].attrs['first'])
            elif 'first' in self.entry['data'].attrs:
                _first = np.int32(self.entry['data'].attrs['first'])
            elif self.parent:
                root = self.parent_root
                if ('peaks' in root[self.entry_name] and
                    'first' in root[self.entry_name]['peaks'].attrs):
                    _first = np.int32(root[self.entry_name]['peaks'].attrs['first'])
                elif 'first' in root[self.entry_name]['data'].attrs:
                    _first = np.int32(root[self.entry_name]['data'].attrs['first'])
        try:
            self._first = np.int(_first)
        except Exception as error:
            self._first = None
        return self._first

    @first.setter
    def first(self, value):
        try:
            self._first = np.int(value)
        except ValueError:
            pass

    @property
    def last(self):
        _last = self._last
        if _last is None:
            if 'peaks' in self.entry and 'last' in self.entry['peaks'].attrs:
                _last = np.int32(self.entry['peaks'].attrs['last'])
            elif 'last' in self.entry['data'].attrs:
                _last = np.int32(self.entry['data'].attrs['last'])
            elif self.parent:
                root = self.parent_root
                if ('peaks' in root[self.entry_name] and
                    'last' in root[self.entry_name]['peaks'].attrs):
                    _last = np.int32(root[self.entry_name]['peaks'].attrs['last'])
                elif 'last' in root[self.entry_name]['data'].attrs:
                    _last = np.int32(root[self.entry_name]['data'].attrs['last'])
        try:
            self._last = np.int(_last)
        except Exception as error:
            self._last = None
        return self._last

    @last.setter
    def last(self, value):
        try:
            self._last = np.int(value)
        except ValueError:
            pass

    @property
    def threshold(self):
        _threshold = self._threshold
        if _threshold is None:
            if 'peaks' in self.entry and 'threshold' in self.entry['peaks'].attrs:
                _threshold = np.int32(self.entry['peaks'].attrs['threshold'])
            elif self.parent:
                root = self.parent_root
                if ('peaks' in root[self.entry_name] and
                    'threshold' in root[self.entry_name]['peaks'].attrs):
                    _threshold = np.int32(root[self.entry_name]['peaks'].attrs['threshold'])
        if _threshold is None:
            if self.maximum is not None:
                _threshold = self.maximum / 10
        try:
            self._threshold = np.float(_threshold)
            if self._threshold <= 0.0:
                self._threshold = None
        except:
            self._threshold = None
        return self._threshold

    @threshold.setter
    def threshold(self, value):
        self._threshold = value

    @property
    def radius(self):
        _radius = self._radius
        if _radius is None:
            if 'peaks' in self.entry and 'radius' in self.entry['peaks'].attrs:
                _radius = np.int32(self.entry['peaks'].attrs['radius'])
            elif self.parent:
                root = self.parent_root
                if ('peaks' in root[self.entry_name] and
                    'radius' in root[self.entry_name]['peaks'].attrs):
                    _radius = np.int32(root[self.entry_name]['peaks'].attrs['radius'])
        if _radius is None:
            _radius = 200
        try:
            self._radius = np.int(_radius)
        except:
            self._radius = 200
        return self._radius

    @radius.setter
    def radius(self, value):
        self._radius = value

    @property
    def width(self):
        _width = self._width
        if _width is None:
            if 'peaks' in self.entry and 'width' in self.entry['peaks'].attrs:
                _width = np.int32(self.entry['peaks'].attrs['width'])
            elif self.parent:
                root = self.parent_root
                if ('peaks' in root[self.entry_name] and
                    'width' in root[self.entry_name]['peaks'].attrs):
                    _width = np.int32(root[self.entry_name]['peaks'].attrs['width'])
        try:
            self._width = np.int(_width)
        except:
            self._width = 3
        return self._width

    @width.setter
    def width(self, value):
        self._width = value

    @property
    def norm(self):
        _norm = self._norm
        if _norm is None:
            if 'peaks' in self.entry and 'norm' in self.entry['peaks'].attrs:
                _norm = np.int32(self.entry['peaks'].attrs['norm'])
            elif self.parent:
                root = self.parent_root
                if ('peaks' in root[self.entry_name] and
                    'norm' in root[self.entry_name]['peaks'].attrs):
                    _norm = np.int32(root[self.entry_name]['peaks'].attrs['norm'])
        try:
            self._norm = np.float(_norm)
            if self._norm <= 0:
                self._norm = None
        except:
            self._norm = None
        return self._norm

    @norm.setter
    def norm(self, value):
        self._norm = value

    @property
    def maximum(self):
        if self._maximum is None:
            if 'maximum' in self.entry['data'].attrs:
                self._maximum = self.entry['data'].attrs['maximum']
        return self._maximum

    def complete(self, program):
        if program == 'nxcombine':
            return program in self.root['entry']
        else:
            return program in self.entry

    def all_complete(self, program):
        """ Check that all entries for this temperature are done """
        complete = True
        for entry in self.entries:
            if program not in self.root[entry]:
                complete = False
        return complete

    def not_complete(self, program):
        return program not in self.entry or self.overwrite

    def start_progress(self, start, stop):
        if self.gui:
            self._step = (stop - start) / 100
            self._value = int(start)
            self.start.emit((0, 100))
        else:
            print('Frame', end='')
        self.stopped = False
        return timeit.default_timer()

    def update_progress(self, i):
        if self.gui:
            _value = int(i/self._step)
            if  _value > self._value:
                self.update.emit(_value)
                self._value = _value
        else:
            print('\rFrame %d' % i, end='')

    def stop_progress(self):
        if not self.gui:
            print('')
        self.stopped = True
        return timeit.default_timer()

    @property
    def stopped(self):
        return self._stopped

    @stopped.setter
    def stopped(self, value):
        self._stopped = value

    def record(self, program, **kwargs):
        """ Record that a task has finished. Update NeXus file and database """
        process = kwargs.pop('process', program)
        parameters = '\n'.join(
            [('%s: %s' % (k, v)).replace('_', ' ').capitalize()
             for (k,v) in kwargs.items()])
        note = NXnote(process, ('Current machine: %s\n' % platform.node() +
                                'Current directory: %s\n' % self.directory +
                                parameters))
        with self.root.nxfile:
            if process in self.entry:
                del self.entry[process]
            self.entry[process] = NXprocess(program='%s' % process,
                                            sequence_index=len(self.entry.NXprocess)+1,
                                            version='nxrefine v'+__version__,
                                            note=note)
        self.record_end(program)
        
        # check if all 3 entries are done - update File
        # if self.all_complete(program):
        #     self.db.start_task(self.wrapper_file, program, 'done')

    def record_start(self, program):
        """ Record that a task has started. Update database """
        try:
            self.db.start_task(self.wrapper_file, program, self.entry_name)
        except Exception:
            pass

    def record_end(self, program):
        """ Record that a task has ended. Update database """
        try:
            self.db.end_task(self.wrapper_file, program, self.entry_name)
        except Exception:
            pass

    def record_fail(self, program):
        """ Record that a task has failed. Update database """
        try:
            self.db.fail_task(self.wrapper_file, program, self.entry_name)
        except Exception:
            pass

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
            else:
                self.record_fail('nxlink')
        elif self.link:
            self.logger.info('Data already linked')
            self.record_end('nxlink')

    def link_data(self):
        if self.field:
            with self.root.nxfile:
                if 'data' not in self.entry:
                    self.entry['data'] = NXdata()
                    self.entry['data/x_pixel'] = np.arange(self.shape[2], dtype=np.int32)
                    self.entry['data/y_pixel'] = np.arange(self.shape[1], dtype=np.int32)
                    self.entry['data/frame_number'] = np.arange(self.shape[0], 
                                                                dtype=np.int32)
                    data_file = os.path.relpath(self.data_file, 
                                                os.path.dirname(self.wrapper_file))
                    self.entry['data/data'] = NXlink(self.path, data_file)
                    self.entry['data'].nxsignal = self.entry['data/data']
                    self.logger.info('Data group created and linked to external data')
                else:
                    if self.entry['data/frame_number'].shape != self.shape[0]:
                        del self.entry['data/frame_number']
                        self.entry['data/frame_number'] = np.arange(self.shape[0], 
                                                                    dtype=np.int32)
                        self.logger.info('Fixed frame number axis')
                self.entry['data'].nxaxes = [self.entry['data/frame_number'],
                                             self.entry['data/y_pixel'],
                                             self.entry['data/x_pixel']]
        else:
            self.logger.info('No raw data loaded')

    def read_logs(self):
        head_file = os.path.join(self.directory, self.entry_name+'_head.txt')
        meta_file = os.path.join(self.directory, self.entry_name+'_meta.txt')
        if os.path.exists(head_file) or os.path.exists(meta_file):
            logs = NXcollection()
        else:
            self.logger.info('No metadata files found')
            return None
        if os.path.exists(head_file):
            with open(head_file) as f:
                lines = f.readlines()
            for line in lines:
                key, value = line.split(', ')
                value = value.strip('\n')
                try:
                   value = np.float(value)
                except:
                    pass
                logs[key] = value
        if os.path.exists(meta_file):
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
            frames = self.entry['data/frame_number'].size
            if 'MCS1' in logs:
                if 'monitor1' in self.entry:
                    del self.entry['monitor1']
                data = logs['MCS1'][:frames]
                #Remove outliers at beginning and end of frames
                data[0] = data[1]
                data[-1] = data[-2]
                self.entry['monitor1'] = NXmonitor(NXfield(data, name='MCS1'),
                                                   NXfield(np.arange(frames,
                                                                     dtype=np.int32),
                                                           name='frame_number'))
            if 'MCS2' in logs:
                if 'monitor2' in self.entry:
                    del self.entry['monitor2']
                data = logs['MCS2'][:frames]
                #Remove outliers at beginning and end of frames
                data[0] = data[1]
                data[-1] = data[-2]
                self.entry['monitor2'] = NXmonitor(NXfield(data, name='MCS2'),
                                                   NXfield(np.arange(frames,
                                                                     dtype=np.int32),
                                                           name='frame_number'))
            if 'source' not in self.entry['instrument']:
                self.entry['instrument/source'] = NXsource()
            self.entry['instrument/source/name'] = 'Advanced Photon Source'
            self.entry['instrument/source/type'] = 'Synchrotron X-ray Source'
            self.entry['instrument/source/probe'] = 'x-ray'
            if 'Storage_Ring_Current' in logs:
                self.entry['instrument/source/current'] = logs['Storage_Ring_Current']
            if 'UndulatorA_gap' in logs:
                self.entry['instrument/source/undulator_gap'] = logs['UndulatorA_gap']
            if 'Calculated_filter_transmission' in logs:
                if 'attenuator' not in self.entry['instrument']:
                    self.entry['instrument/attenuator'] = NXattenuator()
                self.entry['instrument/attenuator/attenuator_transmission'] = (
                                                logs['Calculated_filter_transmission'])

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
                self.record('nxmax', maximum=maximum,
                            first_frame=self.first, last_frame=self.last)
        elif self.maxcount:
            self.logger.info('Maximum counts already found')
            self.record_end('nxmax')

    def find_maximum(self):
        self.logger.info('Finding maximum counts')
        with self.field.nxfile:
            maximum = 0.0
            nframes = self.shape[0]
            chunk_size = self.field.chunks[0]
            if chunk_size < 20:
                chunk_size = 50
            if self.first == None:
                self.first = 0
            if self.last == None:
                self.last = nframes
            data = self.field.nxfile[self.path]
            fsum = np.zeros(nframes, dtype=np.float64)
            pixel_mask = self.pixel_mask
            #Add constantly firing pixels to the mask
            pixel_max = np.zeros((self.shape[1], self.shape[2]))
            v = data[0:10,:,:]
            for i in range(10):
                pixel_max = np.maximum(v[i,:,:], pixel_max)
            pixel_mean=v.sum(0) / 10.
            mask = np.zeros((self.shape[1], self.shape[2]), dtype=np.int8)
            mask[np.where(pixel_max == pixel_mean)] = 1
            mask[np.where(pixel_mean < 100)] = 0
            pixel_mask = pixel_mask | mask
            self.pixel_mask = pixel_mask
            #Start looping over the data
            tic = self.start_progress(self.first, self.last)
            for i in range(self.first, self.last, chunk_size):
                if self.stopped:
                    return None
                self.update_progress(i)
                try:
                    v = data[i:i+chunk_size,:,:]
                except IndexError as error:
                    pass
                if i == self.first:
                    vsum = v.sum(0)
                else:
                    vsum += v.sum(0)
                if pixel_mask is not None:
                    v = np.ma.masked_array(v)
                    v.mask = pixel_mask
                fsum[i:i+chunk_size] = v.sum((1,2))
                if maximum < v.max():
                    maximum = v.max()
                del v
        if pixel_mask is not None:
            vsum = np.ma.masked_array(vsum)
            vsum.mask = pixel_mask
        self.summed_data = NXfield(vsum, name='summed_data')
        self.summed_frames = NXfield(fsum, name='summed_frames')
        toc = self.stop_progress()
        self.logger.info('Maximum counts: %s (%g seconds)' % (maximum, toc-tic))
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
            try:
                from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
                parameters = self.entry['instrument/calibration/refinement/parameters']
                cake = AzimuthalIntegrator(dist=parameters['Distance'].nxvalue,
                                           poni1=parameters['Poni1'].nxvalue,
                                           poni2=parameters['Poni2'].nxvalue,
                                           rot1=parameters['Rot1'].nxvalue,
                                           rot2=parameters['Rot2'].nxvalue,
                                           rot3=parameters['Rot3'].nxvalue,
                                           pixel1=parameters['PixelSize1'].nxvalue,
                                           pixel2=parameters['PixelSize2'].nxvalue,
                                           wavelength = parameters['Wavelength'].nxvalue)
                counts = self.entry['summed_data/summed_data'].nxvalue
                polar_angle, intensity = cake.integrate1d(counts, 2048,
                                                          unit='2th_deg',
                                                          mask=self.pixel_mask,
                                                          correctSolidAngle=True)
                if 'radial_sum' in self.entry:
                    del self.entry['radial_sum']
                self.entry['radial_sum'] = NXdata(NXfield(intensity, name='radial_sum'),
                                                  NXfield(polar_angle, name='polar_angle'))
            except Exception as error:
                self.logger.info('Unable to create radial sum')

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
            else:
                self.write_peaks(peaks)
                self.record('nxfind', threshold=self.threshold,
                            first_frame=self.first, last_frame=self.last,
                            peak_number=len(peaks))
        elif self.find:
            self.logger.info('Peaks already found')
            self.record_end('nxfind')

    def find_peaks(self):
        self.logger.info("Finding peaks")
        with self.root.nxfile:
            self._threshold, self._maximum = self.threshold, self.maximum

        if self.threshold is None:
            if self.maximum is None:
                self.maxcount = True
                self.nxmax()
            self.threshold = self.maximum / 10

        with self.field.nxfile:
            if self.first == None:
                self.first = 0
            if self.last == None:
                self.last = self.shape[0]
            z_min, z_max = self.first, self.last

            tic = self.start_progress(z_min, z_max)

            lio = labelimage(self.shape[-2:], flipper=flip1)
            allpeaks = []
            if len(self.shape) == 2:
                res = None
            else:
                chunk_size = self.field.chunks[0]
                pixel_tolerance = 50
                frame_tolerance = 10
                nframes = z_max
                data = self.field.nxfile[self.path]
                for i in range(0, nframes, chunk_size):
                    if self.stopped:
                        return None
                    try:
                        if i + chunk_size > z_min and i < z_max:
                            self.update_progress(i)
                            v = data[i:i+chunk_size,:,:]
                            for j in range(chunk_size):
                                if i+j >= z_min and i+j <= z_max:
                                    omega = np.float32(i+j)
                                    lio.peaksearch(v[j], self.threshold, omega)
                                    if lio.res is not None:
                                        blob_moments(lio.res)
                                        for k in range(lio.res.shape[0]):
                                            res = lio.res[k]
                                            peak = NXBlob(res[0], res[22],
                                                res[23], res[24], omega,
                                                res[27], res[26], res[29],
                                                self.threshold,
                                                pixel_tolerance,
                                                frame_tolerance)
                                            if peak.isvalid(self.pixel_mask):
                                                allpeaks.append(peak)
                    except IndexError as error:
                        pass

        if not allpeaks:
            toc = self.stop_progress()
            self.logger.info('No peaks found (%g seconds)' % (toc-tic))
            return None

        allpeaks = sorted(allpeaks)

        self.start_progress(z_min, z_max)

        merged_peaks = []
        for z in range(z_min, z_max+1):
            if self.stopped:
                return None
            self.update_progress(z)
            frame = [peak for peak in allpeaks if peak.z == z]
            if not merged_peaks:
                merged_peaks.extend(frame)
            else:
                for peak1 in frame:
                    combined = False
                    for peak2 in last_frame:
                        if peak1 == peak2:
                            for idx in range(len(merged_peaks)):
                                if peak1 == merged_peaks[idx]:
                                    break
                            peak1.combine(merged_peaks[idx])
                            merged_peaks[idx] = peak1
                            combined = True
                            break
                    if not combined:
                        reversed_peaks = [p for p in reversed(merged_peaks)
                                          if p.z >= peak1.z - frame_tolerance]
                        for peak2 in reversed_peaks:
                            if peak1 == peak2:
                                for idx in range(len(merged_peaks)):
                                    if peak1 == merged_peaks[idx]:
                                        break
                                peak1.combine(merged_peaks[idx])
                                merged_peaks[idx] = peak1
                                combined = True
                                break
                        if not combined:
                            merged_peaks.append(peak1)

            if frame:
                last_frame = frame

        merged_peaks = sorted(merged_peaks)
        for peak in merged_peaks:
            peak.merge()

        merged_peaks = sorted(merged_peaks)
        peaks = merged_peaks
        toc = self.stop_progress()
        self.logger.info('%s peaks found (%g seconds)' % (len(peaks), toc-tic))
        return peaks

    def write_peaks(self, peaks):
        group = NXreflections()
        shape = (len(peaks),)
        group['npixels'] = NXfield([peak.np for peak in peaks], dtype=np.float32)
        group['intensity'] = NXfield([peak.intensity for peak in peaks],
                                        dtype=np.float32)
        group['x'] = NXfield([peak.x for peak in peaks], dtype=np.float32)
        group['y'] = NXfield([peak.y for peak in peaks], dtype=np.float32)
        group['z'] = NXfield([peak.z for peak in peaks], dtype=np.float32)
        group['sigx'] = NXfield([peak.sigx for peak in peaks], dtype=np.float32)
        group['sigy'] = NXfield([peak.sigy for peak in peaks], dtype=np.float32)
        group['covxy'] = NXfield([peak.covxy for peak in peaks], dtype=np.float32)
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

    def nxcopy(self):
        if self.is_parent():
            self.logger.info('Set as parent; no parameters copied')
        elif self.not_complete('nxcopy') and self.copy:
            self.record_start('nxcopy')
            if self.parent:
                self.copy_parameters()
                self.record('nxcopy', parent=self.parent)
            else:
                self.logger.info('No parent defined')
                self.record_fail('nxcopy')
        elif self.copy:
            self.logger.info('Parameters already copied')
            self.record_end('nxcopy')

    def copy_parameters(self):
        with self.parent_root.nxfile:
            input = self.parent_root
            input_ref = NXRefine(input[self.entry_name])
            with self.root.nxfile:
                output_ref = NXRefine(self.entry)
                input_ref.copy_parameters(output_ref, sample=True, instrument=True)
        self.logger.info("Parameters copied from '%s'" %
                         os.path.basename(os.path.realpath(self.parent)))

    def nxrefine(self):
        if self.not_complete('nxrefine') and self.refine:
            if not self.complete('nxfind'):
                self.logger.info('Cannot refine until peak search is completed')
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
            else:
                self.record_fail('nxrefine')
        elif self.refine:
            self.logger.info('HKL values already refined')
            self.record_end('nxrefine')

    def refine_parameters(self, lattice=False):
        with self.root.nxfile:
            refine = NXRefine(self.entry)
            refine.refine_hkls(lattice=lattice, chi=True, omega=True)
            fit_report=refine.fit_report
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

    def nxtransform(self):
        if self.not_complete('nxtransform') and self.transform:
            if not self.complete('nxrefine'):
                self.logger.info('Cannot transform until the orientation is complete')
                return
            self.record_start('nxtransform')
            cctw_command = self.prepare_transform()
            if cctw_command:
                self.logger.info('Transform process launched')
                tic = timeit.default_timer()
                with self.field.nxfile:
                    with NXLock(self.transform_file):
                        process = subprocess.run(cctw_command, shell=True,
                                                 stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE)
                toc = timeit.default_timer()
                if process.returncode == 0:
                    self.logger.info('Transform completed (%g seconds)'
                                     % (toc-tic))
                else:
                    self.logger.info(
                        'Transform completed - errors reported (%g seconds)'
                        % (toc-tic))
                self.record('nxtransform', norm=self.norm,
                            command=cctw_command,
                            output=process.stdout.decode(),
                            errors=process.stderr.decode())
            else:
                self.logger.info('CCTW command invalid')
                self.record_fail('nxtransform')
        elif self.transform:
            self.logger.info('Data already transformed')
            self.record_end('nxtransform')

    def get_transform_grid(self):
        if self.Qh and self.Qk and self.Ql:
            try:
                self.Qh = [np.float32(v) for v in self.Qh]
                self.Qk = [np.float32(v) for v in self.Qk]
                self.Ql = [np.float32(v) for v in self.Ql]
            except Exception:
                self.Qh = self.Qk = self.Ql = None
        else:
            if 'transform' in self.entry:
                transform = self.entry['transform']
            elif 'masked_transform' in self.entry:
                transform = self.entry['masked_transform']
            elif self.parent:
                root = self.parent_root
                if 'transform' in root[self.entry_name]:
                    transform = root[self.entry_name]['transform']
                elif 'masked_transform' in root[self.entry_name]:
                    transform = root[self.entry_name]['masked_transform']
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
        with self.root.nxfile:
            if self.norm and 'monitor1' in self.entry:
                self.data['monitor_weight'] = self.entry['monitor1'].nxsignal / self.norm
                self.data['monitor_weight'].attrs['axes'] = 'frame_number'
                self.data['monitor_weight'][0] = self.data['monitor_weight'][1]
                self.data['monitor_weight'][-1] = self.data['monitor_weight'][-2]

    def prepare_transform(self, mask=False):
        if mask:
            transform_file = self.masked_transform_file
        else:
            transform_file = self.transform_file
        with self.root.nxfile:
            self.get_transform_grid()
            if self.norm:
                self.get_normalization()
            if self.Qh and self.Qk and self.Ql:
                refine = NXRefine(self.entry)
                refine.read_parameters()
                refine.h_start, refine.h_step, refine.h_stop = self.Qh
                refine.k_start, refine.k_step, refine.k_stop = self.Qk
                refine.l_start, refine.l_step, refine.l_stop = self.Ql
                refine.define_grid()
                refine.prepare_transform(transform_file, mask=mask)
                refine.write_settings(self.settings_file)
                command = refine.cctw_command(mask)
                if command and os.path.exists(transform_file):
                    with NXLock(transform_file):
                        os.remove(transform_file)
                return command
            else:
                self.logger.info('Invalid HKL grid')
                return None

    def nxprepare(self):
        if self.not_complete('nxprepare_mask') and self.prepare:
            if not self.complete('nxrefine'):
                self.logger.info('Cannot prepare mask until the orientation is complete')
                return
            self.record_start('nxprepare')
            self.logger.info('Preparing 3D mask')
            tic = timeit.default_timer()
            self.prepare_mask()
            self.link_mask()
            self.record('nxprepare', masked_file=self.mask_file, 
                        process='nxprepare_mask')
            toc = timeit.default_timer()
            self.logger.info("3D Mask stored in '%s' (%g seconds)"
                             % (self.mask_file, toc-tic))
        elif self.prepare:
            self.logger.info('3D Mask already prepared')
            self.record_end('nxprepare')

    def prepare_mask(self):
        self.logger.info("Calculating peaks to be masked")
        with self.root.nxfile:
            refine = NXRefine(self.entry)
        peaks = refine.get_xyzs()
        self.logger.info("Optimizing peak frames")
        with self.field.nxfile:
            with self.root.nxfile:
                for peak in peaks:
                    self.get_xyz_frame(peak)
            self.write_xyz_peaks(peaks)
            self.logger.info("Determining 3D mask radii")
            masks = self.prepare_xyz_masks(peaks)
        self.logger.info("Writing 3D mask parameters")
        self.write_xyz_masks(masks)
        self.logger.info("Masked frames stored in %s" % self.mask_file)

    def link_mask(self):
        with self.root.nxfile:
            mask_file = os.path.relpath(self.mask_file, 
                                        os.path.dirname(self.wrapper_file))
            if 'data_mask' in self.data:
                del self.data['data_mask']
            self.data['data_mask'] = NXlink('entry/mask', mask_file)

    def get_xyz_frame(self, peak):
        slab = self.get_xyz_slab(peak)
        if slab.nxsignal.min() < 0: #Slab includes gaps in the detector
            slab = self.get_xyz_slab(peak, width=30)
        cut = slab.sum((1,2))
        x, y = cut.nxaxes[0], cut.nxsignal
        try:
            slope = (y[-1]-y[0]) / (x[-1]-x[0])
            constant = y[0] - slope * x[0]
            z = (cut - constant - slope*x).moment().nxvalue
        except Exception:
            pass
        if z > x[0] and z < x[-1]:
            peak.z = z
        peak.x, peak.y, peak.z = (clamp(peak.x, 0, self.shape[2]-1), 
                                  clamp(peak.y, 0, self.shape[1]-1), 
                                  clamp(peak.z, 0, self.shape[0]-1))
        peak.pixel_count = self.data[peak.z, peak.y, peak.x].nxsignal.nxvalue
        return slab

    def get_xyz_slab(self, peak, width=10):
        xmin, xmax = max(peak.x-width, 0), min(peak.x+width+1, self.shape[1]-1)
        ymin, ymax = max(peak.y-width, 0), min(peak.y+width+1, self.shape[0]-1)
        zmin, zmax = max(peak.z-10, 0), min(peak.z+11, self.shape[0])
        return self.data[zmin:zmax, ymin:ymax, xmin:xmax]

    def write_xyz_peaks(self, peaks):
        extra_peaks = []
        for peak in [p for p in peaks if p.z >= 3600]:
            extra_peak = deepcopy(peak)
            extra_peak.z = peak.z - 3600
            extra_peaks.append(extra_peak)
        for peak in [p for p in peaks if p.z < 50]:
            extra_peak = deepcopy(peak)
            extra_peak.z = peak.z + 3600
            extra_peaks.append(extra_peak)
        peaks.extend(extra_peaks)            
        peaks = sorted(peaks, key=operator.attrgetter('z'))
        peak_array = np.array(list(zip(*[(peak.x, peak.y, peak.z, peak.pixel_count, 
                                          peak.H, peak.K, peak.L) for peak in peaks])))
        collection = NXcollection()
        collection['x'] = peak_array[0]
        collection['y'] = peak_array[1]
        collection['z'] = peak_array[2]
        collection['pixel_count'] = peak_array[3]
        collection['H'] = peak_array[4]
        collection['K'] = peak_array[5]
        collection['L'] = peak_array[6]
        with self.mask_root.nxfile:
            entry = self.mask_root['entry']
            if 'peaks_inferred' in entry:
                del entry['peaks_inferred']
            entry['peaks_inferred'] = collection

    def prepare_xyz_masks(self, peaks):
        with self.root.nxfile:
            masks = []
            peaks = sorted(peaks, key=operator.attrgetter('z'))
            for p in peaks:
                if p.pixel_count >= 0:
                    masks.extend(self.determine_mask(p))
        return masks

    def determine_mask(self, peak):
        with self.root.nxfile:
            with self.field.nxfile:
                slab = self.get_xyz_slab(peak)
                s = slab.nxsignal.nxdata
                slab_axis = slab.nxaxes[0].nxdata
        frames = np.array([np.average(np.ma.masked_where(s[i]<0,s[i]))*np.prod(s[i].shape) 
                           for i in range(s.shape[0])])
        masked_frames = np.ma.masked_where(frames<350000, frames)
        masked_peaks = []
        mask = masked_frames.mask
        if mask.size == 1 and mask == True:
            return []
        elif mask.size == 1 and mask == False:
            for f, z in zip(masked_frames, slab_axis):
                masked_peaks.append(NXPeak(peak.x, peak.y, z, 
                                           H=peak.H, K=peak.K, L=peak.L, 
                                           pixel_count=peak.pixel_count, 
                                           radius=mask_size(f)))
        else:
            for f, z in zip(masked_frames[~mask], slab_axis[~mask]):
                masked_peaks.append(NXPeak(peak.x, peak.y, z, 
                                           H=peak.H, K=peak.K, L=peak.L, 
                                           pixel_count=peak.pixel_count, 
                                           radius=mask_size(f)))
        return masked_peaks

    def write_xyz_masks(self, peaks):
        peaks = sorted(peaks, key=operator.attrgetter('z'))
        peak_array = np.array(list(zip(*[(peak.x, peak.y, peak.z, peak.H, peak.K, peak.L,
                                          peak.radius, peak.pixel_count) 
                                         for peak in peaks])))
        collection = NXcollection()
        collection['x'] = peak_array[0]
        collection['y'] = peak_array[1]
        collection['z'] = peak_array[2]
        collection['H'] = peak_array[3]
        collection['K'] = peak_array[4]
        collection['L'] = peak_array[5]
        collection['radius'] = peak_array[6]
        collection['pixel_count'] = peak_array[7]
        with self.mask_root.nxfile:
            entry = self.mask_root['entry']
            if 'mask_xyz' in entry:
                del entry['mask_xyz']
            entry['mask_xyz'] = collection
    
    def write_xyz_extras(self, peaks):
        peaks = sorted(peaks, key=operator.attrgetter('z'))
        peak_array = np.array(list(zip(*[(peak.x, peak.y, peak.z, peak.H, peak.K, peak.L,
                                          peak.radius, peak.pixel_count) 
                                         for peak in peaks])))
        collection = NXcollection()
        collection['x'] = peak_array[0]
        collection['y'] = peak_array[1]
        collection['z'] = peak_array[2]
        collection['H'] = peak_array[3]
        collection['K'] = peak_array[4]
        collection['L'] = peak_array[5]
        collection['radius'] = peak_array[6]
        collection['pixel_count'] = peak_array[7]
        with self.mask_root.nxfile:
            entry = self.mask_root['entry']
            if 'mask_xyz_extras' in entry:
                del entry['mask_xyz_extras']
            entry['mask_xyz_extras'] = collection

    def read_xyz_peaks(self):
        return self.read_peaks('peaks_inferred')

    def read_xyz_masks(self):
        return self.read_peaks('mask_xyz')

    def read_xyz_extras(self):
        return self.read_peaks('mask_xyz_extras')

    def read_xyz_edges(self):
        return self.read_peaks('mask_xyz_edges')

    def read_peaks(self, peak_group):
        with self.mask_root.nxfile:
            if peak_group not in self.mask_root['entry']:
                return []
            else:
                pg = deepcopy(self.mask_root['entry'][peak_group])
        if 'intensity' not in pg:
            pg.intensity = np.zeros(len(pg.x))
        if 'radius' not in pg:
            pg.radius = np.zeros(len(pg.x))
        peaks = [NXPeak(*args) for args in 
                 list(zip(pg.x, pg.y, pg.z, pg.intensity, pg.pixel_count, 
                          pg.H, pg.K, pg.L, pg.radius))]
        return sorted(peaks, key=operator.attrgetter('z'))

    def nxmasked_transform(self):
        if self.not_complete('nxmasked_transform') and self.transform and self.mask:
            if not self.all_complete('nxprepare_mask'):
                self.logger.info('Cannot perform masked transform until the 3D mask ' + 
                                 'is prepared for all entries')
                return
            self.record_start('nxmasked_transform')
            self.logger.info("Completing and writing 3D mask")
            self.complete_xyz_mask()
            self.logger.info("3D mask written")
            cctw_command = self.prepare_transform(mask=True)
            if cctw_command:
                self.logger.info('Masked transform launched')
                tic = timeit.default_timer()
                with self.field.nxfile:
                    with NXLock(self.masked_transform_file):
                        process = subprocess.run(cctw_command, shell=True,
                                                 stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE)
                toc = timeit.default_timer()
                if process.returncode == 0:
                    self.logger.info('Masked transform completed (%g seconds)'
                                     % (toc-tic))
                else:
                    self.logger.info(
                        'Masked transform completed - errors reported (%g seconds)'
                        % (toc-tic))
                self.record('nxmasked_transform', mask=self.mask_file,
                            radius=self.radius, width=self.width, norm=self.norm,
                            command=cctw_command,
                            output=process.stdout.decode(),
                            errors=process.stderr.decode())
            else:
                self.logger.info('CCTW command invalid')
                self.record_fail('nxmasked_transform')
        elif self.transform and self.mask:
            self.logger.info('Masked data already transformed')
            self.record_end('nxmasked_transform')

    def complete_xyz_mask(self):
        peaks = {}
        masks = {}
        reduce = {}
        for entry in self.entries:
            if entry == self.entry_name:
                reduce[entry] = self
            else:
                reduce[entry] = NXReduce(self.root[entry])
            peaks[entry] = reduce[entry].read_xyz_peaks()
            masks[entry] = reduce[entry].read_xyz_masks()
        extra_masks = []
        for p in [p for p in peaks[self.entry_name] if p.pixel_count < 0]:
            radius = 0
            width = 0
            for e in [e for e in self.entries if e is not self.entry_name]:
                other_masks = [om for om in masks[e] if om.H == p.H and
                                                        om.K == p.K and 
                                                        om.L == p.L]
                for om in other_masks:
                    radius = max(radius, om.radius)
                width = max(width, len(other_masks))
            if radius > 0:
                radius += 20.
                width = int((width + 2) / 2)
                p.z = int(np.rint(p.z))
                for z in [z for z in range(p.z-width, p.z+width+1)]:
                    extra_masks.append(NXPeak(p.x, p.y, z, 
                                              H=p.H, K=p.K, L=p.L, 
                                              pixel_count=p.pixel_count,
                                              radius=radius))
        if extra_masks:
            self.write_xyz_extras(extra_masks)
        self.write_mask()

    def write_mask(self, peaks=None):
        with self.mask_root.nxfile:
            if peaks is None:
                peaks = self.read_xyz_masks()
                peaks.extend(self.read_xyz_extras())
                peaks.extend(self.read_xyz_edges())
            peaks = sorted(peaks, key=operator.attrgetter('z'))
            entry = self.mask_root['entry']
            if 'mask' not in entry:
                entry['mask'] = NXfield(shape=self.shape, dtype=np.int8, fillvalue=0)
            mask = entry['mask']
            x, y = np.arange(self.shape[2]), np.arange(self.shape[1])
            frames = self.shape[0]
            chunk_size = mask.chunks[0]
            for frame in range(0, frames, chunk_size):
                mask_chunk = np.zeros(shape=(chunk_size, self.shape[1], self.shape[2]),
                                      dtype=np.int8)
                for peak in [p for p in peaks if p.z >= frame and p.z < frame+chunk_size]:
                    xp, yp, zp, radius = int(peak.x), int(peak.y), int(peak.z), peak.radius
                    inside = np.array(((x[np.newaxis,:]-xp)**2 + (y[:,np.newaxis]-yp)**2 
                                        < radius**2), dtype=np.int8)
                    mask_chunk[zp-frame] = mask_chunk[zp-frame] | inside
                try:
                    mask[frame:frame+chunk_size] = (mask[frame:frame+chunk_size].nxvalue | 
                                                    mask_chunk)
                except ValueError as error:
                    i, j, k= frame, frames, frames-frame
                    mask[i:j] = mask[i:j].nxvalue | mask_chunk[:k]

    def nxsum(self, scan_list):
        if self.overwrite or not os.path.exists(self.data_file):
            self.logger.info('Sum files launched')
            tic = timeit.default_timer()
            self.sum_files(scan_list)
            toc = timeit.default_timer()
            self.logger.info('Sum completed (%g seconds)' % (toc-tic))
        else:
            self.logger.info('Data already summed')

    def sum_files(self, scan_list):
    
        nframes = 3650
        chunk_size = 50

        for i, scan in enumerate(scan_list):
            reduce = NXReduce(self.entry_name, 
                              os.path.join(self.base_directory, scan))
            if not os.path.exists(reduce.data_file):
                self.logger.info("'%s' does not exist" % reduce.data_file)
                if i == 0:
                    break
                else:
                    continue
            else:
                self.logger.info("Summing %s in '%s'" % (self.entry_name,
                                                         reduce.data_file))
            if i == 0:
                shutil.copyfile(reduce.data_file, self.data_file)
                new_file = h5.File(self.data_file, 'r+')
                new_field = new_file[self.path]
            else:
                scan_file = h5.File(reduce.data_file, 'r')
                scan_field = scan_file[self.path]
                for i in range(0, nframes, chunk_size):
                    new_slab = new_field[i:i+chunk_size,:,:]
                    scan_slab = scan_field[i:i+chunk_size,:,:]
                    new_field[i:i+chunk_size,:,:] = new_slab + scan_slab

    def nxreduce(self):
        self.nxlink()
        self.nxmax()
        self.nxfind()
        self.nxcopy()
        if self.complete('nxcopy'):
            self.nxrefine()
        if self.complete('nxrefine'):
            self.nxprepare()
            self.nxtransform()
            self.nxmasked_transform()
        else:
            self.logger.info('Orientation has not been refined')
            self.record_fail('nxtransform')
            self.record_fail('nxmasked_transform')

    def command(self, parent=False):
        switches = ['-d %s' % self.directory, '-e %s' % self.entry_name]
        if parent:
            command = 'nxparent '
            if self.first is not None:
                switches.append('-f %s' % self.first)
            if self.last is not None:
                switches.append('-l %s' % self.last)
            if self.threshold is not None:
                switches.append('-t %s' % self.threshold)
            if self.radius is not None:
                switches.append('-r %s' % self.radius)
            if self.width is not None:
                switches.append('-w %s' % self.width)
            if self.norm is not None:
                switches.append('-n %s' % self.norm)
            switches.append('-s')
        else:
            command = 'nxreduce '
            if self.link:
                switches.append('-l')
            if self.maxcount:
                switches.append('-m')
            if self.find:
                switches.append('-f')
            if self.copy:
                switches.append('-c')
            if self.refine:
                switches.append('-r')
            if self.prepare:
                switches.append('-p')
            if self.transform:
                switches.append('-t')
            if self.mask:
                switches.append('-M')
            if len(switches) == 2:
                return None
        if self.overwrite:
            switches.append('-o')

        return command+' '.join(switches)

    def queue(self, parent=False):
        """ Add tasks to the server's fifo, and log this in the database """
        command = self.command(parent)
        if command:
            self.server.add_task(command)
            if self.link:
                self.db.queue_task(self.wrapper_file, 'nxlink', self.entry_name)
            if self.maxcount:
                self.db.queue_task(self.wrapper_file, 'nxmax', self.entry_name)
            if self.find:
                self.db.queue_task(self.wrapper_file, 'nxfind', self.entry_name)
            if self.copy:
                self.db.queue_task(self.wrapper_file, 'nxcopy', self.entry_name)
            if self.refine:
                self.db.queue_task(self.wrapper_file, 'nxrefine', self.entry_name)
            if self.prepare:
                self.db.queue_task(self.wrapper_file, 'nxprepare', self.entry_name)
            if self.transform:
                if self.mask:
                    self.db.queue_task(self.wrapper_file, 'nxmasked_transform', 
                                    self.entry_name)
                else:
                    self.db.queue_task(self.wrapper_file, 'nxtransform', 
                                    self.entry_name)


class NXMultiReduce(NXReduce):

    def __init__(self, directory, entries=['f1', 'f2', 'f3'], 
                 mask=False, pdf=False, overwrite=False):
        super(NXMultiReduce, self).__init__(entry='entry', directory=directory,
                                            entries=entries, overwrite=overwrite)
        self.transform_file = os.path.join(self.directory, 'transform.nxs')
        self.masked_transform_file = os.path.join(self.directory,
                                                  'masked_transform.nxs')
        self.mask = mask
        self.pdf = pdf

    def complete(self, program):
        complete = True
        for entry in self.entries:
            if program not in self.root[entry]:
                complete = False
        if not complete and program == 'nxmasked_transform':
            complete = True
            for entry in self.entries:
                if 'nxmask' not in self.root[entry]:
                    complete = False                        
        return complete

    def nxcombine(self):
        if self.mask:
            task = 'nxmasked_combine'
            title = 'Masked combine'
        else:
            task = 'nxcombine'
            title = 'Combine'
        if self.not_complete(task):
            if self.mask:
                if not self.complete('nxmasked_transform'):
                    self.logger.info('Cannot combine until masked transforms complete')
                    return
            elif not self.complete('nxtransform'):
                self.logger.info('Cannot combine until transforms complete')
                return
            self.record_start(task)
            cctw_command = self.prepare_combine()
            if cctw_command:
                if self.mask:
                    self.logger.info('Combining masked transforms (%s)'
                                     % ', '.join(self.entries))
                    transform_file = self.masked_transform_file
                    transform_path = 'masked_transform/data'
                else:
                    self.logger.info('Combining transforms (%s)'
                                     % ', '.join(self.entries))
                    transform_file = self.transform_file
                    transform_path = 'transform/data'
                tic = timeit.default_timer()
                with NXLock(transform_file):
                    if os.path.exists(transform_file):
                        os.remove(transform_file)
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
                    self.logger.info('%s (%s)completed (%g seconds)'
                        % (title, ', '.join(self.entries), toc-tic))
                else:
                    self.logger.info(
                        '%s (%s) completed - errors reported (%g seconds)'
                        % (title, ', '.join(self.entries), toc-tic))
                self.record(task, command=cctw_command,
                            output=process.stdout.decode(),
                            errors=process.stderr.decode())
            else:
                self.logger.info('CCTW command invalid')
                self.record_fail('nxcombine')
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
                              file=os.path.join(self.scan, transform+'.nxs'), name='data')
                if transform in self.entry:
                    del self.entry[transform]
                self.entry[transform] = NXdata(data, [Ql,Qk,Qh])
        except Exception as error:
            self.logger.info('Unable to initialize transform group')
            return None
        input = ' '.join([os.path.join(self.directory,
                                       '%s_%s.nxs\#/entry/data' % (entry, transform))
                          for entry in self.entries])
        output = os.path.join(self.directory, transform+'.nxs\#/entry/data/v')
        return 'cctw merge %s -o %s' % (input, output)

    def nxpdf(self):
        pass

    def command(self):
        command = 'nxcombine '
        switches = ['-d %s' %  self.directory, '-e %s' % ' '.join(self.entries)]
        if self.mask:
            switches.append('-m')
        if self.overwrite:
            switches.append('-o')
        return command+' '.join(switches)

    def queue(self):
        if self.server is None:
            raise NeXusError("NXServer not running")
        self.server.add_task(self.command())
        if self.mask:
            self.db.queue_task(self.wrapper_file, 'nxmasked_combine', 'entry')
        else:
            self.db.queue_task(self.wrapper_file, 'nxcombine', 'entry')


class NXBlob(object):

    def __init__(self, np, average, x, y, z, sigx, sigy, covxy, threshold,
                 pixel_tolerance, frame_tolerance):
        self.np = np
        self.average = average
        self.intensity = np * average
        self.x = x
        self.y = y
        self.z = z
        self.sigx = sigx
        self.sigy = sigy
        self.covxy = covxy
        self.threshold = threshold
        self.peaks = [self]
        self.pixel_tolerance = pixel_tolerance**2
        self.frame_tolerance = frame_tolerance
        self.combined = False

    def __str__(self):
        return "NXBlob x=%f y=%f z=%f np=%i avg=%f" % (self.x, self.y, self.z, self.np, self.average)

    def __repr__(self):
        return "NXBlob x=%f y=%f z=%f np=%i avg=%f" % (self.x, self.y, self.z, self.np, self.average)

    def __lt__(self, other):
        return self.z < other.z

    def __eq__(self, other):
        if abs(self.z - other.z) <= self.frame_tolerance:
            if (self.x - other.x)**2 + (self.y - other.y)**2 <= self.pixel_tolerance:
                return True
            else:
                return False
        else:
            return False

    def __ne__(self, other):
        if abs(self.z - other.z) > self.frame_tolerance:
            if (self.x - other.x)**2 + (self.y - other.y)**2 > self.pixel_tolerance:
                return True
            else:
                return False
        else:
            return False

    def combine(self, other):
        self.peaks.extend(other.peaks)
        self.combined = True
        other.combined = False

    def merge(self):
        np = sum([p.np for p in self.peaks])
        intensity = sum([p.intensity for p in self.peaks])
        self.x = sum([p.x * p.intensity for p in self.peaks]) / intensity
        self.y = sum([p.y * p.intensity for p in self.peaks]) /intensity
        self.z = sum([p.z * p.intensity for p in self.peaks]) / intensity
        self.sigx = sum([p.sigx * p.intensity for p in self.peaks]) / intensity
        self.sigy = sum([p.sigy * p.intensity for p in self.peaks]) / intensity
        self.covxy = sum([p.covxy * p.intensity for p in self.peaks]) / intensity
        self.np = np
        self.intensity = intensity
        self.average = self.intensity / self.np

    def isvalid(self, mask):
        if mask is not None:
            clip = mask[int(self.y),int(self.x)]
            if clip:
                return False
        if np.isclose(self.average, 0.0) or np.isnan(self.average) or self.np < 5:
            return False
        else:
            return True

def mask_size(intensity):
    a = 1.3858
    b = 0.330556764635949
    c = -134.21 + 40 #radius_add
    try:
        if len(intensity) > 1:
            pass
    except Exception:
        pass
    if (intensity<1):
        return 0
    else:
        radius = np.real(c + a * (intensity**b))
        return max(1,np.int(radius))

