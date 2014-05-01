import os, getopt, sys
import indexing, transformer


def refine_peaks(filtered_peaks, parameter_file, output_prefix):
    mytransformer = transformer.transformer()
    myindexer = indexing.indexer()
    mytransformer.loadfiltered(filtered_peaks)
    mytransformer.loadfileparameters(parameter_file)
    mytransformer.compute_tth_eta( )
    mytransformer.addcellpeaks( )
    mytransformer.fit( 3.0 , 8.0 )
    mytransformer.saveparameters(output_prefix+'.pars')
    mytransformer.computegv( )
    mytransformer.savegv(output_prefix+'.gve')
    myindexer.readgvfile(output_prefix+'.gve')
    myindexer.loadpars(parameter_file)
    myindexer.assigntorings()
    myindexer.find()
    myindexer.scorethem()
    myindexer.histogram_drlv_fit()
    myindexer.saveubis(output_prefix+'.ubi')
    myindexer.saveindexing(output_prefix+'.idx')

def main():
    help = "nxrefine -d <directory> -f <filter> -p <parameters> -o <output>"
    try:
        opts, args = getopt.getopt(sys.argv[1:],"hd:f:p:o:",["directory=",
                                    "filter=","parameters=","output="])
    except getopt.GetoptError:
        print help
        sys.exit(2)
    directory = './'
    filtered_peaks = ''
    parameter_file = ''
    output_prefix = ''
    for opt, arg in opts:
        if opt == '-h':
            print help
            sys.exit()
        elif opt in ('-d', '--directory'):
            directory = arg
        elif opt in ('-f', '--filter'):
            filtered_peaks = os.path.join(directory, arg)            
        elif opt in ('-p', '--parameters'):
            print opt, arg
            parameter_file = os.path.join(directory, arg)
        elif opt in ('-o', '--output'):
            output_prefix = os.path.join(directory, arg)            
    if not os.path.exists(filtered_peaks):
        print 'Specify a valid filtered peaks file'
        sys.exit(2)
    if not os.path.exists(parameter_file):
        print 'Specify a valid parameter file'
        sys.exit(2)
    if not output_prefix:
        output_prefix, ext = os.path.splitext(os.path.basename(filtered_peaks))
    refine_peaks(filtered_peaks, parameter_file, output_prefix) 

if __name__=="__main__":
    main()
