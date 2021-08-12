

"""
  punch_holes_2D(centers, radius, xpoints, ypoints)

...
# Arguments

  - `centers::Union{Vector}`: the vector containing the punch centers
  - `radius::Vector`: the tuple containing the punch radii 
  - `Nx::Int64`: the number of points in the x direction
  - `Ny::Int64`: the number of points in the y direction
...

...
# Outputs
  - `absolute_indices::Vector{Int64}`: vector containing the indices of coordinates 
  inside the punch
...

"""
function punch_holes_2D(centers, radius::Union{T, Vector{T}}, 
                        Nx, Ny) where T<:Number
    clen = (typeof(centers) <: Vector) ? length(centers) : 1
    rad  = (typeof(radius) <: Vector) ? radius : radius * ones(clen)
    masking_data_points = []
    absolute_indices = Int64[]
    for a = 1:clen
        c = centers[a]
        count = 1
        for j = 1:Ny
            for h = 1:Nx
                if (((h-c[1]))^2 + ((j-c[2]))^2  <= radius[a]^2)
                    append!(masking_data_points,[(h,j)])
                    append!(absolute_indices, count)
                end
                count = count + 1
            end
        end
    end
    return absolute_indices
end

"""
  punch_holes_3D(centers, radius, xpoints, ypoints, zpoints)

...
# Arguments

  - `centers::Vector{T}`: the vector containing the centers of the punches
  - `radius::Float64`: the radius of the punch
  - `Nx::Int64`: the number of points in the x-direction, this code is hard-coded to start from one. 
  - `Ny::Int64`: the number of points in the y-direction
  - `Nz::Int64`: the number of points in the z-direction
...

...
# Outputs
  - `absolute_indices::Vector{Int64}`: vector containing the indices of coordinates 
  inside the punch
...

"""
function punch_holes_3D(centers, radius, Nx, Ny, Nz)
    clen = length(centers)
    masking_data_points = []
    absolute_indices = Int64[]
    for a = 1:clen
        c = centers[a]
        count = 1
        for i = 1:Nz
            for j = 1:Ny
                for h = 1:Nx
                    if((h-c[1])^2 + (j-c[2])^2 + (i - c[3])^2 <= radius^2)
                        append!(masking_data_points, [(h, j, i)])
                        append!(absolute_indices, count)
                    end
                    count = count +1
                end
            end
        end
    end
    return absolute_indices
end

"""
  punch_3D_cart(center, radius, xpoints, ypoints, zpoints; <kwargs>)

...
# Arguments

  - `center::Tuple{T}`: the tuple containing the center of a round punch
  - `radius::Union{Tuple{Float64},Float64}`: the radii/radius of the punch
  - `x::Vector{T} where T<:Real`: the vector containing the x coordinate
  - `y::Vector{T} where T<:Real`: the vector containing the y coordinate
  - `z::Vector{T} where T<:Real`: the vector containing the z coordinate

# Optional

  - `linear::Bool = false` can return a linear index
...

...
# Outputs
  - `inds::Vector{Int64}`: vector containing the indices of coordinates 
  inside the punch
...

"""
function punch_3D_cart(center, radius, x, y, z; linear = false)
    radius_x, radius_y, radius_z = (typeof(radius) <: Tuple) ? radius : 
                                                (radius, radius, radius)
    inds = filter(i -> (((x[i[1]]-center[1])/radius_x)^2 
                        + ((y[i[2]]-center[2])/radius_y)^2 
                        + ((z[i[3]] - center[3])/radius_z)^2 <= 1.0),
                  CartesianIndices((1:length(x), 1:length(y), 1:length(z))))
    (length(inds) == 0) && error("Empty punch.")
    if linear == false
      return inds
    else
      return LinearIndices(zeros(length(x), length(y), length(z)))[inds]
    end
end

function bounding_box(x::Array{CartesianIndex{3},1})
    #for i in 1:p
    xa = map(t -> t[1], x); xa_min, xa_max = (minimum(xa), maximum(xa))
    xb = map(t -> t[2], x); xb_min, xb_max = (minimum(xb), maximum(xb))
    xc = map(t -> t[3], x); xc_min, xc_max = (minimum(xc), maximum(xc))
    # This requires julia v 1.6
    # return CartesianIndices((xa_min:xa_max, xb_min:xb_max, xc_min:xc_max))
    list = [CartesianIndex(x,y,z) for x in xa_min:xa_max for y in xb_min:xb_max for z in xc_min:xc_max]
    return list
end

intersect_box(A, B) = maximum([minimum(A), minimum(B)]):minimum([maximum(A), maximum(B)])

my_floor(x) = (x>0) ? floor(x) : -floor(abs(x))

"""
 
Generate a list of centers

# Example

```<julia-repl>
xmin = 0
xmax = 6
ymin = 0
ymax = 8
zmin = 0
zmax = 8

centers = LaplaceInterpolation.center_list('A', xmin, xmax, ymin, ymax, zmin,
zmax)
```
"""
function center_list(symm, Qh_min, Qh_max, Qk_min, Qk_max, Ql_min, Ql_max)
    hs = my_floor(Qh_min):my_floor(Qh_max)
    ks = my_floor(Qk_min):my_floor(Qk_max)
    ls = my_floor(Ql_min):my_floor(Ql_max)
    hkl = [(h,k,l) for h in hs for k in ks for l in ls]
    if symm == 'P'
        centers = filter(i -> ~P(i...), hkl)
    elseif symm == 'A'
        centers = filter(i -> ~A(i...), hkl)
    elseif symm == 'B'
        centers = filter(i -> ~B(i...), hkl)
    elseif symm == 'C'
        centers = filter(i -> ~C(i...), hkl)
    elseif symm == 'I'
        centers = filter(i -> ~Ii(i...), hkl)
    elseif symm == 'F'
        centers = filter(i -> ~F(i...), hkl)
    elseif symm == 'R'
        centers = filter(i -> ~R(i...), hkl)
    else
        centers = hkl 
    end
    return centers
end 

function center_check(symm)
    if symm == 'P'
        tof = (h, k, l) -> ~P(h, k, l)
    elseif symm == 'A'
        tof = (h, k, l) -> ~A(h, k, l)
    elseif symm == 'B'
        tof = (h, k, l) -> ~B(h, k, l)
    elseif symm == 'C'
        tof = (h, k, l)-> ~C(h, k, l)
    elseif symm == 'I'
        tof = (h, k, l) -> ~Ii(h, k, l)
    elseif symm == 'F'
        tof = (h, k, l) -> ~F(h, k, l)
    elseif symm == 'R'
        tof = (h, k, l) -> ~R(h, k, l)
    else
        tof = (h, k, l) -> true 
    end
    return tof
end

# Systematic absences

function P(h,k,l)
    return false
end

function A(h,k,l)
    return (k+l)%2 != 0
end

function B(h,k,l)
    return (h+l)%2 != 0
end

function C(h,k,l)
    return (h+k)%2 != 0
end

function Ii(h,k,l)
    return (h+k+l)%2 != 0
end

function F(h,k,l)
    return ((h+k)%2!=0)||((h+l)%2!=0)||((k+l)%2!=0)
end

function R(h,k,l)
    return (-h+k+l)%3 != 0
end
