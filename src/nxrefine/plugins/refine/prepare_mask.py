# -----------------------------------------------------------------------------
# Copyright (c) 2015-2022, AXMAS Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.plotview import NXPlotView
from nexpy.gui.utils import is_file_locked, report_error
from nexpy.gui.widgets import NXPushButton
from nexusformat.nexus import NeXusError, NXdata, NXLock
from nxrefine.nxreduce import NXReduce
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = PrepareDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Prepareing Peaks", error)


class PrepareDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.select_entry(self.choose_entry)

        default = NXSettings().settings['nxreduce']
        self.parameters = GridParameters()
        self.parameters.add('first', default['first'], 'First Frame')
        self.parameters.add('last', default['last'], 'Last Frame')
        self.parameters.add('threshold1', '2', 'Threshold 1')
        self.parameters.add('horizontal1', '11', 'Horizontal Size 1')
        self.parameters.add('threshold2', '0.8', 'Threshold 2')
        self.parameters.add('horizontal2', '51', 'Horizontal Size 2')
        self.parameters.grid()
        self.prepare_button = NXPushButton('Prepare Mask', self.prepare_mask)
        self.plot_button = NXPushButton('Plot Mask', self.plot_mask)
        self.prepare_layout = self.make_layout(self.prepare_button,
                                               self.plot_button,
                                               align='center')
        self.plot_button.setVisible(False)
        self.set_layout(self.entry_layout,
                        self.close_layout(save=True, progress=True))
        self.set_title('Prepare 3D Mask')
        self.reduce = None
        self.mask = None
        self.plotview = None

    def choose_entry(self):
        if self.layout.count() == 2:
            self.insert_layout(1, self.parameters.grid_layout)
            self.insert_layout(2, self.prepare_layout)
        self.reduce = NXReduce(self.entry)
        self.parameters['first'].value = self.reduce.first
        self.parameters['last'].value = self.reduce.last

    @property
    def first(self):
        try:
            return int(self.parameters['first'].value)
        except Exception as error:
            report_error("Preparing Mask", error)

    @property
    def last(self):
        try:
            return int(self.parameters['last'].value)
        except Exception as error:
            report_error("Preparing Mask", error)

    @property
    def threshold1(self):
        try:
            return float(self.parameters['threshold1'].value)
        except Exception as error:
            report_error("Preparing Mask", error)

    @property
    def horizontal1(self):
        try:
            return int(self.parameters['horizontal1'].value)
        except Exception as error:
            report_error("Preparing Mask", error)

    @property
    def threshold2(self):
        try:
            return float(self.parameters['threshold2'].value)
        except Exception as error:
            report_error("Preparing Mask", error)

    @property
    def horizontal2(self):
        try:
            return int(self.parameters['horizontal2'].value)
        except Exception as error:
            report_error("Preparing Mask", error)

    def prepare_mask(self):
        if is_file_locked(self.reduce.raw_file):
            return
        self.start_thread()
        self.reduce = NXReduce(self.entry, prepare=True,
                               first=self.first, last=self.last,
                               overwrite=True, gui=True)
        self.reduce.mask_parameters['threshold_1'] = self.threshold1
        self.reduce.mask_parameters['threshold_1'] = self.threshold1
        self.reduce.mask_parameters['horizontal_size_1'] = self.horizontal1
        self.reduce.mask_parameters['threshold_2'] = self.threshold2
        self.reduce.mask_parameters['horizontal_size_2'] = self.horizontal2
        self.reduce.moveToThread(self.thread)
        self.reduce.start.connect(self.start_progress)
        self.reduce.update.connect(self.update_progress)
        self.reduce.result.connect(self.get_mask)
        self.reduce.stop.connect(self.stop)
        self.thread.started.connect(self.reduce.nxprepare)
        self.thread.start()

    def get_mask(self, mask):
        self.mask = mask
        self.status_message.setText("Mask complete")
        self.status_message.setVisible(True)
        self.plot_button.setVisible(True)

    def plot_mask(self):
        self.plotview = NXPlotView('3D Mask')
        self.plotview.plot(NXdata(self.mask, self.reduce.data.nxaxes,
                                  title=f"3D Mask: {self.reduce.name}"))

    def stop(self):
        self.stop_progress()
        if self.thread and self.thread.isRunning():
            self.reduce.stopped = True
        self.stop_thread()

    def accept(self):
        try:
            if self.mask is None:
                raise NeXusError("No mask has been created")
            elif self.entry.nxfilemode == 'r':
                raise NeXusError("NeXus file opened as readonly")
            self.reduce.write_mask(self.mask)
            self.reduce.record('nxprepare', masked_file=self.reduce.mask_file,
                               threshold1=self.threshold1,
                               horizontal1=self.horizontal1,
                               threshold2=self.threshold2,
                               horizontal2=self.horizontal2,
                               process='nxprepare_mask')
            self.reduce.record_end('nxprepare')
            super().accept()
        except Exception as error:
            report_error("Preparing Mask", error)

    def reject(self):
        self.stop()
        super().reject()
