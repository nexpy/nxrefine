import argparse, os, subprocess
import numpy as np

def crash(msg):
    print(msg)
    exit(1)

def main():

    parser = argparse.ArgumentParser(
        description="Perform workflow for scan")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files linked to this file')
    parser.add_argument('-p', '--parent', help='file name of file to copy from')
    
    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    sample = os.path.basename(os.path.dirname(directory))  
    label = os.path.basename(directory)

    print("Processing sample '%s', label '%s'\n" % (sample, label))
    
    temperature = np.float32(args.temperature)
    files = args.filenames
    parent = args.parent

    label_path = '%s/%s' % (sample, label)

    if sample == None:
        crash('Requires sample!')
    if not os.path.exists(label_path):
        crash("Label does not exist: "+label_path)

    wrapper_files = [filename for filename in os.listdir(label_path) 
                     if filename.endswith('.nxs')]

    for wrapper_file in wrapper_files:
        root = nxload(wrapper_file)    
        for f in files:
            path = os.path.join(sample, label, directory)
            print("\n\nProcessing %s" % path)
            if 'logs' not in root[f]['instrument']:
                print("\n\nReading in metadata in %s\n" % f)
                subprocess.call('nxingest -d %s -f %s' % (path, f), shell=True)
            if 'maximum' not in root[f]['data'].attrs:
                print("\n\nDetermining maximum counts in %s\n" % f)
                subprocess.call('nxmax -f %s -p %s/data'
                                % (wrapper_file, f), shell=True)
            if 'peaks' not in root[f]:
                print("\n\nFinding peaks in %s\n" % f)
                subprocess.call('nxfind -f %s -p %s/data -s 500 -e 2500'
                                % (wrapper_file, f), shell=True)

        if parent:
            print("\n\nCopying parameters from %s\n" % parent)
            subprocess.call('nxcopy -f %s -o %s' 
                            % (parent, wrapper_file), shell=True)
    

if __name__=="__main__":
    main()
