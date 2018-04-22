#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2015, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import argparse, os
from nexusformat.nexus import *
from nxrefine.nxrefine import NXRefine


def main():

    parser = argparse.ArgumentParser(
        description="Copy sample and instrument parameters to another file or entry")
    parser.add_argument('-i', '--input', required=True,
                        help='name of the input NeXus file')
    parser.add_argument('-e', '--entry', 
                        help='path of input NXentry group')
    parser.add_argument('-t', '--target', help='path of target NXentry group')
    parser.add_argument('-o', '--output', help='output NeXus file (if different)')
    
    args = parser.parse_args()
    if args.output:
        input = nxload(args.input)
        input_ref = NXRefine(input['entry'])
        output = nxload(args.output, 'rw')
        output_entry_ref = NXRefine(output['entry'])
        input_ref.copy_parameters(output_entry_ref, sample=True)
        for name in [entry for entry in input if entry != 'entry']:
            if name in output: 
                input_ref = NXRefine(input[name])
                output_ref = NXRefine(output[name])
                input_ref.copy_parameters(output_ref, instrument=True)
                output_entry_ref.link_sample(output_ref)
    else:
        input = nxload(args.filename, 'rw')
        input_ref = NXRefine(input[args.entry])
        output_ref = NXRefine(input[args.target])
        input_ref.copy_parameters(output_ref, instrument=True)
        if 'sample' not in input[args.target] and 'sample' in input['entry']:
            input_ref = NXRefine(input['entry'])
            input_ref.link_sample(output_ref)
    

if __name__=="__main__":
    main()
