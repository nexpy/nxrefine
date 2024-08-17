# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import os
from pathlib import Path

from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.utils import display_message, report_error
from nexpy.gui.widgets import NXLabel, NXPushButton, NXScrollArea
from nexusformat.nexus import NeXusError

from nxrefine.nxbeamline import get_beamlines
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
        settings = NXSettings().settings
        self.default_directory = settings['instrument']['analysis_home']
        self.analysis_path = settings['instrument']['analysis_path']
        self.instrument_parameters = GridParameters()
        defaults = settings['instrument']
        if 'experiment' not in defaults:
            defaults['experiment'] = ''
        for p in defaults:
            self.instrument_parameters.add(p, defaults[p], p)
        self.instrument_parameters['instrument'].box.editingFinished.connect(
            self.check_beamline)
        self.refine_parameters = GridParameters()
        defaults = settings['nxrefine']
        for p in defaults:
            self.refine_parameters.add(p, defaults[p], p)
        self.reduce_parameters = GridParameters()
        defaults = settings['nxreduce']
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
        self.setMinimumWidth(350)

    def choose_directory(self):
        if self.default_directory:
            self.set_default_directory(self.default_directory)
        super().choose_directory()
        directory = self.get_directory()
        if directory:
            directory = Path(directory)
        else:
            self.reject()
            return
        if directory.name == self.analysis_path:
            directory = directory.parent
        elif directory.name == 'tasks':
            directory = directory.parent.parent
        self.settings = NXSettings(directory)
        self.directoryname.setText(directory.name)
        defaults = self.settings.settings['instrument']
        if 'experiment' not in defaults:
            defaults['experiment'] = ''
        for p in defaults:
            if p == 'experiment':
                self.instrument_parameters[p].value = directory.name
                expt_path = directory
            elif p == 'raw_home' and not defaults[p]:
                self.instrument_parameters[p].value = str(directory.parent)
            elif p == 'analysis_home' and not defaults[p]:
                self.instrument_parameters[p].value = str(directory.parent)
            else:
                self.instrument_parameters[p].value = defaults[p]
        if expt_path.name == self.instrument_parameters['analysis_path'].value:
            expt_path = expt_path.parent
        ahp = Path(self.instrument_parameters['analysis_home'].value)
        rhp = Path(self.instrument_parameters['raw_home'].value)
        if ahp in directory.parents:
            rhp = rhp / directory.parent.relative_to(ahp)
            ahp = ahp / directory.parent.relative_to(ahp)
            self.instrument_parameters['analysis_home'].value = str(ahp)
            self.instrument_parameters['raw_home'].value = str(rhp)
        else:
            self.display_message(
                'Warning: Invalid Location',
                'The chosen experiment directory is not in the default '
                f"location '{ahp}'")
        defaults = self.settings.settings['nxrefine']
        for p in defaults:
            self.refine_parameters[p].value = defaults[p]
        defaults = self.settings.settings['nxreduce']
        for p in defaults:
            self.reduce_parameters[p].value = defaults[p]
        if self.layout.count() == 2:
            self.insert_layout(1, self.scroll_area)
            self.setMinimumSize(300, 500)
        self.activate()

    def activate(self):
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def check_beamline(self):
        beamlines = get_beamlines()
        if self.instrument_parameters['instrument'].value not in beamlines:
            display_message("Beamline Not Supported",
                            "Supported beamlines are: "
                            f"{', '.join(str(i) for i in get_beamlines())}")

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
