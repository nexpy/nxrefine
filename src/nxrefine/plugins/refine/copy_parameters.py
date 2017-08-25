import numpy as np
from scipy.optimize import minimize
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.plotview import plotview
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError
from nxrefine.nxrefine import NXRefine, find_nearest


def show_dialog():
    try:
        dialog = CopyDialog()
        dialog.show()
    except Exception as error:
        report_error("Copying Parameters", error)


class CopyDialog(BaseDialog):

    def __init__(self, parent=None):
        super(CopyDialog, self).__init__(parent)

        self.select_entry(text='Select Input Entry')
        self.select_entry(text='Select Output Entry', other=True)
        copy_buttons = self.action_buttons(('Copy Root', self.copy_root),
                                           ('Copy Entry', self.copy_entry))

        self.set_layout(self.entry_layout, self.other_entry_layout, 
                        copy_buttons, self.close_buttons())
        self.set_title('Copying Parameters')

    def copy_root(self):
        root = self.entry.nxroot
        other_root = self.other_entry.nxroot
        if root is other_root:
            raise NeXusError('Cannot copy to the same root')
        input = NXRefine(root['entry'])
        output_main = NXRefine(other_root['entry'])
        input.copy_parameters(output_main, sample=True)
        for name in [entry for entry in root if entry != 'entry']:
            if name in other_root: 
                input = NXRefine(root[name])
                output = NXRefine(other_root[name])
                input.copy_parameters(output, instrument=True)
                output_main.link_sample(output)

    def copy_entry(self):
        if self.entry is self.other_entry:
            raise NeXusError('Cannot copy to the same entry')
        input = NXRefine(self.entry)
        output = NXRefine(self.other_entry)
        if 'instrument' in self.entry:
            input.copy_parameters(output, instrument=True)
        if 'sample' not in self.other_entry and 'sample' in self.entry:
            if self.entry.nxname == 'entry' and self.other_entry.nxname == 'entry':
                input.copy_parameters(output, sample=True)
            elif self.entry.nxname == 'entry' and \
                 self.other_entry.nxname != 'entry' and \
                 self.entry.nxroot is self.other_entry.nxroot:
                input.link_sample(output)
            else:
                try:
                    self.other_entry.makelink(self.other_entry.nxroot['entry/sample'])
                except Exception:
                    pass
