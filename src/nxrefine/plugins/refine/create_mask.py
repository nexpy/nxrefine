# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import os

import numpy as np
from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.plotview import NXPlotView, plotviews
from nexpy.gui.pyqt import getOpenFileName
from nexpy.gui.utils import load_image, report_error
from nexpy.gui.widgets import NXcircle, NXrectangle
from nexusformat.nexus import NeXusError, NXdata, NXfield


def show_dialog():
    try:
        dialog = MaskDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Creating Mask", error)


class MaskDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.data = self.counts = None
        self.xc = self.yc = None
        self.mask = None
        self.shape = None
        self.shapes = []
        self.parameters = {}

        self.set_layout(self.select_entry(self.choose_entry),
                        self.close_buttons(save=True))
        self.set_title('Mask Data')

    def choose_entry(self):
        if self.layout.count() == 2:
            self.shape_box = self.select_box(['Rectangle', 'Circle'])
            self.shape_choice = self.select_box([])
            self.insert_layout(1,
                               self.action_buttons(
                                   ('Import Mask', self.import_mask),
                                   ('Plot Mask', self.plot_data)))
            self.insert_layout(2,
                               self.make_layout(
                                   self.action_buttons(
                                       ('Add Shape', self.add_shape)),
                                   self.shape_box))
            self.insert_layout(3, self.shape_choice)
            self.shape_choice.setVisible(False)
            self.insert_layout(4,
                               self.action_buttons(
                                   ('Remove Shape', self.remove_shape)))
            self.pushbutton['Add Shape'].setCheckable(True)
        self.pixel_mask = self.entry['instrument/detector/pixel_mask'].nxvalue
        self.shape = self.pixel_mask.shape
        self.load_calibration()

    def load_calibration(self):
        if 'calibration' in self.entry['instrument']:
            self.data = self.entry['instrument/calibration']
            self.counts = self.data.nxsignal.nxvalue
            self.xc = self.entry['instrument/detector/beam_center_x'].nxvalue
            self.yc = self.entry['instrument/detector/beam_center_y'].nxvalue
        else:
            self.counts = np.zeros(self.shape)
            x = NXfield(np.arange(self.shape[1], dtype=int), name='x')
            y = NXfield(np.arange(self.shape[0], dtype=int), name='y')
            z = NXfield(self.counts, name='z')
            self.data = NXdata(z, (y, x))
            self.xc, self.yc = self.shape[1] / 2, self.shape[0] / 2

    def import_mask(self):
        mask_file = getOpenFileName(self, 'Open Mask File')
        if os.path.exists(mask_file):
            self.pixel_mask = load_image(mask_file).nxsignal.nxvalue

    @property
    def pv(self):
        try:
            return plotviews['Mask Editor']
        except Exception:
            return NXPlotView('Mask Editor')

    def plot_data(self):
        self.create_mask()
        if self.counts.max() > 0.0:
            mask = np.zeros(self.counts.shape, dtype=float)
            idx = np.where(self.mask == 0)
            mask[idx] = 0.5 * self.counts[idx] / self.counts.max()
            mask += self.mask
            self.pv.plot(NXdata(mask, axes=self.data.nxaxes), log=True)
        else:
            self.pv.plot(NXdata(self.mask, axes=self.data.nxaxes))
        self.pv.aspect = 'equal'
        self.pv.ytab.flipped = True
        self.pv.draw()

    def add_shape(self):
        if self.pushbutton['Add Shape'].isChecked():
            if self.shape_box.currentText() == 'Rectangle':
                self.shape = NXrectangle(self.xc-50, self.yc-50, 100, 100,
                                         border_tol=0.1,
                                         plotview=self.pv,
                                         resize=True, facecolor='r',
                                         edgecolor='k',
                                         linewidth=1, alpha=0.3)
            else:
                self.shape = NXcircle(self.xc, self.yc, 50, border_tol=0.1,
                                      plotview=self.pv, resize=True,
                                      facecolor='r', edgecolor='k',
                                      linewidth=1, alpha=0.3)
            self.shape.connect()
            self.pv.draw()
        else:
            self.shapes.append(self.shape)
            self.pv.shapes.append(self.shapes)
            self.shape_choice.addItem(repr(self.shape))
            self.shape_choice.setVisible(True)
            self.insert_layout(self.shape_options(self.shape))
            self.plot_data()

    def remove_shape(self):
        current_shape = self.shape_choice.selected
        for shape in list(self.shapes):
            if current_shape == repr(shape):
                self.shapes.remove(shape)
                self.shape_choice.remove(current_shape)
        if len(self.shapes) == 0:
            self.shape_choice.setVisible(False)
        self.plot_data()

    def shape_options(self, shape):
        p = self.parameters[shape] = GridParameters()
        if isinstance(shape, NXrectangle):
            x, y = shape.xy
            w, h = shape.width, shape.height
            p.add('x', x, 'Left Pixel')
            p.add('y', y, 'Bottom Pixel')
            p.add('w', w, 'Width')
            p.add('h', h, 'Height')
        else:
            x, y = shape.center
            r = abs(shape.width) / 2
            p.add('x', x, 'X-Center')
            p.add('y', y, 'Y-Center')
            p.add('r', r, 'Radius')
        return p.grid(header=False)

    def create_mask(self):
        x = np.arange(self.pixel_mask.shape[1])
        y = np.arange(self.pixel_mask.shape[0])
        self.mask = self.pixel_mask.copy()
        for shape in self.shapes:
            if isinstance(shape, NXrectangle):
                x0, y0 = shape.xy
                x1, y1 = x0+shape.width, y0+shape.height
                self.mask[int(y0):int(y1), int(x0):int(x1)] = 1
            else:
                xc, yc = shape.center
                r = shape.radius
                inside = (x[None, :]-int(xc))**2+(y[:, None]-int(yc))**2 < r**2
                self.mask = self.mask | inside
        if self.counts is not None:
            self.mask[np.where(self.counts < 0)] = 1

    def accept(self):
        self.create_mask()
        try:
            self.entry['instrument/detector/pixel_mask'] = self.mask
        except NeXusError as error:
            report_error("Creating Mask", error)
            return
        super().accept()
        if 'Mask Editor' in plotviews:
            plotviews['Mask Editor'].close_view()

    def reject(self):
        super().reject()
        if 'Mask Editor' in plotviews:
            plotviews['Mask Editor'].close_view()
