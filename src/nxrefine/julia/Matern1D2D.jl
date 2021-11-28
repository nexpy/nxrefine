
# Helper code

"""
  spdiagm_nonsquare(m, n, args...)

Construct a sparse diagonal matrix from Pairs of vectors and diagonals. Each
vector arg.second will be placed on the arg.first diagonal. By default (if
size=nothing), the matrix is square and its size is inferred from kv, but a
non-square size m×n (padded with zeros as needed) can be specified by passing
m,n as the first arguments.

# Arguments
  - `m::Int64`: First dimension of the output matrix
  - `n::Int64`: Second dimension of the output matrix
  - `args::Tuple{T} where T<:Pair{<:Integer,<:AbstractVector}` 

# Outputs 

  - sparse matrix of size mxn containing the values in args 

"""
function spdiagm_nonsquare(m, n, args...)
    I, J, V = SparseArrays.spdiagm_internal(args...)
    return sparse(I, J, V, m, n)
end

# One-dimensional codes

""" 
    nablasq_grid(n, h)

Laplacian matrix on a 1D grid

# Arguments:
    - `n`: Number of points
    - `h`: Aspect ratio

# Outputs:
    - discrete Laplacian matrix
"""
function nablasq_grid(n::Int64, h::Float64 = 1.0)
  o = ones(n) / h
  del = spdiagm_nonsquare(n + 1, n, -1 => -o, 0 => o)
  A1D = del' * del
  A1D[1, 1] = 1.0 / h ^ 2
  A1D[n, n] = 1.0 / h ^ 2
  return A1D
end

""" 

   matern_1d_grid(y, idx, m, eps, h)

Matern Interpolation in one dimension

# Arguments:
  - `y`: the vector of y's for which the values are known
  - `idx`: the vector of indices for which values are to be interpolated
  - `m::Int64 = 1`: Matern parameter m
  - `eps = 0.0`: Matern parameter eps
  - `h = 1.0`: aspect ratio

# Outputs:
  - vector of interpolated data

# Example:
```<julia-repl>
x = 1:100
h = x[2] - x[1]
y = sin.(2 * pi * x * 0.2)
discard = randperm(100)[1:50]
# Laplace interpolation
y_lap = matern_1d_grid(y, discard, 1, 0.0, h)
# Matern interpolation
y_mat = matern_1d_grid(y, discard, 2, 0.1, h)
```
  
"""
function matern_1d_grid(y::Vector{T}, idx::Vector{Int64}, 
                        m::Int64 = 1, eps = 0.0, h::Float64 = 1.0) where{T<:Number}
  n = length(y)
  A1D = nablasq_grid(n, h)
  C = sparse(I, n, n)
  for i in idx
    C[i, i] = 0.0
  end
  if ((eps == 0)||(eps == 0.0)) && (m == 1)
    # Laplace Interpolation
    return ((C - (sparse(I, n, n) - C) * A1D)) \ (C * y)
  else
    # Matern Interpolation
    for i = 1:size(A1D,1)
      A1D[i, i] = A1D[i, i] + eps^2
    end
    A1DM = A1D ^ m
    return ((C - (sparse(I, n, n) - C) * A1DM)) \ (C * y)
  end
end

# Two dimensional codes

"""
  bdy_nodes(Nx, Ny)

...
# Arguments

  - `Nx::Int64`: the number of points in the first dimension
  - `Ny::Int64`: the number of points in the second dimension
...

...
# Outputs
  - vector containing the indices of coordinates on the boundary of the 2D rectangle
...

"""
function bdy_nodes(Nx, Ny)
  bdy = []
  xnb = []
  ynb = []
  counter = 0
      for j = 1:Ny
          for i = 1:Nx
              counter += 1
              if (j == 1 || j == Ny || i == 1 || i == Nx)
                  bdy = push!(bdy, counter)
                  if (j == 1 || j == Ny)
                      push!(ynb, 1)
                  else
                      push!(ynb, 2)
                  end
                  if (i == 1 || i == Nx)
                      push!(xnb, 1)
                  else
                      push!(xnb, 2)
                  end
              end
          end
      end
  return bdy, xnb, ynb
end

""" 
    nablasq_grid(Nx, Ny, h, k)

Laplacian matrix on a 2D grid

# Arguments:
    - `Nx::Int64`: Number of points in first dimension
    - `Ny::Int64`: Number of points in second dimension
    - `h::Float64`: Aspect ratio in first dimension
    - `k::Float64`: Aspect ratio in second dimension

# Outputs:
    - discrete Laplacian matrix in 2D
"""
function nablasq_grid(Nx::Int64, Ny::Int64, h::Float64, k::Float64)
  o1 = ones(Nx) / h
  del1 = spdiagm_nonsquare(Nx + 1, Nx, -1 => -o1, 0 => o1)
  o2 = ones(Ny) / k
  del2 = spdiagm_nonsquare(Ny + 1, Ny, -1 => -o2,0 => o2)
  A2D = (kron(sparse(I, Ny, Ny), del1' * del1) + 
          kron(del2' * del2, sparse(I, Nx, Nx)))
  bdy, xnb, ynb = bdy_nodes(Nx, Ny)
  count = 1
  for i in bdy
      A2D[i, i] = 0.0
      A2D[i, i] = A2D[i, i] + xnb[count] / h ^ 2 + ynb[count] / k ^ 2 
      count += 1
  end
  return A2D
end

"""

  matern_2d_grid(mat, discard, m, eps, h, k)

...
# Arguments
  - `mat`: the matrix containing the image
  - `idx`: the linear indices of the nodes to be discarded
  - `eps`: Matern parameter eps
  - `m`: The Matern exponent (integer)
  - `h`: The aspect ratio in the first dimension
  - `k`: The aspect ratio in the second dimension

# Outputs
  - matrix containing the interpolated image

# Example:

```<julia-repl>
x = y = 1:30
h = k = x[2] - x[1]
y = sin.(2 * pi * x * 0.2) * cos.(2 * pi * y * 0.3)
discard = randperm(900)[1:450]
# Laplace interpolation
y_lap = matern_2d_grid(y, discard, 1, 0.0, h, k)
# Matern interpolation
y_mat = matern_2d_grid(y, discard, 2, 0.1, h, k)
...

"""
function matern_2d_grid(mat::Matrix, discard::Vector, m::Int64 = 1, eps = 0.0, 
                        h::Float64 = 1.0, k::Float64 = 1.0)
    rows, columns = size(mat)
    A2D = nablasq_grid(rows, columns, h, k)
    sizeA = size(A2D, 1)
    C = sparse(I, sizeA, sizeA)
    for i in discard
        C[i, i] = 0.0
    end
    if ((m == 1)||(m == 1.0)) && (eps == 0.0)
        # Laplace interpolation
        u = ((C - (sparse(I, sizeA, sizeA) - C) * A2D)) \ (C * mat[:])
        return reshape(u, rows, columns)
    else
        # Matern interpolation
        for i = 1:sizeA
            A2D[i,i] = A2D[i,i] + eps^2
        end
        A2D = A2D^m
        u = ((C - (sparse(I, sizeA, sizeA) - C) * A2D)) \ (C * mat[:])
        return reshape(u, rows, columns)   
    end
end

