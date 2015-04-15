import argparse
import os
import re
import numpy as np
from nexusformat.nexus import *


def make_nexus_file(sample_name, sample_label, scan_directory, temperature, 
                    filenames, mask=None):    
    root = NXroot()
    sample = NXsample()
    sample.name = sample_name
    if sample_label:
        sample.label = sample_label
    sample['temperature'] = temperature
    sample['temperature'].attrs['units'] = 'K'
    root.entry = NXentry(sample)
    for f in filenames:
        root[f] = make_entry(mask)
        root[f].makelink(root.entry.sample)
    return root
    

def make_entry(mask=None):
    entry = NXentry()
    entry.instrument = NXinstrument()
    entry.instrument.detector = NXdetector()
    if mask is not None:
        entry.instrument.detector.pixel_mask = mask
        entry.instrument.detector.pixel_mask_applied = False
    return entry


def main():

    parser = argparse.ArgumentParser(
        description="Make NeXus file and directories for new scan")
    parser.add_argument('-s', '--sample', help='sample name')
    parser.add_argument('-l', '--label', default='', help='sample label')
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-t', '--temperature', help='temperature of scan')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files to be linked to this file')
    parser.add_argument('-m', '--maskfile', default='pilatus_mask.nxs',
        help='name of the pixel mask file')
    
    args = parser.parse_args()

    sample_name = args.sample
    sample_label = args.label
    directory = args.directory
    temperature = np.float32(args.temperature)
    filenames = args.filenames
    if args.maskfile is not None:
        mask = nxload(args.maskfile)['entry/mask']
    else:
        mask = None

    scan_directory = os.path.join(sample_name, sample_label, directory)
    try: 
        print filenames
        os.makedirs(scan_directory)
        for f in filenames:
            print os.path.join(scan_directory, f)
            os.mkdir(os.path.join(scan_directory, f))
    except Exception:
        pass

    nexus_file = os.path.join(sample_name, sample_label, sample_name + '_' + directory + '.nxs')
    root = make_nexus_file(sample_name, sample_label, scan_directory, 
                           temperature, filenames, mask)
    root.save(nexus_file, 'w')
    print 'Saving ', nexus_file
    

if __name__=="__main__":
    main()
