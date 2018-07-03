from nexusformat.nexus import *
import numpy as np
import h5py
import copy
import argparse
import os
from tqdm import trange
import ipdb

def chunkify(arr, chunkshape):
    """ Divide NXfield arr into chunks of size chunkshape. If arr doesn't fit
        exactly it will be truncated
        chunkshape: 3-element tuple of ints
    """
    # Where to truncate arr
    bounds = (np.array(arr.shape) // chunkshape) * chunkshape
    # bounds = np.array([100,1000,1000])
    dx,dy,dz = chunkshape
    result = np.zeros(bounds // chunkshape, dtype=arr.dtype)
    for x in trange(result.shape[0]):
        # Avoid memory problems and optimize memory accesses
        slab = arr[x*dx:(x+1)*dx, :bounds[1], :bounds[2]].nxdata
        for y in range(result.shape[1]):
            for z in range(result.shape[2]):
                chunk = slab[:, y*dy:(y+1)*dy, z*dz:(z+1)*dz]
                result[x,y,z] = np.mean(chunk)
    return result

def shrink_mask(oldmask, spacing):
    """ Shrink oldmask to match the array returned from chunkify, using a grid
        defined by spacing
        spacing: 2-element tuple of ints
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
    """ Monitor data is almost all a uniform value, with some that are much
        higher or lower. Sample from oldmon, making sure that the outliers
        are preserved.
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


parser = argparse.ArgumentParser(description="Shrink a NeXus file by lowering\
            the resolution")
parser.add_argument('file', help='name of parent file')
parser.add_argument('-s', '--size', default=10, help='size of the chunks to average')

args = parser.parse_args()
chunkshape = [args.size] * 3
sample_dir = os.path.dirname(args.file)
sample,scan = os.path.basename(args.file).split('_')
scan = os.path.splitext(scan)[0]
f = nxload(args.file)
# Copy the metadata to the new file
# output = NXroot(entries=f.entries)
output = copy.deepcopy(f)
#Create a scaled pixel mask, then copy the other data
det = NXdetector()
old_det = f.entry.instrument.detector
det.pixel_mask = shrink_mask(old_det.pixel_mask, chunkshape[1:3])
det.shape = det.pixel_mask.shape
for k,v in old_det.entries.items():
    if k  in det.entries:
        continue
    det[k] = v
del output.entry.instrument['detector']
output.entry.instrument.detector = det

# ipdb.set_trace()

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
    res = chunkify(olddata.data, chunkshape)
    # Save the new data in the entry's data field and update metadata
    newdata = NXdata()
    newdata.attrs['axes'] = olddata.attrs['axes']
    if entry == 'f1':
        newdata.attrs['first'] = olddata.attrs['first'] // chunkshape[0]
        newdata.attrs['last'] = olddata.attrs['last'] // chunkshape[0]
        newdata.attrs['max'] = res.max()
    newdata.attrs['signal'] = olddata.attrs['signal']
    newdata['frame_number'] = np.arange(res.shape[0])
    newdata['x_pixel'] = np.arange(res.shape[2])
    newdata['y_pixel'] = np.arange(res.shape[1])
    # newdata['data'] = res
    # Create an h5 file to hold the actual data and link to it from output
    # rt = NXroot(NXentry(NXdata()))
    # rt.entry.data.data = res
    # rt.entry.data.data.attrs['signal'] = olddata.data.signal
    data_file = os.path.join(scan_dir, entry + '.h5')
    target = h5py.File(data_file)
    target.create_dataset('entry/data/data',
                data=res, chunks=olddata.data.chunks) # TODO: divide by chunkshape
    target['entry/data/data'].attrs['signal'] = olddata.data.signal
    target.close()
    newdata.data = NXlink('/entry/data/data', data_file)

    del output[entry]['data']
    output[entry]['data'] = newdata

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
    newdet['pixel_mask'] = output.entry.instrument.detector.pixel_mask
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
