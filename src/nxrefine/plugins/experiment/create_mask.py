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
        self.set_title('Create Mask')

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
            self.pushbutton['Add Shape'].setCheckable(True)
        self.pixel_mask = self.entry['instrument/detector/pixel_mask'].nxvalue
        self.shape = self.pixel_mask.shape
        self.load_calibration()
        self.plot_data()
        self.activate()

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

    def plot_limits(self):
        return self.pv.xaxis.get_limits() + self.pv.yaxis.get_limits()

    def add_shape(self):
        if self.pushbutton['Add Shape'].isChecked():
            if self.shape_box.currentText() == 'Rectangle':
                self.shape = MaskRectangle(self.xc-50, self.yc-50, 100, 100,
                                           parent=self,
                                           border_tol=0.1,
                                           plotview=self.pv,
                                           resize=True, facecolor='r',
                                           edgecolor='k',
                                           linewidth=1, alpha=0.3)
            else:
                self.shape = MaskCircle(self.xc, self.yc, 50,
                                        parent=self,
                                        border_tol=0.1,
                                        plotview=self.pv, resize=True,
                                        facecolor='r', edgecolor='k',
                                        linewidth=1, alpha=0.3)
            self.shape.label = repr(self.shape)
            self.shape.connect()
            self.shape_grid = self.shape_options(self.shape)
            self.pv.draw()
            if len(self.shapes) == 0:
                self.insert_layout(3, self.shape_choice)
                self.shape_choice.setVisible(False)
                self.insert_layout(4, self.shape_grid)
                self.insert_layout(5,self.action_buttons(('Remove Shape',
                                                          self.remove_shape)))
            else:
                self.insert_layout(4, self.shape_grid)
            self.pushbutton['Add Shape'].setText('Save Shape')
        else:
            self.shape.label = repr(self.shape)
            self.shapes.append(self.shape)
            self.pv.shapes.append(self.shapes)
            self.shape_choice.addItem(self.shape.label)
            self.shape_choice.setVisible(True)
            xmin, xmax, ymin, ymax = self.plot_limits()
            self.plot_data()
            self.pv.set_plot_limits(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
            self.pv.otab.zoom()
            self.delete_grid(self.shape_grid)
            self.pushbutton['Add Shape'].setText('Add Shape')

    def remove_shape(self):
        current_shape = self.shape_choice.selected
        for shape in list(self.shapes):
            if current_shape == repr(shape):
                self.shapes.remove(shape)
                self.shape_choice.remove(current_shape)
        if len(self.shapes) == 0:
            self.shape_choice.setVisible(False)
        xmin, xmax, ymin, ymax = self.plot_limits()
        self.plot_data()
        self.pv.set_plot_limits(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)

    def change_shape(self):
        if isinstance(self.shape, NXrectangle):
            x = self.parameters[self.shape]['x'].value
            y = self.parameters[self.shape]['y'].value
            w = self.parameters[self.shape]['w'].value
            h = self.parameters[self.shape]['h'].value
            self.shape.set_bounds(x, y, w, h)
        else:
            x = self.parameters[self.shape]['x'].value
            y = self.parameters[self.shape]['y'].value
            self.shape.set_center(x, y)
            r = abs(self.parameters[self.shape]['r'].value)
            self.shape.set_radius(r)
        self.update_shape()

    def update_shape(self):
        if isinstance(self.shape, NXrectangle):
            x, y = self.shape.xy
            w, h = self.shape.width, self.shape.height
            self.parameters[self.shape]['x'].value = x
            self.parameters[self.shape]['y'].value = y
            self.parameters[self.shape]['w'].value = w
            self.parameters[self.shape]['h'].value = h
        else:
            x, y = self.shape.center
            r = abs(self.shape.width) / 2
            self.parameters[self.shape]['x'].value = x
            self.parameters[self.shape]['y'].value = y
            self.parameters[self.shape]['r'].value = r
        self.shape.label = repr(self.shape)
        self.shape_choice.setItemText(
            self.shape_choice.findText(self.shape.label), repr(self.shape))               

    def shape_options(self, shape):
        p = self.parameters[shape] = GridParameters()
        if isinstance(shape, NXrectangle):
            x, y = shape.xy
            w, h = shape.width, shape.height
            p.add('x', x, 'Left Pixel', slot=self.change_shape)
            p.add('y', y, 'Bottom Pixel', slot=self.change_shape)
            p.add('w', w, 'Width', slot=self.change_shape)
            p.add('h', h, 'Height', slot=self.change_shape)
        else:
            x, y = shape.center
            r = abs(shape.width) / 2
            p.add('x', x, 'X-Center', slot=self.change_shape)
            p.add('y', y, 'Y-Center', slot=self.change_shape)
            p.add('r', r, 'Radius', slot=self.change_shape)
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
            mask_path = 'instrument/detector/pixel_mask'
            self.entry[mask_path] = self.mask
            entries = [entry for entry in self.root.entries
                       if entry[-1].isdigit() and entry != self.entry.nxname]
            if entries and self.confirm_action(
                f'Copy mask to other entries? ({", ".join(entries)})',
                    answer='yes'):
                for entry in entries:
                    self.root[entry][mask_path] = self.mask
        except NeXusError as error:
            report_error("Creating Mask", error)
            return
        super().accept()
        if 'Mask Editor' in plotviews:
            plotviews['Mask Editor'].close()

    def reject(self):
        super().reject()
        if 'Mask Editor' in plotviews:
            plotviews['Mask Editor'].close()


class MaskRectangle(NXrectangle):

    def __init__(self, x, y, dx, dy, **kwargs):
        self.parent = kwargs['parent']
        del kwargs['parent']
        super().__init__(x, y, dx, dy, **kwargs)

    def update(self, x, y):
        super().update(x, y)
        self.parent.update_shape()


class MaskCircle(NXcircle):

    def __init__(self, x, y, r, **kwargs):
        self.parent = kwargs['parent']
        del kwargs['parent']
        super().__init__(x, y, r, **kwargs)

    def update(self, x, y):
        super().update(x, y)
        self.parent.update_shape()
