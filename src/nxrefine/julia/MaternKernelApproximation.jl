
# functions: return_boundary_nodes, 
# Matern_3d_Grid, Laplace_3D_grid,
# Parallel_Matern_3DGrid

"""
  return_boundary_nodes(xpoints, ypoints, zpoints)

...
# Arguments

  - `xpoints::Vector{T} where T<:Real`: the vector containing the x coordinate
  - `ypoints::Vector{T} where T<:Real`: the vector containing the y coordinate
  - `zpoints::Vector{T} where T<:Real`: the vector containing the z coordinate
...

...
# Outputs
  - `BoundaryNodes3D::Vector{Int64}`: vector containing the indices of coordinates 
  on the boundary of the rectangular 3D volume
...

"""
function return_boundary_nodes(xpoints, ypoints, zpoints)
    BoundaryNodes3D =[]
    xneighbors = []
    yneighbors = []
    zneighbors = []
    counter = 0
    for k = 1:zpoints
        for j = 1:ypoints
            for i = 1:xpoints
                counter=counter+1
                if(k == 1 || k == zpoints || j == 1|| j == ypoints || i == 1 || i == xpoints)
                    BoundaryNodes3D = push!(BoundaryNodes3D, counter)
                    if(k == 1 || k == zpoints)
                        push!(zneighbors, 1)
                    else
                        push!(zneighbors, 2)
                    end
                    if(j == 1 || j == ypoints)
                        push!(yneighbors, 1)
                    else
                        push!(yneighbors, 2)
                    end
                    if(i == 1 || i == xpoints)
                        push!(xneighbors, 1)
                    else
                        push!(xneighbors, 2)
                    end
                end
            end
        end
    end
    return BoundaryNodes3D, xneighbors, yneighbors, zneighbors
end

"""

  Matern3D_Grid(xpoints, ypoints, zpoints, imgg, epsilon, radius, h, k, l, m)

...
# Arguments
  - `xpoints::Vector{T} where T<:Real`: the vector containing the x coordinate
  - `ypoints::Vector{T} where T<:Real`: the vector containing the y coordinate
  - `zpoints::Vector{T} where T<:Real`: the vector containing the z coordinate
  - `imgg`: the matrix containing the image
  - `epsilon`: Matern parameter epsilon
  - `radius::Vector`: the tuple containing the punch radii 
  - `h::Float`: grid spacing along the x-axis
  - `k::Float`: grid spacing along the y-axis
  - `l::Float`: grid spacing along the z-axis
  - `m::Int` : Matern parameter 

# Outputs
  - tuple containing the restored image and the punched image.
...

"""
function Matern3D_Grid(xpoints, ypoints, zpoints, imgg, epsilon, radius, h, k, l, m)
    A3D = nablasq_3d_grid(length(xpoints), length(ypoints), length(zpoints), h, k, l)
    sizeA = size(A3D, 1)
    for i = 1:sizeA
        A3D[i, i] = A3D[i, i] + epsilon^2
    end
    A3DMatern = A3D
    for i = 1:m - 1
        A3DMatern = A3DMatern * A3D
    end
    discard = punch_holes_nexus(xpoints, ypoints, zpoints, radius)
    punched_image = copy(imgg)
    punched_image[discard] .= 1
    totalsize = prod(size(imgg))
    C = sparse(I, totalsize, totalsize)
    rhs_a = punched_image[:]
    for i in discard
        C[i, i] = 0
        rhs_a[i] = 0
    end
    Id = sparse(I, totalsize, totalsize)    
    u = ((C - (Id - C) * A3DMatern)) \ rhs_a
    return (u, punched_image[:])
end

"""

  Laplace3D_Grid(xpoints, ypoints, zpoints, imgg, radius, h, k, l)

...
# Arguments
  - `xpoints::Vector{T} where T<:Real`: the vector containing the x coordinate
  - `ypoints::Vector{T} where T<:Real`: the vector containing the y coordinate
  - `zpoints::Vector{T} where T<:Real`: the vector containing the z coordinate
  - `imgg`: the matrix containing the image
  - `radius::Vector`: the tuple containing the punch radii 
  - `h::Float`: grid spacing along the x-axis
  - `k::Float`: grid spacing along the y-axis
  - `l::Float`: grid spacing along the z-axis

# Outputs
  - tuple containing the restored image and the punched image.
...

"""
function Laplace3D_Grid(xpoints, ypoints, zpoints, imgg, radius, h, k, l)
    A3D = nablasq_3d_grid(length(xpoints), length(ypoints), length(zpoints), h, k, l)
    discard = punch_holes_nexus(xpoints, ypoints, zpoints, radius)
    punched_image = copy(imgg)
    punched_image[discard] .= 1
    totalsize = prod(size(imgg))
    C = sparse(I, totalsize, totalsize)
    rhs_a = punched_image[:]
    for i in discard
        C[i,i] = 0
        rhs_a[i] = 0
    end
    Id = sparse(I, totalsize, totalsize)
    u = ((C - (Id - C) * A3D)) \ rhs_a
    return u, punched_image[:]
end

"""

  Parallel_Laplace3D_Grid(xpoints, ypoints, zpoints, imgg, radius, h, k, l,
          xmin, xmax, ymin, ymax, zmin, zmax)

Compute the spherically-punched, Laplace-interpolated 3D data

...
# Arguments
  - `xpoints::Vector{T} where T<:Real`: the vector containing the x coordinate
  - `ypoints::Vector{T} where T<:Real`: the vector containing the y coordinate
  - `zpoints::Vector{T} where T<:Real`: the vector containing the z coordinate
  - `imgg`: the matrix containing the image
  - `radius::Vector`: the tuple containing the punch radii 
  - `h::Float`: grid spacing along the x-axis
  - `k::Float`: grid spacing along the y-axis
  - `l::Float`: grid spacing along the z-axis
  - `xmin::Int64`: Vishwas should fill in the next six fields. 
  - `xmax::Int64`:
  - `ymin::Int64`:
  - `ymax::Int64`:
  - `zmin::Int64`:
  - `zmax::Int64`:

# Outputs
  - array containing the restored image 

# Example 

```julia-repl
(xmin, xmax) = (ymin, ymax) = (zmin,zmax) = (0.0, 1.0)
xpoints = ypoints = zpoints = -0.2:0.2:1.2
h = k = l = 0.2
imgg = randn(8,8,8)
radius = 0.2
restored = Parallel_Laplace3D_Grid(xpoints, ypoints, zpoints, imgg, radius, 
                                 h, k, l, xmin, xmax, ymin, ymax, zmin, zmax)
```

...

"""
function Parallel_Laplace3D_Grid(xpoints::Union{StepRangeLen{T},Vector{T}}, 
                                ypoints::Union{StepRangeLen{T},Vector{T}}, 
                                zpoints::Union{StepRangeLen{T},Vector{T}}, 
                                imgg::Array{P,3}, 
                                radius::Union{Q,Tuple{Q,Q,Q}}, 
                                h::Float64, k::Float64, l::Float64, 
                                xmin::R, xmax::R, ymin::R, ymax::R, zmin::R, zmax::R 
                                ) where{T<:Number,P<:Number,Q<:Number,R<:Number}
  # 
  fun(x,y,z,w) = Int(round((x -y)/z) - w ) 
  ran(x,y,z,w) = fun(x, y, z, w) .+ (0, 2*w + 1)
  #
  rad = (typeof(radius) <: Tuple) ? radius : (radius, radius, radius)
  radius_x, radius_y, radius_z = rad 
  stride_h = Int64(round(radius_x / h))
  stride_k = Int64(round(radius_y / k))
  stride_l = Int64(round(radius_z / l))
  cartesian_product_boxes = [(ran(i, xpoints[1], h, stride_h)..., 
                              ran(j, ypoints[1], k, stride_k)...,
                              ran(kk, zpoints[1], l, stride_l)...)  
                         for i in xmin:xmax for j in ymin:ymax for kk in zmin:zmax]
  #
  z3d_restored = copy(imgg)
  #
  Threads.@threads for i = 1:length(cartesian_product_boxes)
    i1, i2, j1, j2, k1, k2 = cartesian_product_boxes[i]
    restored_img = Laplace3D_Grid(xpoints[i1 + 1:i2], ypoints[j1 + 1:j2], 
                           zpoints[k1 + 1:k2], 
                           imgg[i1 + 1:i2, j1 + 1:j2, k1 + 1:k2], 
                           radius, h, k, l)[1]
    z3d_restored[i1 + 1:i2, j1 + 1:j2, k1 + 1:k2] = reshape(restored_img, 
                           (2 * stride_h + 1, 2 * stride_k + 1, 2 * stride_l + 1))
  end
  #
  return z3d_restored[:]
  #
end

"""

  Parallel_Matern3D_Grid(xpoints, ypoints, zpoints, imgg, epsilon, radius, h, k, l,
          xmin, xmax, ymin, ymax, zmin, zmax, m)

Compute the spherically-punched, Matern-interpolated 3D data

...
# Arguments
  - `xpoints::Vector{T} where T<:Real`: the vector containing the x coordinate
  - `ypoints::Vector{T} where T<:Real`: the vector containing the y coordinate
  - `zpoints::Vector{T} where T<:Real`: the vector containing the z coordinate
  - `imgg`: the matrix containing the image
  - `epsilon`: one of the matern parameters
  - `radius::Vector`: the tuple containing the punch radii 
  - `h::Float`: grid spacing along the x-axis
  - `k::Float`: grid spacing along the y-axis
  - `l::Float`: grid spacing along the z-axis
  - `xmin::Int64`: Vishwas should fill in the next six fields. 
  - `xmax::Int64`:
  - `ymin::Int64`:
  - `ymax::Int64`:
  - `zmin::Int64`:
  - `zmax::Int64`:
  - `m::Int64`: The matern order parameter 

# Outputs
  - array containing the restored image 

# Example 

```julia-repl
(xmin, xmax) = (ymin, ymax) = (zmin,zmax) = (0.0, 1.0)
xpoints = ypoints = zpoints = -0.2:0.2:1.2
h = k = l = 0.2
imgg = randn(8,8,8)
m = 2
epsilon = 0.0
radius = 0.2
restored = Parallel_Matern3D_Grid(xpoints, ypoints, zpoints, imgg, epsilon, radius, 
                                  h, k, l, xmin, xmax, ymin, ymax, zmin, zmax, m)
```

...

"""
function Parallel_Matern3D_Grid(xpoints::Union{StepRangeLen{T},Vector{T}}, 
                                ypoints::Union{StepRangeLen{T},Vector{T}}, 
                                zpoints::Union{StepRangeLen{T},Vector{T}}, 
                                imgg::Array{P,3}, epsilon::Q, 
                                radius::Union{Q,Tuple{Q,Q,Q}}, 
                                h::Float64, k::Float64, l::Float64, 
                                xmin::R, xmax::R, ymin::R, ymax::R, zmin::R, zmax::R, 
                                m::Int) where{T<:Number,P<:Number,Q<:Number,R<:Number}
  # 
  fun(x,y,z,w) = Int(round((x -y)/z) - w ) 
  ran(x,y,z,w) = fun(x, y, z, w) .+ (0, 2*w + 1)
  #
  rad = (typeof(radius) <: Tuple) ? radius : (radius, radius, radius)
  radius_x, radius_y, radius_z = rad 
  stride_h = Int64(round(radius_x / h))
  stride_k = Int64(round(radius_y / k))
  stride_l = Int64(round(radius_z / l))
  cartesian_product_boxes = [(ran(i, xpoints[1], h, stride_h)..., 
                              ran(j, ypoints[1], k, stride_k)...,
                              ran(kk, zpoints[1], l, stride_l)...)  
                         for i in xmin:xmax for j in ymin:ymax for kk in zmin:zmax]
  #
  z3d_restored = copy(imgg)
  #
  Threads.@threads for i = 1:length(cartesian_product_boxes)
    i1, i2, j1, j2, k1, k2 = cartesian_product_boxes[i]
    restored_img = Matern3D_Grid(xpoints[i1 + 1:i2], ypoints[j1 + 1:j2], 
                           zpoints[k1 + 1:k2], 
                           imgg[i1 + 1:i2, j1 + 1:j2, k1 + 1:k2], 
                           epsilon, radius, h, k, l, m)[1]
    z3d_restored[i1 + 1:i2, j1 + 1:j2, k1 + 1:k2] = reshape(restored_img, 
                           (2 * stride_h + 1, 2 * stride_k + 1, 2 * stride_l + 1))
  end
  #
  return z3d_restored[:]
  #
end

# function Parallel_Matern3D_Grid(xpoints, ypoints, zpoints, imgg, epsilon, radius, h, k, l, xmin, xmax, ymin, ymax, zmin, zmax, m)
#   xbegin = xpoints[1];
#   ybegin = ypoints[1];
#   zbegin = zpoints[1];
#   cartesian_product_boxes = [];
#   stride = Int(round(radius/h));
#   z3d_restored = copy(imgg);
#   for i = xmin:xmax+1
#       i1 = Int(round((i-xbegin) /h))-stride;
#       i2 = i1+2*stride+1;
#       for j = ymin:ymax+1
#           j1 = Int(round((j-ybegin)/h))-stride;
#           j2 = j1+2*stride+1;
#           for k = zmin:zmax+1
#               k1 = Int(round((k-ybegin)/h)) - stride;
#               k2 = k1+2*stride+1;
#               append!(cartesian_product_boxes,[(i1,i2,j1,j2,k1,k2)]);
#           end
#       end
#   end

#   Threads.@threads for i = 1:length(cartesian_product_boxes)
#     i1 = cartesian_product_boxes[i][1];
#     i2 = cartesian_product_boxes[i][2];
#     j1 = cartesian_product_boxes[i][3];
#     j2 = cartesian_product_boxes[i][4];
#     k1 = cartesian_product_boxes[i][5];
#     k2 = cartesian_product_boxes[i][6];
#     z3temp = imgg[i1+1:i2,j1+1:j2,k1+1:k2];
#     restored_img, punched_image = Matern3D_Grid(xpoints[i1+1:i2], ypoints[j1+1:j2], zpoints[k1+1:k2], z3temp, epsilon, radius, h, k, l, m);
#     restored_img_reshape = reshape(restored_img, (2*stride+1,2*stride+1,2*stride+1));
#     z3d_restored[i1+1:i2, j1+1:j2, k1+1:k2] = restored_img_reshape;
#   end
#   return z3d_restored[:];
# end


