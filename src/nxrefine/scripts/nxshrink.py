import argparse
import nxrefine.shrink_nxs as shrink

def main():
    parser = argparse.ArgumentParser(description="Shrink a NeXus file by lowering\
                the resolution")
    parser.add_argument('file', help='name of parent file')
    parser.add_argument('-s', '--size', default=10, help='size of the chunks to average')

    args = parser.parse_args()
    shrink.run(args.file, args.size)

if __name__ == '__main__':
    main()
