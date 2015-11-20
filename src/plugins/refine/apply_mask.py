import numpy as np
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.mainwindow import report_error
from nexusformat.nexus import NeXusError


def show_dialog():
    dialog = MaskDialog()
    dialog.show()
#    except NeXusError as error:
#        report_error("Applying Mask", error)
        

class MaskDialog(BaseDialog):

    def __init__(self, parent=None):
        super(MaskDialog, self).__init__(parent)
        self.select_entry(self.choose_entry)
        self.parameters = GridParameters()
        self.parameters.add('mask', 'pilatus_mask/entry/mask', 'Mask Path')
        self.action_buttons(('Save Mask', self.save_mask))
        self.set_layout(self.entry_layout, self.parameters.grid(), 
                        self.action_buttons(('Save Mask', self.save_mask)), 
                        self.close_buttons())
        self.set_title('Mask Data')

    def save_mask(self):
        mask = self.treeview.tree[self.parameters['mask'].value]
        if mask.dtype != np.bool:
            raise NeXusError('Mask must be a Boolean array')
        elif len(mask.shape) == 1:
            raise NeXusError('Mask must be at least two-dimensional')
        elif len(mask.shape) > 2:
            mask = mask[0]                
        self.entry['instrument/detector/pixel_mask'] = mask
        self.entry['instrument/detector/pixel_mask_applied'] = False
#        except NeXusError as error:
#            report_error('Applying Mask', error)
