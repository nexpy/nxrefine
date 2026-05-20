# -----------------------------------------------------------------------------
# Copyright (c) 2022-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import numpy as np
from nexpy.gui.dialogs import NXDialog
from nexpy.gui.pyqt import QtWidgets
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import NXLabel, NXLineEdit
from nexusformat.nexus import NeXusError, NXdata, NXfield

from nxrefine.nxparent import NXParent
from nxrefine.nxreduce import NXMultiReduce


class TransformDialog(NXDialog):

    def __init__(self, scans_file, subentry=None):
        super().__init__()
        self.parent = NXParent(scans_file, subentry=subentry)
        self.reduce = NXMultiReduce(self.parent.root)
        self.refine = self.reduce.refine

        self.Qgrid = QtWidgets.QGridLayout()
        self.Qgrid.setSpacing(10)
        headers = ['Axis', 'Q', 'dQ', 'N', 'Max']
        width = [25, 50, 50, 25, 50]
        column = 0
        for header in headers:
            label = NXLabel(header, bold=True, align='center')
            self.Qgrid.addWidget(label, 0, column)
            self.Qgrid.setColumnMinimumWidth(column, width[column])
            column += 1
        self.Qbox = {}
        self.dQbox = {}
        self.Nbox = {}
        self.maxbox = {}
        for i, label in enumerate(['H', 'K', 'L']):
            self.Qgrid.addWidget(NXLabel(label, align='center'), i+1, 0)
            self.Qbox[label] = NXLineEdit(slot=self.calculate, width=100,
                                          align='right')
            self.Qgrid.addWidget(self.Qbox[label], i+1, 1)
            self.dQbox[label] = NXLineEdit(slot=self.calculate, width=100,
                                           align='right')
            self.Qgrid.addWidget(self.dQbox[label], i+1, 2)
            self.Nbox[label] = NXLabel(align='center')
            self.Qgrid.addWidget(self.Nbox[label], i+1, 3)
            self.maxbox[label] = NXLabel(align='center')
            self.Qgrid.addWidget(self.maxbox[label], i+1, 4)
        self.set_layout(self.Qgrid, self.close_buttons(save=True))
        self.setWindowTitle('Transforming Data')
        self.refine.initialize_grid()
        self.update_grid()

    def update_grid(self):
        if self.parent.transform:
            transform = self.parent.transform
            h_stop = transform['Qh'][-1]
            k_stop = transform['Qk'][-1]            
            l_stop = transform['Ql'][-1]
            h_step = transform['Qh'][1] - transform['Qh'][0]
            k_step = transform['Qk'][1] - transform['Qk'][0]
            l_step = transform['Ql'][1] - transform['Ql'][0]
            h_shape = len(transform['Qh'])
            k_shape = len(transform['Qk'])
            l_shape = len(transform['Ql'])
        else:
            h_stop = self.refine.h_stop
            k_stop = self.refine.k_stop
            l_stop = self.refine.l_stop
            h_step = self.refine.h_step
            k_step = self.refine.k_step
            l_step = self.refine.l_step
            h_shape = self.refine.h_shape
            k_shape = self.refine.k_shape
            l_shape = self.refine.l_shape
        self.Qbox['H'].setText(f"{h_stop:g}")
        self.Qbox['K'].setText(f"{k_stop:g}")
        self.Qbox['L'].setText(f"{l_stop:g}")
        self.dQbox['H'].setText(f"{h_step:g}")
        self.dQbox['K'].setText(f"{k_step:g}")
        self.dQbox['L'].setText(f"{l_step:g}")
        self.Nbox['H'].setText(f"{h_shape:g}")
        self.Nbox['K'].setText(f"{k_shape:g}")
        self.Nbox['L'].setText(f"{l_shape:g}")
        self.maxbox['H'].setText(f"{self.refine.Qmax / self.refine.astar:g}")
        self.maxbox['K'].setText(f"{self.refine.Qmax / self.refine.bstar:g}")
        self.maxbox['L'].setText(f"{self.refine.Qmax / self.refine.cstar:g}")

    def calculate(self):
        for label, rlu in [('H', self.refine.astar),
                           ('K', self.refine.bstar),
                           ('L', self.refine.cstar)]:
            self.Nbox[label].setText(
                int(np.round(2 * float(self.Qbox[label].text()) /
                             float(self.dQbox[label].text()), 2)) + 1)
            self.maxbox[label].setText(f"{self.refine.Qmax / rlu:g}")

    def get_parameters(self, Q):
        stop, step = float(self.Qbox[Q].text()), float(self.dQbox[Q].text())
        return -stop, step, stop

    def write_parameters(self):
        h_start, h_step, h_stop = self.get_parameters('H')
        k_start, k_step, k_stop = self.get_parameters('K')
        l_start, l_step, l_stop = self.get_parameters('L')
        h_shape = int(np.round((h_stop - h_start) / h_step, 2)) + 1
        k_shape = int(np.round((k_stop - k_start) / k_step, 2)) + 1
        l_shape = int(np.round((l_stop - l_start) / l_step, 2)) + 1
        H = NXfield(np.linspace(h_start, h_stop, h_shape), name='Qh',
                    scaling_factor=self.refine.astar, long_name='H (r.l.u.)')
        K = NXfield(np.linspace(k_start, k_stop, k_shape), name='Qk',
                    scaling_factor=self.refine.bstar, long_name='K (r.l.u.)')
        L = NXfield(np.linspace(l_start, l_stop, l_shape), name='Ql',
                    scaling_factor=self.refine.cstar, long_name='L (r.l.u.)')
        with self.parent.root:
            scan_info = self.parent.root[f'{self.parent.entry}/nxscans']
            if 'transform' in scan_info:
                del scan_info['transform']
            scan_info['transform'] = NXdata(axes=(L, K, H))
            scan_info['transform'].attrs['angles'] = (self.refine.gamma_star,
                                                      self.refine.beta_star,
                                                      self.refine.alpha_star)
        self.parent.reload()

    def accept(self):
        try:
            self.write_parameters()
            super().accept()
        except NeXusError as error:
            self.parent.reload()
            report_error("Preparing Data Transform", error)
            super().reject()
