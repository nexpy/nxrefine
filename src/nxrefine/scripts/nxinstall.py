#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2022-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

"""Prefetch Julia and its packages so NXRefine can run offline."""

import sys

from nxrefine.nxutils import load_julia, prime_julia_environment


def main():
    prime_julia_environment()

    import juliapkg

    print("Resolving Julia and Julia packages (requires internet)...")
    juliapkg.resolve()

    from juliacall import Main
    Main.seval("using Roots, LinearAlgebra, SparseArrays")

    load_julia(['LaplaceInterpolation.jl'])

    print("\nJulia environment:")
    juliapkg.status()
    print("\nNXRefine can now run without internet access.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
