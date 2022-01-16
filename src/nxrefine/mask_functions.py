import numpy as np
from nexusformat.nexus import NXdata


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

    filled = mask.astype(float)
    for i in range(2):
        gaps = consecutive(np.where(mask_gaps.sum(i) == mask_gaps.shape[i])[0])
        for gap in gaps:
            if i == 0:
                filled[:, :, gap[0]:gap[-1]+1] = np.tile(np.maximum(
                    filled[:, :, gap[0]-1], filled[:, :, gap[-1]+1]),
                    (len(gap), 1)).T
            else:
                filled[:, gap[0]:gap[-1]+1, :] = np.tile(np.maximum(
                    filled[:, gap[0]-1, :], filled[:, gap[-1]+1, :]),
                    (len(gap), 1))
    return filled


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


def mask_volume(volume, pixel_mask, horiz_size_1=11, threshold_1=2,
                horiz_size_2=51, threshold_2=0.8):
    """Generate a 3D mask around Bragg peaks.

    Parameters
    ----------
    volume : array-like
        3D array containing a slab of the raw data.
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

    Returns
    -------
    array-like
        3D array containing the mask for the slab.
    """

    diff_volume = volume[1:, :, :] - volume[0:-1, :, :]

    horiz_kern_1 = np.ones((1, horiz_size_1, horiz_size_1))
    sum1 = horiz_kern_1.sum()
    horiz_kern_2 = np.ones((1, horiz_size_2, horiz_size_2))
    sum2 = horiz_kern_2.sum()

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
    mask = np.maximum(vol_smoothed[0:-1], vol_smoothed[1:])
    return mask
