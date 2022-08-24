import numpy as np
from nexusformat.nexus import nxopen, nxsetlock, NXdata
from skimage.feature import peak_local_max


def peak_search(data_file, data_path, i, j, k, threshold, min_pixels=10):
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

    Returns
    -------
    list of NXBlobs
        Peak locations and intensities stored in NXBlob instances
    """
    nxsetlock(600)

    with nxopen(data_file, "r") as data_root:
        data = data_root[data_path][j:k].nxvalue.clip(0)

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


class NXBlob(object):

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

    nxsetlock(600)
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
    with nxopen(mask_file, 'rw') as mask_root:
        mask_root[mask_path][j+1:k-1] = (
            np.maximum(vol_smoothed[0:-1], vol_smoothed[1:]))
    return i
