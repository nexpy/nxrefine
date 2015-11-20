import numpy as np
from scipy.optimize import minimize
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.mainwindow import report_error
from nexpy.gui.plotview import get_plotview, plotview
from nexusformat.nexus import *
from nxpeaks.nxrefine import NXRefine, find_nearest


def show_dialog():
#    try:
    dialog = RefineLatticeDialog()
    dialog.show()
#    except NeXusError as error:
#        report_error("Refining Lattice", error)


class RefineLatticeDialog(BaseDialog):

    def __init__(self, parent=None):
        super(RefineLatticeDialog, self).__init__(parent)

        self.select_entry(self.choose_entry)

        self.refine = NXRefine(self.entry)
        self.refine.read_parameters()

        self.parameters = GridParameters()
        self.parameters.add('symmetry', self.refine.symmetries, 'Symmetry', 
                            None, self.set_symmetry)
        self.parameters.add('a', self.refine.a, 'Unit Cell - a (Ang)', True)
        self.parameters.add('b', self.refine.b, 'Unit Cell - b (Ang)', True)
        self.parameters.add('c', self.refine.c, 'Unit Cell - c (Ang)', True)
        self.parameters.add('alpha', self.refine.alpha, 'Unit Cell - alpha (deg)', False)
        self.parameters.add('beta', self.refine.beta, 'Unit Cell - beta (deg)', False)
        self.parameters.add('gamma', self.refine.gamma, 'Unit Cell - gamma (deg)', False)
        self.parameters.add('wavelength', self.refine.wavelength, 'Wavelength (Ang)', False)
        self.parameters.add('distance', self.refine.distance, 'Distance (mm)', False)
        self.parameters.add('yaw', self.refine.yaw, 'Yaw (deg)', False)
        self.parameters.add('pitch', self.refine.pitch, 'Pitch (deg)', False)
        self.parameters.add('roll', self.refine.roll, 'Roll (deg)', False)
        self.parameters.add('xc', self.refine.xc, 'Beam Center - x', False)
        self.parameters.add('yc', self.refine.yc, 'Beam Center - y', False)
        self.parameters.add('polar', self.refine.polar_max, 
                            'Max. Polar Angle (deg)', None, self.set_polar_max)
        self.parameters.add('polar_tolerance', self.refine.polar_tolerance, 'Polar Angle Tolerance')

        action_buttons = self.action_buttons(('Plot', self.plot_lattice),
                                             ('Refine', self.refine_parameters),
                                             ('Restore', self.restore_parameters),
                                             ('Save', self.write_parameters))

        self.set_layout(self.entry_layout, self.parameters.grid(), 
                        action_buttons, self.close_buttons())
        self.set_title('Refining Lattice')
        self.parameters['symmetry'].value = self.guess_symmetry()
        
    def choose_entry(self):
        self.refine = NXRefine(self.entry)
        self.update_parameters()

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
        self.parameters['polar'].value = self.refine.polar_max
        self.parameters['polar_tolerance'].value = self.refine.polar_tolerance

    def transfer_parameters(self):
        self.refine.a, self.refine.b, self.refine.c, \
            self.refine.alpha, self.refine.beta, self.refine.gamma = \
                self.get_lattice_parameters()
        self.refine.set_symmetry()
        self.refine.wavelength = self.get_wavelength()
        self.refine.distance = self.get_distance()
        self.refine.yaw, self.refine.pitch, self.refine.roll = self.get_tilts()
        self.refine.xc, self.refine.yc = self.get_centers()
        self.refine.polar_max = self.get_polar_max()
        self.refine.polar_tol = self.get_tolerance()

    def write_parameters(self):
        self.transfer_parameters()
        polar_angles, azimuthal_angles = self.refine.calculate_angles(
                                             self.refine.xp, self.refine.yp)
        self.refine.write_angles(polar_angles, azimuthal_angles)
        self.refine.write_parameters()

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

    def guess_symmetry(self):
        self.refine.a, self.refine.b, self.refine.c, \
            self.refine.alpha, self.refine.beta, self.refine.gamma = \
                self.get_lattice_parameters()
        return self.refine.guess_symmetry()

    def get_lattice_parameters(self):
        return (self.parameters['a'].value,
                self.parameters['b'].value,
                self.parameters['c'].value,
                self.parameters['alpha'].value,
                self.parameters['beta'].value,
                self.parameters['gamma'].value)

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

    def get_polar_max(self):
        return self.parameters['polar'].value

    def set_polar_max(self):
        self.refine.set_polar_max(self.get_polar_max())

    def get_tolerance(self):
        return self.parameters['polar_tolerance'].value

    def plot_lattice(self):
        self.transfer_parameters()
        self.set_polar_max()
        self.plot_peaks(self.refine.x, self.refine.y)
        self.plot_rings()

    def plot_peaks(self, x, y):
        try:
            polar_angles, azimuthal_angles = self.refine.calculate_angles(x, y)
            if polar_angles[0] > polar_angles[-1]:
                polar_angles = polar_angles[::-1]
                azimuthal_angles = azimuthal_angles[::-1]
            azimuthal_field = NXfield(azimuthal_angles, name='azimuthal_angle')
            azimuthal_field.long_name = 'Azimuthal Angle'
            polar_field = NXfield(polar_angles, name='polar_angle')
            polar_field.long_name = 'Polar Angle'
            plotview = get_plotview()
            plotview.plot(NXdata(azimuthal_field, polar_field, title='Peak Angles'))
        except NeXusError as error:
            report_error('Plotting Lattice', error)

    def plot_rings(self, polar_max=None):
        if polar_max is None:
            polar_max = self.refine.polar_max
        peaks = self.refine.calculate_rings(polar_max)
        plotview = get_plotview()
        plotview.vlines(peaks, colors='r', linestyles='dotted')
        plotview.draw()
    
    def plot_peak(self, i):
        x, y, z = self.refine.xp[i], self.refine.yp[i], self.refine.zp[i]/10.0
        xmin, xmax = max(0,int(x)-200), min(int(x)+200,data.v.shape[2])
        ymin, ymax = max(0,int(y)-200), min(int(y)+200,data.v.shape[1])
        zmin, zmax = max(0.0,z-20.0), min(z+20.0, 360.0)
        xslab=np.s_[zmin:zmax,ymin:ymax,x]
        yslab=np.s_[zmin:zmax,y,xmin:xmax]
        zslab=np.s_[z,ymin:ymax,xmin:xmax]
        pvz.plot(data[zslab], log=True)
        pvz.crosshairs(x, y)
        pvy.plot(data[yslab], log=True)
        pvy.crosshairs(x, z)
        pvx.plot(data[xslab], log=True)
        pvx.crosshairs(y, z)

    def refine_parameters(self):
        self.parameters.refine_parameters(self.residuals)
        self.update_parameters()

    def residuals(self, p):
        self.parameters.get_parameters(p)
        self.transfer_parameters()
        polar_angles, _ = self.refine.calculate_angles(self.refine.x, self.refine.y)
        rings = self.refine.calculate_rings()
        residuals = np.array([find_nearest(rings, polar_angle) - polar_angle 
                              for polar_angle in polar_angles])
        return np.sum(residuals**2)

    def restore_parameters(self):
        self.parameters.restore_parameters()
        self.transfer_parameters()

