# -----------------------------------------------------------------------------
# Copyright (c) 2023-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import logging
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
                               NXfield, NXfilter, NXgoniometer, NXinstrument,
                               NXmonitor, NXsource, nxopen)

from .nxsettings import NXSettings

logger = logging.getLogger(__name__)

prefix_pattern = re.compile(r'^([^.]+)(?:(?<!\d)|(?=_))')
file_index_pattern = re.compile(r'^(.*?)([0-9]*)[.](.*)$')
directory_index_pattern = re.compile(r'^(.*?)([0-9]*)$')

_beamlines_imported = False


def import_beamlines():
    """Load NXBeamLine subclasses registered via the
    ``nxrefine.beamlines`` entry-point group.

    Idempotent; subsequent calls are no-ops. Plugins that fail to
    import are logged with a traceback so authors can diagnose them
    instead of silently disappearing.
    """
    global _beamlines_imported
    if _beamlines_imported:
        return
    for entry in entry_points(group='nxrefine.beamlines'):
        try:
            entry.load()
        except Exception:
            logger.warning(
                f"Failed to load nxrefine beamline plugin {entry.name!r}",
                exc_info=True)
    _beamlines_imported = True


def _all_subclasses(cls):
    """Yield every direct and indirect subclass of ``cls``."""
    for sub in cls.__subclasses__():
        yield sub
        yield from _all_subclasses(sub)


def _discover_beamlines():
    """Return ``{name: subclass}`` for every registered beamline.

    Plugins are discovered lazily on first call. Two plugins
    registering the same ``name`` produce a warning, with the
    later-loaded one winning.
    """
    import_beamlines()
    registry = {}
    for cls in _all_subclasses(NXBeamLine):
        name = cls.name
        existing = registry.get(name)
        if existing is not None and existing is not cls:
            logger.warning(
                f"Duplicate beamline name {name!r}: "
                f"{existing.__module__}.{existing.__name__} replaced by "
                f"{cls.__module__}.{cls.__name__}")
        registry[name] = cls
    return registry


def get_beamlines():
    """Return a list of available beamline names.

    Returns
    -------
    list of str
        Names of beamlines defined by NXBeamLine subclasses, including
        plugins discovered via the ``nxrefine.beamlines`` entry-point
        group.
    """
    return list(_discover_beamlines())


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
    try:
        return _discover_beamlines()[instrument]
    except KeyError:
        raise NeXusError(f"No beamline defined for '{instrument}'")


class NXBeamLine:
    """Generic class containing facility-specific information"""

    name = 'Unknown'
    source_name = 'Unknown'
    source_type = 'Synchrotron X-Ray Source'
    create_macro_enabled = False
    import_data_enabled = False

    def __init__(self, reduce=None, directory=None, *args, **kwargs):
        self.reduce = reduce
        if self.reduce:
            self.directory = self.reduce.directory
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

    def create_macro(self, *args, **kwargs):
        raise NeXusError(
            f"Making scan macros not implemented for {self.name}")

    def import_data(self, *args, **kwargs):
        raise NeXusError(
            f"Importing data not implemented for {self.name}")

    def load_data(self, *args, **kwargs):
        if self.reduce:
            return self.reduce.raw_data_exists()
        else:
            return False

    def get_logs(self):
        """Return an NXcollection of raw beamline log values, or None."""
        return None

    def get_source(self, logs=None):
        """Return an NXsource describing this beamline, or None."""
        return None

    def get_attenuator(self, logs=None):
        """Return an NXattenuator, or None."""
        return None

    def get_filter_transmission(self, logs=None):
        """Return an NXdata holding per-frame filter transmission, or None."""
        return None

    def get_monitor(self, logs=None):
        """Return an NXmonitor for the channel named by ``self.monitor``,
        or None.

        Subclasses decide how to map ``self.monitor`` to their raw data
        source; only one monitor is ever written to the wrapper file,
        at ``entry['monitor']``.
        """
        return None

    def get_goniometer(self, logs=None):
        """Return an NXgoniometer holding any goniometer angles
        (phi/chi/theta/omega) that this beamline can supply from its
        raw logs, or None.

        Unlike the other ``get_*`` hooks, the returned group is
        *merged* into ``entry['instrument/goniometer']`` rather than
        replacing it: only the fields supplied by the beamline are
        overwritten, so angles set elsewhere (e.g. by the
        ``experiment/new_configuration`` plugin) are preserved when
        the beamline doesn't supply them.

        Beamlines that get goniometer values from a separate
        configuration step (e.g. Sector 6) should leave this as
        ``None``; beamlines whose log files carry the actual scan
        angles (e.g. QM2 reading from a SPEC file) override it.
        """
        return None

    def get_start_time(self, logs=None):
        """Return an ISO-format start time, or None."""
        return None

    def read_logs(self):
        """Populate the wrapper entry with metadata from this beamline.

        Composes the ``get_*`` accessors and writes the results in the
        canonical NeXus paths. Subclasses normally only need to override
        the ``get_*`` methods; override ``read_logs`` itself only when
        the default layout doesn't fit.
        """
        with self.reduce:
            if 'instrument' not in self.entry:
                self.entry['instrument'] = NXinstrument()
            # Sweep pre-refactor monitor groups so old wrappers don't
            # accumulate stale data alongside the new entry['monitor'].
            for stale in ('monitor1', 'monitor2'):
                if stale in self.entry:
                    del self.entry[stale]
            logs = self.get_logs()
            for path, value in (
                    ('instrument/logs',       logs),
                    ('instrument/source',     self.get_source(logs)),
                    ('instrument/attenuator', self.get_attenuator(logs)),
                    ('monitor',               self.get_monitor(logs)),
            ):
                if value is not None:
                    if path in self.entry:
                        del self.entry[path]
                    self.entry[path] = value
            ft = self.get_filter_transmission(logs)
            if ft is not None:
                if 'filter' not in self.entry['instrument']:
                    self.entry['instrument/filter'] = NXfilter()
                if 'transmission' in self.entry['instrument/filter']:
                    del self.entry['instrument/filter/transmission']
                self.entry['instrument/filter/transmission'] = ft
            goniometer = self.get_goniometer(logs)
            if goniometer is not None:
                if 'goniometer' not in self.entry['instrument']:
                    self.entry['instrument/goniometer'] = NXgoniometer()
                target = self.entry['instrument/goniometer']
                for name in goniometer.entries:
                    if name in target:
                        del target[name]
                    target[name] = goniometer[name]
            start = self.get_start_time(logs)
            if start is not None:
                self.entry['start_time'] = start
                if 'data/frame_time' in self.entry:
                    self.entry['data/frame_time'].attrs['start'] = start

    def read_monitor(self, monitor=None):
        """Return the per-frame monitor signal used for normalization.

        Reads from ``entry['monitor']`` written by ``read_logs``, with
        a fallback to ``entry['instrument/logs/{monitor}']`` for raw
        data that hasn't been promoted to an NXmonitor.
        """
        try:
            from scipy.signal import savgol_filter
            if monitor is None:
                monitor = self.monitor
            if 'monitor' in self.entry:
                monitor_signal = self.entry['monitor'].nxsignal
            elif (monitor is not None
                  and 'instrument/logs' in self.entry
                  and monitor in self.entry['instrument/logs']):
                monitor_signal = self.entry[f'instrument/logs/{monitor}']
            else:
                raise NeXusError(f"Monitor {monitor!r} not found")
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
        except Exception:
            self.reduce.log(f"Cannot identify monitor {self.monitor}")
            return np.ones(shape=(self.reduce.nframes), dtype=float)


class Sector6Beamline(NXBeamLine):

    name = '6-ID-D'
    source_name = 'Advanced Photon Source'
    create_macro_enabled = True
    import_data_enabled = False

    def __init__(self, reduce=None, *args, **kwargs):
        super().__init__(reduce)

    def create_macro(self, scan_files, command='Pil2Mscan'):
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

    def get_logs(self):
        head_file = self.directory / f"{self.entry.nxname}_head.txt"
        meta_file = self.directory / f"{self.entry.nxname}_meta.txt"
        if not (head_file.exists() and meta_file.exists()):
            if not head_file.exists():
                self.reduce.log(
                    f"'{self.entry.nxname}_head.txt' does not exist")
            if not meta_file.exists():
                self.reduce.log(
                    f"'{self.entry.nxname}_meta.txt' does not exist")
            raise NeXusError('Metadata files not available')
        logs = NXcollection()
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
        return logs

    def get_source(self, logs=None):
        source = NXsource()
        source['name'] = self.source_name
        source['type'] = self.source_type
        source['probe'] = 'x-ray'
        if logs is not None:
            if 'Storage_Ring_Current' in logs:
                source['current'] = logs['Storage_Ring_Current']
            if 'SCU_Current' in logs:
                source['undulator_current'] = logs['SCU_Current']
            if 'UndulatorA_gap' in logs:
                source['undulator_gap'] = logs['UndulatorA_gap']
        return source

    def get_attenuator(self, logs=None):
        if logs is None or 'Calculated_filter_transmission' not in logs:
            return None
        attenuator = NXattenuator()
        attenuator['attenuator_transmission'] = (
            logs['Calculated_filter_transmission'])
        return attenuator

    def get_filter_transmission(self, logs=None):
        if logs is None or 'Shutter' not in logs:
            return None
        frames = self.entry['data/frame_number'].size
        transmission = NXfield(1.0 - logs['Shutter'][:frames],
                               name='transmission')
        frame_field = NXfield(np.arange(frames), name='frame_number')
        return NXdata(transmission, frame_field)

    def get_monitor(self, logs=None):
        if (logs is None or self.monitor is None
                or self.monitor not in logs):
            return None
        frame_number = self.entry['data/frame_number']
        frames = frame_number.size
        data = logs[self.monitor][:frames]
        # Remove outliers at beginning and end of frames
        data[0] = data[1]
        data[-1] = data[-2]
        monitor = NXmonitor(NXfield(data, name=self.monitor), frame_number)
        if 'data/frame_time' in self.entry:
            monitor['frame_time'] = self.entry['data/frame_time']
        return monitor

    def get_start_time(self, logs=None):
        time_path = 'entry/instrument/NDAttributes/NDArrayTimeStamp'
        if time_path not in self.root:
            return None
        start = datetime.fromtimestamp(self.root[time_path][0])
        # In EPICS, the epoch started in 1990, not 1970
        return start.replace(year=start.year+20).isoformat()
