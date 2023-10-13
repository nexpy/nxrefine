# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from configparser import ConfigParser
from pathlib import Path

from nexusformat.nexus import NeXusError


class NXSettings(ConfigParser):
    """A ConfigParser subclass that preserves the case of option names"""

    def __init__(self, experiment=None, default=None, **kwargs):
        super().__init__(allow_no_value=True)
        self.file = self.get_file(experiment=experiment, default=default)
        self.directory = self.file.parent
        self.experiment = experiment
        self.read(self.file)
        sections = self.sections()
        if experiment:
            if 'server' in sections:
                self.remove_section('server')
            if 'nodes' in sections:
                self.remove_section('nodes')
        elif 'server' not in sections:
            self.add_section('server')
        if 'instrument' not in sections:
            self.add_section('instrument')
        if 'nxrefine' not in sections:
            self.add_section('nxrefine')
        if 'nxreduce' not in sections:
            self.add_section('nxreduce')
        if 'setup' in sections:
            for option in self.options('setup'):
                self.set('server', option, self.get('setup', option))
            self.remove_section('setup')
            self.save()
        self.add_defaults()

    def __repr__(self):
        return f"NXSettings({self.file})"

    def get_file(self, experiment=None, default=None):
        self.home_settings = ConfigParser()
        home_directory = Path.home() / '.nxserver'
        if not home_directory.exists():
            home_directory.mkdir()
        self.home_file = home_directory / 'settings.ini'
        self.home_settings.read(self.home_file)
        if 'setup' not in self.home_settings.sections():
            self.home_settings.add_section('setup')
        if default:
            self.home_settings.set('setup', 'directory', default)
            with open(self.home_file, 'w') as f:
                self.home_settings.write(f)
        elif self.home_settings.has_option('setup', 'directory'):
            default = self.home_settings.get('setup', 'directory')
        if default:
            default = Path(default).resolve()
            if default.name != 'nxserver':
                default = default / 'nxserver'
            if not default.exists():
                default.mkdir()
            if not default.joinpath('locks').exists():
                default.joinpath('locks').mkdir(mode=0o777)
        if experiment is None and default is None:
            raise NeXusError(
                "Please define settings directory - type 'nxsettings -h'")
        elif experiment is None:
            return default / 'settings.ini'
        else:
            experiment = Path(experiment).resolve()
            if experiment.name != 'tasks':
                if experiment.joinpath('tasks').exists():
                    experiment = experiment / 'tasks'
                else:
                    raise NeXusError(
                        f"'{experiment}' not a valid directory for settings")
            if not experiment.joinpath('settings.ini').exists():
                if default and default.joinpath('settings.ini').exists():
                    experiment.joinpath('settings.ini').write_text(
                        default.joinpath('settings.ini').read_text())
            return experiment / 'settings.ini'

    def add_defaults(self):
        settings_changed = False
        if self.experiment is None:
            default = {'type': 'multicore', 'cores': 4, 'concurrent': True,
                       'run_command': None, 'template': None, 'cctw': 'cctw'}
            for p in default:
                if not self.has_option('server', p):
                    self.set('server', p, default[p])
                    settings_changed = True
        default = {'source': None, 'instrument': None,
                   'raw_home': None, 'raw_path': None,
                   'analysis_home': None, 'analysis_path': None}
        for p in default:
            if not self.has_option('instrument', p):
                self.set('instrument', p, default[p])
                settings_changed = True
        default = {'wavelength': 0.141, 'distance': 650, 'geometry': 'default',
                   'phi': -5.0, 'phi_end': 360.0, 'phi_step': 0.1,
                   'chi': -90.0, 'omega': 0.0, 'theta': 0.0,
                   'x': 0.0, 'y': 0.0,
                   'nsteps': 3, 'frame_rate': 10}
        for p in default:
            if not self.has_option('nxrefine', p):
                self.set('nxrefine', p, default[p])
                settings_changed = True
        default = {'threshold': 50000, 'min_pixels': 10,
                   'first': 10, 'last': 3640,
                   'polar_max': 10.0, 'hkl_tolerance': 0.05,
                   'monitor': 'monitor2', 'norm': 30000,
                   'polarization': 0.99, 'qmin': 6.0, 'qmax': 16.0,
                   'radius': 0.2}
        for p in default:
            if not self.has_option('nxreduce', p):
                self.set('nxreduce', p, default[p])
                settings_changed = True
        if settings_changed:
            self.save()

    def input_defaults(self):
        for s in ['server', 'instrument', 'NXRefine', 'NXReduce']:
            print(f'\n{s} Parameters\n-------------------')
            s = s.lower()
            for p in self.options(s):
                value = input(f"{p} [{self.get(s, p)}]: ")
                if value:
                    self.set(s, p, value)
        self.save()

    @property
    def settings(self):
        _settings = {}
        if self.experiment is None:
            _settings['server'] = {k: v for (k, v) in self.items('server')}
        _settings['instrument'] = {k: v for (k, v) in self.items('instrument')}
        _settings['nxrefine'] = {k: v for (k, v) in self.items('nxrefine')}
        _settings['nxreduce'] = {k: v for (k, v) in self.items('nxreduce')}
        return _settings

    def get(self, section, option, **kwargs):
        value = super().get(section, option, **kwargs)
        if value in [None, 'None', 'none', '']:
            return None
        elif value in ['True', 'true', 'Yes', 'yes', 'Y', 'y']:
            return True
        elif value in ['False', 'false', 'No', 'no', 'N', 'n']:
            return False
        else:
            try:
                v = float(value)
                if v.is_integer():
                    return int(v)
                else:
                    return v
            except ValueError:
                return value

    def set(self, section, option, value=None):
        if isinstance(value, int) or isinstance(value, float):
            super().set(section, option, f"{value:g}")
        elif value is not None:
            super().set(section, option, str(value))
        else:
            super().set(section, option)

    def save(self):
        with open(self.file, 'w') as f:
            self.write(f)
