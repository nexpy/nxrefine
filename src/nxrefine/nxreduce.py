import logging, logging.handlers
import os
import errno
import platform
import subprocess
import sys
import time
import timeit
import datetime
import numpy as np
from h5py import is_hdf5

from nexusformat.nexus import *

from nexpy.gui.pyqt import QtCore
from nexpy.gui.utils import timestamp

import nxrefine.nxdatabase as nxdb
from .nxrefine import NXRefine
from .nxlock import Lock
from .nxserver import NXServer
from . import blobcorrector, __version__
from .connectedpixels import blob_moments
from .labelimage import labelimage, flip1


class NXReduce(QtCore.QObject):

    def __init__(self, entry='f1', directory=None, parent=None, entries=None,
                 data='data/data', extension='.h5', path='/entry/data/data',
                 threshold=None, first=None, last=None, radius=200, width=3,
                 Qh=None, Qk=None, Ql=None, 
                 link=False, maxcount=False, find=False, copy=False,
                 refine=False, lattice=False, transform=False, mask=False,
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
        self.base_directory = os.path.dirname(self.wrapper_file)
        self.task_directory = os.path.join(self.root_directory, 'tasks')
        self.parent_file = os.path.join(self.base_directory,
                                        self.sample+'_parent.nxs')
        self.mask_file = os.path.join(self.directory,
                                      self.entry_name+'_mask.nxs')
        self.log_file = os.path.join(self.task_directory, 'nxlogger.log')
        self.transform_file = os.path.join(self.directory,
                                           self.entry_name+'_transform.nxs')
        self.masked_transform_file = os.path.join(self.directory,
                                        self.entry_name+'_masked_transform.nxs')
        self.settings_file = os.path.join(self.directory,
                                           self.entry_name+'_transform.pars')

        self._root = None
        self._data = data
        self._field = None
        self._pixel_mask = None
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
        self.radius = radius
        self.width = width
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
        self.mask = mask
        self.overwrite = overwrite
        self.gui = gui

        self._stopped = False

        self.init_logs()
        db_file = os.path.join(self.task_directory, 'nxdatabase.db')
        nxdb.init('sqlite:///' + db_file)
        try:
            self.server = NXServer(self.root_directory)
        except Exception as error:
            self.server = None

    start = QtCore.Signal(object)
    update = QtCore.Signal(object)
    result = QtCore.Signal(object)
    stop = QtCore.Signal()

    def init_logs(self):
        self.logger = logging.getLogger("%s_%s['%s']"
                                        % (self.sample, self.scan, self.entry_name))
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
            with Lock(self.wrapper_file):
                self._root = nxload(self.wrapper_file, 'r+')
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
            self._field = nxload(self.data_file, 'r')[self.path]
        return self._field

    @property
    def data_file(self):
        return self.entry[self._data].nxfilename

    def data_exists(self):
        return is_hdf5(self.data_file)

    @property
    def pixel_mask(self):
        if self._pixel_mask is None:
            try:
                self._pixel_mask = self.entry['instrument/detector/pixel_mask'].nxvalue
            except Exception as error:
                pass
        return self._pixel_mask

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
                with Lock(self.parent):
                    root = nxload(self.parent)
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
                with Lock(self.parent):
                    root = nxload(self.parent)
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
                with Lock(self.parent):
                    root = nxload(self.parent)
                    if ('peaks' in root[self.entry_name] and
                        'threshold' in root[self.entry_name]['peaks'].attrs):
                        _threshold = np.int32(root[self.entry_name]['peaks'].attrs['threshold'])
        if _threshold is None:
            if self.maximum is not None:
                _threshold = self.maximum / 10
        try:
            self._threshold = np.float(_threshold)
        except:
            self._threshold = None
        return self._threshold

    @threshold.setter
    def threshold(value):
        self._threshold = value

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

    def record(self, program, **kwds):
        """ Record that a task has finished. Update NeXus file and database """
        parameters = '\n'.join(
            [('%s: %s' % (k, v)).replace('_', ' ').capitalize()
             for (k,v) in kwds.items()])
        note = NXnote(program, ('Current machine: %s\n' % platform.node() +
                                'Current directory: %s\n' % self.directory +
                                parameters))
        if program in self.entry:
            del self.entry[program]
        self.entry[program] = NXprocess(program='%s' % program,
                                sequence_index=len(self.entry.NXprocess)+1,
                                version='nxrefine v'+__version__,
                                note=note)
        nxdb.end_task(self.wrapper_file, program, self.entry_name)
        # check if all 3 entries are done - update File
        # if self.all_complete(program):
        #     nxdb.start_task(self.wrapper_file, program, 'done')

    def record_start(self, program):
        """ Record that a task has started. Update database """
        nxdb.start_task(self.wrapper_file, program, self.entry_name)

    def nxlink(self):
        self.record_start('nxlink')
        if self.not_complete('nxlink') and self.link:
            if not self.data_exists():
                self.logger.info('Data file not available')
                return
            with Lock(self.wrapper_file):
                self.link_data()
                logs = self.read_logs()
                if logs:
                    if 'logs' in self.entry['instrument']:
                        del self.entry['instrument']['logs']
                    self.entry['instrument']['logs'] = logs
                    self.transfer_logs()
                    self.record('nxlink', logs='Transferred')
                    self.logger.info('Entry linked to raw data')
                else:
                    self.record('nxlink')
        elif self.link:
            self.logger.info('Data already linked')
            self.record('nxlink')

    def link_data(self):
        if self.field:
            shape = self.field.shape
            if 'data' not in self.entry:
                self.entry['data'] = NXdata()
                self.entry['data/x_pixel'] = np.arange(shape[2], dtype=np.int32)
                self.entry['data/y_pixel'] = np.arange(shape[1], dtype=np.int32)
                self.entry['data/frame_number'] = np.arange(shape[0], dtype=np.int32)
                data_file = os.path.relpath(self.data_file, os.path.dirname(self.wrapper_file))
                self.entry['data/data'] = NXlink(self.path, data_file)
                self.entry['data'].nxsignal = self.entry['data/data']
                self.logger.info('Data group created and linked to external data')
            else:
                if self.entry['data/frame_number'].shape != shape[0]:
                    del self.entry['data/frame_number']
                    self.entry['data/frame_number'] = np.arange(shape[0], dtype=np.int32)
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

    def transfer_logs(self):
        logs = self.entry['instrument/logs']
        frames = self.entry['data/frame_number'].size
        if 'MCS1' in logs:
            if 'monitor1' in self.entry:
                del self.entry['monitor1']
            data = logs['MCS1'][:frames]
            self.entry['monitor1'] = NXmonitor(NXfield(data, name='MCS1'),
                                               NXfield(np.arange(frames,
                                                                 dtype=np.int32),
                                                       name='frame_number'))
        if 'MCS2' in logs:
            if 'monitor2' in self.entry:
                del self.entry['monitor2']
            data = logs['MCS2'][:frames]
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
            self.entry['instrument/attenuator/attenuator_transmission'] = logs['Calculated_filter_transmission']

    def nxmax(self):
        self.record_start('nxmax')
        if self.not_complete('nxmax') and self.maxcount:
            if not self.data_exists():
                self.logger.info('Data file not available')
                return
            with Lock(self.data_file):
                maximum = self.find_maximum()
            if self.gui:
                if maximum:
                    self.result.emit(maximum)
                self.stop.emit()
            else:
                with Lock(self.wrapper_file):
                    self.write_maximum(maximum)
        elif self.maxcount:
            self.logger.info('Maximum counts already found')
            self.record('nxmax')

    def find_maximum(self):
        self.logger.info('Finding maximum counts')
        maximum = 0.0
        nframes = self.field.shape[0]
        chunk_size = self.field.chunks[0]
        if chunk_size < 20:
            chunk_size = 50
        data = self.field.nxfile[self.path]
        if self.first == None:
            self.first = 0
        if self.last == None:
            self.last = self.field.shape[0]
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
            if self.pixel_mask is not None:
                v = np.ma.masked_array(v)
                v.mask = self.pixel_mask
            if maximum < v.max():
                maximum = v.max()
            del v
        if self.pixel_mask is not None:
            vsum = np.ma.masked_array(vsum)
            vsum.mask = self.pixel_mask
        self.summed_data = NXfield(vsum, name='summed_data')
        toc = self.stop_progress()
        self.logger.info('Maximum counts: %s (%g seconds)' % (maximum, toc-tic))
        return maximum

    def write_maximum(self, maximum):
        self.entry['data'].attrs['maximum'] = maximum
        self.entry['data'].attrs['first'] = self.first
        self.entry['data'].attrs['last'] = self.last
        if 'summed_data' in self.entry:
            del self.entry['summed_data']
        self.entry['summed_data'] = NXdata(self.summed_data,
                                           self.entry['data'].nxaxes[-2:])
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
            self.entry['radial_sum'] = NXdata(
                NXfield(intensity, name='radial_sum'),
                NXfield(polar_angle, name='polar_angle'))
        except Exception as error:
            self.logger.info('Unable to create radial sum')
        self.record('nxmax', maximum=maximum,
                    first_frame=self.first, last_frame=self.last)

    def nxfind(self):
        self.record_start('nxfind')
        if self.not_complete('nxfind') and self.find:
            if not self.data_exists():
                self.logger.info('Data file not available')
                return
            with Lock(self.data_file):
                peaks = self.find_peaks()
            if self.gui:
                if peaks:
                    self.result.emit(peaks)
                self.stop.emit()
            else:
                with Lock(self.wrapper_file):
                    self.write_peaks(peaks)
        elif self.find:
            self.logger.info('Peaks already found')
            self.record('nxfind')

    def find_peaks(self):
        self.logger.info("Finding peaks")
        if self.threshold is None:
            if self.maximum is None:
                self.nxmax()
            self.threshold = self.maximum / 10

        if self.first == None:
            self.first = 0
        if self.last == None:
            self.last = self.field.shape[0]
        z_min, z_max = self.first, self.last

        tic = self.start_progress(z_min, z_max)

        lio = labelimage(self.field.shape[-2:], flipper=flip1)
        allpeaks = []
        if len(self.field.shape) == 2:
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
                                        peak = NXpeak(res[0], res[22],
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
        if 'peaks' in self.entry:
            del self.entry['peaks']
        self.entry['peaks'] = group
        refine = NXRefine(self.entry)
        polar_angles, azimuthal_angles = refine.calculate_angles(refine.xp,
                                                                 refine.yp)
        refine.write_angles(polar_angles, azimuthal_angles)
        self.record('nxfind', threshold=self.threshold,
                    first_frame=self.first, last_frame=self.last,
                    peak_number=len(peaks))

    def nxcopy(self):
        self.record_start('nxcopy')
        if self.not_complete('nxcopy') and self.copy:
            if self.parent:
                self.copy_parameters()
                self.record('nxcopy', parent=self.parent)
            else:
                self.logger.info('No parent defined')
                self.record('nxcopy')
        elif self.copy:
            self.logger.info('Data already copied')
            self.record('nxcopy')

    def copy_parameters(self):
        with Lock(self.parent):
            input = nxload(self.parent)
            input_ref = NXRefine(input[self.entry_name])
        with Lock(self.wrapper_file):
            output_ref = NXRefine(self.entry)
            input_ref.copy_parameters(output_ref, sample=True, instrument=True)
        self.logger.info("Parameters copied from '%s'" %
                         os.path.basename(os.path.realpath(self.parent)))

    def nxrefine(self):
        self.record_start('nxrefine')
        if self.not_complete('nxrefine') and self.refine:
            if not self.complete('nxfind'):
                self.logger.info('Cannot refine until peak search is completed')
                return
            with Lock(self.wrapper_file):
                if self.lattice or self.first_entry:
                    lattice = True
                else:
                    lattice = False
                result = self.refine_parameters(lattice=lattice)
                if not self.gui:
                    self.write_refinement(result)
        elif self.refine:
            self.logger.info('HKL values already refined')
            self.record('nxrefine')

    def refine_parameters(self, lattice=False):
        refine = NXRefine(self.entry)
        refine.refine_hkls(lattice=lattice, chi=True, omega=True)
        fit_report=refine.fit_report
        refine.refine_hkls(chi=True, omega=True, phi=True)
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
        refine.write_parameters()
        self.record('nxrefine', fit_report=refine.fit_report)

    def nxtransform(self):
        self.record_start('nxtransform')
        if self.not_complete('nxtransform') and self.transform:
            if not self.complete('nxrefine'):
                self.logger.info('Cannot transform until the orientation is complete')
                return
            with Lock(self.wrapper_file):
                cctw_command = self.prepare_transform()
            if cctw_command:
                self.logger.info('Transform process launched')
                tic = timeit.default_timer()
                with Lock(self.data_file):
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
                self.record('nxtransform', command=cctw_command,
                            output=process.stdout.decode(),
                            errors=process.stderr.decode())
            else:
                self.logger.info('CCTW command invalid')
                self.record('nxtransform')
        elif self.transform:
            self.logger.info('Data already transformed')
            self.record('nxtransform')

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
            elif self.parent:
                with Lock(self.parent):
                    root = nxload(self.parent)
                    if 'transform' in root[self.entry_name]:
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

    def prepare_transform(self, mask=False):
        if mask:
            transform_file = self.masked_transform_file
        else:
            transform_file = self.transform_file
        self.get_transform_grid()
        if self.Qh and self.Qk and self.Ql:
            refine = NXRefine(self.entry)
            refine.read_parameters()
            refine.h_start, refine.h_step, refine.h_stop = self.Qh
            refine.k_start, refine.k_step, refine.k_stop = self.Qk
            refine.l_start, refine.l_step, refine.l_stop = self.Ql
            refine.define_grid()
            refine.prepare_transform(transform_file, mask=mask)
            if not mask:
                refine.write_settings(self.settings_file)
            return refine.cctw_command(mask)
        else:
            self.logger.info('Invalid HKL grid')
            return None

    def nxmasked_transform(self):
        self.record_start('nxmasked_transform')
        if self.not_complete('nxmasked_transform') and self.mask:
            with Lock(self.wrapper_file):
                self.calculate_mask()
                refine = NXRefine(self.entry)
                cctw_command = self.prepare_transform(mask=True)
            if cctw_command:
                self.logger.info('Masked transform launched')
                tic = timeit.default_timer()
                with Lock(self.data_file):
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
                            radius=self.radius, width=self.width,
                            command=cctw_command,
                            output=process.stdout.decode(),
                            errors=process.stderr.decode())
            else:
                self.logger.info('CCTW command invalid')
        elif self.mask:
            self.logger.info('Masked data already transformed')
            self.record('nxmasked_transform')

    def calculate_mask(self):
        self.logger.info("Calculating 3D mask")
        data_shape = self.entry['data/data'].shape
        mask = np.zeros(shape=data_shape, dtype=np.bool)
        x, y = np.arange(data_shape[2]), np.arange(data_shape[1])
        xp, yp, zp = self.entry['peaks/x'], self.entry['peaks/y'], self.entry['peaks/z']
        tic = self.start_progress(0, len(xp))
        inside = np.array([(x[np.newaxis,:]-int(cx))**2 + 
                          (y[:,np.newaxis]-int(cy))**2 < self.radius**2 
                          for cx,cy in zip(xp,yp)], dtype=np.bool)
        if self.width == 1:
            i, j = 0, 1
        elif self.width == 3:
            i, j = 1, 2
        elif self.width == 5:
            i, j = 2, 3
        for k, frame in enumerate([int(z) for z in zp]):
            if self.stopped:
                return None
            self.update_progress(frame)
            mask[frame-i:frame+j] = mask[frame-i:frame+j] | inside[k]
        root = nxload(self.mask_file, 'w')
        if 'entry' not in root:
            root['entry'] = NXentry()
        entry = root['entry']
        if 'mask' in entry:
            del entry['mask']
        entry['mask'] = mask
        mask_file = os.path.relpath(self.mask_file, os.path.dirname(self.wrapper_file))
        if 'data_mask' in self.data:
            del self.data['data_mask']
        self.data['data_mask'] = NXlink('entry/mask', mask_file)
        toc = self.stop_progress()
        self.logger.info("3D Mask stored in '%s' (%g seconds)"
                         % (self.mask_file, toc-tic))

    def nxreduce(self):
        self.nxlink()
        self.nxmax()
        self.nxfind()
        self.nxcopy()
        self.nxrefine()
        self.nxtransform()
        self.nxmasked_transform()

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
        if not self.server.is_running():
            raise NeXusError("NXServer not running")

        command = self.command(parent)
        if command:
            self.server.add_task(self.command(parent))
            now = datetime.datetime.now()
            # TODO: How should I handle nxparent command?
            if command.split()[0] == 'nxparent':
                return
            if self.link:
                nxdb.queue_task(self.wrapper_file, 'nxlink', self.entry_name)
            if self.maxcount:
                nxdb.queue_task(self.wrapper_file, 'nxmax', self.entry_name)
            if self.find:
                nxdb.queue_task(self.wrapper_file, 'nxfind', self.entry_name)
            if self.copy:
                nxdb.queue_task(self.wrapper_file, 'nxcopy', self.entry_name)
            if self.refine:
                nxdb.queue_task(self.wrapper_file, 'nxrefine', self.entry_name)
            if self.transform:
                if self.mask:
                    nxdb.queue_task(self.wrapper_file, 'nxmasked_transform', 
                                    self.entry_name)
                else:
                    nxdb.queue_task(self.wrapper_file, 'nxtransform', 
                                    self.entry_name)


class NXMultiReduce(NXReduce):

    def __init__(self, directory, entries=['f1', 'f2', 'f3'], 
                 mask=False, pdf=False, overwrite=False):
        super(NXMultiReduce, self).__init__(entry='entry', directory=directory,
                                            entries=entries, overwrite=overwrite)
        self.mask = mask
        self.pdf = pdf

    def complete(self, program):
        complete = True
        for entry in self.entries:
            if program not in self.root[entry]:
                complete = False
        return complete

    def nxcombine(self):
        if self.mask:
            task = 'masked_combine'
        else:
            task = 'nxcombine'
        self.record_start(task)
        if self.not_complete(task):
            if self.mask and not self.complete('nxmasked_transform'):
                self.logger.info('Cannot combine until masked transforms complete')
                return
            elif not self.complete('nxtransform'):
                self.logger.info('Cannot combine until transforms complete')
                return
            with Lock(self.wrapper_file):
                cctw_command = self.prepare_combine()
            if cctw_command:
                self.logger.info('Combining transforms (%s)'
                                 % ', '.join(self.entries))
                tic = timeit.default_timer()
                process = subprocess.run(cctw_command, shell=True,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
                toc = timeit.default_timer()
                if process.returncode == 0:
                    self.logger.info('Combine completed (%g seconds)'
                                     % (toc-tic))
                else:
                    self.logger.info(
                        'Combine completed - errors reported (%g seconds)'
                        % (toc-tic))
                self.record(task, command=cctw_command,
                            output=process.stdout.decode(),
                            errors=process.stderr.decode())
            else:
                self.logger.info('CCTW command invalid')
                self.record(task)
        else:
            self.logger.info('Data already combined')
            self.record(task)

    def prepare_combine(self):
        if self.mask:
            transform = 'masked_transform'
        else:
            transform = 'transform'
        try:
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
        nxdb.queue_task(self.wrapper_file, 'nxcombine', None)


class NXpeak(object):

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
        return "Peak x=%f y=%f z=%f np=%i avg=%f" % (self.x, self.y, self.z, self.np, self.average)

    def __repr__(self):
        return "Peak x=%f y=%f z=%f np=%i avg=%f" % (self.x, self.y, self.z, self.np, self.average)

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
