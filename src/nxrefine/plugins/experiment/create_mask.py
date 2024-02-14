# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
from pathlib import Path

import numpy as np
from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.plotview import NXPlotView, plotviews
from nexpy.gui.pyqt import getOpenFileName
from nexpy.gui.utils import load_image, report_error
from nexpy.gui.widgets import NXcircle, NXrectangle
from nexusformat.nexus import NeXusError, NXdata, NXfield

from nxrefine.nxutils import detector_flipped


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
            self.shape_choice = self.select_box([], slot=self.edit_shape)
            self.insert_layout(1,
                               self.action_buttons(
                                   ('Import Mask', self.import_mask),
                                   ('Plot Mask', self.plot_data)))
            self.insert_layout(2,
                               self.make_layout(
                                   self.action_buttons(
                                       ('Add Shape', self.add_shape)),
                                   self.shape_box))
        self.pixel_mask = self.entry['instrument/detector/pixel_mask'].nxvalue
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
            self.counts = np.zeros(self.pixel_mask.shape)
            x = NXfield(np.arange(self.counts.shape[1], dtype=int), name='x')
            y = NXfield(np.arange(self.counts.shape[0], dtype=int), name='y')
            z = NXfield(self.counts, name='z')
            self.data = NXdata(z, (y, x))
            self.xc = self.counts.shape[1] / 2
            self.yc = self.counts.shape[0] / 2

    def import_mask(self):
        mask_file = getOpenFileName(self, 'Open Mask File')
        if Path(mask_file).exists():
            self.pixel_mask = load_image(mask_file).nxsignal.nxvalue

    @property
    def pv(self):
        try:
            return plotviews['Mask Editor']
        except Exception:
            return NXPlotView('Mask Editor')

    @property
    def title(self):
        return '/'.join([self.entry.nxroot.nxname+self.entry.nxpath,
                         'instrument/detector/pixel_mask'])

    def plot_data(self):
        self.create_mask()
        if self.counts.max() > 0.0:
            mask = np.zeros(self.counts.shape, dtype=float)
            idx = np.where(self.mask == 0)
            mask[idx] = 0.5 * self.counts[idx] / self.counts.max()
            mask += self.mask
            self.pv.plot(NXdata(mask, axes=self.data.nxaxes, title=self.title),
                         log=True)
        else:
            self.pv.plot(NXdata(self.mask, axes=self.data.nxaxes,
                                title=self.title))
        self.pv.aspect = 'equal'
        self.pv.ytab.flipped = detector_flipped(self.entry)
        self.pv.draw()

    def plot_limits(self):
        return self.pv.xaxis.get_limits() + self.pv.yaxis.get_limits()

    def add_shape(self):
        if self.shape is not None:
            self.save_shape()
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
        self.shape.connect()
        self.pv.draw()
        self.shapes.append(self.shape)
        if self.layout.count() == 4:
            self.shape_grid = self.shape_options(self.shape)
            self.insert_layout(3, self.shape_choice)
            self.insert_layout(4, self.shape_grid)
            self.insert_layout(5, self.action_buttons(
                ('Save Shape', self.save_shape),
                ('Remove Shape', self.remove_shape)))
        self.shape_choice.add(repr(self.shape))
        self.shape_choice.select(repr(self.shape))
        self.edit_shape()

    def edit_shape(self):
        current_shape = self.shape_choice.selected
        for shape in list(self.shapes):
            if current_shape == repr(shape):
                try:
                    self.delete_grid(self.shape_grid)
                except Exception:
                    pass
                self.shape = shape
                self.shape_choice.setVisible(True)
                self.pushbutton['Save Shape'].setVisible(True)
                self.pushbutton['Remove Shape'].setVisible(True)
                self.shape_grid = self.shape_options(self.shape)
                self.insert_layout(4, self.shape_grid)        

    def save_shape(self):
        self.pv.shapes.append(self.shapes)
        xmin, xmax, ymin, ymax = self.plot_limits()
        self.plot_data()
        self.pv.set_plot_limits(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
        self.pv.otab.zoom()

    def remove_shape(self):
        current_shape = self.shape_choice.selected
        for shape in list(self.shapes):
            if current_shape == repr(shape):
                self.shapes.remove(shape)
                self.shape_choice.remove(current_shape)
        self.save_shape()
        if len(self.shapes) == 0:
            self.shape_choice.setVisible(False)
            self.pushbutton['Save Shape'].setVisible(False)
            self.pushbutton['Remove Shape'].setVisible(False)
            try:
                self.delete_grid(self.shape_grid)
            except Exception:
                pass

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
        self.update_shape(self.shape)

    def update_shape(self, shape):
        if isinstance(shape, NXrectangle):
            x, y = shape.xy
            w, h = shape.width, shape.height
            self.parameters[shape]['x'].value = x
            self.parameters[shape]['y'].value = y
            self.parameters[shape]['w'].value = w
            self.parameters[shape]['h'].value = h
        else:
            x, y = shape.center
            r = abs(shape.width) / 2
            self.parameters[shape]['x'].value = x
            self.parameters[shape]['y'].value = y
            self.parameters[shape]['r'].value = r
        self.shape_choice.setItemText(
            self.shape_choice.findText(shape.label), repr(shape))               
        shape.label = repr(shape)

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
        self.label = repr(self)

    def update(self, x, y):
        super().update(x, y)
        self.parent.update_shape(self)


class MaskCircle(NXcircle):

    def __init__(self, x, y, r, **kwargs):
        self.parent = kwargs['parent']
        del kwargs['parent']
        super().__init__(x, y, r, **kwargs)
        self.label = repr(self)

    def update(self, x, y):
        super().update(x, y)
        self.parent.update_shape(self)
