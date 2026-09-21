# -----------------------------------------------------------------------------
# Copyright (c) 2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from nexpy.gui.dialogs import NXDialog
from nexpy.gui.widgets import NXLabel, NXLineEdit, NXPlainTextEdit


class SubentryDialog(NXDialog):
    """Modal prompt for a new subentry's name and a short description."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_title('New Subentry')

        self.name = ''
        self.description = ''

        self.name_edit = NXLineEdit(width=240)
        self.description_edit = NXPlainTextEdit(wrap=True)
        self.description_edit.setMinimumHeight(90)
        self.description_edit.setMinimumWidth(360)

        name_row = self.make_layout(NXLabel('Name:'), self.name_edit,
                                    'stretch')
        description_row = self.make_layout(
            NXLabel('Description:'), self.description_edit,
            vertical=True, align='left')

        self.set_layout(name_row,
                        description_row,
                        self.close_buttons())

    def accept(self):
        self.name = self.name_edit.text().strip()
        self.description = self.description_edit.toPlainText().strip()
        super().accept()

    @classmethod
    def get_subentry(cls, parent=None):
        """Run the dialog modally; return (name, description) or None."""
        dialog = cls(parent)
        if dialog.exec_() and dialog.name:
            return dialog.name, dialog.description
        return None
