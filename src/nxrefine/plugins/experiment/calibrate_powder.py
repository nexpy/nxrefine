# -----------------------------------------------------------------------------
# Copyright (c) 2022-2024, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import os

import numpy as np
import pyFAI
from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.plotview import NXPlotView, plotviews
from nexpy.gui.pyqt import getOpenFileName, getSaveFileName
from nexpy.gui.utils import (confirm_action, display_message, load_image,
                             report_error)
from nexusformat.nexus import (NeXusError, NXcollection, NXdata, NXfield,
                               NXprocess)
from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
from pyFAI.calibrant import ALL_CALIBRANTS
from pyFAI.geometryRefinement import GeometryRefinement
from pyFAI.massif import Massif

from nxrefine.nxutils import NXExecutor, as_completed, detector_flipped


def show_dialog():
    try:
        dialog = CalibrateDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Calibrating Powder", error)


class CalibrateDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.data = None
        self.counts = None
        self.points = []
        self.ai = None
        self.cake_geometry = None
        self.polarization = None
        self.ring = 0
        self.phi_max = -np.pi

        cstr = str(ALL_CALIBRANTS)
        calibrants = sorted(cstr[cstr.index(':')+2:].split(', '))
        self.parameters = GridParameters()
        self.parameters.add('calibrant', calibrants, 'Calibrant')
        self.parameters['calibrant'].value = 'CeO2'
        self.parameters.add('wavelength', 0.5, 'Wavelength (Ang)', False)
        self.parameters.add('distance', 100.0, 'Detector Distance (mm)', True)
        self.parameters.add('xc', 512, 'Beam Center - x', True)
        self.parameters.add('yc', 512, 'Beam Center - y', True)
        self.parameters.add('yaw', 0.0, 'Yaw (degrees)', True)
        self.parameters.add('pitch', 0.0, 'Pitch (degrees)', True)
        self.parameters.add('roll', 0.0, 'Roll (degrees)', True)
        self.parameters.add('search_size', 10, 'Search Size (pixels)')
        self.rings_box = self.select_box([f'Ring{i}' for i in range(1, 21)])
        self.set_layout(self.select_entry(self.choose_entry),
                        self.progress_layout(close=True))
        self.set_title('Calibrate Powder')

    def choose_entry(self):
        if self.layout.count() == 2:
            self.insert_layout(
                1, self.action_buttons(
                    ('Import Powder Data', self.import_powder),
                    ('Import Calibration', self.import_calibration),
                    ('Export Calibration', self.export_calibration)))
            self.insert_layout(2, self.parameters.grid(header=False))
            self.insert_layout(
                3, self.action_buttons(('Select Points', self.select),
                                       ('Autogenerate Rings', self.auto),
                                       ('Clear Points', self.clear_points)))
            self.pushbutton['Select Points'].setCheckable(True)
            self.pushbutton['Select Points'].setChecked(False)
            self.insert_layout(4, self.make_layout(self.rings_box))
            self.insert_layout(
                5, self.action_buttons(('Calibrate', self.calibrate),
                                       ('Plot Cake', self.plot_cake),
                                       ('Restore', self.restore_parameters),
                                       ('Save', self.save_parameters)))
        self.parameters['wavelength'].value = (
            self.entry['instrument/monochromator/wavelength'])
        detector = self.entry['instrument/detector']
        self.parameters['distance'].value = detector['distance']
        self.parameters['yaw'].value = detector['yaw']
        self.parameters['pitch'].value = detector['pitch']
        self.parameters['roll'].value = detector['roll']
        if 'beam_center_x' in detector:
            self.parameters['xc'].value = detector['beam_center_x']
        if 'beam_center_y' in detector:
            self.parameters['yc'].value = detector['beam_center_y']
        self.pixel_size = (
            self.entry['instrument/detector/pixel_size'].nxvalue * 1e-3)
        self.pixel_mask = self.entry['instrument/detector/pixel_mask'].nxvalue
        if 'calibration' in self.entry['instrument']:
            signal = self.entry['instrument/calibration'].nxsignal
            axes = self.entry['instrument/calibration'].nxaxes
            self.counts = signal.nxvalue
            self.parameters['calibrant'].value = (
                self.entry['instrument/calibration/calibrant'])
            self.data = NXdata(signal, axes,
                title=f'{self.calibrant.name} Powder Calibration')
            self.shape = self.counts.shape
            self.plot_data()
            if 'refinement' in self.entry['instrument/calibration']:
                parameters = (
                    self.entry['instrument/calibration/refinement/parameters'])
                self.ai = AzimuthalIntegrator(
                    dist=parameters['Distance'].nxvalue,
                    detector=parameters['Detector'].nxvalue,
                    poni1=parameters['Poni1'].nxvalue,
                    poni2=parameters['Poni2'].nxvalue,
                    rot1=parameters['Rot1'].nxvalue,
                    rot2=parameters['Rot2'].nxvalue,
                    rot3=parameters['Rot3'].nxvalue,
                    pixel1=parameters['PixelSize1'].nxvalue,
                    pixel2=parameters['PixelSize2'].nxvalue,
                    wavelength=parameters['Wavelength'].nxvalue)
            self.activate()
        else:
            self.close_plots()

    def import_powder(self):
        powder_file = getOpenFileName(self, 'Open Powder Data File')
        if Path(powder_file).exists():
            self.data = load_image(powder_file)
            self.data['title'] = f'{self.calibrant.name} Powder Calibration'
            self.counts = self.data.nxsignal.nxvalue
            self.shape = self.counts.shape
            self.plot_data()

    def import_calibration(self):
        calibration_file = getOpenFileName(self, 'Open Calibration File')
        if Path(calibration_file).exists():
            self.ai = pyFAI.load(calibration_file)
            self.read_parameters()

    def export_calibration(self):
        if self.ai is None:
            display_message("No calibration available")
            return
        calibration_file = getSaveFileName(self, "Choose a Filename",
                                           'calibration.poni')
        if calibration_file:
            self.ai.write(calibration_file)

    @property
    def search_size(self):
        return int(self.parameters['search_size'].value)

    @property
    def selected_ring(self):
        return int(self.rings_box.currentText()[4:]) - 1

    @property
    def ring_color(self):
        colors = ['r', 'b', 'g', 'c', 'm'] * 4
        return colors[self.ring]

    @property
    def pv(self):
        try:
            return plotviews['Powder Calibration']
        except Exception:
            return NXPlotView('Powder Calibration')

    def plot_data(self):
        self.pv.plot(self.data, log=True)
        self.pv.aspect = 'equal'
        self.pv.ytab.flipped = detector_flipped(self.entry)
        self.clear_points()

    def on_button_press(self, event):
        self.pv.make_active()
        if event.inaxes:
            self.xp, self.yp = event.x, event.y
        else:
            self.xp, self.yp = 0, 0

    def on_button_release(self, event):
        if event.inaxes:
            if abs(event.x - self.xp) > 5 or abs(event.y - self.yp) > 5:
                return
            x, y = self.pv.inverse_transform(event.xdata, event.ydata)
            for i, point in enumerate(self.points):
                circle = point[1][0]
                if circle.shape.contains_point(
                        self.pv.ax.transData.transform((x, y))):
                    circle.remove()
                    for circle in point[1][1:]:
                        circle.remove()
                    del self.points[i]
                    return
            self.ring = self.selected_ring
            try:
                points = self.get_points(x, y)
                self.add_points(points)
            except Exception:
                return

    def circle(self, idx, idy, alpha=1.0):
        return self.pv.circle(idx, idy, self.search_size,
                              facecolor=self.ring_color, edgecolor='k',
                              alpha=alpha)

    def select(self):
        if self.pushbutton['Select Points'].isChecked():
            self.pv.cidpress = self.pv.canvas.mpl_connect(
                'button_press_event', self.on_button_press)
            self.pv.cidrelease = self.pv.canvas.mpl_connect(
                'button_release_event', self.on_button_release)
        else:
            self.pv.canvas.mpl_disconnect(self.pv.cidpress)
            self.pv.canvas.mpl_disconnect(self.pv.cidrelease)

    def auto(self):
        xc, yc = self.parameters['xc'].value, self.parameters['yc'].value
        wavelength = self.parameters['wavelength'].value
        distance = self.parameters['distance'].value * 1e-3
        nrings = self.selected_ring + 1

        self.status_message.setText("Generating rings...")
        self.start_progress((0, nrings))
        with NXExecutor() as executor:
            futures = []
            for ring in range(self.selected_ring+1):
                if len([p for p in self.points if p[0] == ring]) > 0:
                    continue
                theta = 2 * np.arcsin(wavelength /
                                      (2*self.calibrant.dSpacing[ring]))
                radius = distance * np.tan(theta) / self.pixel_size
                futures.append(executor.submit(
                    generate_ring, self.counts, ring, radius, xc, yc,
                    self.pixel_mask, self.search_size))            
            for i, future in enumerate(as_completed(futures)):
                ring, points = future.result()
                self.ring = ring
                self.add_points(points)
                self.update_progress(i)
                futures.remove(future)
        self.stop_progress()
        self.status_message.setText("Rings complete")

    def get_points(self, x, y):
        idx, idy = find_peak(x, y, self.counts, self.search_size)
        points = [(float(idy), float(idx))]
        massif = Massif(self.counts)
        points.extend(massif.find_peaks((idy, idx), stdout=False))
        return points

    def add_points(self, points):
        y, x = points[0]
        circles = [self.circle(x, y)]
        circles.extend(self.circle(x, y, alpha=0.3) for y, x in points[1:])
        self.points.append([self.ring, circles])

    def clear_points(self):
        for i, point in enumerate(self.points):
            for circle in point[1]:
                circle.remove()
        self.points = []

    @property
    def calibrant(self):
        return ALL_CALIBRANTS[self.parameters['calibrant'].value]

    @property
    def point_array(self):
        points = []
        for point in self.points:
            ring = point[0]
            for p in point[1]:
                x, y = [round(v) for v in p.center]
                points.append((x, y, ring))
        return np.array(points)

    def prepare_parameters(self):
        self.parameters.set_parameters()
        self.wavelength = self.parameters['wavelength'].value * 1e-10
        self.distance = self.parameters['distance'].value * 1e-3
        self.yaw = np.radians(self.parameters['yaw'].value)
        self.pitch = np.radians(self.parameters['pitch'].value)
        self.roll = np.radians(self.parameters['roll'].value)
        self.xc = self.parameters['xc'].value
        self.yc = self.parameters['yc'].value

    def calibrate(self):
        if len(self.points) == 0:
            display_message("No points selected")
            return
        self.prepare_parameters()
        self.orig_pixel1 = self.pixel_size
        self.orig_pixel2 = self.pixel_size
        self.ai = GeometryRefinement(self.point_array,
                                     dist=self.distance,
                                     wavelength=self.wavelength,
                                     pixel1=self.pixel_size,
                                     pixel2=self.pixel_size,
                                     calibrant=self.calibrant)
        self.refine()
        self.ai.reset()

    def refine(self):
        self.ai.data = self.point_array

        if self.parameters['wavelength'].vary:
            self.ai.refine2()
            fix = []
        else:
            fix = ['wavelength']
        if not self.parameters['distance'].vary:
            fix.append('dist')
        self.ai.refine2_wavelength(fix=fix)
        self.read_parameters()
        self.ai.reset()

    def plot_cake(self):
        if 'Cake Plot' in plotviews:
            plotview = plotviews['Cake Plot']
        else:
            plotview = NXPlotView('Cake Plot')
        if self.ai is None:
            display_message("No refinement performed")
            return
        res = self.ai.integrate2d(self.counts, 1024, 1024, method='csr',
                                  unit='2th_deg', correctSolidAngle=True)
        self.cake_data = NXdata(res[0],
                                (NXfield(res[2], name='azimumthal_angle'),
                                 NXfield(res[1], name='polar_angle')))
        self.cake_data['title'] = f'{self.calibrant.name} Cake Plot'
        plotview.plot(self.cake_data, log=True)
        wavelength = self.parameters['wavelength'].value
        polar_angles = [2 * np.degrees(np.arcsin(wavelength/(2*d)))
                        for d in self.calibrant.dSpacing]
        plotview.vlines([polar_angle for polar_angle in polar_angles
                         if polar_angle < plotview.xaxis.max],
                        linestyle=':', color='r')

    def read_parameters(self):
        self.parameters['wavelength'].value = self.ai.wavelength * 1e10
        self.parameters['yaw'].value = np.degrees(self.ai.rot1)
        self.parameters['pitch'].value = np.degrees(self.ai.rot2)
        self.parameters['roll'].value = np.degrees(self.ai.rot3)
        fit2d = self.ai.getFit2D()
        self.parameters['distance'].value = fit2d['directDist']
        self.parameters['xc'].value = fit2d['centerX']
        self.parameters['yc'].value = fit2d['centerY']

    def restore_parameters(self):
        self.parameters.restore_parameters()

    def save_parameters(self):
        if self.ai is None:
            display_message("No refinement performed")
            return
        elif 'calibration' in self.entry['instrument']:
            if confirm_action(
                    "Do you want to overwrite existing calibration data?"):
                del self.entry['instrument/calibration']
            else:
                return
        instrument = self.entry['instrument']
        instrument['calibration'] = self.data
        instrument['calibration/calibrant'] = (
            self.parameters['calibrant'].value)
        process = NXprocess()
        process.program = 'pyFAI'
        process.version = pyFAI.version
        process.parameters = NXcollection()
        process.parameters['Detector'] = instrument['detector/description']
        process.parameters['PixelSize1'] = self.ai.pixel1
        process.parameters['PixelSize2'] = self.ai.pixel2
        process.parameters['Distance'] = self.ai.dist
        process.parameters['Poni1'] = self.ai.poni1
        process.parameters['Poni2'] = self.ai.poni2
        process.parameters['Rot1'] = self.ai.rot1
        process.parameters['Rot2'] = self.ai.rot2
        process.parameters['Rot3'] = self.ai.rot3
        process.parameters['Wavelength'] = self.ai.wavelength
        instrument['calibration/refinement'] = process
        monochromator = instrument['monochromator']
        monochromator['wavelength'] = self.parameters['wavelength'].value
        monochromator['energy'] = (
            12.398419739640717 / self.parameters['wavelength'].value)
        detector = instrument['detector']
        detector['distance'] = self.parameters['distance'].value
        detector['yaw'] = self.parameters['yaw'].value
        detector['pitch'] = self.parameters['pitch'].value
        detector['roll'] = self.parameters['roll'].value
        detector['beam_center_x'] = self.parameters['xc'].value
        detector['beam_center_y'] = self.parameters['yc'].value
        try:
            detector['polarization'] = self.ai.polarization(
                factor=0.99, shape=detector['pixel_mask'].shape)
        except Exception:
            pass
        entries = [entry for entry in self.root.entries
                   if entry[-1].isdigit() and entry != self.entry.nxname]
        if entries and self.confirm_action(
            f'Copy mask to other entries? ({", ".join(entries)})',
                answer='yes'):
            for entry in [self.root[e]for e in entries]:
                other_instrument = entry['instrument']
                if 'calibration' in other_instrument:
                    del other_instrument['calibration']
                other_instrument['calibration'] = instrument['calibration']
                other_monochromator = entry['instrument/monochromator']
                other_monochromator['wavelength'] = monochromator['wavelength']
                other_monochromator['energy'] = monochromator['energy']
                other_detector = entry['instrument/detector']
                other_detector['distance'] = detector['distance']
                other_detector['yaw'] = detector['yaw']
                other_detector['pitch'] = detector['pitch']
                other_detector['roll'] = detector['roll']
                other_detector['beam_center_x'] = detector['beam_center_x']
                other_detector['beam_center_y'] = detector['beam_center_y']
                try:
                    other_detector['polarization'] = detector['polarization']
                except Exception:
                    pass

    def close_plots(self):
        if 'Powder Calibration' in plotviews:
            plotviews['Powder Calibration'].close()
        if 'Cake Plot' in plotviews:
            plotviews['Cake Plot'].close()

    def close(self):
        self.reject()

    def accept(self):
        super().accept()
        self.close_plots()

    def reject(self):
        super().reject()
        self.close_plots()


def generate_ring(counts, ring, radius, xc, yc, pixel_mask, search_size):
    points = []
    phi = -np.pi
    while phi < np.pi:
        x, y = int(xc + radius*np.cos(phi)), int(yc + radius*np.sin(phi))
        if ((x > 0 and x < counts.shape[1]) and (y > 0 and y < counts.shape[0])
                and not pixel_mask[y, x]):
            phi, extra_points = get_points(x, y, counts, xc=xc, yc=yc, phi=phi,
                                           search_size=search_size)
            points.extend(extra_points)
        phi += 0.2
    return ring, points
 

def get_points(x, y, counts, xc=None, yc=None, phi=None, search_size=10):
    logging.getLogger('pyFAI.massif').setLevel(logging.ERROR)
    if phi is None:
        phi = 0.0
    idx, idy = find_peak(x, y, counts, search_size)
    points = [(float(idy), float(idx))]
    massif = Massif(counts)
    points.extend(massif.find_peaks((idy, idx), stdout=False))
    if xc is not None and yc is not None:
        phis = np.array([np.arctan2(p[0]-yc, p[1]-xc) for p in points])
        if phi < -0.5*np.pi:
            phis[np.where(phis > 0.0)] -= 2 * np.pi
        phi = max(*phis, phi)
        phis = [np.degrees(p) for p in phis]
    return phi, points
           

def find_peak(x, y, counts, search_size=10):
    s = search_size
    left = int(np.round(x - s * 0.5))
    if left < 0:
        left = 0
    top = int(np.round(y - s * 0.5))
    if top < 0:
        top = 0
    region = counts[top:(top+s), left:(left+s)]
    idy, idx = np.where(region == region.max())
    idx = left + idx[0]
    idy = top + idy[0]
    return idx, idy

