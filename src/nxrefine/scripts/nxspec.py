import argparse, os, subprocess
import numpy as np
from nexusformat.nexus import *


def read_specfile(spec_file):
    subprocess.call('spec2nexus --quiet '+spec_file, shell=True)
    subentries = []
    prefix = os.path.splitext(os.path.basename(spec_file))[0]
    directory = os.path.dirname(spec_file)
    try:
        spec = nxload(os.path.join(directory, prefix+'.hdf5'))
        for entry in spec.NXentry:
            entry.nxclass = NXsubentry
            subentries.append(entry)
    except:
        pass
    return subentries


def write_specfile(entry, spec_file):
    subentries = read_specfile(spec_file)
    for subentry in subentries:
        if subentry.nxname not in entry:
            entry[subentry.nxname] = subentry
            print("'%s' added to '%s'" % (subentry.nxname, entry.nxname))
        else:
            print("'%s' already in '%s'" % (subentry.nxname, entry.nxname))


def main():

    parser = argparse.ArgumentParser(
        description="Perform workflow for scan")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files to be linked to this file')
    parser.add_argument('-s', '--spec', default='scan.spec',
                        help="Name of SPEC file used in collecting images")
    
    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
    label = os.path.basename(os.path.dirname(directory))
    directory = os.path.basename(directory)
    files = args.filenames
    spec = args.spec

    label_path = '%s/%s' % (sample, label)
    wrapper_file = '%s/%s_%s.nxs' % (label_path, sample, directory)

    print("Processing sample '%s', label '%s', scan '%s'" % (sample,
                                                             label,
                                                             directory))
    
    root = nxload(wrapper_file, 'rw')    
    for f in files:
        entry = root[f]
        spec_file = os.path.join(label_path, directory, f, spec)
        if os.path.exists(spec_file):
            write_specfile(entry, spec_file)
        else:
            print("'%s' not found" % spec_file)              
                

if __name__=="__main__":
    main()
