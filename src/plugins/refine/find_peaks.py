from PySide import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexpy.api.nexus import NeXusError, NXfield, NXdata
from nxpeaks import connectedpixels, labelimage
import nxpeaks.peakmerge as peakmerge


def show_dialog(parent=None):
    try:
        dialog = FindDialog(parent)
        dialog.show()
    except NeXusError as error:
        report_error("Finding Peaks", error)


class FindDialog(BaseDialog):

    def __init__(self, parent=None):
        super(FindDialog, self).__init__(parent)
        self.node = self.get_node()
        if self.node.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')
        self.root = self.node.nxroot
        self.node = self.root['entry/data/v']
        self.layout = QtGui.QVBoxLayout()
        threshold_layout = QtGui.QHBoxLayout()
        threshold_label = QtGui.QLabel('Threshold:')
        self.threshold_box = QtGui.QLineEdit('0.0')
        threshold_layout.addWidget(threshold_label)
        threshold_layout.addWidget(self.threshold_box)
        threshold_layout.addStretch()
        self.layout.addLayout(threshold_layout)
        limit_layout = QtGui.QHBoxLayout()
        limit_label = QtGui.QLabel('Z-Limits:')
        self.min_box = QtGui.QLineEdit('0')
        self.max_box = QtGui.QLineEdit(str(self.node.shape[0]))
        limit_layout.addWidget(limit_label)
        limit_layout.addWidget(self.min_box)
        limit_layout.addWidget(self.max_box)
        self.layout.addLayout(limit_layout)
        find_layout = QtGui.QHBoxLayout()
        self.find_button = QtGui.QPushButton('Find Peaks')
        self.find_button.clicked.connect(self.find_peaks)
        find_layout.addStretch()
        find_layout.addWidget(self.find_button)
        find_layout.addStretch()
        self.layout.addLayout(find_layout)
        self.setLayout(self.layout)
        self.setWindowTitle('Find Peaks')

        if 'maximum' in self.node.attrs:        
            self.threshold = np.float32(self.node.maximum) / 20
            self.threshold_box.setText(str(self.threshold))
        self.npk = 0

    def get_threshold(self):
        return np.float32(self.threshold_box.text())

    def get_limits(self):
        return np.int32(self.min_box.text()), np.int32(self.max_box.text())

    def find_peaks(self):

        self.layout.removeWidget(self.find_button)
        self.find_button.setVisible(False)
        if len(self.node.shape) == 2:
            self.layout.addWidget(self.buttonbox(save=True))
        elif len(self.node.shape) > 2:
            self.layout.addLayout(self.progress_layout(save=True))

        self.threshold = self.get_threshold()
        self.blim = np.zeros(self.node.shape[-2:], np.int32)
        self.verbose = 0
       
        lio = labelimage.labelimage(self.node.shape[-2:], flipper=labelimage.flip1)
        allpeaks = []
        if len(self.node.shape) == 2:
            res = None
        else:
            chunk_size = self.node.nxfile[self.node.nxpath].chunks[0]
            z_min, z_max = self.get_limits()
            self.progress_bar.setRange(z_min, z_max)
            for i in range(0, self.node.shape[0], chunk_size):
                try:
                    self.progress_bar.setValue(i)
                    self.update_progress()
                    if i + chunk_size > z_min and i < z_max:
                        v = self.node[i:i+chunk_size,:,:].nxdata
                        for j in range(chunk_size):
                            if i+j >= z_min and i+j <= z_max:
                                omega = np.float32(i+j)
                                lio.peaksearch(v[j], self.threshold, omega)
                                if lio.res is not None:
                                    connectedpixels.blob_moments(lio.res)
                                    lio.mergelast()
                                    for k in range(lio.res.shape[0]):
                                        peak = lio.res[k]
                                        allpeaks.append(NXpeak(peak[0], peak[22], 
                                            peak[23], peak[24], omega, 
                                            peak[27], peak[26], peak[29], 
                                            self.threshold))
                except IndexError as error:
                    pass
            self.progress_bar.setVisible(False)
        
        if not allpeaks:
            self.reject()
            report_error('Finding peaks', 'No peaks found')
        merger = peakmerge.peakmerger()
        merger.allpeaks = allpeaks
        merger.mergepeaks()
        self.peaks = merger.merged

    def accept(self):
        try:
            root = self.node.nxroot
            if 'peaks' in root.entry.sample.entries:
                del root.entry.sample['peaks']
            root.entry.sample.peaks = NXdata()
            shape = (len(self.peaks),)
            root.entry.sample.peaks.npixels = NXfield(
                [peak.np for peak in self.peaks], dtype=np.float32)
            root.entry.sample.peaks.intensity = NXfield(
                [peak.avg for peak in self.peaks], dtype=np.float32)
            root.entry.sample.peaks.x = NXfield(
                [peak.x for peak in self.peaks], dtype=np.float32)
            root.entry.sample.peaks.x = NXfield(
                [peak.x for peak in self.peaks], dtype=np.float32)
            root.entry.sample.peaks.y = NXfield(
                [peak.y for peak in self.peaks], dtype=np.float32)
            root.entry.sample.peaks.z = NXfield(
                [peak.omega for peak in self.peaks], dtype=np.float32)
            root.entry.sample.peaks.sigx = NXfield(
                [peak.sigx for peak in self.peaks], dtype=np.float32)
            root.entry.sample.peaks.sigy = NXfield(
                [peak.sigy for peak in self.peaks], dtype=np.float32)
            root.entry.sample.peaks.covxy = NXfield(
                [peak.covxy for peak in self.peaks], dtype=np.float32)
            super(FindDialog, self).accept()
        except NeXusError as error:
            report_error('Finding peaks', error)


class NXpeak(peakmerge.peak):

    def __init__(self, np, avg, x, y, z, sigx, sigy, covxy, threshold):
        self.TOLERANCE = 4.0
        self.omegatol = 0.25
        self.np = np
        self.avg = avg
        self.x = self.xc = x
        self.y = self.yc = y
        self.omega = z
        self.sigx = sigx
        self.sigy = sigy
        self.covxy = covxy
        self.threshold = threshold
        self.num = self.omega = z
        self.forgotten = False