#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2022-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

"""Prefetch Julia and its packages so NXRefine can run offline."""

import os
import sys


def main():
    if not os.environ.get('JULIA_SSL_CA_ROOTS_PATH'):
        try:
            import certifi
            os.environ['JULIA_SSL_CA_ROOTS_PATH'] = certifi.where()
        except ImportError:
            pass

    import juliapkg

    print("Resolving Julia and Julia packages (requires internet)...")
    juliapkg.resolve()

    from juliacall import Main
    Main.seval("using Roots, LinearAlgebra, SparseArrays")

    from nxrefine.nxutils import load_julia
    load_julia(['LaplaceInterpolation.jl', 'get_xyzs.jl'])

    print("\nJulia environment:")
    juliapkg.status()
    print("\nNXRefine can now run without internet access.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
