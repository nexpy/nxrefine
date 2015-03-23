from PySide import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexusformat.nexus import NeXusError, NXfield, NXdata
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
        self.entry = self.node.nxentry
        self.node = self.entry['data/v']
        try:
            self.mask = self.entry['instrument/detector/pixel_mask']
        except NeXusError:
            self.mask = None
        self.layout = QtGui.QVBoxLayout()
        self.threshold_box = QtGui.QLineEdit(str(self.entry['data'].attrs['maximum']/20.0))
        self.min_box = QtGui.QLineEdit('0')
        self.max_box = QtGui.QLineEdit(str(self.node.shape[0]))
        self.pixel_tolerance_box = QtGui.QLineEdit('10')
        self.frame_tolerance_box = QtGui.QLineEdit('10')
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(QtGui.QLabel('Threshold:'), 0, 0)
        grid.addWidget(QtGui.QLabel('First Frame:'), 1, 0)
        grid.addWidget(QtGui.QLabel('Last Frame:'), 2, 0)
        grid.addWidget(QtGui.QLabel('Pixel Tolerance:'), 3, 0)
        grid.addWidget(QtGui.QLabel('Frame Tolerance:'), 4, 0)
        grid.addWidget(self.threshold_box, 0, 1)
        grid.addWidget(self.min_box, 1, 1)
        grid.addWidget(self.max_box, 2, 1)
        grid.addWidget(self.pixel_tolerance_box, 3, 1)
        grid.addWidget(self.frame_tolerance_box, 4, 1)
        self.layout.addLayout(grid)
        find_layout = QtGui.QHBoxLayout()
        self.find_button = QtGui.QPushButton('Find Peaks')
        self.find_button.clicked.connect(self.find_peaks)
        self.peak_count = QtGui.QLabel()
        self.peak_count.setVisible(False)
        find_layout.addStretch()
        find_layout.addWidget(self.find_button)
        find_layout.addWidget(self.peak_count)
        find_layout.addStretch()
        self.layout.addLayout(find_layout)
        self.setLayout(self.layout)

        self.setWindowTitle('Find Peaks')

        if 'maximum' in self.node.attrs:        
            self.threshold_box.setText(str(np.float32(self.node.maximum) / 20))
        self.npk = 0

    def get_threshold(self):
        return np.float32(self.threshold_box.text())

    def get_limits(self):
        return np.int32(self.min_box.text()), np.int32(self.max_box.text())

    def get_tolerance(self):
        """
        Return pixel and frame tolerances from the text boxes.
        
        Note that the pixel tolerance is squared to save square-root 
        calculations in peak comparisons.
        """
        return (np.float32(self.pixel_tolerance_box.text())**2, 
                np.float32(self.frame_tolerance_box.text()))

    def find_peaks(self):

        self.layout.removeWidget(self.find_button)
        self.find_button.setVisible(False)
        if len(self.node.shape) == 2:
            self.layout.addWidget(self.buttonbox(save=True))
        elif len(self.node.shape) > 2:
            self.layout.addLayout(self.progress_layout(save=True))

        threshold = self.get_threshold()
        self.blim = np.zeros(self.node.shape[-2:], np.int32)
        self.verbose = 0
       
        lio = labelimage.labelimage(self.node.shape[-2:], flipper=labelimage.flip1)
        allpeaks = []
        if len(self.node.shape) == 2:
            res = None
        else:
            chunk_size = self.node.nxfile[self.node.nxpath].chunks[0]
            z_min, z_max = self.get_limits()
            pixel_tolerance, frame_tolerance = self.get_tolerance()
            self.progress_bar.setRange(z_min, z_max)
            for i in range(0, self.node.shape[0], chunk_size):
                try:
                    if i + chunk_size > z_min and i < z_max:
                        self.progress_bar.setValue(i)
                        self.update_progress()
                        v = self.node[i:i+chunk_size,:,:].nxdata
                        for j in range(chunk_size):
                            if i+j >= z_min and i+j <= z_max:
                                omega = np.float32(i+j)
                                lio.peaksearch(v[j], threshold, omega)
                                if lio.res is not None:
                                    connectedpixels.blob_moments(lio.res)
                                    for k in range(lio.res.shape[0]):
                                        res = lio.res[k]
                                        peak = NXpeak(res[0], res[22],
                                            res[23], res[24], omega,
                                            res[27], res[26], res[29],
                                            threshold,
                                            pixel_tolerance,
                                            frame_tolerance)
                                        if peak.isvalid(self.mask):
                                            allpeaks.append(peak)
                except IndexError as error:
                    pass

        if not allpeaks:
            self.reject()
            report_error('Finding peaks', 'No peaks found')
        allpeaks = sorted(allpeaks)

        self.progress_bar.reset()
        self.progress_bar.setRange(z_min, z_max)

        merged_peaks = []
        for z in range(z_min, z_max+1):
            self.progress_bar.setValue(z)
            self.update_progress()
            frame = [peak for peak in allpeaks if peak.z == z]
            if not merged_peaks:
                merged_peaks.extend(frame)
            else:
                for peak1 in frame:
                    combined = False
                    for peak2 in last_frame:
                        idx = merged_peaks.index(peak2)
                        if peak1 == peak2:
                            peak1.combine(peak2)
                            merged_peaks[idx] = peak1
                            combined = True
                            break
                    if not combined:
                        for peak2 in reversed(merged_peaks):
                            idx = merged_peaks.index(peak2)
                            if peak1 == peak2:
                                peak1.combine(peak2)
                                merged_peaks[idx] = peak1
                                combined = True
                                break
                        if not combined:
                            merged_peaks.append(peak1)

            if frame:
                last_frame = frame

        merged_peaks = sorted(merged_peaks)
        for peak in merged_peaks:
            peak.merge()

        merged_peaks = sorted(merged_peaks)
        self.peaks = merged_peaks

        self.progress_bar.setVisible(False)

        self.peak_count.setText('%s peaks found' % len(self.peaks))
        self.peak_count.setVisible(True)

    def accept(self):
        try:
            entry = self.node.nxentry
            if 'peaks' in entry.entries:
                del entry['peaks']
            entry.peaks = NXdata()
            shape = (len(self.peaks),)
            entry.peaks.npixels = NXfield(
                [peak.np for peak in self.peaks], dtype=np.float32)
            entry.peaks.intensity = NXfield(
                [peak.intensity for peak in self.peaks], dtype=np.float32)
            entry.peaks.x = NXfield(
                [peak.x for peak in self.peaks], dtype=np.float32)
            entry.peaks.y = NXfield(
                [peak.y for peak in self.peaks], dtype=np.float32)
            entry.peaks.z = NXfield(
                [peak.z for peak in self.peaks], dtype=np.float32)
            entry.peaks.sigx = NXfield(
                [peak.sigx for peak in self.peaks], dtype=np.float32)
            entry.peaks.sigy = NXfield(
                [peak.sigy for peak in self.peaks], dtype=np.float32)
            entry.peaks.covxy = NXfield(
                [peak.covxy for peak in self.peaks], dtype=np.float32)
            super(FindDialog, self).accept()
        except NeXusError as error:
            report_error('Finding peaks', error)


class NXpeak(object):

    def __init__(self, np, average, x, y, z, sigx, sigy, covxy, threshold,
                 pixel_tolerance, frame_tolerance):
        self.np = np
        self.average = average
        self.intensity = np * average
        self.x = x
        self.y = y
        self.z = z
        self.sigx = sigx
        self.sigy = sigy
        self.covxy = covxy
        self.threshold = threshold
        self.peaks = [self]
        self.pixel_tolerance = pixel_tolerance
        self.frame_tolerance = frame_tolerance
        self.combined = False

    def __str__(self):
        return "Peak x=%f y=%f z=%f np=%i avg=%f" % (self.x, self.y, self.z, self.np, self.average)

    def __repr__(self):
        return "Peak x=%f y=%f z=%f np=%i avg=%f" % (self.x, self.y, self.z, self.np, self.average)

    def __cmp__(self, other):
        if np.isclose(self.z, other.z):
            return 0
        elif self.z < other.z:
            return -1
        elif self.z > other.z:
            return 1

    def __eq__(self, other):
        if abs(self.z - other.z) <= self.frame_tolerance:
            if (self.x - other.x)**2 + (self.y - other.y)**2 <= self.pixel_tolerance:
                return True
            else:
                return False
        else:
            return False

    def __ne__(self, other):
        if abs(self.z - other.z) > self.frame_tolerance:
            if (self.x - other.x)**2 + (self.y - other.y)**2 > self.pixel_tolerance:
                return True
            else:
                return False
        else:
            return False

    def combine(self, other):
        self.peaks.extend(other.peaks)
        self.combined = True
        other.combined = False

    def merge(self):
        np = sum([p.np for p in self.peaks])
        intensity = sum([p.intensity for p in self.peaks])
        self.x = sum([p.x * p.intensity for p in self.peaks]) / intensity
        self.y = sum([p.y * p.intensity for p in self.peaks]) /intensity
        self.z = sum([p.z * p.intensity for p in self.peaks]) / intensity
        self.sigx = sum([p.sigx * p.intensity for p in self.peaks]) / intensity
        self.sigy = sum([p.sigy * p.intensity for p in self.peaks]) / intensity
        self.covxy = sum([p.covxy * p.intensity for p in self.peaks]) / intensity
        self.np = np
        self.intensity = intensity
        self.average = self.intensity / self.np

    def isvalid(self, mask):
        if mask is not None:
            clip = mask[int(self.y),int(self.x)]
            if clip.nxdata:
                return False
        if np.isclose(self.average, 0.0) or np.isnan(self.average) or self.np < 5:
            return False
        else:
            return True
