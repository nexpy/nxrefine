import os
import socket
import sys
import timeit
import numpy as np

import portalocker

from nexusformat.nexus import *

from . import blobcorrector, __version__
from .connectedpixels import blob_moments
from .labelimage import labelimage, flip1
from .nxserver import NXServer


class NXReduce(object):

    def __init__(self, directory, entry='f1', data='data/data', parent=None,
                 extension='.h5', path='/entry/data/data',
                 threshold=None, first=None, last=None, 
                 refine=False, overwrite=False):

        self.directory = directory.rstrip('/')
        self.sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
        self.label = os.path.basename(os.path.dirname(directory))
        self.scan = os.path.basename(directory)
        
        self.wrapper_file = os.path.join(self.sample, self.label, 
                                         '%s_%s.nxs' % (self.sample, self.scan))
        self._root = None 
        self._entry = entry
        self._data = data
        self._mask = None
        self._parent = None
        
        self.extension = extension
        self.path = path

        self.threshold = threshold
        self._maximum = None
        self.first = first
        self.last = last
        self.refine = refine
        self.overwrite = overwrite

    @property
    def command(self):
        switches = '-d %s -e %s' % (self.directory, self._entry)
        if self.refine:
            switches += ' -r'
        if self.overwrite:
            switches += ' -o'
        return 'nxtask ' + switches

    @property
    def root(self):
        if self._root is None:
            with portalocker.Lock(self.wrapper_file, timeout=30):
                self._root = nxload(self.wrapper_file, 'r+')
        return self._root

    @property
    def entry(self):
        return self.root[self._entry]

    @property
    def data(self):
        if self._data is None:
            try:
                with portalocker.Lock(self.data_file, timeout=30):
                    self._data = nxload(self.data_file, 'r')[self.data_target]
            except Exception as error:
                pass
        return self._data

    @property
    def data_file(self):
        return self.entry[self._data].nxfilename

    @property
    def data_target(self):
        return self.entry[self._data].nxtarget

    @property
    def mask(self):
        if self._mask is None:
            try:
                self._mask = self.entry['instrument/detector/pixel_mask'].nxvalue
            except Exception as error:
                pass
        return self._mask

    @property
    def parent(self):
        return self._parent

    @property
    def maximum(self):
        if self._maximum is None:
            if 'maximum' in self.entry['data'].attrs:
                self._maximum = self.entry['data'].attrs['maximum']
            elif 'maximum' in self.entry['peaks'].attrs:
                self._maximum = self.entry['peaks'].attrs['maximum']
        return self._maximum

    def peaks_done(self):
        return 'peaks' in self.entry

    def update_progress(self, i):
        s = 'Frame %d' % i
        if i > 0:
            s = '\r' + s
        logging.infos, end='')

    def link_data(self):
        if self.data:
            with portalocker.Lock(self.wrapper_file, timeout=30):
                data_shape = self.data.shape
                if 'data' not in self.entry:
                    self.entry['data'] = NXdata()
                    self.entry['data/x_pixel'] = np.arange(data_shape[2], dtype=np.int32)
                    self.entry['data/y_pixel'] = np.arange(data_shape[1], dtype=np.int32)
                    self.entry['data/frame_number'] = np.arange(data_shape[0], dtype=np.int32)
                    self.entry['data/data'] = NXlink(self.data_target, self.data_file)
                else:
                    if self.entry['data/frame_number'].shape != data_shape[0]:
                        del self.entry['data/frame_number']
                        self.entry['data/frame_number'] = np.arange(data_shape[0], dtype=np.int32)
                        logging.info('Fixed frame number axis')
                    if ('data' in entry['data'] and 
                        entry['data/data']._filename != data_file):
                        del entry['data/data']
                        entry['data/data'] = NXlink(data_target, data_file)
                        logging.info('Fixed path to external data')
                self.entry['data'].nxsignal = self.entry['data/data']
                self.entry['data'].nxaxes = [self.entry['data/frame_number'], 
                                             self.entry['data/y_pixel'], 
                                             self.entry['data/x_pixel']] 
        else:
            logging.info('No raw data file found')

    def read_logs(self):
        head_file = os.path.join(self.directory, entry+'_head.txt')
        meta_file = os.path.join(self.directory, entry+'_meta.txt')
        if os.path.exists(head_file) or os.path.exists(meta_file):
            logs = NXcollection()
        else:
            logging.info('No metadata files found')
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
        with portalocker.Lock(self.wrapper_file, timeout=30):
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

    def find_maximum(self):
        maximum = 0.0
        if len(self.data.shape) == 2:
            maximum = self.data[:,:].max()
        else:
            nframes = self.data.shape[0]
            chunk_size = self.data.chunks[0]
            for i in range(0, nframes, chunk_size):
                try:
                    update_progress(i)
                    v = self.data[i:i+chunk_size,:,:]
                except IndexError as error:
                    pass
                if self.mask is not None:
                    v = np.ma.masked_array(v)
                    v.mask = self.mask
                if maximum < v.max():
                    maximum = v.max()
                del v
        return maximum

    @lock_file(self.data_file)
    def find_peaks(self):
        if self.threshold is None:
            if self.maximum is None:
                self._maximum = self.find_maximum()     
            self.threshold = self.maximum / 10

        z_min, z_max = self.first, self.last
        if z_min == None:
            z_min = 0
        if z_max == None:
            z_max = self.data.shape[0]

        lio = labelimage(self.data.shape[-2:], flipper=flip1)
        allpeaks = []
        if len(self.data.shape) == 2:
            res = None
        else:
            chunk_size = self.data.chunks[0]
            pixel_tolerance = 50
            frame_tolerance = 10
            nframes = self.data.shape[0]
            for i in range(0, nframes, chunk_size):
                try:
                    if i + chunk_size > z_min and i < z_max:
                        update_progress(i)
                        v = self.data[i:i+chunk_size,:,:].nxvalue
                        for j in range(chunk_size):
                            if i+j >= z_min and i+j <= z_max:
                                omega = np.float32(i+j)
                                lio.peaksearch(v[j], threshold, omega)
                                if lio.res is not None:
                                    blob_moments(lio.res)
                                    for k in range(lio.res.shape[0]):
                                        res = lio.res[k]
                                        peak = NXpeak(res[0], res[22],
                                            res[23], res[24], omega,
                                            res[27], res[26], res[29],
                                            threshold,
                                            pixel_tolerance,
                                            frame_tolerance)
                                        if peak.isvalid(self.mask):
                                            allpeaks.append(peak)
                except IndexError as error:
                    pass

        if not allpeaks:
            raise NeXusError('No peaks found')

        allpeaks = sorted(allpeaks)
        
        logging.info('\nMerging peaks')

        merged_peaks = []
        for z in range(z_min, z_max+1):
            update_progress(z)
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
        
        group = NXdata()
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
        note = NXnote('nxfind '+' '.join(sys.argv[1:]), 
                      ('Current machine: %s\n'
                       'Current working directory: %s')
                       % (socket.gethostname(), os.getcwd()))
        group['nxfind'] = NXprocess(program='nxfind', 
                                    sequence_index=len(entry.NXprocess)+1, 
                                    version=__version__, 
                                    note=note)
        return group

    def copy(self):
        if self.parent:
            input = nxload(self.parent)
            input_ref = NXRefine(input[self._entry])
            output = nxload(output_file, 'rw')
            output_entry_ref = NXRefine(output['entry'])
            input_ref.copy_parameters(output_entry_ref, sample=True)
            for name in [entry for entry in input if entry != 'entry']:
                if name in output: 
                    input_ref = NXRefine(input[name])
                    output_ref = NXRefine(output[name])
                    input_ref.copy_parameters(output_ref, instrument=True)
                    if 'sample' not in output[name] and 'sample' in input['entry']:
                        output_entry_ref.link_sample(output_ref)

    def reduce(self):
        subprocess.call('nxlink -d %s -e %s' % (directory, entry), shell=True)
        subprocess.call('nxmax -d %s -e %s' % (directory, entry), shell=True)
        subprocess.call('nxfind -d %s -e %s -f %s -l %s'
                        % (directory, entry, first, last), shell=True)

    if parent:
        subprocess.call('nxcopy -i %s -o %s' % (parent, wrapper_file), shell=True)
    if refine and 'orientation_matrix' in root[entries[0]]['instrument/detector']:
        subprocess.call('nxrefine -d %s' % directory, shell=True)
    if transform:
        if parent:
            subprocess.call('nxtransform -d %s -p %s' % (directory, parent), shell=True)
        else:
            subprocess.call('nxtransform -d %s' % directory, shell=True)
        subprocess.call('nxcombine -d %s' % directory, shell=True)



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
