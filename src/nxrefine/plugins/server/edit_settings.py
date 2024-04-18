# -----------------------------------------------------------------------------
# Copyright (c) 2015-2023, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os
from pathlib import Path

from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.utils import display_message, report_error
from nexpy.gui.widgets import NXScrollArea
from nexusformat.nexus import NeXusError

from nxrefine.nxbeamline import get_beamlines
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = ServerSettingsDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Editing Server Settings", error)


class ServerSettingsDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = NXSettings()
        self.server_parameters = GridParameters()
        defaults = self.settings.settings['server']
        for p in defaults:
            self.server_parameters.add(p, defaults[p], p)
        self.instrument_parameters = GridParameters()
        defaults = self.settings.settings['instrument']
        for p in defaults:
            self.instrument_parameters.add(p, defaults[p], p)
        self.instrument_parameters['instrument'].box.editingFinished.connect(
            self.check_beamline)
        self.refine_parameters = GridParameters()
        defaults = self.settings.settings['nxrefine']
        for p in defaults:
            self.refine_parameters.add(p, defaults[p], p)
        self.reduce_parameters = GridParameters()
        defaults = self.settings.settings['nxreduce']
        for p in defaults:
            self.reduce_parameters.add(p, defaults[p], p)
        scroll_layout = self.make_layout(
            self.server_parameters.grid(header=False, title='Server'),
            self.instrument_parameters.grid(header=False,
                                            title='Instrument'),
            self.refine_parameters.grid(header=False, title='NXRefine'),
            self.reduce_parameters.grid(header=False, title='NXReduce'),
            vertical=True)
        self.set_layout(NXScrollArea(scroll_layout),
                        self.close_layout(save=True))
        self.setMinimumWidth(300)
        self.set_title('Edit Settings')

    def check_beamline(self):
        beamlines = get_beamlines()
        if self.instrument_parameters['instrument'].value not in beamlines:
            display_message("Beamline Not Supported",
                            "Supported beamlines are: "
                            f"{', '.join(str(i) for i in get_beamlines())}")

    def accept(self):
        try:
            for p in self.server_parameters:
                self.settings.set('server', p,
                                  self.server_parameters[p].value)
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
            report_error("Editing Server Settings", error)
