# -----------------------------------------------------------------------------
# Copyright (c) 2015-2022, AXMAS Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context, resource_tracker

import numpy as np
from nexusformat.nexus import (NeXusError, NXdata, NXentry, NXfield, NXlog,
                               NXroot, nxopen, nxsetconfig)
from skimage.feature import peak_local_max


def peak_search(data_file, data_path, i, j, k, threshold, mask=None,
                min_pixels=10):
    """Identify peaks in the slab of raw data

    Parameters
    ----------
    data_file : str
        File path to the raw data file
    data_path : str
        Internal path to the raw data
    i : int
        Index of first z-value of output peaks
    j : int
        Index of first z-value of processed slab
    k : int
        Index of last z-value of processed slab
    threshold : float
        Peak threshold
    mask : array-like
        Pixel mask for detector
    min_pixels : int
        Minimum pixel separation of peaks, default=10

    Returns
    -------
    list of NXBlobs
        Peak locations and intensities stored in NXBlob instances
    """
    nxsetconfig(lock=3600, lockexpiry=28800)

    with nxopen(data_file, "r") as data_root:
        data = data_root[data_path][j:k].nxvalue.clip(0)

    if mask is not None:
        data = np.where(mask, 0, data)

    nframes = data.shape[0]
    saved_blobs = []
    last_blobs = []
    for z in range(nframes):
        blobs = [
            NXBlob(x, y, z, data[z, int(y), int(x)], min_pixels=min_pixels)
            for y, x in peak_local_max(
                data[z], min_distance=min_pixels, threshold_abs=threshold
            )
        ]
        for lb in last_blobs:
            found = False
            for b in blobs:
                if lb == b:
                    found = True
                    b.update(lb)
            if not found:
                lb.refine(data)
                if lb.is_valid():
                    saved_blobs.append(lb)
        last_blobs = blobs
    for blob in saved_blobs:
        blob.z += j
    return i, saved_blobs


class NXBlob:

    def __init__(self, x, y, z, max_value=0.0, intensity=0.0,
                 sigx=0.0, sigy=0.0, sigz=0.0, min_pixels=10):
        self.x = x
        self.y = y
        self.z = z
        self.max_value = max_value
        self.intensity = intensity
        self.sigx = sigx
        self.sigy = sigy
        self.sigz = sigz
        self.min_pixels = min_pixels

    def __repr__(self):
        return (
            f"NXBlob(x={self.x:.2f} y={self.y:.2f} z={self.z:.2f} "
            + f"intensity={self.intensity:.2f} "
            + f"dx={self.sigx:.2f} dy={self.sigy:.2f} dz={self.sigz:.2f})"
        )

    def __eq__(self, other):
        if (
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        ) < 100:
            return True
        else:
            return False

    @property
    def xyz(self):
        return (int(self.z), int(self.y), int(self.x))

    def update(self, other):
        if other.max_value > self.max_value:
            self.x = other.x
            self.y = other.y
            self.z = other.z
            self.max_value = other.max_value

    def refine(self, data):
        def peak_range():
            idx = []
            for i in range(3):
                idx.append(np.s_[max(0, self.xyz[i] - self.min_pixels):
                           min(self.xyz[i] + self.min_pixels, data.shape[i])])
            return tuple(idx)

        slab = NXdata(data)[peak_range()]
        slabx = slab.sum((0, 1))
        self.x, self.sigx = slabx.mean().nxvalue, slabx.std().nxvalue
        slaby = slab.sum((0, 2))
        self.y, self.sigy = slaby.mean().nxvalue, slaby.std().nxvalue
        slabz = slab.sum((1, 2))
        self.z, self.sigz = slabz.mean().nxvalue, slabz.std().nxvalue
        self.intensity = slab.sum()

    def is_valid(self):
        if self.sigx < 0.5 or self.sigy < 0.5:
            return False
        else:
            return True


def fill_gaps(mask, mask_gaps):
    """Fill in gaps in the detector.

    Many 2D detectors produce arrays with gaps, e.g., between detector
    chips. This function takes a 3D mask, comprising a set of 2D
    detector frames and fills in the gaps with the maximum values of the
    mask on either side of the gaps, defined by a 2D detector mask. This
    only fills in gaps that extend over the entire detector, i.e., if
    the detector mask contains other masked pixels, they are ignored.

    Parameters
    ----------
    mask : array-like
        3D mask before gap-filling.
    mask_gaps : array-like
        2D detector mask. This has to be the same shape as the last two
        dimensions of the 3D mask. Values of 1 represent masked pixels.

    Returns
    -------
    array-like
        3D mask with the gaps filled in.
    """

    def consecutive(arr):
        return np.split(arr, np.where(np.diff(arr) != 1)[0]+1)

    mask = mask.astype(float)
    for i in range(2):
        gaps = consecutive(np.where(mask_gaps.sum(i) == mask_gaps.shape[i])[0])
        for gap in gaps:
            if i == 0:
                mask[:, :, gap[0]:gap[-1]+1] = np.tile(np.expand_dims(
                    np.maximum(mask[:, :, gap[0]-1],
                               mask[:, :, gap[-1]+1]), 2),
                    (1, 1, len(gap)))
            else:
                mask[:, gap[0]:gap[-1]+1, :] = np.tile(np.expand_dims(
                    np.maximum(mask[:, gap[0]-1, :],
                               mask[:, gap[-1]+1, :]), 1),
                    (1, len(gap), 1))
    return mask


def local_sum(X, K):
    """Computes the local sum inside the box of size K."""
    G = X
    d = len(X.shape)
    for i in range(d):
        zeros_shape = list(G.shape)
        zeros_shape[i] = K.shape[i]
        G_1 = np.concatenate([G, np.zeros(zeros_shape)], axis=i)
        G_2 = np.concatenate([np.zeros(zeros_shape), G], axis=i)
        G = np.cumsum(G_1-G_2, axis=i)
    G = G[tuple(slice(None, -1, None) for _ in range(d))]
    return G


def local_sum_same(X, K, padding):
    """Computes the sum inside the box of size K.

    Parameters
    ----------
    X : array-like
        Padded array
    K : array-like
        Convolution kernel
    padding : tuple
        Length padded in each dimension

    Returns
    -------
    array-like
        Array of the original shape (i.e., X without padding)
    """
    d = len(X.shape)
    G = local_sum(X, K)
    shapeK = K.shape
    shapeG = G.shape
    left = [(shapeK[i] - 1)//2 for i in range(d)]
    initial = [left[i] + padding[i] for i in range(d)]
    right = [shapeK[i] - 1 - left[i] for i in range(d)]
    shift_from_end = [- right[i] - padding[i] for i in range(d)]
    final = [shapeG[i] + shift_from_end[i] for i in range(d)]
    G = G[tuple(slice(initial[i], final[i], None) for i in range(d))]
    return G


def mask_volume(data_file, data_path, mask_file, mask_path, i, j, k,
                pixel_mask, threshold_1=2, horiz_size_1=11,
                threshold_2=0.8, horiz_size_2=51):
    """Generate a 3D mask around Bragg peaks.

    Parameters
    ----------
    data_file : str
        File path to the raw data file
    data_path : str
        Internal path to the raw data
    mask_file : str
        File path to the mask file
    mask_path : str
        Internal path to the mask array
    i : int
        Index of first z-value of output mask
    j : int
        Index of first z-value of processed slab
    k : int
        Index of last z-value of processed slab
    pixel_mask : array-like
        2D detector mask. This has to be the same shape as the last two
        dimensions of the 3D slab. Values of 1 represent masked pixels.
    horiz_size_1 : int, optional
        Size of smaller convolution rectangles, by default 11
    threshold_1 : int, optional
        Threshold for performing the smaller convolution, by default 2
    horiz_size_2 : int, optional
        Size of larger convolution rectangles, by default 51
    threshold_2 : float, optional
        Threshold for performing the larger convolution, by default 0.8
    queue : Queue, optional
        Queue used in multiprocessing, by default None
    """

    nxsetconfig(lock=3600, lockexpiry=28800)
    with nxopen(data_file, 'r') as data_root:
        volume = data_root[data_path][j:k].nxvalue

    horiz_size_1, horiz_size_2 = int(horiz_size_1), int(horiz_size_2)
    sum1, sum2 = horiz_size_1**2, horiz_size_2**2
    horiz_kern_1 = np.ones((1, horiz_size_1, horiz_size_1))
    horiz_kern_2 = np.ones((1, horiz_size_2, horiz_size_2))

    diff_volume = volume[1:] - volume[:-1]

    padded_length = [0, horiz_size_1, horiz_size_1]
    vol_smoothed = local_sum_same(
        np.pad(
            diff_volume,
            pad_width=((0, 0),
                       (horiz_size_1, horiz_size_1),
                       (horiz_size_1, horiz_size_1)),
            mode='edge'),
        horiz_kern_1, padded_length)
    vol_smoothed /= sum1

    vol_smoothed[np.abs(vol_smoothed) < threshold_1] = 0

    vol_smoothed[vol_smoothed < 0] = 1
    vol_smoothed[vol_smoothed > 0] = 1

    vol_smoothed = fill_gaps(vol_smoothed, pixel_mask)

    padded_length = [0, horiz_size_2, horiz_size_2]
    vol_smoothed = local_sum_same(
        np.pad(
            vol_smoothed,
            pad_width=((0, 0),
                       (horiz_size_2, horiz_size_2),
                       (horiz_size_2, horiz_size_2)),
            mode='edge'),
        horiz_kern_2, padded_length)
    vol_smoothed /= sum2
    vol_smoothed[vol_smoothed < threshold_2] = 0
    vol_smoothed[vol_smoothed > threshold_2] = 1
    nxsetconfig(lock=3600, lockexpiry=28800)
    with nxopen(mask_file, 'rw') as mask_root:
        mask_root[mask_path][j+1:k-1] = (
            np.maximum(vol_smoothed[0:-1], vol_smoothed[1:]))
    return i


def init_julia():
    from julia.api import Julia
    from julia.core import JuliaError
    try:
        jl = Julia(compiled_modules=False)
    except JuliaError:
        import julia
        julia.install()
        jl = Julia(compile_modules=False)
    return jl


def load_julia(resources):
    import importlib.resources

    from julia import Main
    for resource in resources:
        Main.include(
            str(importlib.resources.files('nxrefine.julia') / resource))


def parse_orientation(orientation):
    """Return the detector orientation matrix based on the input.
    
    The detector orientation is used to convert from detector to
    laboratory coordinates. It may be defined by a string defining which
    laboratory axes are parallel to the detector axes. For example, if
    the detector y axis is parallel to the laboratory z axis, and the
    detector x and z axes are anti-parallel to the laboratory y and x
    axes, the string would be  "-y +z -x". If the orientation is passed
    to the function as a 3x3 array, it is returned unchanged as a
    NumPy matrix.

    Parameters
    ----------
    orientation : NXfield, str or array_like
        The description of the orientation as a string or a 3x3 array. 

    Returns
    -------
    np.matrix
        Matrix containing the detector orientation

    Raises
    ------
    NeXusError
        Invalid input value describing the orientation.
    """    
    try:
        if isinstance(orientation, NXfield):
            orientation = orientation.nxvalue
        if isinstance(orientation, str):
            _omat = np.zeros((3, 3), dtype=int)
            i = 0
            d = 1
            for c in orientation.replace(' ', ''):
                if c == '+':
                    d = 1
                elif c == '-':
                    d = -1
                else:
                    j = 'xyz'.index(c)
                    _omat[i][j] = d
                    d = 1
                    i += 1
            return np.matrix(_omat)
        else:
            return np.matrix(orientation)
    except Exception:
        raise NeXusError('Invalid detector orientation')


def detector_flipped(entry):
    """Return True if the y-axis is flipped.
    
    If images from the detector have their origin in the top-left
    corner, their y-axis needs to be flipped in order to view the
    physical geometry of the detector.
    
    Note
    ----
    The detector orientation has only recently been specified in the
    NXRefine module. Before this, all the images were assumed to be
    flipped.

    Parameters
    ----------
    entry : NXentry
        The NeXus entry group containing the detector information

    Returns
    -------
    bool
        True if the detector is flipped along the y-axis.
    """    
    if 'detector_orientation' in entry['instrument/detector']:
        omat = np.array(parse_orientation(
            entry['instrument/detector/detector_orientation']))
        if omat[1][2] == -1:
            return True
        else:
            return False
    else:
        return True


class SpecParser:
    """Parse a SPEC data file."""

    def __init__(self, spec_file):
        from spec2nexus.spec import SpecDataFile
        self.SPECfile = SpecDataFile(spec_file)

    def read(self, scan_list=None):
        """Convert scans from SPEC file into NXroot object and structure.

        Each scan in the range from self.scanmin to self.scanmax (inclusive)
        will be converted to a NXentry.  Scan data will go in a NXdata where
        the signal=1 is the last column and the corresponding axes= is the
        first column.

        Parameters
        ----------
        scan_list : int or list of ints
            Scan numbers to be imported

        Returns
        -------
        NXroot
            NXroot object containing entries for each SPEC scaan
        """
        import spec2nexus
        from spec2nexus import utils

        # check that scan_list is valid
        complete_scan_list = list(self.SPECfile.scans)
        if scan_list is None:
            scan_list = complete_scan_list
        else:
            if isinstance(scan_list, int):
                scan_list = [scan_list]
            for key in [str(s) for s in scan_list]:
                if key not in complete_scan_list:
                    msg = 'Scan ' + str(key) + ' was not found'
                    raise ValueError(msg)

        root = NXroot()

        root.attrs['spec2nexus'] = str(spec2nexus.__version__)
        header0 = self.SPECfile.headers[0]
        root.attrs['SPEC_file'] = self.SPECfile.fileName
        root.attrs['SPEC_epoch'] = header0.epoch
        root.attrs['SPEC_date'] = utils.iso8601(header0.date)
        root.attrs['SPEC_comments'] = '\n'.join(header0.comments)
        try:
            c = header0.comments[0]
            user = c[c.find('User = '):].split('=')[1].strip()
            root.attrs['SPEC_user'] = user
        except Exception:
            pass
        root.attrs['SPEC_num_headers'] = len(self.SPECfile.headers)

        for key in [str(s) for s in scan_list]:
            scan = self.SPECfile.getScan(key)
            scan.interpret()
            entry = NXentry()
            entry.title = str(scan)
            entry.date = utils.iso8601(scan.date)
            entry.command = scan.scanCmd
            entry.scan_number = NXfield(scan.scanNum)
            entry.comments = '\n'.join(scan.comments)
            entry.data = self.scan_NXdata(
                scan)            # store the scan data
            entry.positioners = self.metadata_NXlog(
                scan.positioner, 'SPEC positioners (#P & #O lines)')
            if hasattr(scan, 'metadata') and len(scan.metadata) > 0:
                entry.metadata = self.metadata_NXlog(
                    scan.metadata,
                    'SPEC metadata (UNICAT-style #H & #V lines)')

            if len(scan.G) > 0:
                entry.G = NXlog()
                desc = "SPEC geometry arrays, defined by SPEC diffractometer"
                # e.g.: SPECD/four.mac
                # http://certif.com/spec_manual/fourc_4_9.html
                entry.G.attrs['description'] = desc
                for item, value in scan.G.items():
                    entry.G[item] = NXfield(list(map(float, value.split())))
            if scan.T != '':
                entry['counting_basis'] = NXfield(
                    'SPEC scan with constant counting time')
                entry['T'] = NXfield(float(scan.T))
                entry['T'].units = 's'
                entry['T'].description = 'Scan with constant counting time'
            elif scan.M != '':
                entry['counting_basis'] = NXfield(
                    'SPEC scan with constant monitor count')
                entry['M'] = NXfield(float(scan.M))
                entry['M'].units = 'counts'
                entry['M'].description = 'Scan with constant monitor count'
            if scan.Q != '':
                entry['Q'] = NXfield(list(map(float, scan.Q)))
                entry['Q'].description = 'hkl at start of scan'

            root['scan_' + str(key)] = entry

        return root

    def scan_NXdata(self, scan):
        """Return the scan data in an NXdata object."""

        nxdata = NXdata()

        if len(scan.data) == 0:       # what if no data?
            # since no data available, provide trivial, fake data
            # keeping the NXdata base class compliant with the NeXus standard
            nxdata.attrs['description'] = 'SPEC scan has no data'
            nxdata['noSpecData_y'] = NXfield([0, 0])   # primary Y axis
            nxdata['noSpecData_x'] = NXfield([0, 0])   # primary X axis
            nxdata.nxsignal = nxdata['noSpecData_y']
            nxdata.nxaxes = [nxdata['noSpecData_x'], ]
            return nxdata

        nxdata.attrs['description'] = 'SPEC scan data'

        scan_type = scan.scanCmd.split()[0]
        if scan_type in ('mesh', 'hklmesh'):
            # hklmesh  H 1.9 2.1 100  K 1.9 2.1 100  -800000
            self.parser_mesh(nxdata, scan)
        elif scan_type in ('hscan', 'kscan', 'lscan', 'hklscan'):
            # hklscan  1.00133 1.00133  1.00133 1.00133  2.85 3.05  200 -400000
            h_0, h_N, k_0, k_N, l_0, l_N = scan.scanCmd.split()[1:7]
            if h_0 != h_N:
                axis = 'H'
            elif k_0 != k_N:
                axis = 'K'
            elif l_0 != l_N:
                axis = 'L'
            else:
                axis = 'H'
            self.parser_1D_columns(nxdata, scan)
            nxdata.nxaxes = nxdata[axis]
        else:
            self.parser_1D_columns(nxdata, scan)

        return nxdata

    def parser_1D_columns(self, nxdata, scan):
        """Generic data parser for 1-D column data."""
        from spec2nexus import utils
        for column in scan.L:
            if column in scan.data:
                nxdata[column] = NXfield(scan.data[column])

        signal = utils.sanitize_name(
            nxdata, scan.column_last)  # primary Y axis
        axis = utils.sanitize_name(
            nxdata, scan.column_first)  # primary X axis
        nxdata.nxsignal = nxdata[signal]
        nxdata.nxaxes = nxdata[axis]

        self.parser_mca_spectra(nxdata, scan, axis)

    def parser_mca_spectra(self, nxdata, scan, primary_axis_label):
        """Parse for optional MCA spectra."""
        if '_mca_' in scan.data:        # check for it
            for mca_key, mca_data in scan.data['_mca_'].items():
                key = "__" + mca_key
                nxdata[key] = NXfield(mca_data)
                nxdata[key].units = "counts"
                ch_key = key + "_channel"
                nxdata[ch_key] = NXfield(range(1, len(mca_data[0])+1))
                nxdata[ch_key].units = 'channel'
                axes = (primary_axis_label, ch_key)
                nxdata[key].axes = ':'.join(axes)

    def parser_mesh(self, nxdata, scan):
        """Data parser for 2-D mesh and hklmesh."""
        # 2-D parser: http://www.certif.com/spec_help/mesh.html
        # mesh motor1 start1 end1 intervals1 motor2 start2 end2 intervals2 time
        # 2-D parser: http://www.certif.com/spec_help/hklmesh.html
        #  hklmesh Q1 start1 end1 intervals1 Q2 start2 end2 intervals2 time
        # mesh:    nexpy/examples/33id_spec.dat  scan 22  (MCA gives 3-D data)
        # hklmesh: nexpy/examples/33bm_spec.dat  scan 17  (no MCA data)
        from spec2nexus import utils
        (label1, start1, end1, intervals1, label2, start2, end2,
         intervals2, time) = scan.scanCmd.split()[1:]
        if label1 not in scan.data:
            label1 = scan.L[0]      # mnemonic v. name
        if label2 not in scan.data:
            label2 = scan.L[1]      # mnemonic v. name
        axis1 = scan.data.get(label1)
        axis2 = scan.data.get(label2)
        intervals1, intervals2 = int(intervals1), int(intervals2)
        start1, end1 = float(start1), float(end1)
        start2, end2 = float(start2), float(end2)
        time = float(time)
        if len(axis1) < intervals1:  # stopped scan before second row started
            self.parser_1D_columns(nxdata, scan)        # fallback support
            # TODO: what about the MCA data in this case?
        else:
            axis1 = axis1[0:intervals1+1]
            axis2 = [axis2[row]
                     for row in range(len(axis2)) if row % (intervals1+1) == 0]

            column_labels = scan.L
            column_labels.remove(label1)    # special handling
            column_labels.remove(label2)    # special handling
            if scan.scanCmd.startswith('hkl'):
                # find the reciprocal space axis held constant
                label3 = [
                    key for key in ('H', 'K', 'L')
                    if key not in (label1, label2)][0]
                axis3 = scan.data.get(label3)[0]
                nxdata[label3] = NXfield(axis3)
                column_labels.remove(label3)    # already handled

            nxdata[label1] = NXfield(axis1)    # 1-D array
            nxdata[label2] = NXfield(axis2)    # 1-D array

            # build 2-D data objects
            data_shape = [len(axis2), len(axis1)]
            for label in column_labels:
                axis = np.array(scan.data.get(label))
                nxdata[label] = NXfield(utils.reshape_data(axis, data_shape))

            signal_axis_label = utils.sanitize_name(nxdata, scan.column_last)
            nxdata.nxsignal = nxdata[signal_axis_label]
            nxdata.nxaxes = [nxdata[label2], nxdata[label1]]

        if '_mca_' in scan.data:    # 3-D array
            # TODO: ?merge with parser_mca_spectra()?
            for mca_key, mca_data in scan.data['_mca_'].items():
                key = "__" + mca_key

                spectra_lengths = list(map(len, mca_data))
                num_channels = max(spectra_lengths)
                if num_channels != min(spectra_lengths):
                    msg = 'MCA spectra have different lengths'
                    msg += ' in scan #' + str(scan.scanNum)
                    msg += ' in file ' + str(scan.specFile)
                    raise ValueError(msg)

                data_shape += [num_channels, ]
                mca = np.array(mca_data)
                nxdata[key] = NXfield(utils.reshape_data(mca, data_shape))
                nxdata[key].units = "counts"

                try:
                    # use MCA channel numbers as known at time of scan
                    chan1 = scan.MCA['first_saved']
                    chanN = scan.MCA['last_saved']
                    channel_range = range(chan1, chanN+1)
                except Exception:
                    # basic indices
                    channel_range = range(1, num_channels+1)

                ch_key = key + "_channel"
                nxdata[ch_key] = NXfield(channel_range)
                nxdata[ch_key].units = 'channel'
                axes = (label1, label2, ch_key)
                nxdata[key].axes = ':'.join(axes)

    def metadata_NXlog(self, spec_metadata, description):
        """Return the specific metadata in an NXlog object."""
        from spec2nexus import utils
        nxlog = NXlog()
        nxlog.attrs['description'] = description
        for subkey, value in spec_metadata.items():
            nxlog[subkey] = NXfield(value)
        return nxlog


class NXExecutor(ProcessPoolExecutor):
    """ProcessPoolExecutor class using 'spawn' for new processes."""

    def __init__(self, max_workers=None, mp_context='spawn'):
        if mp_context:
            mp_context = get_context(mp_context)
        else:
            mp_context = None
        super().__init__(max_workers=max_workers, mp_context=mp_context)

    def __repr__(self):
        return f"NXExecutor(max_workers={self._max_workers})"

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)
        if self._mp_context.get_start_method(allow_none=False) != 'fork':
            resource_tracker._resource_tracker._stop()
        return False
