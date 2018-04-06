import numpy as np
from pyFAI.calibrant import Calibrant, ALL_CALIBRANTS

from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.plotview import NXPlotView, plotviews
from nexpy.gui.utils import report_error, confirm_action, load_image
from nexusformat.nexus import *
from nxrefine.nxrefine import NXRefine


def show_dialog():
    try:
        dialog = LoadDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Loading Calibration", error)


class LoadDialog(BaseDialog):

    def __init__(self, parent=None):
        super(LoadDialog, self).__init__(parent)

        self.plotview = None
        self.data = None

        self.set_layout(self.filebox('Choose Powder Calibration File'),
                        self.action_buttons(('Load File', self.load_file)),
                        self.select_entry(),
                        self.close_buttons(save=True))
        self.set_title('Loading Calibration')

    def load_file(self):
        self.data = load_image(self.get_filename())
        if self.plotview is None:
            if 'Powder Calibration' in plotviews:
                self.plotview = plotviews['Powder Calibration']
            else:
                self.plotview = NXPlotView('Powder Calibration')
        self.plotview.plot(self.data, log=True)
        self.plotview.aspect='equal'
        self.plotview.ytab.flipped = True         
        
    def accept(self):
        if self.data is None:
            self.reject()
        else:
            if 'calibration' in self.entry['instrument']:
                if confirm_action(
                        "Do you want to overwrite existing calibration data?"):
                    del self.entry['instrument/calibration']
                else:
                    self.reject()
                    return
            self.entry['instrument/calibration'] = self.data
            super(LoadDialog, self).accept()
        if 'Powder Calibration' in plotviews and self.plotview == plotviews['Powder Calibration']:
            self.plotview.close_view()

    def reject(self):
        super(LoadDialog, self).reject()
        if 'Powder Calibration' in plotviews and self.plotview == plotviews['Powder Calibration']:
            self.plotview.close_view()
