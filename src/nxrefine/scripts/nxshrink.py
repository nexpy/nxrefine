import argparse
import nxrefine.shrink_nxs as shrink
import nxrefine.paralell_shrink as par_shrink

def main():
    parser = argparse.ArgumentParser(description="Shrink a NeXus file by lowering\
                the resolution")
    parser.add_argument('file', help='name of wrapper file to shrink')
    parser.add_argument('-s', '--size', type=int, default=5,
                help='size of the chunks to average, default 5')
    parser.add_argument('--no-parallel', action='store_true',
                help='Process entries sequentially instead of in parallel')

    args = parser.parse_args()
    if args.no_parallel:
        shrink.run(args.file, args.size)
    else:
        par_shrink.run(args.file, args.size)

if __name__ == '__main__':
    main()
