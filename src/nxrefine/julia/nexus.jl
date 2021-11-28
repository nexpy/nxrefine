
"""
  punch_holes_nexus(xpoints, ypoints, zpoints, radius)

...
# Arguments

  - `xpoints::Vector{T} where T<:Real`: the vector containing the x coordinate
  - `ypoints::Vector{T} where T<:Real`: the vector containing the y coordinate
  - `zpoints::Vector{T} where T<:Real`: the vector containing the z coordinate
  - `radius::Union{Float64,Vector{Float64}}`: the radius, or radii of the punch, if vector.
...

...
# Outputs


  - `absolute_indices::Vector{Int64}`: vector containing the indices of coordinates 
  inside the punch

...
"""
function punch_holes_nexus(xpoints, ypoints, zpoints, radius)
    rad = (typeof(radius) <: Tuple) ? radius : (radius, radius, radius)
    radius_x, radius_y, radius_z = rad 
    absolute_indices = Int64[]
    count = 1
    for i = 1:length(zpoints)
        ir = round(zpoints[i])
        for j = 1:length(ypoints)
            jr = round(ypoints[j])
            for h = 1:length(xpoints)
                hr = round(xpoints[h])
                if (((hr - xpoints[h])/radius_x)^2 + ((jr - ypoints[j])/radius_y)^2 + ((ir - zpoints[i])/radius_z)^2 <= 1.0)
                    append!(absolute_indices, count)
                end
                count=count+1
            end
        end
    end
    return absolute_indices
end

"""
  punch_holes_nexus_Cartesian(x, y, z, radius)

...
# Arguments

  - `x::Vector{T} where T<:Real`: the vector containing the x coordinate
  - `y::Vector{T} where T<:Real`: the vector containing the y coordinate
  - `z::Vector{T} where T<:Real`: the vector containing the z coordinate
  - `radius::Union{Float64,Tuple{Float64}}`: the radius, or radii of the punch, if vector.
...

...
# Outputs

  - `inds::Vector{Int64}`: vector containing the indices of coordinates 
  inside the punch

...
"""
function punch_holes_nexus_Cartesian(x, y, z, radius)
    radius_x, radius_y, radius_z = (typeof(radius) <: Tuple) ? radius : (radius, radius, radius)
    inds = filter(i -> (((x[i[1]] - round(x[i[1]])) / radius_x) ^2 
                        + ((y[i[2]] - round(y[i[2]])) / radius_y) ^2 
                        + ((z[i[3]] - round(z[i[3]])) / radius_z) ^2 <= 1.0),
                  CartesianIndices((1:length(x), 1:length(y), 1:length(z))))
    return inds
end

"""

  interp_1lu(x, y, z, imgg, punch_template, eps, m)

Interpolate around the bragg peaks in the image by tiling the punch_template

...
# Arguments
  - `x::Vector{T} where T<:Real`: the vector containing the x coordinate
  - `y::Vector{T} where T<:Real`: the vector containing the y coordinate
  - `z::Vector{T} where T<:Real`: the vector containing the z coordinate
  - `imgg::Array{Float64,3]`: the matrix containing the image
  - `punch_template::Array{Float64,3}`: one lattice unit template of the values to be filled 
  - `eps::Float64 = 0.0`: Matern parameter eps
  - `m::Int64 = 1` : Matern parameter 

# Outputs
  - array containing the interpolated image 
...
"""
function interp_1lu(x, y, z, imgg, punch_template, eps, m)
  discard = findall(punch_template .> 0)
  res = interp(x, y, z, imgg, discard, eps, m)
  return res
end

"""

  interp_nexus(x, y, z, imgg, punch_template, eps, m)

Interpolate around the bragg peaks in the image by tiling the punch_template

...
# Arguments
  - `x::Vector{T} where T<:Real`: the vector containing the x coordinate
  - `y::Vector{T} where T<:Real`: the vector containing the y coordinate
  - `z::Vector{T} where T<:Real`: the vector containing the z coordinate
  - `imgg::Array{Float64,3]`: the matrix containing the image
  - `punch_template::Array{Float64,3}`: one lattice unit template of the values to be filled 
  - `eps::Float64 = 0.0`: Matern parameter eps
  - `m::Int64 = 1` : Matern parameter 

# Outputs
  - array containing the interpolated image 
...

# Example

```<julia-repl>
x = y = z = collect(-0.5:0.1:10)
imgg = randn(length(x), length(y), length(z))
punch_template = zeros(10, 10, 10); punch_template[5, 5, 5] = 1
interp_nexus(x, y, z, imgg, punch_template)
```
"""
function interp_nexus(x, y, z, imgg, punch_template, eps = 0.0, m = 1)
  discard = findall(punch_template .> 0)
  x_unit, y_unit, z_unit = size(punch_template)
  Nx, Ny, Nz = size(imgg)
  Qx = ceil(x[end]) + 1 
  Qy = ceil(y[end]) + 1
  Qz = ceil(z[end]) + 1
  corners_x = findall((x .- 0.5) .% 1 .== 0.0)
  corners_y = findall((y .- 0.5) .% 1 .== 0.0)
  corners_z = findall((z .- 0.5) .% 1 .== 0.0)
  corners = [CartesianIndex(xind, yind, zind) for xind in corners_x[1:end-1] 
                                              for yind in corners_y[1:end-1]
                                              for zind in corners_y[1:end-1]]
  # punched = copy(imgg);
  # Threads.@threads for (i,c) in enumerate(corners)
  for (i,c) in enumerate(corners)
    tcx = minimum([Nx, Tuple(c)[1] + x_unit])
    tcy = minimum([Ny, Tuple(c)[2] + y_unit])
    tcz = minimum([Nz, Tuple(c)[3] + z_unit])
    tc = CartesianIndex(tcx, tcy, tcz)
    imgg[c:tc] = interp(x[c[1]:tc[1]], y[c[2]:tc[2]], z[c[3]:tc[3]], 
                       imgg[c:tc], discard, Float64(eps), Int64(m))
    # punched[c:tc] .= 0.0
  end
  return imgg
end
