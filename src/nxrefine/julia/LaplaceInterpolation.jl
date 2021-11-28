module LaplaceInterpolation

  using LinearAlgebra, SparseArrays

  include("Matern1D2D.jl")
  export nablasq_grid, bdy_nodes, matern_1d_grid, matern_2d_grid 

  include("GeneralMK3D.jl")
  export nablasq_3d_grid, matern_3d_grid, matern_w_punch

  include("MaternKernelApproximation.jl")
  export spdiagm_nonsquare, return_boundary_nodes
  export Matern3D_Grid, Parallel_Matern3D_Grid

  include("punch.jl")
  export punch_holes_3D, punch_holes_2D, punch_3d_cart, center_list 

  include("nexus.jl")
  # These functions are unexported

  # Only works with juliia v 1.6 and higher
  include("arbitrary_dim.jl")
  export nablasq_arb, interp

end
