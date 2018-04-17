import argparse, os, subprocess
import numpy as np

def crash(msg):
    print(msg)
    exit(1)

def main():

    parser = argparse.ArgumentParser(
        description="Perform workflow for scan")
    parser.add_argument('-s', '--sample', help='sample name')
    parser.add_argument('-l', '--label', help='sample label')
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files linked to this file')
    parser.add_argument('-p', '--parent', help='file name of file to copy from')
    
    args = parser.parse_args()

    sample = args.sample
    label = args.label
    directory = args.directory.rstrip('/')
    if sample is None and label is None:
        sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
        label = os.path.basename(os.path.dirname(directory))
        directory = os.path.basename(directory)

    print("Processing sample '%s', label '%s', scan '%s'\n" % (sample,
                                                               label,
                                                               directory))
    ext = args.extension
    
    temperature = np.float32(args.temperature)
    files = args.filenames
    parent = args.parent

    label_path = '%s/%s' % (sample, label)
    wrapper_file = '%s/%s_%s.nxs' % (label_path, sample, directory)

    if sample == None:
        crash('Requires sample!')
    if not os.path.exists(label_path):
        crash("Label does not exist: "+label_path)
    
    for f in files:
        path = os.path.join(sample, label, directory)
        print("\n\nProcessing %s" % path)
        print("\n\nReading in metadata in %s\n" % f)
        subprocess.call('nxingest -d %s -f %s' % (path, f), shell=True)
        print("\n\nDetermining maximum counts in %s\n" % f)
        subprocess.call('nxmax -f %s -p %s/data'
                        % (wrapper_file, f), shell=True)
        print("\n\nFinding peaks in %s\n" % f)
        subprocess.call('nxfind -f %s -p %s/data -s 500 -e 2500'
                        % (wrapper_file, f), shell=True)

    if parent:
        print("\n\nCopying parameters from %s\n" % parent)
        subprocess.call('nxcopy -f %s -o %s' 
                        % (parent, wrapper_file), shell=True)
        

if __name__=="__main__":
    main()
