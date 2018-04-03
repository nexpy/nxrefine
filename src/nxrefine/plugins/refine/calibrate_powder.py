import numpy as np
from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
from pyFAI.blob_detection import BlobDetection
from pyFAI.calibrant import Calibrant, ALL_CALIBRANTS
from pyFAI.geometryRefinement import GeometryRefinement
from pyFAI.massif import Massif

from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.plotview import NXPlotView, plotviews
from nexpy.gui.utils import report_error, load_image
from nexusformat.nexus import *
from nxrefine.nxrefine import NXRefine


def show_dialog():
    dialog = CalibrateDialog()
    dialog.show()
#    except NeXusError as error:
#        report_error("Calibrating Powder", error)


class CalibrateDialog(BaseDialog):

    def __init__(self, parent=None):
        super(CalibrateDialog, self).__init__(parent)

        self.plotview = None
        self.data = None
        self.points = []
        self.pattern_geometry = None
        self.cake_geometry = None
        self.is_calibrated = False    

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
        self.parameters.add('search_size', 20, 'Search Size (pixels)')
        rings = ['Ring1', 'Ring2', 'Ring3', 'Ring4', 'Ring5']
        self.rings_box = self.select_box(rings)
        self.set_layout(self.select_entry(self.choose_entry),
                        self.action_buttons(('Plot Calibration', self.plot_data)),
                        self.parameters.grid(header=False),
                        self.make_layout(
                            self.action_buttons(('Select Points', self.select)),
                            self.rings_box),
                        self.action_buttons(('Calibrate', self.calibrate),
                                            ('Plot Cake', self.plot_cake),
                                            ('Restore', self.restore_parameters)), 
                        self.close_buttons(save=True))
        self.set_title('Calibrating Powder')

    def choose_entry(self):
        if 'calibration' not in self.entry['instrument']:
            raise NeXusError('Please load calibration data to this entry')
        self.update_parameters()
        self.plot_data()

    def update_parameters(self):
        self.parameters['wavelength'].value = self.entry['instrument/monochromator/wavelength']
        detector = self.entry['instrument/detector']
        self.parameters['distance'].value = detector['distance']
        self.parameters['yaw'].value = detector['yaw']
        self.parameters['pitch'].value = detector['pitch']
        self.parameters['roll'].value = detector['roll']
        if 'beam_center_x' in detector:
            self.parameters['xc'].value = detector['beam_center_x']
        if 'beam_center_y' in detector:
            self.parameters['yc'].value = detector['beam_center_y']
        self.data = self.entry['instrument/calibration']


    def write_parameters(self):
        self.entry['instrument/monochromator/wavelength'] = self.parameters['wavelength'].value
        self.entry['instrument/monochromator/energy'] = self.parameters['wavelength'].value * 12.398419739640717
        detector = self.entry['instrument/detector']
        detector['distance'] = self.parameters['distance'].value
        detector['yaw'] = self.parameters['yaw'].value
        detector['pitch'] = self.parameters['pitch'].value
        detector['roll'] = self.parameters['roll'].value
        detector['beam_center_x'] = self.parameters['xc'].value
        detector['beam_center_y'] = self.parameters['yc'].value

    @property
    def search_size(self):
        return int(self.parameters['search_size'].value)

    @property
    def ring(self):
        return int(self.rings_box.currentText()[-1]) - 1

    @property
    def ring_color(self):
        colors = ['r', 'b', 'g', 'c', 'm']
        return colors[self.ring]

    def plot_data(self):
        if self.plotview is None:
            if 'Powder Calibration' in plotviews:
                self.plotview = plotviews['Powder Calibration']
            else:
                self.plotview = NXPlotView('Powder Calibration')
        self.plotview.plot(self.data, log=True)
        self.plotview.aspect='equal'
        self.plotview.ytab.flipped = True
        self.clear_peaks()

    def on_button_press(self, event):
        self.plotview.make_active()
        if event.inaxes:
            self.xp, self.yp = event.x, event.y
        else:
            self.xp, self.yp = 0, 0

    def on_button_release(self, event):
        if event.inaxes:
            if abs(event.x - self.xp) > 5 or abs(event.y - self.yp) > 5:
                return
            x, y = self.plotview.inverse_transform(event.xdata, event.ydata)
            for i, point in enumerate(self.points):
                circle = point[0]
                if circle.contains_point(self.plotview.ax.transData.transform((x,y))):
                    circle.remove()
                    del self.points[i]
                    return
            idx, idy = self.find_peak(x, y)            
            self.points.append([self.plotview.circle(idx, idy, self.search_size,
                                    facecolor=self.ring_color, edgecolor='k'),
                                idy, idx, self.ring])

    def select(self):
        self.plotview.cidpress = self.plotview.mpl_connect(
                                    'button_press_event', self.on_button_press)
        self.plotview.cidrelease = self.plotview.mpl_connect(
                                    'button_release_event', self.on_button_release)

    def find_peak(self, x, y):
        s = self.search_size
        left = int(np.round(x - s * 0.5))
        if left < 0:
            left = 0
        top = int(np.round(y - s * 0.5))
        if top < 0:
            top = 0
        region = self.data.nxsignal.nxvalue[top:(top+s),left:(left+s)]
        idy, idx = np.where(region == region.max())
        idx = left + idx[0]
        idy = top + idy[0]
        return idx, idy

    def clear_peaks(self):
        self.points = []
        
    @property
    def calibrant(self):
        return ALL_CALIBRANTS[self.parameters['calibrant'].value]

    @property
    def point_array(self):
        return np.array([point[1:4] for point in self.points])

    def prepare_parameters(self):
        self.parameters.set_parameters()
        self.wavelength = self.parameters['wavelength'].value * 1e-10
        self.distance = self.parameters['distance'].value * 1e-3
        self.yaw = np.radians(self.parameters['yaw'].value)
        self.pitch = np.radians(self.parameters['pitch'].value)
        self.roll = np.radians(self.parameters['roll'].value)
        self.pixel_size = self.entry['instrument/detector/pixel_size'].nxvalue * 1e-3
        self.xc = self.parameters['xc'].value
        self.yc = self.parameters['yc'].value

    def calibrate(self):
        self.prepare_parameters()
        self.orig_pixel1 = self.pixel_size
        self.orig_pixel2 = self.pixel_size
        self.pattern_geometry = GeometryRefinement(self.point_array,
                                                   dist=self.distance,
                                                   wavelength=self.wavelength,
                                                   pixel1=self.pixel_size,
                                                   pixel2=self.pixel_size,
                                                   calibrant=self.calibrant)
        self.refine()
        self.create_cake_geometry()
        self.pattern_geometry.reset()

    def refine(self):
        self.pattern_geometry.data = self.point_array

        if self.parameters['wavelength'].vary:
            self.pattern_geometry.refine2()
            fix = []
        else:
            fix = ['wavelength']
        if not self.parameters['distance'].vary:
            fix.append('dist')
        self.pattern_geometry.refine2_wavelength(fix=fix)
        self.read_parameters()
        self.is_calibrated = True
        self.create_cake_geometry()
        self.pattern_geometry.reset()

    def create_cake_geometry(self):
        self.cake_geometry = AzimuthalIntegrator()
        pyFAI_parameter = self.pattern_geometry.getPyFAI()
        pyFAI_parameter['wavelength'] = self.pattern_geometry.wavelength
        self.cake_geometry.setPyFAI(dist=pyFAI_parameter['dist'],
                                    poni1=pyFAI_parameter['poni1'],
                                    poni2=pyFAI_parameter['poni2'],
                                    rot1=pyFAI_parameter['rot1'],
                                    rot2=pyFAI_parameter['rot2'],
                                    rot3=pyFAI_parameter['rot3'],
                                    pixel1=pyFAI_parameter['pixel1'],
                                    pixel2=pyFAI_parameter['pixel2'])
        self.cake_geometry.wavelength = pyFAI_parameter['wavelength']

    def plot_cake(self):
        if 'Cake Plot' not in plotviews:
            plotview = plotviews['Cake Plot']
        else:
            plotview = NXPlotView('Cake Plot')    
        if not is_calibrated:
            raise NeXusError('No refinement performed')
        res = self.cake_geometry.integrate2d(self.data.nxsignal.nxvalue, 
                                             1024, 1024,
                                             method='csr',
                                             unit='2th_deg',
                                             correctSolidAngle=True)
        self.cake_data = NXdata(res[0], (NXfield(res[2], name='azimumthal_angle'),
                                         NXfield(res[1], name='polar_angle')))
        plotview.plot(self.cake_data, log=True)

    def read_parameters(self):
        pyFAI = self.pattern_geometry.getPyFAI()
        fit2d = self.pattern_geometry.getFit2D()
        self.parameters['wavelength'].value = self.pattern_geometry.wavelength * 1e10
        self.parameters['distance'].value = pyFAI['dist'] * 1e3
        self.parameters['yaw'].value = np.degrees(pyFAI['rot1'])
        self.parameters['pitch'].value = np.degrees(pyFAI['rot2'])
        self.parameters['roll'].value = np.degrees(pyFAI['rot3'])
        self.parameters['xc'].value = fit2d['centerX']
        self.parameters['yc'].value = fit2d['centerY']

    def restore_parameters(self):
        self.parameters.restore_parameters()

    def accept(self):
        self.write_parameters()
        super(CalibrateDialog, self).accept()
        if 'Powder Calibration' in plotviews:
            plotviews['Powder Calibration'].close_view()
        if 'Cake Plot' in plotviews:
            plotviews['Cake Plot'].close_view()

    def reject(self):
        super(CalibrateDialog, self).reject()
        if 'Powder Calibration' in plotviews:
            plotviews['Powder Calibration'].close_view()
        if 'Cake Plot' in plotviews:
            plotviews['Cake Plot'].close_view()
