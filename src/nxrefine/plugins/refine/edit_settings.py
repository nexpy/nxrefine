# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os
from pathlib import Path

from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import NXLabel, NXPushButton, NXScrollArea
from nexusformat.nexus import NeXusError

from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = ExperimentSettingsDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Editing Experiment Settings", error)


class ExperimentSettingsDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.directory_button = NXPushButton('Choose Experiment Directory',
                                             self.choose_directory)
        self.directoryname = NXLabel(bold=True)
        self.settings = NXSettings()
        self.instrument_parameters = GridParameters()
        defaults = self.settings.settings['instrument']
        if 'experiment' not in defaults:
            defaults['experiment'] = ''
        for p in defaults:
            self.instrument_parameters.add(p, defaults[p], p)
        self.refine_parameters = GridParameters()
        defaults = self.settings.settings['nxrefine']
        for p in defaults:
            self.refine_parameters.add(p, defaults[p], p)
        self.reduce_parameters = GridParameters()
        defaults = self.settings.settings['nxreduce']
        for p in defaults:
            self.reduce_parameters.add(p, defaults[p], p)
        scroll_layout = self.make_layout(
            self.make_layout(self.directoryname),
            self.instrument_parameters.grid(header=False,
                                            title='Instrument'),
            self.refine_parameters.grid(header=False, title='NXRefine'),
            self.reduce_parameters.grid(header=False, title='NXReduce'),
            vertical=True)
        self.scroll_area = NXScrollArea(scroll_layout)
        self.set_layout(self.make_layout(self.directory_button),
                        self.close_layout(save=True))
        self.set_title('Edit Experiment Settings')

    def choose_directory(self):
        super().choose_directory()
        directory = self.get_directory()
        if directory:
            directory = Path(directory)
        else:
            self.reject()
            return
        self.settings = NXSettings(directory)
        if directory.name == 'tasks':
            directory = directory.parent
        self.directoryname.setText(directory.name)
        defaults = self.settings.settings['instrument']
        if 'experiment' not in defaults:
            defaults['experiment'] = ''
        for p in defaults:
            if p == 'experiment':
                self.instrument_parameters[p].value = directory.name
                experiment_path = directory
            elif p == 'raw_home' and not defaults[p]:
                self.instrument_parameters[p].value = str(directory.parent)
            elif p == 'analysis_home' and not defaults[p]:
                self.instrument_parameters[p].value = str(directory.parent)
            else:
                self.instrument_parameters[p].value = defaults[p]
        rhp = Path(self.instrument_parameters['raw_home'].value)
        if rhp in experiment_path.parents:
            rhp = rhp / experiment_path.parent.relative_to(rhp)
            self.instrument_parameters['raw_home'].value = str(rhp)
            if defaults['analysis_home'] == defaults['raw_home']:
                self.instrument_parameters['analysis_home'].value = str(rhp)
        else:
            self.display_message(
                'Warning: Raw Home Inconsistency',
                'The chosen experiment directory is not in the default '
                f"location '{defaults['raw_home']}'")
        defaults = self.settings.settings['nxrefine']
        for p in defaults:
            self.refine_parameters[p].value = defaults[p]
        defaults = self.settings.settings['nxreduce']
        for p in defaults:
            self.reduce_parameters[p].value = defaults[p]
        if self.layout.count() == 2:
            self.insert_layout(1, self.scroll_area)
            self.setMinimumSize(300, 500)

    def accept(self):
        try:
            for p in self.instrument_parameters:
                self.settings.set('instrument', p,
                                  self.instrument_parameters[p].value)
            for p in self.refine_parameters:
                self.settings.set('nxrefine', p,
                                  self.refine_parameters[p].value)
            for p in self.reduce_parameters:
                self.settings.set('nxreduce', p,
                                  self.reduce_parameters[p].value)
            self.settings.save()
            super().accept()
        except Exception as error:
            report_error("Editing Experiment Settings", error)
