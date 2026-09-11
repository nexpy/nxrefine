# -----------------------------------------------------------------------------
# Copyright (c) 2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

from nexpy.gui.dialogs import GridParameters, NXDialog
from nexpy.gui.utils import confirm_action, display_message, report_error
from nexpy.gui.widgets import NXLabel, NXLineEdit
from nexusformat.nexus import NeXusError, NXfield, nxopen

from nxrefine.nxparent import NXParent, format_scan_prefix, load_file
from nxrefine.nxrefine import NXRefine
from nxrefine.nxreduce import auto_transmission_q
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = NewScanDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Creating New Scan", error)


class NewScanDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.parameters = None
        self.set_layout(self.directorybox('Choose Experiment Directory'),
                        self.close_layout(save=True))
        self.set_title('New Scan')
        settings = NXSettings().settings
        self.analysis_path = settings['instrument']['analysis_path']

    def choose_directory(self):
        super().choose_directory()
        if not self.task_directory.is_dir():
            display_message("Invalid Directory",
                f"'{self.experiment_directory}' is not a valid directory.")
            self.directoryname.setText('')
            return
        self.settings = NXSettings(self.task_directory).settings
        self.mainwindow.default_directory = str(self.experiment_directory)
        self.sample_box = self.select_box(self.get_samples())
        self.sample_layout = self.make_layout(
            self.action_buttons(('Choose Sample', self.choose_sample)),
            self.sample_box)
        if self.layout.count() == 2:
            self.insert_layout(1, self.sample_layout)
        self.activate()

    def get_samples(self):
        if self.experiment_directory.exists():
            sample_directories = [f for
                                  f in self.experiment_directory.iterdir()
                                  if f.is_dir()]
        else:
            return []
        samples = []
        for sample_directory in sample_directories:
            label_directories = [f for f in sample_directory.iterdir()
                                 if f.is_dir()]
            for label_directory in label_directories:
                samples.append(
                    label_directory.relative_to(self.experiment_directory))
        return sorted([str(sample) for sample in samples])

    def choose_sample(self):
        if self.layout.count() == 3:
            configurations = self.get_configurations()
            if configurations:
                self.configuration_box = self.select_box(configurations)
                self.configuration_layout = self.make_layout(
                    self.action_buttons(('Choose Experiment Configuration',
                                         self.choose_configuration)),
                    self.configuration_box)
                self.nexus_file = None
                self.insert_layout(2, self.configuration_layout)
            else:
                self.insert_layout(2, self.filebox('Choose Nexus File'))
                self.status_message.setText(
                    'No Configurations Found. Copy from a NeXus file.')
        else:
            self.reset_prefix()

    def get_configurations(self):
        directory = self.experiment_directory / 'configurations'
        if directory.exists():
            return sorted([str(f.name) for f in directory.glob('*.nxs')])
        else:
            return []

    def initialize_parameters(self, default=None):
        fallback = NXSettings(self.task_directory).settings['nxreduce']
        if default is None:
            default = fallback
        else:
            default = {default[field].nxname: default[field].nxvalue
                       for field in default}
        param_map = {
            'threshold':     ('Peak Threshold', fallback['threshold']),
            'first_frame':   ('First Frame', fallback['first_frame']),
            'last_frame':    ('Last Frame', fallback['last_frame']),
            'polar_max':     ('Max. Polar Angle', fallback['polar_max']),
            'hkl_tolerance': ('HKL Tolerance (Å-1)',
                              fallback['hkl_tolerance']),
            'monitor':       ('Normalization Monitor', fallback['monitor']),
            'norm':          ('Normalization Value', fallback['norm']),
            'radius':        ('Punch Radius (Å)', fallback['radius']),
            'scan_path':     ('Scan Path', fallback['scan_path']),
            'scan_units':    ('Scan Units', fallback['scan_units'])}

        self.parameters = GridParameters()
        self.parameters.add('parent', self.sample, 'Prefix',
                            slot=self.update_scan)
        for key, (label, fallback) in param_map.items():
            value = default.get(key, fallback)
            if value is None:
                value = ''
            if key in ('scan_path', 'scan_units'):
                self.parameters.add(key, value, label,
                                    slot=self.update_scan_labels)
            else:
                self.parameters.add(key, value, label)

        self.parameters_grid = self.parameters.grid(header=False, width=200)
        self.parameters_grid.setHorizontalSpacing(10)
        self.parameters_layout = self.make_layout(self.parameters_grid)

        self.checkbox_layout = self.checkboxes(
            ('create_parent', 'Create Parent', True))

        self.scan_box = NXLineEdit('300', align='right', slot=self.update_scan)
        self.scan_name_label = NXLabel(self.scan_label)
        self.scan_units_label = NXLabel(self.scan_units)
        self.scan_layout = self.make_layout(self.scan_name_label,
                                            self.scan_box,
                                            self.scan_units_label)
        self.scandir_box = NXLineEdit('', align='right')
        self.scandir_layout = self.make_layout(NXLabel('Scan Directory'),
                                               self.scandir_box)
        self.update_scan()

    def choose_configuration(self):
        if self.layout.count() == 4:
            self.initialize_parameters()
            self.insert_layout(3, self.parameters_layout,
                               self.checkbox_layout, self.scan_layout,
                               self.scandir_layout)
        else:
            self.reset_prefix()

    def choose_file(self):
        self.set_default_directory(self.sample_directory)
        super().choose_file(filter="Nexus Files (*.nxs)")
        self.nexus_file = self.get_filename()
        if self.nexus_file is None:
            return
        with nxopen(self.nexus_file) as root:
            if 'nxscans/settings' in root['entry']:
                default = root['entry/nxscans/settings']
            elif 'nxreduce' in root['entry']:
                default = root['entry/nxreduce']
            else:
                default = None
        if self.layout.count() == 4:
            self.initialize_parameters(default)
            self.insert_layout(3, self.parameters_layout,
                               self.checkbox_layout, self.scan_layout,
                               self.scandir_layout)
        else:
            self.reset_prefix()
        self.status_message.setText("Values copied from NeXus file")

    @property
    def experiment_directory(self):
        directory = self.get_directory()
        if self.analysis_path and directory.name != self.analysis_path:
            directory = directory / self.analysis_path
        return directory

    @property
    def task_directory(self):
        return self.experiment_directory / 'tasks'

    @property
    def configuration_file(self):
        configuration = self.configuration_box.currentText()
        return self.experiment_directory / 'configurations' / configuration

    @property
    def sample(self):
        return Path(self.sample_box.currentText()).parent.name

    @property
    def label(self):
        return Path(self.sample_box.currentText()).name

    @property
    def sample_directory(self):
        return self.experiment_directory / self.sample / self.label

    @property
    def create_parent_checked(self):
        return self.checkbox['create_parent'].isChecked()

    @property
    def prefix(self):
        return self.parameters['parent'].value

    @property
    def parent_file(self):
        parent_name = self.prefix + '_scans.nxs'
        return self.sample_directory.joinpath(parent_name)

    @property
    def scan_field(self):
        return self.parameters['scan_path'].value

    @property
    def scan_units(self):
        return self.parameters['scan_units'].value

    @property
    def scan_label(self):
        if self.scan_field:
            return Path(self.scan_field).name.replace('_', ' ').title()
        else:
            return 'Scan Value'

    @property
    def scan_value(self):
        try:
            return float(self.scan_box.text())
        except ValueError:
            return self.scan_box.text()

    @property
    def scan_directory(self):
        return self.scandir_box.text()

    @scan_directory.setter
    def scan_directory(self, value):
        self.scandir_box.setText(value)

    @property
    def scan_file(self):
        return self.sample + '_' + self.scandir_box.text() + '.nxs'

    @property
    def scan_prefix(self):
        return format_scan_prefix(self.prefix, self.sample)

    def get_scan_directory(self, value):
        try:
            value = float(value)
        except (ValueError, TypeError):
            pass
        if isinstance(value, float):
            prefix = 'm' if value < 0 else ''
            value = abs(value)
            if value.is_integer():
                value_str = str(int(value))
            else:
                value_str = str(value).replace('.', 'p')
            units = self.scan_units
        else:
            prefix = ''
            value_str = str(value)
            units = ''
        return f"{self.scan_prefix}{prefix}{value_str}{units}"

    @property
    def scan_selected(self):
        return self.scan_directory == self.get_scan_directory(
            self.scan_value)

    def update_scan(self):
        self.scan_directory = self.get_scan_directory(self.scan_value)

    def update_scan_labels(self):
        """Refresh the scan variable and units labels, and the directory.

        Called when the scan path or scan units are edited: the scan path
        names the variable displayed beside the value box, while the units
        are shown after it and form part of the scan directory name.
        """
        self.scan_name_label.setText(self.scan_label)
        self.scan_units_label.setText(self.scan_units)
        self.update_scan()

    def reset_prefix(self):
        """Reset the prefix to the current sample name.

        Called when the sample or configuration is re-chosen after the
        parameter grid has already been built, so the scan directory
        stays consistent with the new prefix.
        """
        if self.parameters is None:
            return
        self.parameters['parent'].value = self.sample
        self.update_scan()

    def copy_file(self, config_file, target):
        target.copy_file(config_file)

    def write_grid_settings(self, target):
        for p in self.parameters:
            value = self.parameters[p].value
            if value == '' or value is None:
                continue
            target.settings[p] = value
        q_min, q_max = self._auto_q(target)
        if q_min is not None:
            target.settings['qmin'] = q_min
        if q_max is not None:
            target.settings['qmax'] = q_max

    def _auto_q(self, target):
        """Compute (qmin, qmax) from the target's copied geometry.

        Returns ``(None, None)`` if the geometry needed for the
        calculation is incomplete; the runtime will then fill in
        qmin/qmax when nxmax first runs.
        """
        try:
            refine = NXRefine(target.entry)
            data = (target.entry['data']
                    if 'data' in target.entry else None)
            shape = (tuple(ax.shape[0] for ax in data.nxaxes)
                     if data is not None else None)
            return auto_transmission_q(refine, shape)
        except Exception:
            return None, None

    def config_source(self):
        return self.nexus_file if self.nexus_file else self.configuration_file

    def create_scan_set(self):
        if self.create_parent_checked:
            parent = NXParent(self.parent_file, prefix=self.prefix)
            with parent.root:
                parent.initialize()
                self.copy_file(self.config_source(), parent)
                self.write_grid_settings(parent)
            if parent.root.nxfile is None:
                parent.root.save(self.parent_file, 'w')
            self.parent = parent
            self.build_scan(parent, register=True)
        else:
            scan_path = self.sample_directory / self.scan_file
            scan = NXParent(scan_path, prefix=self.prefix)
            with scan.root:
                scan.initialize()
                self.copy_file(self.config_source(), scan)
                self.write_grid_settings(scan)
            self.parent = scan
            self.build_scan(scan, register=False)

    def build_scan(self, source, register):
        self.sample_directory.joinpath(self.scan_directory).mkdir(
            exist_ok=True)
        scan_path = self.sample_directory / self.scan_file
        if register:
            with nxopen(scan_path, 'w') as root:
                for entry in source.root.entries:
                    root[entry] = source.root[entry]
                NXParent(root).relink_data(self.scan_directory)
                root[self.scan_field] = NXfield(self.scan_value,
                                               units=self.scan_units)
            source.add_scan(self.scan_file, selected=self.scan_selected)
        else:
            with source.root:
                source.relink_data(self.scan_directory)
                source.root[self.scan_field] = NXfield(
                    self.scan_value, units=self.scan_units)
            if source.root.nxfile is None:
                source.root.save(scan_path, 'w')

    def accept(self):
        if self.create_parent_checked and self.parent_file.is_file():
            if not confirm_action(
                    "Overwrite parent file?",
                    f"'{self.parent_file}' already exists."):
                return
        scan_path = self.sample_directory / self.scan_file
        if scan_path.is_file() and not confirm_action(
                "Overwrite existing scan file?",
                f"'{scan_path}' already exists."):
            return
        self.create_scan_set()
        load_file(scan_path)
        if self.create_parent_checked:
            load_file(self.parent_file)
        super().accept()
