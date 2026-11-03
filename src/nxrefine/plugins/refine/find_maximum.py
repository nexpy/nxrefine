# -----------------------------------------------------------------------------
# Copyright (c) 2014-2025, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import numpy as np
from nexpy.gui.dialogs import GridParameters, NXDialog
from nexpy.gui.plotview import NXPlotView
from nexpy.gui.pyqt import QtCore
from nexpy.gui.utils import display_message, is_file_locked, report_error
from nexpy.gui.widgets import NXCheckBox, NXLabel
from nexusformat.nexus import NeXusError, NXdata, NXfield

from nxrefine.nxreduce import NXReduce
from nxrefine.nxutils import detector_flipped

from ._dialog_helpers import add_parent_subentries, hide_combined_entry


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
        self.output = NXLabel('Maximum Value:')
        self.parameters = GridParameters()
        self.parameters.add('first', '', 'First Frame')
        self.parameters.add('last', '', 'Last Frame')
        self.parameters.add('qmin', '', 'Minimum Scattering Q (Ang-1)')
        self.parameters.add('qmax', '', 'Maximum Scattering Q (Ang-1)')
        self.parameters.add('baseline_weight', '', 'Baseline Weight')
        self.checkbox['over'] = NXCheckBox('Over?')
        self.checkbox['reference'] = NXCheckBox('Use as Reference Scan')
        self.reference_label = NXLabel('')
        self.reference_layout = self.make_layout(self.checkbox['reference'],
                                                 self.reference_label)
        self.maximum_layout = self.make_layout(
            self.action_buttons(('Find Maximum', self.find_maximum)),
            self.output)
        self.plot_layout = self.make_layout(
            self.action_buttons(
                ('Plot Summed Frames', self.plot_summed_frames),
                ('Plot Partial Frames', self.plot_partial_frames),
                ('Plot Transmission', self.plot_transmission)),
            self.checkbox['over'])
        self.transmission_layout = self.make_layout(
            self.action_buttons(
                ('Plot Summed Data', self.plot_summed_data),
                ('Plot Transmission Mask', self.plot_transmission_mask),
                ))
        self.set_layout(self.entry_layout, self.progress_layout(save=True))
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.set_title('Find Maximum Value')
        self.reduce = None
        self.label = ''
        self.summed_data = None
        self.summed_frames = None
        self.partial_frames = None

    def switch_root(self):
        super().switch_root()
        add_parent_subentries(self)
        hide_combined_entry(self)

    def choose_entry(self):
        self.reduce = NXReduce(self.entry, subentry=self.subentry or None)
        self.label = self.reduce.name
        self.maximum = self.reduce.maximum
        if self.layout.count() == 2:
            self.insert_layout(1, self.parameters.grid())
            self.insert_layout(2, self.maximum_layout)
            self.insert_layout(3, self.plot_layout)
            self.insert_layout(4, self.transmission_layout)
            self.insert_layout(5, self.reference_layout)
        self.update_reference()
        if self.reduce.first:
            self.parameters['first'].value = self.reduce.first
        if self.reduce.last:
            self.parameters['last'].value = self.reduce.last
        qmin_val = self.reduce.qmin
        qmax_val = self.reduce.qmax
        if qmin_val is not None:
            self.parameters['qmin'].value = f"{float(qmin_val):.1f}"
        if qmax_val is not None:
            self.parameters['qmax'].value = f"{float(qmax_val):.1f}"
        self.parameters['baseline_weight'].value = self.reduce.baseline_weight
        target = self.reduce.scan_entry or self.entry
        sums = target['frame_sums'] if 'frame_sums' in target else target
        if 'summed_frames' in sums:
            self.summed_frames = sums['summed_frames'].nxsignal
            if 'partial_frames' in sums['summed_frames']:
                self.partial_frames = sums['summed_frames/partial_frames']
            else:
                self.partial_frames = None
        else:
            self.summed_frames = None
            self.partial_frames = None
        if 'summed_data' in sums:
            self.summed_data = sums['summed_data'].nxsignal
        else:
            self.summed_data = None
        self.monitor = self.reduce.read_monitor()

    def update_reference(self):
        """Show the parent's reference scan and set the checkbox.

        Only the first entry of a scan can define the reference. The box
        is checked if there is no reference yet or this scan is it.
        """
        parent = self.reduce.parent
        reference = parent.reference if parent else None
        enabled = bool(parent) and self.reduce.is_first_entry()
        scan = self.reduce.wrapper_file.stem
        if not parent:
            text = 'No parent file'
        elif reference is None:
            text = 'Reference: None'
        else:
            text = (f"Reference: {reference['reference_scan']} "
                    f"({reference['reference_level']:g})")
        self.reference_label.setText(text)
        self.checkbox['reference'].setEnabled(enabled)
        self.checkbox['reference'].setChecked(
            enabled and (reference is None
                         or reference['reference_scan'] == scan))

    @property
    def set_reference(self):
        """True or False if the reference can be set, otherwise None."""
        if self.checkbox['reference'].isEnabled():
            return self.checkbox['reference'].isChecked()
        return None

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
    def baseline_weight(self):
        """Weight of the frames above the baseline, or None if invalid."""
        try:
            weight = float(self.parameters['baseline_weight'].value)
        except Exception:
            return None
        return weight if 0.0 < weight <= 1.0 else None

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
                               baseline_weight=self.baseline_weight,
                               subentry=self.subentry or None,
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
            self.pv.plot(NXdata(self.summed_frames / self.monitor,
                                NXfield(np.arange(self.reduce.nframes),
                                        name='nframes',
                                        long_title='Frame No.'),
                                title=f'Summed Frames: {self.label}'),
                                markersize=2, over=self.over)
        else:
            display_message('Summed Frames not available')

    def plot_partial_frames(self):
        if self.partial_frames:
            self.pv.plot(NXdata(self.partial_frames / self.monitor,
                                NXfield(np.arange(self.reduce.nframes),
                                        name='nframes',
                                        long_title='Frame No.'),
                                title=f'Partial Frames: {self.label}'),
                                markersize=2, over=self.over)
        else:
            display_message('Partial Frames not available')

    def plot_transmission_mask(self):
        refine = self.reduce.refine
        entries = [e for e in (refine.scan_entry, refine.entry)
                   if e is not None]
        for path in ('instrument/detector/beam_center_x',
                     'instrument/detector/beam_center_y'):
            if not any(path in e for e in entries):
                display_message(
                    'Beam center not available for this entry; '
                    'select an entry with detector geometry.')
                return
        try:
            qmin_val = (float(self.qmin)
                        if self.qmin not in (None, '') else None)
            qmax_val = (float(self.qmax)
                        if self.qmax not in (None, '') else None)
        except (TypeError, ValueError):
            qmin_val = qmax_val = None
        if qmin_val is None or qmax_val is None:
            display_message(
                'qmin and qmax must be set to plot the transmission mask.')
            return
        self.reduce.qmin = qmin_val
        self.reduce.qmax = qmax_val
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
        return self.reduce.calculate_transmission()

    def plot_transmission(self):
        """Plot the baseline fitted to the partial frames.

        If `Over?` is checked, the baseline is plotted in the units of
        the partial frames (divided by the monitor, if it is used), so
        that it can be compared with them. Otherwise, it is plotted as
        used in normalizing the data, scaled to the parent's reference
        level if there is one, or to a median of 1.0 if not.
        """
        if self.partial_frames:
            if self.baseline_weight is not None:
                self.reduce.baseline_weight = self.baseline_weight
            transmission = self.calculate_transmission()
            signal = transmission.nxsignal
            median = self.reduce._transmission_median(signal)
            if median is not None:
                values = signal.nxvalue * median / self.monitor
                if not self.over:
                    values = values / (self.reduce.get_reference_level()
                                       or np.median(values))
                transmission = NXdata(
                    NXfield(values, name='transmission',
                            long_name='Sample Transmission'),
                    transmission.nxaxes, title='Sample Transmission')
            self.pv.plot(transmission, markersize=2, over=self.over)
        else:
            display_message('Partial frames not available')

    def applied_q(self, name):
        """Return the Q limit used in calculating the partial frames.

        The limits are stored with the partial frames when they are
        calculated, so they are not the values currently in the dialog
        if those have been edited since.
        """
        return self.reduce._transmission_attr(self.partial_frames, name)

    def accept(self):
        """Save the results and close the dialog.

        If Find Maximum has been run, all the results are written. If
        not, only the transmission is recalculated from the partial
        frames saved in the file, using the current first and last
        frames and baseline weight, and the other results are left as
        they are.
        """
        try:
            if self.baseline_weight is not None:
                self.reduce.baseline_weight = self.baseline_weight
            if self.reduce.summed_frames is None:
                if self.first is not None:
                    self.reduce.first = self.first
                if self.last is not None:
                    self.reduce.last = self.last
                self.reduce.write_transmission(
                    set_reference=self.set_reference)
                self.reduce.write_parameters(
                    baseline_weight=self.reduce.baseline_weight)
            else:
                self.reduce.write_maximum(set_reference=self.set_reference)
                self.reduce.write_parameters(
                    baseline_weight=self.reduce.baseline_weight)
                self.reduce.record('nxmax', maximum=self.maximum,
                                   first_frame=self.first,
                                   last_frame=self.last,
                                   qmin=self.applied_q('qmin'),
                                   qmax=self.applied_q('qmax'))
                self.reduce.record_end('nxmax')
            self.stop()
            super().accept()
        except Exception as error:
            report_error("Finding Maximum", error)

    def reject(self):
        self.stop()
        super().reject()
