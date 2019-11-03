from __future__ import absolute_import

import numpy as np
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.plotview import NXPlotView, plotviews
from nexpy.gui.widgets import NXrectangle, NXcircle
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError


def show_dialog():
    try:
        dialog = MaskDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Creating Mask", error)
        

class MaskDialog(BaseDialog):

    def __init__(self, parent=None):
        super(MaskDialog, self).__init__(parent)
        
        self.plotview = None
        self.shapes = []
        self.parameters = {}
        self.select_entry(self.choose_entry)
        self.shape_box = self.select_box(['Rectangle', 'Circle'])
        self.shape_choice = self.select_box([], slot=self.choose_shape)
        self.set_layout(self.entry_layout, 
                        self.make_layout(
                            self.action_buttons(('Add Shape', self.add_shape)),
                            self.shape_box),
                        self.shape_choice,
                        self.close_buttons(save=True))
        self.shape_choice.setVisible(False)
        self.set_title('Mask Data')

    def choose_entry(self):
        if 'calibration' not in self.entry['instrument']:
            raise NeXusError('Please load calibration data to this entry')
        self.data = self.entry['instrument/calibration']
        self.counts = self.data.nxsignal.nxvalue
        self.mask = self.entry['instrument/detector/pixel_mask'].nxvalue
        self.xc = self.entry['instrument/detector/beam_center_x'].nxvalue
        self.yc = self.entry['instrument/detector/beam_center_y'].nxvalue
        self.plot_data()
        shape = self.data.nxsignal.shape

    def plot_data(self):
        if self.plotview is None:
            if 'Mask Editor' in plotviews:
                self.plotview = plotviews['Mask Editor']
            else:
                self.plotview = NXPlotView('Mask Editor')
        self.plotview.plot(self.data, log=True)
        self.plotview.aspect='equal'
        self.plotview.ytab.flipped = True
        self.plotview.draw()

    def add_shape(self):
        if self.shape_box.currentText() == 'Rectangle':
            self.shapes.append(NXrectangle(self.xc-50, self.yc-50, 100, 100,
                                           border_tol=0.1, 
                                           plotview=self.plotview,
                                           resize=True, facecolor='r', 
                                           edgecolor='k',
                                           linewidth=1, alpha=0.3))
        else:
            self.shapes.append(NXcircle(self.xc, self.yc, 50, border_tol=0.1, 
                                        plotview=self.plotview, resize=True,
                                        facecolor='r', edgecolor='k',
                                        linewidth=1, alpha=0.3))
        self.plotview.draw()
        self.shapes[-1].connect()
        self.shape_choice.addItem(repr(self.shapes[-1]))
        self.shape_choice.setVisible(True)
        self.insert_layout(self.shape_options(self.shapes[-1]))

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

    def choose_shape(self):
        pass

    def accept(self):
        x, y = np.arange(self.mask.shape[1]), np.arange(self.mask.shape[0])
        for shape in self.shapes:
            if isinstance(shape, NXrectangle):
                x0, y0 = shape.xy
                x1, y1 = x0+shape.width, y0+shape.height               
                self.mask[int(y0):int(y1),int(x0):int(x1)] = 1
            else:
                xc, yc = shape.center
                r = shape.radius
                inside = (x[None,:]-int(xc))**2+(y[:,None]-int(yc))**2 < r**2
                self.mask = self.mask | inside
        self.mask[np.where(self.counts<0)] = 1
        try:
            self.entry['instrument/detector/pixel_mask'] = self.mask
        except NeXusError as error:
            report_error("Creating Mask", error)
            return
        super(MaskDialog, self).accept()
        if 'Mask Editor' in plotviews:
            plotviews['Mask Editor'].close_view()

    def reject(self):
        super(MaskDialog, self).reject()
        if 'Mask Editor' in plotviews:
            plotviews['Mask Editor'].close_view()
