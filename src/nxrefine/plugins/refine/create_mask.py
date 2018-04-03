from __future__ import absolute_import

import numpy as np
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.plotview import NXPlotView, plotviews, NXrectangle, NXcircle
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
        
        self.select_entry(self.choose_entry)
        self.shape_box = self.select_box(['Rectangle', 'Circle'])
        self.set_layout(self.entry_layout, 
                        self.make_layout(
                            self.action_buttons(('Add Shape', self.add_shape)),
                            self.shape_box),
                        self.close_buttons(save=True))
        self.set_title('Mask Data')

    def choose_entry(self):
        if 'calibration' not in self.entry['instrument']:
            raise NeXusError('Please load calibration data to this entry')
        self.data = self.entry['instrument/calibration']
        self.plot_data()
        shape = self.data.nxsignal.shape
        self.y, self.x = (shape[0]/2.0, shape[1]/2.0)

    def plot_data(self):
        if self.plotview is None:
            if 'Mask Editor' in plotviews:
                self.plotview = plotviews['Mask Editor']
            else:
                self.plotview = NXPlotView('Mask Editor')
        self.plotview.plot(self.data, log=True)
        self.plotview.aspect='equal'
        self.plotview.ytab.flipped = True
        self.plotview.deactivate()

    def add_shape(self):
        if self.shape_box.currentText() == 'Rectangle':
            self.shapes.append(NXrectangle(self.x-100, self.y-100, 200, 200,
                                           border_tol=0.1, plotview=self.plotview,
                                           facecolor='r', edgecolor='k',
                                           linewidth=1, alpha=0.3))
        else:
            self.shapes.append(NXcircle(self.x, self.y, 200, border_tol=0.1, 
                                        plotview=self.plotview,
                                        facecolor='r', edgecolor='k',
                                        linewidth=1, alpha=0.3))
        self.plotview.draw()
        self.shapes[-1].connect()    

    def accept(self):
        mask = self.entry['instrument/detector/pixel_mask'].nxvalue
        x, y = np.arange(mask.shape[1]), np.arange(mask.shape[0])
        for shape in self.shapes:
            if isinstance(shape, NXrectangle):
                rect = shape.rectangle
                x0, y0 = int(rect.get_x()), int(rect.get_y())
                x1, y1 = int(x0+rect.get_width()), int(y0+rect.get_height())               
                mask[y0:y1,x0:x1] = 1
            else:
                circle = shape.circle
                xc, yc = circle.center
                r = circle.radius
                inside = (x[None,:]-int(xc))**2+(y[:,None]-int(yc))**2 < r**2
                mask = mask | inside
        self.entry['instrument/detector/pixel_mask'] = mask        
        super(MaskDialog, self).accept()
        if 'Mask Editor' in plotviews:
            plotviews['Mask Editor'].close_view()

    def reject(self):
        super(MaskDialog, self).reject()
        if 'Mask Editor' in plotviews:
            plotviews['Mask Editor'].close_view()
