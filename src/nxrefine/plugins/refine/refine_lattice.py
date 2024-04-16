# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import operator

import numpy as np
from nexpy.gui.datadialogs import ExportDialog, GridParameters, NXDialog
from nexpy.gui.plotview import NXPlotView
from nexpy.gui.pyqt import QtCore, QtGui, QtWidgets
from nexpy.gui.utils import display_message, report_error
from nexpy.gui.widgets import NXLabel, NXLineEdit, NXPushButton
from nexusformat.nexus import NeXusError, NXdata, NXfield
from nxrefine.nxreduce import NXReduce
from nxrefine.nxrefine import NXRefine


def show_dialog():
    try:
        dialog = RefineLatticeDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Refining Lattice", error)


class RefineLatticeDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.select_entry(self.choose_entry)

        self.refine_buttons = self.action_buttons(
            ('Refine Angles', self.refine_angles),
            ('Refine HKLs', self.refine_hkls),
            ('Restore', self.restore_parameters),
            ('Reset', self.reset_parameters))

        self.orientation_buttons = self.action_buttons(
            ('Refine Orientation Matrix', self.refine_orientation),
            ('Remove Orientation Matrix', self.remove_orientation))

        self.lattice_buttons = self.action_buttons(
            ('Plot', self.plot_lattice),
            ('List', self.list_peaks),
            ('Update', self.update_scaling),
            ('Save', self.write_parameters))

        self.set_layout(self.entry_layout, self.close_layout())

        self.layout.setSpacing(2)

        self.set_title('Refining Lattice')

        self.peaks_box = None
        self.table_model = None
        self.orient_box = None
        self.update_box = None
        self.tolerance_box = None
        self.fit_report = []
        self.ringview = None

    def define_parameters(self):
        self.parameters = GridParameters()
        self.parameters.add('symmetry', self.refine.symmetries, 'Symmetry',
                            None, self.set_lattice_parameters)
        self.parameters.add('a', self.refine.a, 'Unit Cell - a (Ang)', False,
                            slot=self.set_lattice_parameters)
        self.parameters.add('b', self.refine.b, 'Unit Cell - b (Ang)', False,
                            slot=self.set_lattice_parameters)
        self.parameters.add('c', self.refine.c, 'Unit Cell - c (Ang)', False,
                            slot=self.set_lattice_parameters)
        self.parameters.add('alpha', self.refine.alpha,
                            'Unit Cell - alpha (deg)', False,
                            slot=self.set_lattice_parameters)
        self.parameters.add('beta', self.refine.beta, 'Unit Cell - beta (deg)',
                            False, slot=self.set_lattice_parameters)
        self.parameters.add('gamma', self.refine.gamma,
                            'Unit Cell - gamma (deg)', False,
                            slot=self.set_lattice_parameters)
        self.parameters.add('wavelength', self.refine.wavelength,
                            'Wavelength (Ang)', False)
        self.parameters.add('distance', self.refine.distance, 'Distance (mm)',
                            False)
        self.parameters.add('yaw', self.refine.yaw, 'Yaw (deg)', False)
        self.parameters.add('pitch', self.refine.pitch, 'Pitch (deg)', False)
        self.parameters.add('roll', self.refine.roll, 'Roll (deg)')
        self.parameters.add('xc', self.refine.xc, 'Beam Center - x', False)
        self.parameters.add('yc', self.refine.yc, 'Beam Center - y', False)
        self.parameters.add('phi', self.refine.phi, 'Phi Start (deg)', False)
        self.parameters.add('phi_step', self.refine.phi_step, 'Phi Step (deg)')
        self.parameters.add('chi', self.refine.chi, 'Chi (deg)', False)
        self.parameters.add('omega', self.refine.omega, 'Omega (deg)', False)
        self.parameters.add('theta', self.refine.theta, 'Theta (deg)', False)
        self.parameters.add('xs', self.refine.xs, 'Sample x (mm)', False)
        self.parameters.add('ys', self.refine.ys, 'Sample y (mm)', False)
        self.parameters.add('zs', self.refine.zs, 'Sample z (mm)', False)
        self.parameters.add('omat', self.refine.detector_orientation,
                            'Detector Orientation')
        self.parameters.add('polar', self.reduce.polar_max,
                            'Max. Polar Angle (deg)', None, self.set_polar_max)
        self.parameters.add('polar_tolerance', self.refine.polar_tolerance,
                            'Polar Angle Tolerance')
        self.parameters.add('peak_tolerance', self.refine.peak_tolerance,
                            'Peak Angle Tolerance')
        self.parameters.add('hkl_tolerance', self.reduce.hkl_tolerance,
                            'HKL Tolerance (Å-1)', slot=self.set_hkl_tolerance)

        self.parameters.grid()
        self.parameters.grid_layout.setVerticalSpacing(1)

    def choose_entry(self):
        try:
            refine = NXRefine(self.entry)
            if refine.xp is None:
                raise NeXusError("No peaks in entry")
        except NeXusError as error:
            report_error("Refining Lattice", error)
            return
        self.refine = refine
        self.reduce = NXReduce(self.entry)
        self.set_title(f"Refining {self.refine.name}")
        if self.layout.count() == 2:
            self.define_parameters()
            self.insert_layout(1, self.parameters.grid_layout)
            self.insert_layout(2, self.refine_buttons)
            self.insert_layout(3, self.orientation_buttons)
            self.insert_layout(4, self.parameters.report_layout())
            self.insert_layout(5, self.lattice_buttons)
        self.set_lattice_parameters()
        self.update_parameters()
        self.update_table()

    def report_score(self):
        try:
            self.status_message.setText(f'Score: {self.refine.score():.4f}')
            if self.peaks_box in self.mainwindow.dialogs:
                self.status_text.setText(f'Score: {self.refine.score():.4f}')
        except Exception as error:
            pass

    def update_parameters(self):
        self.parameters['a'].value = self.refine.a
        self.parameters['b'].value = self.refine.b
        self.parameters['c'].value = self.refine.c
        self.parameters['alpha'].value = self.refine.alpha
        self.parameters['beta'].value = self.refine.beta
        self.parameters['gamma'].value = self.refine.gamma
        self.parameters['wavelength'].value = self.refine.wavelength
        self.parameters['distance'].value = self.refine.distance
        self.parameters['yaw'].value = self.refine.yaw
        self.parameters['pitch'].value = self.refine.pitch
        self.parameters['roll'].value = self.refine.roll
        self.parameters['xc'].value = self.refine.xc
        self.parameters['yc'].value = self.refine.yc
        self.parameters['phi'].value = self.refine.phi
        self.parameters['phi_step'].value = self.refine.phi_step
        self.parameters['chi'].value = self.refine.chi
        self.parameters['omega'].value = self.refine.omega
        self.parameters['theta'].value = self.refine.theta
        self.parameters['xs'].value = self.refine.xs
        self.parameters['ys'].value = self.refine.ys
        self.parameters['zs'].value = self.refine.zs
        self.parameters['omat'].value = self.refine.detector_orientation
        self.parameters['polar_tolerance'].value = self.refine.polar_tolerance
        self.parameters['peak_tolerance'].value = self.refine.peak_tolerance
        self.parameters['hkl_tolerance'].value = self.refine.hkl_tolerance
        self.parameters['symmetry'].value = self.refine.symmetry
        try:
            self.refine.polar_angles, self.refine.azimuthal_angles = \
                self.refine.calculate_angles(self.refine.xp, self.refine.yp)
        except Exception:
            pass
        self.report_score()

    def transfer_parameters(self):
        self.refine.symmetry = self.get_symmetry()
        self.refine.a, self.refine.b, self.refine.c, \
            self.refine.alpha, self.refine.beta, self.refine.gamma = \
            self.get_lattice_parameters()
        self.refine.set_symmetry()
        self.refine.wavelength = self.get_wavelength()
        self.refine.distance = self.get_distance()
        self.refine.yaw, self.refine.pitch, self.refine.roll = self.get_tilts()
        self.refine.xc, self.refine.yc = self.get_centers()
        self.refine.phi, self.refine.phi_step = self.get_phi()
        self.refine.chi, self.refine.omega, self.refine.theta = (
            self.get_angles())
        self.refine.xs, self.refine.ys, self.refine.zs = (
            self.get_sample_shift())
        self.refine.detector_orientation = self.get_omat()
        self.refine.polar_tolerance = self.get_polar_tolerance()
        self.refine.peak_tolerance = self.get_peak_tolerance()

    def write_parameters(self):
        if self.entry.nxfilemode == 'r':
            display_message("NeXus file opened as readonly")
            return
        elif ('nxrefine' in self.entry or
              'orientation_matrix' in self.entry['instrument/detector']):
            if not self.confirm_action('Overwrite existing refinement?'):
                return
        self.transfer_parameters()
        polar_angles, azimuthal_angles = self.refine.calculate_angles(
            self.refine.xp, self.refine.yp)
        self.refine.write_angles(polar_angles, azimuthal_angles)
        self.refine.write_parameters()
        self.reduce.write_parameters(polar_max=self.refine.polar_max,
                                     hkl_tolerance=self.reduce.hkl_tolerance)
        self.reduce.record_start('nxrefine')
        self.reduce.record('nxrefine', polar_max=self.reduce.polar_max,
                           hkl_tolerance=self.reduce.hkl_tolerance,
                           fit_report='\n'.join(self.fit_report))
        self.reduce.logger.info('Orientation refined in NeXpy')
        self.reduce.record_end('nxrefine')
        root = self.entry.nxroot
        entries = [entry for entry in root.entries
                   if entry[-1].isdigit() and entry != self.entry.nxname]
        if entries and self.confirm_action(
            f'Copy orientation to other entries? ({", ".join(entries)})',
                answer='yes'):
            om = self.entry['instrument/detector/orientation_matrix']
            for entry in entries:
                root[entry]['instrument/detector/orientation_matrix'] = om
        self.define_data()
        if len(self.paths) > 0:
            self.update_scaling()

    def update_scaling(self):
        self.define_data()
        if len(self.paths) == 0:
            display_message("Refining Lattice", "No data groups to update")
        if self.update_box in self.mainwindow.dialogs:
            try:
                self.update_box.close()
            except Exception:
                pass
        self.update_box = NXDialog(parent=self)
        self.update_box.set_title('Update Scaling Factors')
        self.update_box.setMinimumWidth(300)
        self.update_box.set_layout(self.paths.grid(header=('', 'Data Groups',
                                                           '')),
                                   self.update_box.close_layout())
        self.update_box.close_box.accepted.connect(self.update_data)
        self.update_box.show()

    def define_data(self):

        def is_valid(data):
            try:
                valid_axes = [['Ql', 'Qk', 'Qh'], ['l', 'k', 'h'],
                              ['z', 'y', 'x']]
                axis_names = [axis.nxname for axis in data.nxaxes]
                return axis_names in valid_axes
            except Exception:
                return False

        root = self.entry.nxroot
        self.paths = GridParameters()
        i = 0
        for entry in root.NXentry:
            for data in [d for d in entry.NXdata if is_valid(d)]:
                i += 1
                self.paths.add(i, data.nxpath, i, True, width=200)

    def update_data(self):
        try:
            for path in [self.paths[p].value for p in self.paths
                         if self.paths[p].vary]:
                data = self.entry.nxroot[path]
                if [axis.nxname for axis in data.nxaxes] == ['z', 'y', 'x']:
                    lp = self.refine.lattice_parameters
                else:
                    lp = self.refine.reciprocal_lattice_parameters
                for i, axis in enumerate(data.nxaxes):
                    data[axis.nxname].attrs['scaling_factor'] = lp[2-i]
                data.attrs['angles'] = lp[5:2:-1]
            self.update_box.close()
        except NeXusError as error:
            report_error("Updating Groups", error)

    def get_symmetry(self):
        return self.parameters['symmetry'].value

    def set_symmetry(self):
        self.refine.symmetry = self.get_symmetry()
        self.refine.set_symmetry()
        self.update_parameters()
        if self.refine.symmetry == 'cubic':
            self.parameters['b'].vary = False
            self.parameters['c'].vary = False
            self.parameters['alpha'].vary = False
            self.parameters['beta'].vary = False
            self.parameters['gamma'].vary = False
        elif self.refine.symmetry == 'tetragonal':
            self.parameters['b'].vary = False
            self.parameters['alpha'].vary = False
            self.parameters['beta'].vary = False
            self.parameters['gamma'].vary = False
        elif self.refine.symmetry == 'orthorhombic':
            self.parameters['alpha'].vary = False
            self.parameters['beta'].vary = False
            self.parameters['gamma'].vary = False
        elif self.refine.symmetry == 'hexagonal':
            self.parameters['b'].vary = False
            self.parameters['alpha'].vary = False
            self.parameters['beta'].vary = False
            self.parameters['gamma'].vary = False
        elif self.refine.symmetry == 'monoclinic':
            self.parameters['alpha'].vary = False
            self.parameters['gamma'].vary = False

    def get_lattice_parameters(self):
        return (self.parameters['a'].value,
                self.parameters['b'].value,
                self.parameters['c'].value,
                self.parameters['alpha'].value,
                self.parameters['beta'].value,
                self.parameters['gamma'].value)

    def set_lattice_parameters(self):
        symmetry = self.get_symmetry()
        if symmetry == 'cubic':
            self.parameters['b'].value = self.parameters['a'].value
            self.parameters['c'].value = self.parameters['a'].value
            self.parameters['alpha'].value = 90.0
            self.parameters['beta'].value = 90.0
            self.parameters['gamma'].value = 90.0
            self.parameters['a'].enable(vary=True)
            self.parameters['b'].disable(vary=False)
            self.parameters['c'].disable(vary=False)
            self.parameters['alpha'].disable(vary=False)
            self.parameters['beta'].disable(vary=False)
            self.parameters['gamma'].disable(vary=False)
        elif symmetry == 'tetragonal':
            self.parameters['b'].value = self.parameters['a'].value
            self.parameters['alpha'].value = 90.0
            self.parameters['beta'].value = 90.0
            self.parameters['gamma'].value = 90.0
            self.parameters['a'].enable(vary=True)
            self.parameters['b'].disable(vary=False)
            self.parameters['c'].enable(vary=True)
            self.parameters['alpha'].disable(vary=False)
            self.parameters['beta'].disable(vary=False)
            self.parameters['gamma'].disable(vary=False)
        elif symmetry == 'orthorhombic':
            self.parameters['alpha'].value = 90.0
            self.parameters['beta'].value = 90.0
            self.parameters['gamma'].value = 90.0
            self.parameters['a'].enable(vary=True)
            self.parameters['b'].enable(vary=True)
            self.parameters['c'].enable(vary=True)
            self.parameters['alpha'].disable(vary=False)
            self.parameters['beta'].disable(vary=False)
            self.parameters['gamma'].disable(vary=False)
        elif symmetry == 'hexagonal':
            self.parameters['b'].value = self.parameters['a'].value
            self.parameters['alpha'].value = 90.0
            self.parameters['beta'].value = 90.0
            self.parameters['gamma'].value = 120.0
            self.parameters['a'].enable(vary=True)
            self.parameters['b'].disable(vary=False)
            self.parameters['c'].enable(vary=True)
            self.parameters['alpha'].disable(vary=False)
            self.parameters['beta'].disable(vary=False)
            self.parameters['gamma'].disable(vary=False)
        elif symmetry == 'monoclinic':
            self.parameters['alpha'].value = 90.0
            self.parameters['gamma'].value = 90.0
            self.parameters['a'].enable(vary=True)
            self.parameters['b'].enable(vary=True)
            self.parameters['c'].enable(vary=True)
            self.parameters['alpha'].disable(vary=False)
            self.parameters['beta'].enable(vary=True)
            self.parameters['gamma'].disable(vary=False)
        else:
            self.parameters['a'].enable(vary=True)
            self.parameters['b'].enable(vary=True)
            self.parameters['c'].enable(vary=True)
            self.parameters['alpha'].enable(vary=True)
            self.parameters['beta'].enable(vary=True)
            self.parameters['gamma'].enable(vary=True)

    def get_wavelength(self):
        return self.parameters['wavelength'].value

    def get_distance(self):
        return self.parameters['distance'].value

    def get_tilts(self):
        return (self.parameters['yaw'].value,
                self.parameters['pitch'].value,
                self.parameters['roll'].value)

    def get_centers(self):
        return self.parameters['xc'].value, self.parameters['yc'].value

    def get_phi(self):
        return (self.parameters['phi'].value,
                self.parameters['phi_step'].value)

    def get_angles(self):
        return (self.parameters['chi'].value,
                self.parameters['omega'].value,
                self.parameters['theta'].value)

    def get_sample_shift(self):
        return (self.parameters['xs'].value,
                self.parameters['ys'].value,
                self.parameters['zs'].value)

    def get_omat(self):
        return self.parameters['omat'].value

    def get_polar_max(self):
        return self.parameters['polar'].value

    def set_polar_max(self):
        self.refine.polar_max = self.get_polar_max()
        self.refine.initialize_idx()
        self.update_table()

    def get_polar_tolerance(self):
        return self.parameters['polar_tolerance'].value

    def get_peak_tolerance(self):
        return self.parameters['peak_tolerance'].value

    def get_hkl_tolerance(self):
        return float(self.parameters['hkl_tolerance'].value)

    def set_hkl_tolerance(self):
        self.refine.hkl_tolerance = self.get_hkl_tolerance()
        self.update_table()
        try:
            self.tolerance_box.setText(self.refine.hkl_tolerance)
        except Exception:
            pass

    def read_tolerance_box(self):
        value = float(self.tolerance_box.text())
        self.parameters['hkl_tolerance'].value = value
        self.refine.hkl_tolerance = value
        self.update_table()

    def plot_lattice(self):
        self.transfer_parameters()
        self.set_polar_max()
        self.plot_peaks()

    def plot_peaks(self):
        try:
            x, y = (self.refine.xp[self.refine.idx],
                    self.refine.yp[self.refine.idx])
            polar_angles, azimuthal_angles = self.refine.calculate_angles(x, y)
            if polar_angles[0] > polar_angles[-1]:
                polar_angles = polar_angles[::-1]
                azimuthal_angles = azimuthal_angles[::-1]
            azimuthal_field = NXfield(azimuthal_angles, name='azimuthal_angle')
            azimuthal_field.long_name = 'Azimuthal Angle'
            polar_field = NXfield(polar_angles, name='polar_angle')
            polar_field.long_name = 'Polar Angle'
            if 'Ring Plot' in self.plotviews:
                self.ringview = self.plotviews['Ring Plot']
            else:
                self.ringview = NXPlotView('Ring Plot')
            self.ringview.plot(NXdata(azimuthal_field, polar_field,
                               title=f'{self.refine.name} Peak Angles'),
                               xmax=self.get_polar_max())
            self.ringview.vlines(self.refine.two_thetas,
                                 colors='r', linestyles='dotted')
            self.ringview.draw()
        except NeXusError as error:
            report_error('Plotting Lattice', error)

    @property
    def refined(self):
        refined = {}
        for p in self.parameters:
            if self.parameters[p].vary:
                refined[p] = True
        return refined

    def refine_angles(self):
        self.parameters.status_message.setText('Fitting...')
        self.parameters.status_message.repaint()
        self.mainwindow.app.app.processEvents()
        self.parameters['phi'].vary = False
        self.transfer_parameters()
        try:
            self.refine.refine_angles(**self.refined)
        except NeXusError as error:
            report_error('Refining Lattice', error)
            self.parameters.status_message.setText('')
            return
        self.parameters.result = self.refine.result
        self.parameters.fit_report = self.refine.fit_report
        self.fit_report.append(self.refine.fit_report)
        self.update_parameters()
        self.parameters.status_message.setText(self.parameters.result.message)
        self.update_table()

    def refine_hkls(self):
        self.parameters.status_message.setText('Fitting...')
        self.parameters.status_message.repaint()
        self.mainwindow.app.app.processEvents()
        self.transfer_parameters()
        try:
            self.refine.refine_hkls(**self.refined)
        except NeXusError as error:
            report_error('Refining Lattice', error)
            self.parameters.status_message.setText('')
            return
        self.parameters.result = self.refine.result
        self.parameters.fit_report = self.refine.fit_report
        self.fit_report.append(self.refine.fit_report)
        self.update_parameters()
        self.parameters.status_message.setText(self.parameters.result.message)
        self.update_table()

    def refine_orientation(self):
        self.parameters.status_message.setText('Fitting...')
        self.parameters.status_message.repaint()
        self.mainwindow.app.app.processEvents()
        self.transfer_parameters()
        self.refine.refine_orientation_matrix()
        self.parameters.result = self.refine.result
        self.parameters.fit_report = self.refine.fit_report
        self.fit_report.append(self.refine.fit_report)
        self.update_parameters()
        self.parameters.status_message.setText(self.parameters.result.message)
        self.update_table()

    def remove_orientation(self):
        self.refine.Umat = None
        self.report_score()

    def restore_parameters(self):
        self.refine.restore_parameters()
        self.update_parameters()
        try:
            self.fit_report.pop()
        except IndexError:
            pass

    def reset_parameters(self):
        self.refine.read_parameters()
        self.update_parameters()
        self.set_symmetry()
        try:
            self.fit_report.pop()
        except IndexError:
            pass

    def list_peaks(self):
        if self.peaks_box in self.mainwindow.dialogs:
            self.update_table()
            return
        else:
            self.transfer_parameters()
        self.peaks_box = NXDialog(self)
        self.peaks_box.setMinimumWidth(600)
        self.peaks_box.setMinimumHeight(600)
        header = ['i', 'x', 'y', 'z', 'Polar', 'Azi', 'Intensity',
                  'H', 'K', 'L', 'Diff']
        peak_list = self.refine.get_peaks()
        self.refine.assign_rings()
        self.rings = self.refine.make_rings()
        self.ring_list = self.refine.get_ring_list()
        if self.refine.primary is None:
            self.refine.primary = 0
        if self.refine.secondary is None:
            self.refine.secondary = 1
        self.primary_box = NXLineEdit(self.refine.primary, width=80,
                                      align='right')
        self.secondary_box = NXLineEdit(self.refine.secondary, width=80,
                                        align='right')
        orient_button = NXPushButton('Orient', self.choose_peaks)
        orient_layout = self.make_layout(NXLabel('Primary'), self.primary_box,
                                         NXLabel('Secondary'),
                                         self.secondary_box, 'stretch',
                                         orient_button, align='right')

        self.table_view = QtWidgets.QTableView()
        self.table_model = NXTableModel(self, peak_list, header)
        self.table_view.setModel(self.table_model)
        self.table_view.resizeColumnsToContents()
        self.table_view.horizontalHeader().resizeSections(
            QtWidgets.QHeaderView.ResizeToContents)
        self.table_view.setMinimumWidth(570)
        self.table_view.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows)
        self.table_view.doubleClicked.connect(self.plot_peak)
        self.table_view.setSortingEnabled(True)
        self.table_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
        self.status_text = NXLabel(f'Score: {self.refine.score():.4f}')
        self.tolerance_box = NXLineEdit(self.refine.hkl_tolerance, width=80,
                                        slot=self.read_tolerance_box,
                                        align='right')
        self.tolerance_box.setMaxLength(5)
        export_button = NXPushButton('Export', self.export_peaks)
        save_button = NXPushButton('Save', self.save_orientation)
        close_button = NXPushButton('Close', self.close_peaks_box)
        close_layout = self.make_layout(self.status_text, 'stretch',
                                        NXLabel('HKL Tolerance'),
                                        self.tolerance_box, 'stretch',
                                        export_button, save_button,
                                        close_button)
        self.peaks_box.set_layout(orient_layout, self.table_view, close_layout)
        self.peaks_box.set_title(f'{self.refine.name} Peak Table')
        self.peaks_box.adjustSize()
        self.peaks_box.show()
        self.peakview = None
        self.report_score()

    def update_table(self):
        if self.peaks_box not in self.mainwindow.dialogs:
            return
        elif self.table_model is None:
            self.close_peaks_box()
            self.list_peaks()
        self.transfer_parameters()
        self.table_model.peak_list = self.refine.get_peaks()
        self.refine.assign_rings()
        self.ring_list = self.refine.get_ring_list()
        rows, columns = len(self.table_model.peak_list), 11
        self.table_model.dataChanged.emit(
            self.table_model.createIndex(0, 0),
            self.table_model.createIndex(rows - 1, columns - 1))
        self.table_view.resizeColumnsToContents()
        self.peaks_box.set_title(f'{self.refine.name} Peak Table')
        self.peaks_box.adjustSize()
        self.peaks_box.setVisible(True)
        self.report_score()

    def plot_peak(self):
        row = self.table_view.currentIndex().row()
        data = self.entry.data
        i, x, y, z = [self.table_view.model().peak_list[row][i]
                      for i in range(4)]
        signal = data.nxsignal
        xmin, xmax = max(0, x-200), min(x+200, signal.shape[2])
        ymin, ymax = max(0, y-200), min(y+200, signal.shape[1])
        zmin, zmax = max(0, z-20), min(z+20, signal.shape[0])
        zslab = np.s_[zmin:zmax, ymin:ymax, xmin:xmax]
        if 'Peak Plot' in self.plotviews:
            self.peakview = self.plotviews['Peak Plot']
        else:
            self.peakview = NXPlotView('Peak Plot')
        self.peakview.plot(data[zslab], log=True)
        self.peakview.ax.set_title(f'{data.nxtitle}: Peak {i}')
        self.peakview.ztab.maxbox.setValue(z)
        self.peakview.aspect = 'equal'
        self.peakview.crosshairs(x, y, color='r', linewidth=0.5)

    @property
    def primary(self):
        return int(self.primary_box.text())

    @property
    def secondary(self):
        return int(self.secondary_box.text())

    def choose_peaks(self):
        try:
            if self.orient_box in self.mainwindow.dialogs:
                self.orient_box.close()
        except Exception:
            pass
        self.orient_box = NXDialog(self)
        self.peak_parameters = GridParameters()
        self.peak_parameters.add('primary', self.primary, 'Primary',
                                 readonly=True)
        self.peak_parameters.add('secondary', self.secondary, 'Secondary',
                                 readonly=True)
        self.peak_parameters.add('angle',
                                 self.refine.angle_peaks(self.primary,
                                                         self.secondary),
                                 'Angle (deg)', readonly=True)
        self.peak_parameters.add(
            'primary_hkl', self.ring_list[self.refine.rp[self.primary]],
            'Primary HKL', slot=self.choose_secondary_grid)
        self.orient_box.set_layout(self.peak_parameters.grid(header=False,
                                                             spacing=5),
                                   self.action_buttons(('Orient',
                                                        self.orient)),
                                   self.orient_box.close_buttons(close=True))
        self.orient_box.set_title('Orient Lattice')
        self.orient_box.show()
        try:
            self.setup_secondary_grid()
        except NeXusError as error:
            report_error("Refining Lattice", error)
            self.orient_box.close()

    def setup_secondary_grid(self):
        ps_angle = self.refine.angle_peaks(self.primary, self.secondary)
        n_phkl = len(self.ring_list[self.refine.rp[self.primary]])
        self.hkl_parameters = [GridParameters() for i in range(n_phkl)]
        min_diff = self.get_peak_tolerance()
        min_p = None
        min_hkl = None
        for i in range(n_phkl):
            phkl = eval(self.peak_parameters['primary_hkl'].box.items()[i])
            for hkls in self.rings[self.refine.rp[self.secondary]][1]:
                for hkl in hkls:
                    hkl_angle = self.refine.angle_hkls(phkl, hkl)
                    diff = abs(ps_angle - hkl_angle)
                    if diff < self.get_peak_tolerance():
                        self.hkl_parameters[i].add(str(hkl), hkl_angle,
                                                   str(hkl), vary=False,
                                                   readonly=True)
                        if diff < min_diff:
                            min_diff = diff
                            min_p = i
                            min_hkl = str(hkl)
            self.orient_box.insert_layout(i+1, self.hkl_parameters[i].grid(
                header=['HKL', 'Angle (deg)', 'Select'],
                spacing=5))
        if min_hkl is None:
            raise NeXusError("No matching peaks found")
        self.peak_parameters['primary_hkl'].box.setCurrentIndex(min_p)
        self.hkl_parameters[min_p][min_hkl].vary = True
        self.choose_secondary_grid()

    def choose_secondary_grid(self):
        box = self.peak_parameters['primary_hkl'].box
        for i in [i for i in range(box.count()) if i != box.currentIndex()]:
            self.hkl_parameters[i].hide_grid()
        self.hkl_parameters[box.currentIndex()].show_grid()

    @property
    def primary_hkl(self):
        return eval(self.peak_parameters['primary_hkl'].value)

    @property
    def secondary_hkl(self):
        for hkls in self.hkl_parameters:
            for hkl in hkls:
                if hkls[hkl].vary is True:
                    return eval(hkls[hkl].name)

    def orient(self):
        self.refine.primary = self.primary
        self.refine.secondary = self.secondary
        self.refine.Umat = self.refine.get_UBmat(self.primary,
                                                 self.secondary,
                                                 self.primary_hkl,
                                                 self.secondary_hkl)
        self.update_table()

    def export_peaks(self):
        peaks = list(zip(*[p for p in self.table_model.peak_list
                           if p[-1] < self.get_hkl_tolerance()]))
        idx = NXfield(peaks[0], name='index')
        x = NXfield(peaks[1], name='x')
        y = NXfield(peaks[2], name='y')
        z = NXfield(peaks[3], name='z')
        pol = NXfield(peaks[4], name='polar_angle', units='degree')
        azi = NXfield(peaks[5], name='azimuthal_angle', units='degree')
        polarization = self.refine.get_polarization()
        intensity = NXfield(peaks[6]/polarization[y, x], name='intensity')
        H = NXfield(peaks[7], name='H', units='rlu')
        K = NXfield(peaks[8], name='K', units='rlu')
        L = NXfield(peaks[9], name='L', units='rlu')
        diff = NXfield(peaks[10], name='diff')
        peaks_data = NXdata(intensity, idx, diff, H, K, L, pol, azi, x, y, z)
        export_dialog = ExportDialog(peaks_data, parent=self)
        export_dialog.show()

    def save_orientation(self):
        self.write_parameters()

    def close_peaks_box(self):
        try:
            self.peaks_box.close()
        except Exception:
            pass
        self.peaks_box = None

    def accept(self):
        if 'transform' not in self.entry:
            if self.confirm_action("Set up transforms?", answer="yes"):
                self.treeview.select_node(self.entry)
                from . import transform_data
                transform_data.show_dialog()
        super().accept()


class NXTableModel(QtCore.QAbstractTableModel):

    def __init__(self, parent, peak_list, header, *args):
        super().__init__(parent, *args)
        self.peak_list = peak_list
        self.header = header
        self.parent = parent

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.peak_list)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.peak_list[0])

    def data(self, index, role):
        row, col = index.row(), index.column()
        peak = int(self.peak_list[row][0])
        if not index.isValid():
            return None
        elif role == QtCore.Qt.ToolTipRole:
            return str(
                self.parent.ring_list[self.parent.refine.rp[peak]])[1: -1]
        elif role == QtCore.Qt.DisplayRole:
            value = self.peak_list[row][col]
            if col < 4:
                return str(value)
            elif col == 6:
                return f"{value:5.3g}"
            elif col == 10:
                return f"{value:.3f}"
            else:
                return f"{value:.2f}"
        elif index.column() == 0 and role == QtCore.Qt.CheckStateRole:
            if self.parent.refine._idx.mask[peak]:
                return QtCore.Qt.Unchecked
            else:
                return QtCore.Qt.Checked
        elif role == QtCore.Qt.TextAlignmentRole:
            return int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        elif role == QtCore.Qt.BackgroundRole:
            if (peak == self.parent.refine.primary or
                    peak == self.parent.refine.secondary):
                return QtGui.QColor(QtCore.Qt.lightGray)
            elif self.peak_list[row][10] > self.parent.refine.hkl_tolerance:
                return QtGui.QColor(QtCore.Qt.red)
            else:
                return None
        return None

    def setData(self, index, value, role):
        row = index.row()
        if not index.isValid():
            return False
        elif index.column() == 0 and role == QtCore.Qt.CheckStateRole:
            i = int(self.peak_list[row][0])
            if value == QtCore.Qt.Checked:
                self.parent.refine._idx.mask[i] = False
            elif value == QtCore.Qt.Unchecked:
                self.parent.refine._idx.mask[i] = True
            self.dataChanged.emit(index, index)
            self.parent.report_score()
            return True
        return False

    def headerData(self, col, orientation, role):
        if (orientation == QtCore.Qt.Horizontal and
                role == QtCore.Qt.DisplayRole):
            return self.header[col]
        return None

    def flags(self, index):
        if index.column() == 0:
            return super().flags(index) | QtCore.Qt.ItemIsUserCheckable
        else:
            return super().flags(index)

    def sort(self, col, order):
        """sort table by given column number col"""
        self.layoutAboutToBeChanged.emit()
        self.peak_list = sorted(self.peak_list, key=operator.itemgetter(col))
        if order == QtCore.Qt.DescendingOrder:
            self.peak_list.reverse()
        self.layoutChanged.emit()
