# -----------------------------------------------------------------------------
# Copyright (c) 2015-2023, AXMAS Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import re
import sys
from datetime import datetime

if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points

from pathlib import Path

import numpy as np
from nexusformat.nexus import (NeXusError, NXattenuator, NXcollection, NXdata,
                               NXfield, NXfilter, NXinstrument, NXmonitor,
                               NXsource, nxopen)

from .nxsettings import NXSettings

prefix_pattern = re.compile(r'^([^.]+)(?:(?<!\d)|(?=_))')
file_index_pattern = re.compile(r'^(.*?)([0-9]*)[.](.*)$')
directory_index_pattern = re.compile(r'^(.*?)([0-9]*)$')


def import_beamlines():
    for entry in entry_points(group='nxrefine.beamlines'):
        try:
            entry.load()
        except Exception:
            pass


def get_beamlines():
    """Return a list of available beamline names

    Returns
    -------
    list of str
        Names of beamlines defined by NXBeamLine subclasses
    """    
    return [beamline.name for beamline in NXBeamLine.__subclasses__()]


def get_beamline(instrument=None):
    """Return subclass of NXBeamLine for a particular instrument

    Parameters
    ----------
    instrument : str, optional
        Name of the instrument, by default None. If not specified, the
        instrument defined by the default server settings is used.

    Returns
    -------
    NXBeamLine
        Subclass of NXBeamLine for the requested instrument
    """    
    if instrument is None:
        instrument = NXSettings().settings['instrument']['instrument']
    if instrument == '':
        raise NeXusError("No beamline defined in settings")
    else:
        for beamline in NXBeamLine.__subclasses__():
            if beamline.name == instrument:
                return beamline
        raise NeXusError(f"No beamline defined for '{instrument}'")


class NXBeamLine:
    """Generic class containing facility-specific information"""

    name = 'Unknown'
    source_name = 'Unknown'
    source_type = 'Synchrotron X-Ray Source'
    make_scans_enabled = False
    import_data_enabled = False

    def __init__(self, reduce=None, directory=None, *args, **kwargs):
        self.reduce = reduce
        if self.reduce:
            self.directory = Path(self.reduce.directory)
            self.base_directory = self.directory.parent
            self.root = self.reduce.root
            self.entry = self.reduce.entry
            self.scan = self.reduce.scan
            self.sample = self.reduce.sample
            self.label = self.reduce.label
            self.monitor = self.reduce.monitor
        elif directory:
            self.directory = Path(directory)
            self.base_directory = self.directory
            self.label = self.base_directory.name
            self.sample = self.base_directory.parent.name
            self.root = self.entry = self.scan = self.monitor = None
        self.settings = NXSettings(self.base_directory.parent.parent).settings
        self.experiment = self.settings['instrument']['experiment']
        self.raw_home = Path(self.settings['instrument']['raw_home'])
        self.raw_path = self.settings['instrument']['raw_path']
        self.raw_directory = self.raw_home / self.experiment / self.raw_path
        self.probe = 'xrays'

    def __repr__(self):
        return f"NXBeamLine('{self.name}')"

    def make_scans(self, *args, **kwargs):
        raise NeXusError(
            f"Making scan macros not implemented for {self.beamline.name}")

    def import_data(self, *args, **kwargs):
        raise NeXusError(
            f"Importing data not implemented for {self.beamline.name}")

    def load_data(self, *args, **kwargs):
        if self.reduce:
            return self.reduce.raw_data_exists()
        else:
            return False

    def read_logs(self, *args, **kwargs):
        pass

    def read_monitor(self, monitor=None):
        pass


class Sector6Beamline(NXBeamLine):

    name = '6-ID-D'
    source_name = 'Advanced Photon Source'
    make_scans_enabled = True
    import_data_enabled = False

    def __init__(self, reduce=None, *args, **kwargs):
        super().__init__(reduce)

    def make_scans(self, scan_files, command='Pil2Mscan'):
        command = self.textbox['Scan Command'].text()
        parameters = ['#command path filename temperature detx dety '
                      'phi_start phi_step phi_end chi omega frame_rate']
        for scan_file in [Path(f) for f in scan_files]:
            root = nxopen(scan_file)
            temperature = root.entry.sample.temperature
            scan_dir = scan_file.stem.replace(self.sample+'_', '')
            for entry in [root[e] for e in root if e[-1].isdigit()]:
                if 'phi_set' in entry['instrument/goniometer']:
                    phi_start = entry['instrument/goniometer/phi_set']
                else:
                    phi_start = entry['instrument/goniometer/phi']
                phi_step = entry['instrument/goniometer/phi'].attrs['step']
                phi_end = entry['instrument/goniometer/phi'].attrs['end']
                if 'chi_set' in entry['instrument/goniometer']:
                    chi = entry['instrument/goniometer/chi_set']
                else:
                    chi = entry['instrument/goniometer/chi']
                if 'omega_set' in entry['instrument/goniometer']:
                    omega = entry['instrument/goniometer/omega_set']
                else:
                    omega = entry['instrument/goniometer/omega']
                dx = entry['instrument/detector/translation_x']
                dy = entry['instrument/detector/translation_y']
                if ('frame_time' in entry['instrument/detector'] and
                        entry['instrument/detector/frame_time'] > 0.0):
                    frame_rate = 1.0 / entry['instrument/detector/frame_time']
                else:
                    frame_rate = 10.0
                scan_file = entry.nxname
                if command == 'Pil2Mscan':
                    parameters.append(
                        f'{command} '
                        f'{scan_file.parent.joinpath(scan_dir)} '
                        f'{scan_file} {temperature:.6g} {dx:.6g} {dy:.6g} '
                        f'{phi_start:.6g} {phi_step:.6g} {phi_end:.6g} '
                        f'{chi:.6g} {omega:.6g} {frame_rate:.6g}')
            if command == 'Pil2Mstring':
                parameters.append(f'Pil2Mstring("{scan_dir}")')
            elif command != 'Pil2Mscan':
                parameters.append(f'{command} {temperature}')
        return parameters

    def read_logs(self):
        """Read metadata from experimental scans."""
        head_file = self.directory / f"{self.entry.nxname}_head.txt"
        meta_file = self.directory / f"{self.entry.nxname}_meta.txt"
        if head_file.exists() and meta_file.exists():
            logs = NXcollection()
        else:
            if not head_file.exists():
                self.reduce.log(
                    f"'{self.entry.nxname}_head.txt' does not exist")
            if not meta_file.exists():
                self.reduce.log(
                    f"'{self.entry.nxname}_meta.txt' does not exist")
            raise NeXusError('Metadata files not available')
        with open(head_file) as f:
            lines = f.readlines()
        for line in lines:
            key, value = line.split(', ')
            value = value.strip('\n')
            try:
                value = float(value)
            except Exception:
                pass
            logs[key] = value
        meta_input = np.genfromtxt(meta_file, delimiter=',', names=True)
        for i, key in enumerate(meta_input.dtype.names):
            logs[key] = [array[i] for array in meta_input]

        with self.reduce:
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
            self.entry['instrument/source/name'] = self.source_name
            self.entry['instrument/source/type'] = self.source_type
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
            if 'Shutter' in logs:
                if 'filter' not in self.entry['instrument']:
                    self.entry['instrument/filter'] = NXfilter()
                transmission = NXfield(1.0 - logs['Shutter'][:frames],
                                       name='transmission')
                frames = NXfield(np.array(range(frames)), name='frame_number')
                if 'transmission' in self.entry['instrument/filter']:
                    del self.entry['instrument/filter/transmission']
                self.entry['instrument/filter/transmission'] = (
                    NXdata(transmission, frames))
                time_path = 'entry/instrument/NDAttributes/NDArrayTimeStamp'
            if time_path in self.root:
                start = datetime.fromtimestamp(f[time_path][0])
                # In EPICS, the epoch started in 1990, not 1970
                start_time = start.replace(year=start.year+20).isoformat()
                self.entry['start_time'] = start_time
                self.entry['data/frame_time'].attrs['start'] = start_time

    def read_monitor(self, monitor=None):
        try:
            from scipy.signal import savgol_filter
            if monitor is None:
                if self.monitor is None:
                    monitor = self.settings['nxreduce']['monitor']
                else:
                    monitor = self.monitor
            if monitor in self.entry:
                monitor_signal = self.entry[monitor].nxsignal
            elif monitor in self.entry['instrument/logs']:
                monitor_signal = self.entry[
                    f'instrument/logs/{monitor}']
            monitor_signal = monitor_signal.nxvalue[:self.reduce.nframes]
            monitor_signal[0] = monitor_signal[1]
            monitor_signal[-1] = monitor_signal[-2]
            monitor_signal = monitor_signal / self.reduce.norm
            if monitor_signal.size > 1000:
                filter_size = 501
            elif monitor_signal.size > 200:
                filter_size = 101
            else:
                filter_size = monitor_signal.size
            return savgol_filter(monitor_signal, filter_size, 2)
        except Exception as error:
            self.reduce.log(f"Cannot identify monitor {self.monitor}")
            return np.ones(shape=(self.reduce.nframes), dtype=float)


import_beamlines()
