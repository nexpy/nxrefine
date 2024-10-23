# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import numpy as np
from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.plotview import NXPlotView
from nexpy.gui.pyqt import QtCore
from nexpy.gui.utils import (confirm_action, display_message, is_file_locked,
                             report_error)
from nexpy.gui.widgets import NXCheckBox, NXLabel
from nexusformat.nexus import (NeXusError, NXdata, NXfield, NXinstrument,
                               NXsample)

from nxrefine.nxreduce import NXReduce
from nxrefine.nxutils import detector_flipped


def show_dialog():
    try:
        dialog = MaximumDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Finding Maximum", error)


class MaximumDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.select_entry(self.choose_entry)

        self.set_layout(self.entry_layout, self.progress_layout(save=True))
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.set_title('Find Maximum Value')
        self.reduce = None
        self.label = ''
        self.summed_data = None
        self.summed_frames = None
        self.partial_frames = None

    def choose_entry(self):
        self.reduce = NXReduce(self.entry)
        self.label = self.reduce.name
        if self.layout.count() == 2:
            self.output = NXLabel('Maximum Value:')
            self.parameters = GridParameters()
            self.parameters.add('first', '', 'First Frame')
            self.parameters.add('last', '', 'Last Frame')
            self.parameters.add('qmin', '', 'Minimum Scattering Q (Ang-1)')
            self.parameters.add('qmax', '', 'Maximum Scattering Q (Ang-1)')
            self.parameters.add('fw', '5', 'Frame Window')
            self.parameters.add('fs', '20', 'Filter Size')
            self.insert_layout(1, self.parameters.grid())
            self.insert_layout(
                2, self.make_layout(self.action_buttons(('Find Maximum',
                                                         self.find_maximum)),
                                    self.output))
            self.checkbox['over'] = NXCheckBox('Over?')
            self.insert_layout(
                3, self.make_layout(self.action_buttons(
                    ('Plot Summed Data', self.plot_summed_data),
                    ('Plot Summed Frames', self.plot_summed_frames),
                    ('Plot Partial Frames', self.plot_partial_frames)),
                                    self.checkbox['over']))
            self.checkbox['transmission'] = NXCheckBox('Save Transmission')
            self.insert_layout(
                4, self.make_layout(self.action_buttons(
                    ('Plot Transmission Mask', self.plot_transmission_mask),
                    ('Plot Transmission', self.plot_transmission))))
            self.checkbox['copy'] = NXCheckBox('Copy to other entries?')
            self.insert_layout(
                5, self.make_layout(self.action_buttons(
                    ('Save Transmission', self.save_transmission)),
                                    self.checkbox['copy'])
            )
        self.maximum = self.reduce.maximum
        if self.reduce.first:
            self.parameters['first'].value = self.reduce.first
        if self.reduce.last:
            self.parameters['last'].value = self.reduce.last
        if self.reduce.qmin:
            self.parameters['qmin'].value = self.reduce.qmin
        if self.reduce.qmax:
            self.parameters['qmax'].value = self.reduce.qmax
        if 'summed_frames' in self.entry:
            self.summed_frames = self.entry['summed_frames'].nxsignal
            if 'partial_frames' in self.entry['summed_frames']:
                self.partial_frames = (
                    self.entry['summed_frames/partial_frames'])
            else:
                self.partial_frames = None
        else:
            self.summed_frames = None
            self.partial_frames = None
        if 'summed_data' in self.entry:
            self.summed_data = self.entry['summed_data'].nxsignal
        else:
            self.summed_data = None
        self.monitor = self.reduce.read_monitor()

    @property
    def first(self):
        try:
            _first = np.int32(self.parameters['first'].value)
            if _first >= 0:
                return _first
            else:
                return None
        except Exception:
            return None

    @property
    def last(self):
        try:
            _last = np.int32(self.parameters['last'].value)
            if _last > 0:
                return _last
            else:
                return None
        except Exception:
            return None

    @property
    def qmin(self):
        try:
            return self.parameters['qmin'].value
        except Exception:
            return None

    @property
    def qmax(self):
        try:
            return self.parameters['qmax'].value
        except Exception:
            return None

    @property
    def frame_window(self):
        try:
            return int(self.parameters['fw'].value)
        except Exception:
            return None

    @property
    def filter_size(self):
        try:
            return int(self.parameters['fs'].value)
        except Exception:
            return None

    @property
    def maximum(self):
        return float(self.output.text().split()[-1])

    @maximum.setter
    def maximum(self, value):
        if value is not None:
            self.output.setText(f'Maximum Value: {value}')
        else:
            self.output.setText('')

    def find_maximum(self):
        if is_file_locked(self.reduce.raw_file):
            display_message('Data file is locked')
            return
        self.start_thread()
        self.reduce = NXReduce(self.entry, first=self.first, last=self.last,
                               qmin=self.qmin, qmax=self.qmax,
                               maxcount=True, overwrite=True, gui=True)
        self.reduce.moveToThread(self.thread)
        self.reduce.start.connect(self.start_progress)
        self.reduce.update.connect(self.update_progress)
        self.reduce.result.connect(self.get_result)
        self.reduce.stop.connect(self.stop)
        self.thread.started.connect(self.reduce.nxmax)
        self.thread.finished.connect(self.stop)
        self.thread.start(QtCore.QThread.LowestPriority)

    def get_result(self, result):
        self.maximum = result['maximum']
        self.summed_data = result['summed_data']
        self.summed_frames = result['summed_frames']
        self.partial_frames = result['partial_frames']

    def stop(self):
        self.stop_progress()
        if self.thread and self.thread.isRunning():
            self.reduce.stopped = True
        self.stop_thread()

    @property
    def pv(self):
        if 'Maximum' in self.plotviews:
            return self.plotviews['Maximum']
        else:
            return NXPlotView('Maximum')

    @property
    def over(self):
        return self.checkbox['over'].isChecked()

    @property
    def copy(self):
        return self.checkbox['copy'].isChecked()

    def plot_summed_data(self):
        if self.summed_data:
            self.pv.plot(NXdata(self.summed_data,
                                (NXfield(np.arange(self.reduce.shape[1]),
                                         name='y'),
                                 NXfield(np.arange(self.reduce.shape[2]),
                                         name='x')),
                                title=f'Summed Data: {self.label}'),
                         log=True)
            self.pv.aspect = 'equal'
            self.pv.ytab.flipped = detector_flipped(self.entry)
        else:
            display_message('Summed_data not available')

    def plot_summed_frames(self):
        if self.summed_frames:
            if self.over:
                NXdata(self.summed_frames / self.monitor).oplot(markersize=2)
            else:
                self.pv.plot(NXdata(self.summed_frames / self.monitor,
                                    NXfield(np.arange(self.reduce.nframes),
                                            name='nframes',
                                            long_title='Frame No.'),
                                    title=f'Summed Frames: {self.label}'),
                             markersize=2)
        else:
            display_message('Summed Frames not available')

    def plot_partial_frames(self):
        if self.partial_frames:
            if self.over:
                NXdata(self.partial_frames / self.monitor).oplot(markersize=2)
            else:
                self.pv.plot(NXdata(self.partial_frames / self.monitor,
                                    NXfield(np.arange(self.reduce.nframes),
                                            name='nframes',
                                            long_title='Frame No.'),
                                    title=f'Partial Frames: {self.label}'),
                             markersize=2)
        else:
            display_message('Partial Frames not available')

    def plot_transmission_mask(self):
        self.reduce.qmin = self.qmin
        self.reduce.qmax = self.qmax
        self.pv.plot(NXdata(self.reduce.transmission_coordinates(),
                            (NXfield(np.arange(self.reduce.shape[1]),
                                     name='y'),
                             NXfield(np.arange(self.reduce.shape[2]),
                                     name='x')),
                            title=f'Transmission Mask: {self.label}'))
        self.pv.aspect = 'equal'
        self.pv.ytab.flipped = detector_flipped(self.entry)

    def calculate_transmission(self):
        self.reduce.partial_frames = self.partial_frames
        return self.reduce.calculate_transmission(
            frame_window=self.frame_window, filter_size=self.filter_size)

    def plot_transmission(self):
        if self.partial_frames:
            self.reduce.qmin = self.qmin
            self.reduce.qmax = self.qmax
            transmission = self.calculate_transmission()
            if 'maximum' in transmission.nxsignal.attrs:
                transmission *= transmission.nxsignal.attrs['maximum']
            if self.over:
                transmission.oplot(markersize=2)
            else:
                self.pv.plot(transmission, markersize=2)
        else:
            display_message('Partial frames not available')

    def save_transmission(self):
        if self.partial_frames:
            transmission = self.calculate_transmission()
            if 'instrument' not in self.entry:
                self.entry['instrument'] = NXinstrument()
            if 'sample' not in self.entry['instrument']:
                self.entry['instrument/sample'] = NXsample()
            if 'transmission' in self.entry['instrument/sample']:
                if confirm_action(f"Overwrite transmission?"):
                    del self.entry['instrument/sample/transmission']
                else:
                    return
            self.entry['instrument/sample/transmission'] = transmission
            if self.copy:
                for entry in [self.root[e] for e in self.root if
                              e != self.entry.nxname and e[-1].isdigit()]:
                    if 'instrument' not in entry:
                        entry['instrument'] = NXinstrument()
                    if 'sample' not in entry['instrument']:
                        entry['instrument/sample'] = NXsample()
                    if 'transmission' in entry['instrument/sample']:
                        del entry['instrument/sample/transmission']
                    entry['instrument/sample/transmission'] = transmission

    def accept(self):
        try:
            self.reduce.write_maximum()
            self.reduce.record('nxmax', maximum=self.maximum,
                               first_frame=self.first, last_frame=self.last,
                               qmin=self.qmin, qmax=self.qmax)
            self.reduce.record_end('nxmax')
            self.stop()
            super().accept()
        except Exception as error:
            report_error("Finding Maximum", error)

    def reject(self):
        self.stop()
        super().reject()
