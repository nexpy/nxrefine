from nexusformat.nexus import *
import numpy as np
import math
import h5py
import copy
import os
from tqdm import trange
import gc
import ipdb
# import cProfile
# from pycallgraph import PyCallGraph
# from pycallgraph.output import GraphvizOutput


def chunkify(arr, chunkshape, mask=None):
    """ Divide NXfield arr into chunks of size chunkshape, truncating if necessary

        arr: NXfield to shrink
        chunkshape: 3-element tuple of ints
        mask: np.ndarray of boolean values, with True denoting pixels in
            arr to ignore
    """
    # Where to truncate arr
    bounds = (np.array(arr.shape) // chunkshape) * chunkshape
    bounds[0] = 100
    dx,dy,dz = chunkshape
    pix_per_slab = 8 # Height of slabs
    ds = pix_per_slab*dx
    numslabs = math.ceil(bounds[0] / ds)
    result = np.ma.masked_array(np.zeros(bounds // chunkshape, dtype=arr.dtype))
    if mask is not None:
        mask = mask[:bounds[1], :bounds[2]].astype(bool)
    for s in trange(numslabs):
        gc.collect() # we need to clean up leftover slabs
        try:
            slab = arr[s*ds : (s+1)*ds, :bounds[1], :bounds[2]].nxdata
        except:
            # Slab upper bound went beyond arr.shape[0]
            slab = arr[s*ds:bounds[0], :bounds[1], :bounds[2]].nxdata
        for x in range(ds//dx):
            real_x = x + s*pix_per_slab
            if real_x >= result.shape[0]:
                # We reached the end of the array
                break
            for y in range(result.shape[1]):
                for z in range(result.shape[2]):
                    chunk = slab[x*dx:(x+1)*dx, y*dy:(y+1)*dy, z*dz:(z+1)*dz]
                    m = mask[y*dy:(y+1)*dy, z*dz:(z+1)*dz]
                    try:
                        # ie if m[1,2] is True, ignore chunk[:,1,2]
                        result[real_x, y, z] = np.max(chunk[:,~m])
                    except ValueError:
                        # Chunk is entirely masked out
                        result[real_x, y, z] = np.ma.masked
    return result

def shrink_mask(oldmask, spacing):
    """ Shrink oldmask to match the array returned from chunkify

        spacing: 2-element tuple of ints. Specifies where to sample oldmask
    """
    data = oldmask.nxdata
    bounds = (np.array(data.shape) // spacing) * spacing
    newmask = np.zeros(bounds // spacing, dtype=data.dtype)
    dx,dy = spacing
    for x in range(newmask.shape[0]):
        for y in range(newmask.shape[1]):
            newmask[x,y] = data[spacing[0]*x, spacing[1]*y]
    return newmask

def shrink_monitor(oldmon, spacing):
    """ Sample from oldmon, making sure that the outliers are preserved

        Monitor data is almost all a uniform value, with some that are much
            higher or lower.
        Oldmon: MCSx field of monitor:NXdata.
        Spacing: int
    """
    data = oldmon.nxdata
    bounds = (np.array(oldmon.shape) // spacing) * spacing
    newmon = np.zeros(bounds // spacing, dtype=oldmon.dtype)
    for x in range(newmon.shape[0]):
        chunk = data[x*spacing : (x+1)*spacing]
        # threshold is qualitative...
        if chunk.max() / chunk.mean() > 1.4:
            newmon[x] = chunk.max()
        else:
            newmon[x] = chunk.min()
    return newmon


def run(file, size):
    file = os.path.realpath(file)
    chunkshape = [size] * 3
    sample_dir = os.path.dirname(file)
    sample,scan = os.path.basename(file).split('_')
    scan = os.path.splitext(scan)[0]
    f = nxload(file)
    # Copy the metadata to the new file
    # output = NXroot(entries=f.entries)
    output = copy.deepcopy(f)
    #Create a scaled pixel mask, then copy the other data
    det = NXdetector()
    old_det = f.entry.instrument.detector
    det.pixel_mask = shrink_mask(old_det.pixel_mask, chunkshape[1:3])
    det.shape = det.pixel_mask.shape
    for k,v in old_det.entries.items():
        if k in det.entries:
            continue
        det[k] = v
    del output.entry.instrument['detector']
    output.entry.instrument.detector = det

    # Save output as the wrapper file and crete the scan directory
    try:
        outfilename = sample + '_shrunk_' + scan
        output.save(os.path.join(sample_dir, outfilename))
        scan_dir = os.path.join(sample_dir, 'shrunk_' + scan)
    except OSError:
        dirs = os.listdir(sample_dir)
        num = 1 + sum(1 for d in dirs if outfilename in d)
        output.save(os.path.join(sample_dir, outfilename + str(num)))
        scan_dir = os.path.join(sample_dir, 'shrunk_' + scan + str(num))

    os.mkdir(scan_dir)

    for entry in ['f1', 'f2', 'f3']:
        olddata = f[entry].data
        try:
            mask = f[entry].instrument.detector.pixel_mask.nxvalue
        except NeXusError:
            mask = None
        # cProfile.run('chunkify(olddata.data, chunkshape, mask)')
        res = chunkify(olddata.data, chunkshape, mask)
        # Save the new data in the entry's data field and update metadata
        newdata = NXdata()
        newdata.attrs['axes'] = olddata.attrs['axes']
        if entry == 'f1':
            first = olddata.attrs['first'] // chunkshape[0]
            last = olddata.attrs['last'] // chunkshape[0]
        newdata.attrs['first'] = first
        newdata.attrs['last'] = last
        newdata.attrs['max'] = res.max()
        newdata.attrs['signal'] = olddata.attrs['signal']
        newdata['frame_number'] = np.arange(res.shape[0])
        newdata['x_pixel'] = np.arange(res.shape[2])
        newdata['y_pixel'] = np.arange(res.shape[1])
        # Create an h5 file to hold the actual data and link to it from output
        data_file = os.path.join(scan_dir, entry + '.h5')
        target = h5py.File(data_file)
        target.create_dataset('entry/data/data',
                    data=res, chunks=olddata.data.chunks) # TODO: auto chunks?
        target['entry/data/data'].attrs['signal'] = olddata.data.signal
        target.close()
        newdata.data = NXlink('/entry/data/data', data_file)

        del output[entry]['data']
        output[entry]['data'] = newdata
        del output[entry]['peaks']

        # Update calibration
        newcal = output[entry].instrument.calibration
        newcal.header.nColumns = res.shape[2]
        newcal.header.nRows = res.shape[1]
        newcal.header.rowsPerStrip = res.shape[2]
        newcal.header.stripByteCounts = res.shape[1] * res.shape[2] * res.dtype.itemsize
        del newcal['x'], newcal['y']
        newcal.x = np.arange(res.shape[2])
        newcal.y = np.arange(res.shape[1])
        # TODO: What is cal.z???

        # Update detector
        newdet = output[entry].instrument.detector
        newdet.beam_center_x /= chunkshape[2]
        newdet.beam_center_y /= chunkshape[1]
        del newdet['pixel_mask']
        if res.mask is not False:
            newdet['pixel_mask'] = res.mask[0,...]
        else:
            newdet['pixel_mask'] = np.zeros(res.shape[1:3], dtype=bool)
        sig_path = os.path.basename(output.nxfilename) + newdet.nxfilepath
        newdet.pixel_mask.attrs['signal_path'] = sig_path
        newdet.shape = newdet['pixel_mask'].shape

        # Update monitors
        for i in ('1','2'):
            mon = output[entry]['monitor' + i]
            del mon['frame_number']
            mon.frame_number = np.arange(res.shape[0])
            newmon = shrink_monitor(mon['MCS' + i], chunkshape[0])
            del mon['MCS' + i]
            mon['MCS' + i] = newmon


if __name__ == '__main__':
    run('/home/patrick/de-bulk/GUP-58871/agcrse2/xtal1a/agcrse2_300K.nxs', 10)
