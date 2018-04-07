from math import sqrt
import argparse, glob, os, socket, sys, timeit

import numpy as np

from nexusformat.nexus import *

from nxrefine import blobcorrector, __version__
from nxrefine.connectedpixels import blob_moments
from nxrefine.labelimage import labelimage, flip1


def find_peaks(group, threshold=None, z_min=None, z_max=None):

    field = group.nxsignal
    try:
        mask = field.nxentry['instrument/detector/pixel_mask'].nxdata
        if len(mask.shape) > 2:
            mask = mask[0]
    except Exception:
        mask = None

    if threshold is None:
        if 'maximum' in field.nxgroup.attrs:        
            threshold = np.float32(field.nxgroup.maximum) / 20
        elif 'maximum' in field.attrs:
            threshold = np.float32(field.maximum) / 20
        else:
            raise NeXusError(
                'Must give threshold if the field maximum is unknown')

    if z_min == None:
        z_min = 0
    if z_max == None:
        z_max = field.shape[0]
       
    lio = labelimage(field.shape[-2:], flipper=flip1)
    allpeaks = []
    if len(field.shape) == 2:
        res = None
    else:
        chunk_size = field.chunks[0]
        pixel_tolerance = 50
        frame_tolerance = 10
        for i in range(0, field.shape[0], chunk_size):
            try:
                if i + chunk_size > z_min and i < z_max:
                    print('Processing', i)
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
                                    if peak.isvalid(mask):
                                        allpeaks.append(peak)
            except IndexError as error:
                pass

    if not allpeaks:
        raise NeXusError('No peaks found')
    allpeaks = sorted(allpeaks)

    merged_peaks = []
    for z in range(z_min, z_max+1):
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
    peaks = merged_peaks

    print('%s peaks found' % len(peaks))

    if len(peaks) > 0:
        write_peaks(field, peaks)


def write_peaks(field, peaks):
    entry = field.nxentry
    if 'peaks' in entry.entries:
        del entry['peaks']
    entry.peaks = NXdata()
    shape = (len(peaks),)
    entry.peaks.npixels = NXfield([peak.np for peak in peaks], dtype=np.float32)
    entry.peaks.intensity = NXfield([peak.intensity for peak in peaks], 
                                    dtype=np.float32)
    entry.peaks.x = NXfield([peak.x for peak in peaks], dtype=np.float32)
    entry.peaks.y = NXfield([peak.y for peak in peaks], dtype=np.float32)
    entry.peaks.z = NXfield([peak.z for peak in peaks], dtype=np.float32)
    entry.peaks.sigx = NXfield([peak.sigx for peak in peaks], dtype=np.float32)
    entry.peaks.sigy = NXfield([peak.sigy for peak in peaks], dtype=np.float32)
    entry.peaks.covxy = NXfield([peak.covxy for peak in peaks], dtype=np.float32)


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


def main():

    parser = argparse.ArgumentParser(
        description="Find peaks within the NeXus data")
    parser.add_argument('-f', '--filename', required=True,
                        help='NeXus file name')
    parser.add_argument('-p', '--path', default='/entry/data',
                        help='path of the NXdata group within the NeXus file')
    parser.add_argument('-t', '--threshold', type=float,
                        help='peak threshold - defaults to maximum counts/20')
    parser.add_argument('-s', '--start', type=int, help='starting frame')
    parser.add_argument('-e', '--end', type=int, help='ending frame')

    args = parser.parse_args()

    tic=timeit.default_timer()
    root = nxload(args.filename, 'rw')
    entry = root[args.path].nxentry
    find_peaks(root[args.path], args.threshold, args.start, args.end)
    note = NXnote('nxfind '+' '.join(sys.argv[1:]), 
                  ('Current machine: %s\n'
                   'Current working directory: %s')
                    % (socket.gethostname(), os.getcwd()))
    entry['nxfind'] = NXprocess(program='nxfind', 
                                sequence_index=len(entry.NXprocess)+1, 
                                version=__version__, 
                                note=note)

    toc=timeit.default_timer()
    print(toc-tic, 'seconds for', args.filename)


if __name__=="__main__":
    main()
