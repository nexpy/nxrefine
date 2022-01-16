# -----------------------------------------------------------------------------
# Copyright (c) 2015-2022, AXMAS Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.pyqt import QtCore
from nexpy.gui.utils import is_file_locked, report_error
from nexpy.gui.widgets import NXLabel, NXPushButton
from nexusformat.nexus import NeXusError, NXLock, NXLockException
from nxrefine.nxreduce import NXReduce


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

        self.parameters = GridParameters()
        self.parameters.add('threshold1', '2', 'Threshold 1')
        self.parameters.add('horizontal1', '11', 'Horizontal Size 1')
        self.parameters.add('threshold2', '0.8', 'Threshold 2')
        self.parameters.add('horizontal2', '51', 'Horizontal Size 2')
        self.prepare_button = NXPushButton('Prepare Masks', self.prepare_mask)
        prepare_layout = self.make_layout(self.prepare_button, self.peak_count,
                                          align='center')
        self.set_layout(self.entry_layout,
                        self.parameters.grid(),
                        prepare_layout,
                        self.progress_layout(save=True))
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.set_title('Prepare Masks')
        self.reduce = None

    def choose_entry(self):
        self.reduce = NXReduce(self.entry)

    @property
    def threshold1(self):
        try:
            _threshold1 = int(self.parameters['threshold1'].value)
            if _threshold1 > 0.0:
                return _threshold1
            else:
                return None
        except Exception:
            return None

    @property
    def horizontal1(self):
        try:
            _horizontal1 = int(self.parameters['horizontal1'].value)
            if _horizontal1 > 0.0:
                return _horizontal1
            else:
                return None
        except Exception:
            return None

    @property
    def threshold2(self):
        try:
            _threshold2 = int(self.parameters['threshold2'].value)
            if _threshold2 > 0.0:
                return _threshold2
            else:
                return None
        except Exception:
            return None

    @property
    def horizontal2(self):
        try:
            _horizontal2 = int(self.parameters['horizontal2'].value)
            if _horizontal2 > 0.0:
                return _horizontal2
            else:
                return None
        except Exception:
            return None

    def prepare_mask(self):
        if is_file_locked(self.reduce.data_file):
            if self.confirm_action('Clear lock?',
                                   f'{self.reduce.data_file} is locked'):
                NXLock(self.reduce.data_file).release()
            else:
                return
        self.start_thread()
        self.reduce = NXReduce(self.entry, prepare=True, overwrite=True,
                               gui=True)
        self.reduce.mask_parameters['threshold_1'] = self.threshold1
        self.reduce.mask_parameters['horizontal_size_1'] = self.horizontal1
        self.reduce.mask_parameters['threshold_2'] = self.threshold2
        self.reduce.mask_parameters['horizontal_size_2'] = self.horizontal2
        self.reduce.moveToThread(self.thread)
        self.reduce.start.connect(self.start_progress)
        self.reduce.update.connect(self.update_progress)
        self.reduce.stop.connect(self.stop)
        self.thread.started.connect(self.reduce.nxprepare)
        self.thread.start(QtCore.QThread.LowestPriority)

    def stop(self):
        self.stop_progress()
        if self.thread and self.thread.isRunning():
            self.reduce.stopped = True
        self.stop_thread()

    def accept(self):
        try:
            self.reduce.write_peaks(self.peaks)
            self.reduce.record('nxprepare', threshold=self.threshold,
                               first_frame=self.first, last_frame=self.last,
                               min_pixels=self.min_pixels,
                               peak_number=len(self.peaks))
            self.reduce.record_end('nxprepare')
            super().accept()
        except Exception as error:
            report_error("Preparing Masks", str(error))

    def reject(self):
        self.stop()
        super().reject()
