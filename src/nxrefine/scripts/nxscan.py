import argparse, os, subprocess, time


def crash(msg):
    print(msg)
    exit(1)


def main():

    parser = argparse.ArgumentParser(
        description="Make NeXus file and directories for new scan")
    parser.add_argument('-d', '--directory', help='sample directory')
    parser.add_argument('-p', '--parent', help='scan parent')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files to be linked to this file')
    parser.add_argument('-m', '--maskfiles', 
        default=['mask_f1', 'mask_f2', 'mask_f3'], nargs='+',
        help='name of the pixel mask files')
    parser.add_argument('-t', '--temperatures', nargs='+', help='list of temperatures')
    parser.add_argument('-w', '--wait', action='store_true', default=False,
                        help='wait for stream completion')    
    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    parent = args.parent
    sample = os.path.basename(os.path.dirname(directory))
    label = os.path.basename(directory)
    files = args.filenames
    maskfiles = args.maskfiles
    if len(maskfiles) < len(files):
        if len(maskfiles) == 1:
            maskfiles = [maskfiles] * len(files)
        else:
            crash('No. of maskfiles must same as no. of filenames or 1')
    temperatures = args.temperatures
    wait = args.wait

    for temperature in temperatures:
        dir = temperature+'K'
        scan_dir = os.path.join(directory, dir)
        for (f, m) in zip(files, maskfiles):
            if wait:
                while not os.path.exists(os.path.join(scan_dir, 'f', 'done.txt')):
                    time.sleep(10)
            subprocess.call('nxwork -s %s -l %s -d %s -t %s -f %s -m %s -p %s'
                        % (sample, label, dir, temperature, f, m, parent), shell=True)
        subprocess.call('nxtransform -d %s  -f %s -p %s' % (scan_dir, f, parent), shell=True)

if __name__=="__main__":
    main()
