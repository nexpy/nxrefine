# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.plotview import get_plotview
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError, NXdata, NXfield
from nxrefine.nxrefine import NXRefine


def show_dialog():
    try:
        dialog = CalculateDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Calculating Angles", error)


class CalculateDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.select_entry(self.choose_entry)

        self.refine = NXRefine()

        self.parameters = GridParameters()
        self.parameters.add('wavelength', self.refine.wavelength,
                            'Wavelength (Ang)')
        self.parameters.add('distance', self.refine.distance,
                            'Detector Distance (mm)')
        self.parameters.add('xc', self.refine.xc, 'Beam Center - x')
        self.parameters.add('yc', self.refine.yc, 'Beam Center - y')
        self.parameters.add('pixel', self.refine.pixel_size, 'Pixel Size (mm)')
        self.action_buttons = self.action_buttons(
            ('Plot', self.plot_lattice), ('Save', self.write_parameters))
        self.set_layout(self.entry_layout, self.close_buttons())
        self.set_title(f'{self.label} Calculate Angles')

    def choose_entry(self):
        self.refine = NXRefine(self.entry)
        if 'peaks' in self.entry:
            if self.layout.count() == 2:
                self.insert_layout(1, self.parameters.grid(header=False))
                self.insert_layout(2, self.action_buttons)
            self.update_parameters()
        else:
            self.display_message("Calculating Angles",
                                 "No peaks have been found in this entry")

    def update_parameters(self):
        self.parameters['wavelength'].value = self.refine.wavelength
        self.parameters['distance'].value = self.refine.distance
        self.parameters['xc'].value = self.refine.xc
        self.parameters['yc'].value = self.refine.yc
        self.parameters['pixel'].value = self.refine.pixel_size

    def get_wavelength(self):
        return self.parameters['wavelength'].value

    def get_distance(self):
        return self.parameters['distance'].value

    def get_centers(self):
        return self.parameters['xc'].value, self.parameters['yc'].value

    def get_pixel_size(self):
        return self.parameters['pixel'].value

    def get_parameters(self):
        self.refine.wavelength = self.get_wavelength()
        self.refine.distance = self.get_distance()
        self.refine.xc, self.refine.yc = self.get_centers()
        self.refine.pixel_size = self.get_pixel_size()
        self.refine.yaw = self.refine.pitch = self.refine.roll = None

    def plot_lattice(self):
        try:
            self.get_parameters()
            self.plot_peaks(self.refine.xp, self.refine.yp)
        except NeXusError as error:
            report_error("Calculating Angles", error)

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
            plotview.plot(NXdata(azimuthal_field, polar_field,
                                 title=f'Peak Angles: {self.refine.name}'))
        except NeXusError as error:
            report_error("Plotting Lattice", error)

    def write_parameters(self):
        try:
            self.get_parameters()
            polar_angles, azimuthal_angles = self.refine.calculate_angles(
                self.refine.xp, self.refine.yp)
            self.refine.write_angles(polar_angles, azimuthal_angles)
            self.refine.write_parameters()
        except NeXusError as error:
            report_error("Calculating Angles", error)
