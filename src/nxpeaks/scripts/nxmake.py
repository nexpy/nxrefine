import os
import re
import numpy as np
import subprocess

from nexusformat.nexus import *

#home_dir = '/home/bessrc/sharedbigdata/data1/osborn-2014-1'
#directory_pattern = re.compile('(.*)[kK]') 
#directory_pattern = re.compile('(.*)_([0-9]*)[kK]')
#raw_files = ['f1', 'f2'] 
#raw_files = ['ff1scan', 'ff2scan', 'fb1scan', 'fb2scan', 'sfscan', 'sbscan', 'ubfscan', 'ubbscan']
#pixel_mask = nxload(os.path.join(home_dir, 'pilatus_mask.nxs'))['entry/mask']
#pixel_mask = None


def make_nexus_file(scan_dir, sample_dir, filenames, pattern, specfile,
                    label=False):
    if label:
        sample_label = parent(scan_dir)
        sample_name = grandparent(scan_dir)
    else:
        sample = parent(scan_dir)
    scan = os.path.basename(scan_dir)
    nexus_file = os.path.join(sample_dir, sample_name + '_' + scan + '.nxs')
    root = NXroot()
    sample = NXsample()
    sample.name = sample_name
    if label:
        sample.label = sample_label
    try:
        sample.temperature = np.float32(re.match(pattern, scan).group(1))
        sample.temperature.units='K'
    except ValueError:
        pass
    root.entry = NXentry(sample)
    for f in filenames:
        if f+'.nxs' in os.listdir(scan_dir):
            root[f] = make_entry(os.path.join(scan_dir, f+'.nxs'))
            root[f].makelink(root.entry.sample)
            if specfile is not None:
                subentries = import_spec_file(os.path.join(scan_dir, f, specfile))
            for subentry in subentries:
                root[f][subentry.nxname] = subentry
    print nexus_file
    root.save(nexus_file, 'w')
    
def make_entry(scan_file):
    root = nxload(scan_file)
    entry = NXentry(NXdata())
    entry.filename = root.entry.filename
    entry.start_time = root.entry.start_time
    entry.instrument = root.entry.instrument
    if pixel_mask:
        entry.instrument.detector.pixel_mask = pixel_mask
        entry.instrument.detector.pixel_mask_applied = False
    entry.data.x_pixel = root.entry.data.x_pixel
    entry.data.y_pixel = root.entry.data.y_pixel
    entry.data.frame_number = root.entry.data.frame_number
    entry.data.data = NXlink(target='/entry/data/data', file=scan_file)
    entry.data.nxsignal = entry.data.data
    entry.data.nxaxes = [entry.data.frame_number, entry.data.y_pixel, 
                         entry.data.x_pixel]
    return entry

def import_spec_file(specfile):
    subprocess.call('spec2nexus --quiet '+specfile, shell=True)
    subentries = []
    prefix = os.path.splitext(os.path.basename(specfile))[0]
    directory = os.path.dirname(specfile)
    try:
        spec = nxload(os.path.join(directory, prefix+'.hdf5'))
        for entry in spec.NXentry:
            entry.nxclass = NXsubentry
            subentries.append(entry)
    except:
        pass
    return subentries

def subdirs(dir):
    return [os.path.join(dir,f) for f in os.listdir(dir) 
            if os.path.isdir(os.path.join(dir,f))]

def parent(dir):
    return os.path.basename(os.path.dirname(dir))

def grandparent(dir):
    return os.path.basename(os.path.dirname(os.path.dirname(dir)))

def main():

    parser = argparse.ArgumentParser(
        description="Create composite NeXus files")
    parser.add_argument('-d', '--directory', default='./')
    parser.add_argument('-p', '--pattern', default='(.*)[kK]')
    parser.add_argument('-l', '--label', action='store_true')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2'])
    parser.add_argument('-m', '--maskfile')
    parser.add_argument('-s', '--specfile')

    args = parser.parse_args()

    directory = args.directory
    filenames = args.filenames
    pattern = re.compile(args.pattern)
    specfile = args.specfile
    label = args.label
    mask nxload(os.path.join(directory, 'pilatus_mask.nxs'))['entry/mask']

    for sample_name in subdirs(directory):
        if label:
            for sample_label in subdirs(os.path.join(directory, sample_name)):
                sample_dir = os.path.join(directory, sample_name, sample_label)
                for scan_dir in subdirs(sample_dir):
                    make_nexus_file(scan_dir, sample_dir, args)
        else:
            sample_dir = os.path.join(directory, sample_name)
            for scan_dir in subdirs(sample_dir):
                make_nexus_file(scan_dir, sample_dir, args)


if __name__ == '__main__':
    main()

