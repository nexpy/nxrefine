# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os
from configparser import ConfigParser
from pathlib import Path

from nexusformat.nexus import NeXusError


class NXSettings(ConfigParser):
    """A ConfigParser subclass that preserves the case of option names"""

    def __init__(self, directory=None, create=False, **kwargs):
        super().__init__(allow_no_value=True)
        self.defaults = {
            'server': {'type': 'multicore', 'cores': 4, 'concurrent': True,
                       'run_command': None, 'template': None, 'cctw': 'cctw'},
            'instrument': {'source': None, 'instrument': None,
                           'raw_home': None, 'raw_path': None,
                           'analysis_home': None, 'analysis_path': None},
            'nxrefine': {'wavelength': 0.2, 'distance': 500,
                         'detector_orientation': '-y +z -x',
                         'phi': -5.0, 'phi_end': 360.0, 'phi_step': 0.1,
                         'chi': 0.0, 'omega': 0.0, 'theta': 0.0,
                         'x': 0.0, 'y': 0.0,
                         'nsteps': 3, 'frame_rate': 10},
            'nxreduce': {'threshold': 50000, 'min_pixels': 10,
                         'first': 10, 'last': 3640,
                         'polar_max': 10.0, 'hkl_tolerance': 0.05,
                         'monitor': 'monitor1', 'norm': 50000,
                         'polarization': 0.99, 'qmin': 5.0, 'qmax': 10.0,
                         'radius': 0.2}
        }
        self.create = create
        if directory:
            directory = Path(directory).resolve()
        self.file = self.get_file(directory)
        if self.file is None:
            raise NeXusError(f'{directory} is not a valid directory')
        self.directory = self.file.parent
        if self.create:
            self.make_file()
        else:
            self.read()

    def __repr__(self):
        return f"NXSettings({self.file})"

    def get_file(self, directory=None):
        if directory is None:
            if 'NX_SERVER' in os.environ:
                directory = Path(os.environ['NX_SERVER'])
            else:
                home_file = Path.home() / '.nxserver' / 'settings.ini'
                try:
                    home_settings = ConfigParser()
                    home_settings.read(home_file)
                    directory = Path(home_settings.get('setup', 'directory'))
                except Exception:
                    raise NeXusError("Default server settings not defined")
            if directory.name != 'nxserver':
                directory = directory / 'nxserver'
        if directory.exists():
            if directory.name == 'nxserver':
                self.server = True
                return directory / 'settings.ini'
            elif directory.name == 'tasks':
                self.server = False
                return directory / 'settings.ini'
            elif directory.joinpath('nxserver').exists():
                self.server = True
                return directory / 'nxserver' / 'settings.ini'
            elif directory.joinpath('tasks').exists():
                self.server = False
                return directory / 'tasks' / 'settings.ini'
            elif directory.joinpath('nxrefine').exists():
                self.server = False
                return directory / 'nxrefine' / 'tasks' / 'settings.ini'
        return None

    def make_file(self):
        if self.file.exists():
            return
        Path(self.file.parent).mkdir(parents=True, exist_ok=True)
        if self.server:
            self.set_defaults()
            self.save()
            if not self.file.parent.joinpath('locks').exists():
                self.file.parent.joinpath('locks').mkdir(mode=0o777)
        else:
            default_file = self.get_file()
            self.file.write_text(default_file.read_text())
            self.read()
            self.save()

    def set_defaults(self):

        def update_section(section):
            if section not in self.sections():
                self.add_section(section)
            for option in self.options(section):
                if option not in self.defaults[section]:
                    self.remove_option(section, option)
            for option in self.defaults[section]:
                if not self.has_option(section, option):
                    self.set(section, option, self.defaults[section][option])
            
        if self.server:
            if 'setup' in self.sections():
                for option in self.options('setup'):
                    self.set('server', option, self.get('setup', option))
                self.remove_section('setup')
            update_section('server')
        else:
            for section in ['server', 'nodes', 'setup']:
                if section in self.sections():
                    self.remove_section(section)
        update_section('instrument')
        update_section('nxrefine')
        update_section('nxreduce')

    def input_defaults(self):
        sections = ['Instrument', 'NXRefine', 'NXReduce']
        if self.server:
            sections.insert(0, 'Server')
        for s in sections:
            print(f'\n{s} Parameters\n-------------------')
            s = s.lower()
            for p in self.options(s):
                value = input(f"{p} [{self.get(s, p)}]: ")
                if value:
                    self.set(s, p, value)
        save = input("Save? [n]: ")
        if save == 'y' or save == 'Y':
            self.save()

    @property
    def settings(self):
        sections = ['instrument', 'nxrefine', 'nxreduce']
        if self.server:
            sections.insert(0, 'server')
        _settings = {}
        for section in sections:
            _settings[section] = {k: v for (k, v) in self.items(section)}
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

    def read(self, filename=None):
        if filename is None:
            filename = self.file
        super().read(filename)
        self.set_defaults()

    def save(self):
        with open(self.file, 'w') as f:
            self.write(f)
