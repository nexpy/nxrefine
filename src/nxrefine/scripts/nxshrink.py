import argparse
import nxrefine.shrink_nxs as shrink

def main():
    parser = argparse.ArgumentParser(description="Shrink a NeXus file by lowering\
                the resolution")
    parser.add_argument('file', help='name of wrapper file to shrink')
    parser.add_argument('-s', '--size', type=int, default=5,
                help='size of the chunks to average, default 5')

    args = parser.parse_args()
    shrink.run(args.file, args.size)

if __name__ == '__main__':
    main()
