from nexpy.gui.pyqt import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.mainwindow import report_error
from nexusformat.nexus import *

from nxpeaks import blobcorrector, __version__
from nxpeaks.connectedpixels import blob_moments
from nxpeaks.labelimage import labelimage, flip1

def show_dialog():
#    try:
    dialog = FindDialog()
    dialog.show()
#    except NeXusError as error:
#        report_error("Finding Peaks", error)


class FindDialog(BaseDialog):

    def __init__(self, parent=None):
        super(FindDialog, self).__init__(parent)

        self.select_entry(self.choose_entry)

        try:
            threshold = np.float32(self.entry.data.attrs['maximum']) / 20
            max_frame = np.int32(len(self.entry.data.nxaxes[0]))
        except Exception:
            threshold = 5000
            max_frame = 0

        self.parameters = GridParameters()
        self.parameters.add('threshold', threshold, 'Threshold')
        self.parameters.add('min', 0, 'First Frame')
        self.parameters.add('max', max_frame, 'Last Frame')
        self.parameters.add('pixel_tolerance', 50, 'Pixel Tolerance')
        self.parameters.add('frame_tolerance', 10, 'Frame Tolerance')
        find_layout = QtGui.QHBoxLayout()
        self.find_button = QtGui.QPushButton('Find Peaks')
        self.find_button.clicked.connect(self.find_peaks)
        self.peak_count = QtGui.QLabel()
        self.peak_count.setVisible(False)
        find_layout.addStretch()
        find_layout.addWidget(self.find_button)
        find_layout.addWidget(self.peak_count)
        find_layout.addStretch()
        self.set_layout(self.entry_layout, self.parameters.grid(), 
                        find_layout)
        self.set_title('Find Peaks')

        self.npk = 0
        try:
            self.parameters['max'].value = self.entry['data'].nxsignal.shape[0]
            self.parameters['threshold'].value = (
                self.entry['data'].attrs['maximum'] / 20)
        except Exception:
            pass

    def choose_entry(self):
        try:
            self.parameters['threshold'].value = self.entry['data'].attrs['maximum'] / 20
            self.parameters['max'].value = len(self.entry.data.nxaxes[0])
        except Exception:
            pass

    def get_threshold(self):
        return self.parameters['threshold'].value

    def get_limits(self):
        return np.int32(self.parameters['min'].value), np.int32(self.parameters['max'].value)

    def get_tolerance(self):
        """
        Return pixel and frame tolerances from the text boxes.
        
        Note that the pixel tolerance is squared to save square-root 
        calculations in peak comparisons.
        """
        return (self.parameters['pixel_tolerance'].value,
                self.parameters['frame_tolerance'].value)

    def find_peaks(self):

        field = self.entry['data'].nxsignal
        try:
            self.mask = self.entry['instrument/detector/pixel_mask']
        except NeXusError:
            self.mask = None

        self.layout.removeWidget(self.find_button)
        self.find_button.setVisible(False)
        if len(field.shape) == 2:
            self.layout.addWidget(self.close_buttons(save=True))
        elif len(field.shape) > 2:
            self.layout.addLayout(self.progress_layout(save=True))

        threshold = self.get_threshold()
        self.blim = np.zeros(field.shape[-2:], np.int32)
        self.verbose = 0
   
        lio = labelimage(field.shape[-2:], flipper=flip1)
        allpeaks = []
        if len(field.shape) == 2:
            res = None
        else:
            chunk_size = field.nxfile[field.nxpath].chunks[0]
            z_min, z_max = self.get_limits()
            pixel_tolerance, frame_tolerance = self.get_tolerance()
            self.progress_bar.setRange(z_min, z_max)
            for i in range(0, field.shape[0], chunk_size):
                try:
                    if i + chunk_size > z_min and i < z_max:
                        self.progress_bar.setValue(i)
                        self.update_progress()
                        v = field[i:i+chunk_size,:,:].nxdata
                        for j in range(chunk_size):
                            if i+j >= z_min and i+j <= z_max:
                                omega = np.float32(i+j)
                                lio.peaksearch(v[j], threshold, omega)
                                if lio.res is not None:
                                    blob_moments(lio.res)
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
                        if peak1 == peak2:
                            for idx in range(len(merged_peaks)):
                                if peak1 == merged_peaks[idx]:
                                    break
                            peak1.combine(merged_peaks[idx])
                            merged_peaks[idx] = peak1
                            combined = True
                            break
                    if not combined:
                        reversed_peaks = [p for p in reversed(merged_peaks)
                                          if p.z >= peak1.z - frame_tolerance]
                        for peak2 in reversed_peaks:
                            if peak1 == peak2:
                                for idx in range(len(merged_peaks)):
                                    if peak1 == merged_peaks[idx]:
                                        break
                                peak1.combine(merged_peaks[idx])
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
            if 'peaks' in self.entry.entries:
                del self.entry['peaks']
            self.entry.peaks = NXdata()
            shape = (len(self.peaks),)
            self.entry.peaks.npixels = NXfield(
                [peak.np for peak in self.peaks], dtype=np.float32)
            self.entry.peaks.intensity = NXfield(
                [peak.intensity for peak in self.peaks], dtype=np.float32)
            self.entry.peaks.x = NXfield(
                [peak.x for peak in self.peaks], dtype=np.float32)
            self.entry.peaks.y = NXfield(
                [peak.y for peak in self.peaks], dtype=np.float32)
            self.entry.peaks.z = NXfield(
                [peak.z for peak in self.peaks], dtype=np.float32)
            self.entry.peaks.sigx = NXfield(
                [peak.sigx for peak in self.peaks], dtype=np.float32)
            self.entry.peaks.sigy = NXfield(
                [peak.sigy for peak in self.peaks], dtype=np.float32)
            self.entry.peaks.covxy = NXfield(
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
        self.pixel_tolerance = pixel_tolerance**2
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
            if clip:
                return False
        if np.isclose(self.average, 0.0) or np.isnan(self.average) or self.np < 5:
            return False
        else:
            return True
