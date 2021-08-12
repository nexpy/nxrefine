
#=
""" Give the boundary nodes """
function bdy_nodes(dims::Tuple)
    D = length(dims)
    nbdy = prod(dims) - prod(dims .- 2)
    bdy = CartesianIndex{D}[]
    for (i, d) in enumerate(dims)
        # This only works with julia v 1.6
        push!(bdy, CartesianIndices((dims[1:(i-1)]..., 1:(d-1):d, dims[(i+1):D]...))[:]...)
    end
    bdy = unique(bdy)
    neighbors = zeros(length(bdy), D)
    for (j, b) in enumerate(bdy)
        for i in 1:D
          neighbors[j, i] = ((Tuple(b)[i] == 1)||(Tuple(b)[i] == dims[i])) ? 1 : 2
        end
    end
    return bdy, neighbors
end
=#

"""
  bdy_nodes(dims)

Boundary node computation, for arbitrary dimension

...
# Arguments

  - `dims::Tuple` number of points in each direction
...

...
# Outputs
  - `Vector{Int64}`: vector containing the indices of coordinates 
  on the boundary of the hyperrectangle volume
...

"""
function bdy_nodes(dims::Tuple)
    D = length(dims)
    bdy = CartesianIndex[]
    for d in CartesianIndices(dims)
        if (sum(Tuple(d) .== 1) > 0) || (sum(Tuple(d) .== dims) > 0) 
            push!(bdy, d)
        end
    end
    neighbors = zeros(Int64, length(bdy), D)
    for (j, b) in enumerate(bdy)
        for i in 1:D
          neighbors[j, i] = ((Tuple(b)[i] == 1)||(Tuple(b)[i] == dims[i])) ? 1 : 2
        end
    end
    return bdy, neighbors
end

""" Write the matrix """
function nablasq_arb(dims, aspect_ratios)
  D = length(dims)
  oh = map(i -> ones(dims[i])/aspect_ratios[i], 1:length(dims))
  del = Vector{SparseArrays.SparseMatrixCSC{Float64, Int64}}(undef, D)
  for (i, d) in enumerate(dims)
    del[i] = spdiagm_nonsquare(d + 1, d, -1 => -oh[i], 0 => oh[i])
  end
  A = zeros(prod(dims), prod(dims))
  for i in 1:D
      A += kron([sparse(I, dims[j], dims[j]) for j in 1:(i-1)]..., del[i]'*del[i],
                [sparse(I, dims[j], dims[j]) for j in (i+1):D]...)
  end
  bdy, neighbors = bdy_nodes(dims)
  for (count, b) in enumerate(bdy)
    i = LinearIndices(zeros(dims...))[b]
    A[i, i] = 0.0
    for j in 1:D
      A[i, i] += neighbors[count, j] / aspect_ratios[j] ^ 2
    end
  end
  return A
end

""" Helper function to give the Matern matrix in arbitrary dimensions """
function _Matern_matrix(dims, m, eps, aspect_ratios)
    A = nablasq_arb(dims, aspect_ratios) 
    sizeA = size(A, 1)
    for i = 1:sizeA
        A[i, i] = A[i, i] + eps^2
    end
    return A^m
end

""" Compute the interpolation """
function interp(data, ind, m, eps, aspect_ratios) 
    dims = size(data)
    A = (eps == 0.0)&&(m == 1) ? 
                nablasq_arb(dims, aspect_ratios) :
                _Matern_matrix(dims, m, eps, aspect_ratios) 
    totalsize = prod(dims)
    C = sparse(I, totalsize, totalsize)
    rhs_a = data[:]
    for i in ind
        j = (typeof(i) <: CartesianIndex) ? LinearIndices(data)[i] : i
        C[j, j] = 0.0
        rhs_a[j] = 0.0
    end
    Id = sparse(I, totalsize, totalsize)    
    u = ((C - (Id - C) * A)) \ rhs_a
    return reshape(u, dims...)
end     
