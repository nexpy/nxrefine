
# Julia code
using LinearAlgebra, Roots

function rotmat(axis, angle)
    cang = cos(pi*angle/180)        
    sang = sin(pi*angle/180)
    if axis == 1
        mat = [1.0 0 0; 0 cang -sang; 0 sang cang]
    elseif axis == 2
        mat = [cang 0.0 sang; 0.0 1.0 0.0; -sang 0.0 cang]
    else
        mat = [cang -sang 0.0; sang cang 0.0; 0.0 0.0 1.0]
    end
    if angle ≈ 0.0
        mat = diagm(ones(3))
    end
    return mat
end
        
# vec function is replaced with vcat
function vec(x,y=0.0,z=0.0)
    return vcat(x,y,z)
end

Gmat(phi) = Gmat0 * rotmat(3, phi)
norm_Evec2 = norm(Evec)^2

function get_xyz(h,k,l)
    phis = Array{Float64,1}(undef,2)
    if !((h==0)&&(k==0)&&(l==0))
        v5 = UBmat*vec(h,k,l)
        function ewald_condition(phi) 
            return (norm_Evec2 - norm((Gmat(phi)*v5 + Evec))^2)
        end
        phis = unique(round.(filter(x-> (x!=nothing)&&(x<360.0)&&(x>=0.0), map(x-> try find_zero(ewald_condition,(x,x+30),Bisection()); catch; nothing end,0.0:30:270)),digits=4))

        function get_ij(phi) 
            p = Gmat(phi)*v5 + Evec
            normalize!(p)
            v3 = -(Dvec[1,1]/p[1,1]) *p
            v2 = Dmat*(v3+Dvec)
            v1 = Omat*v2+Cvec
            return (v1[1], v1[2])
        end
        peaks = Tuple{Float64,Float64,Float64,Int64,Int64,Int64}[]
        for phi in phis
            x,y = get_ij(phi)
            z = ((phi+5.0)/0.1)%3600
            z += (z<25.0)*3600.0 .+ (z>3625.0)*(-3600.0)  
            if (x > 0)&&(x < shape[2])&&(y > 0)&&(y < shape[1])
                push!(peaks,(x, y, z, h, k, l))
            end
        end
        return peaks
    else
        skip;
    end
end

function get_xyzs(Qh,Qk,Ql)
    return map(i->get_xyz(i...),Iterators.product(-Qh:Qh,-Qk:Qk,-Ql:Ql))[:]
end