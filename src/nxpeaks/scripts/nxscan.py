import os, subprocess, time

def main():

    parser = argparse.ArgumentParser(
        description="Make NeXus file and directories for new scan")
    parser.add_argument('-d', '--directory', help='sample directory')
    parser.add_argument('-p', '--parent', help='scan parent')
    parser.add_argument('-t', '--temperatures', nargs='+', help='list of temperatures')
    
    args = parser.parse_args()

    directory = args.directory.rstrip('/')
    parent = args.parent
    sample = os.path.basename(os.path.dirname(directory))
    label = os.path.basename(directory)
    temperatures = args.temperatures

    for temperature in temperatures:
        dir = temperature+'K'
        scan_dir = os.path.join(directory, dir)
        while not os.path.exists(os.path.join(scan_dir, 'f1', 'done.txt')):
            sleep.wait(30)
        subprocess.call('nxwork -s %s -l %s -d %s -t %s -f f1 -m mask_f1 -p %s'
                        % (sample, label, dir, temperature, parent), shell=True)
        subprocess.call('nxtransform -d %s  -f f1 -p %s' % (scan_dir, parent))           

if __name__=="__main__":
    main()
