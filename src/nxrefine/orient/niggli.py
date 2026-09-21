import numpy as np
from numpy.linalg import norm
from .orientedlattice import get_UB, get_abc


def angle_cal(a:np.ndarray, b:np.ndarray) -> float:
    """Calculate the angle between two vectors, unit: radian"""
    cos_angle = np.dot(a, b) / (norm(a) * norm(b))
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    return np.arccos(cos_angle)

def abc_norm_sum(UB:np.ndarray) -> float:
    """total side length |a|+|b|+|c|"""
    _, a, b, c = get_abc(UB)
    return norm(a) + norm(b) + norm(c)

def diff_from_90(UB: np.ndarray) -> float:
    """total angle difference from 90 degrees"""
    invertable, a, b, c = get_abc(UB)
    if not invertable:
        return -1
    
    alpha = np.degrees(angle_cal(b, c))
    beta = np.degrees(angle_cal(c, a))
    gamma = np.degrees(angle_cal(a, b))

    return abs(alpha - 90) + abs(beta - 90) + abs(gamma - 90)

def has_Niggli_angles(a:np.ndarray, b:np.ndarray, c:np.ndarray, epsilon:float) -> bool:
    """Geometry/Crystal/NiggliCell::HasNiggliAngles - line 154 to 168
    
    Check if a,b,c cell has angles satifying Niggli condition within epsilon.
    Specifically, check if all angles are strictly less than 90 degrees,
    or all angles are greater than or equal to 90 degrees. The inequality
    requirements are relaxed by an amount specified by the paramter epsilon
    to accommodate some experimental and/or rounding error in the calculated
    angles.

    Parameters
    ----------
    a: np.ndarray
        Vector in the direction of the real cell edge vector 'a'
    b: np.ndarray
        Vector in the direction of the real cell edge vector 'b'
    c: np.ndarray
        Vector in the direction of the real cell edge vector 'c'
    epsilon: float
        Tolerance (in degrees) around 90 degrees. For example
        an angle theta will be considered strictly less than 90
        degrees, if it is less than 90+epsilon.
    """
    alpha = np.degrees(angle_cal(b, c))
    beta = np.degrees(angle_cal(c, a))
    gamma = np.degrees(angle_cal(a, b))

    if (alpha < 90 + epsilon) and (beta < 90 + epsilon) and (gamma < 90 + epsilon):
        return True
    if (alpha >= 90 - epsilon) and (beta >= 90 - epsilon) and (gamma >= 90 - epsilon):
        return True
    
    return False

def make_Niggli_UB(UB:np.ndarray) -> tuple[bool, np.ndarray]:
    """Geometry/Crystal/NiggliCell::MakeNiggliUB - line 451 to 524

    Try to find a UB that is equivalent to the original UB, but corresponds to a Niggli 
    reduced cell with the smallest sum of edge lengths and with angles that are farthest 
    from 90 degrees.

    If a possibly constructive change was made, the function returns True and a new UB 
    matrix. If no constructive change was found, it returns False and the original UB.

    Parameters
    ----------
    UB: np.ndarray
        the original UB
    """
    invertable, a, b, c = get_abc(UB)
    if not invertable:
        return False, UB
    # make a list of linear combinations of vectors a,b,c with coefficients up to 5
    N_coeff = 5
    directions = [
        a*i + b*j + c*k 
        for i in range(-N_coeff, N_coeff+1) 
        for j in range(-N_coeff, N_coeff+1) 
        for k in range(-N_coeff, N_coeff+1) 
        if not (i==0 and j==0 and k==0)
    ]
    # sort the list of linear combinations in order of increasing length
    directions.sort(key=lambda v: norm(v))
    # form a list of possible UB matrices using sides from the list of linear combinations, 
    # using shorter directions first. Keep trying more until 25 UBs are found. Only keep 
    # UBs corresponding to cells with at least a minimum cell volume
    UB_list = []
    num_needed = 25
    max_to_try = 5
    while (len(UB_list) < num_needed and max_to_try < len(directions)):
        max_to_try *= 2
        num_to_try = min(max_to_try, len(directions))

        min_vol = 0.1
        for i in range(0, num_to_try-2):
            a = directions[i]
            for j in range(i+1, num_to_try-1):
                b = directions[j]
                acrossb = np.cross(a, b)
                candidates = np.array(directions[j+1:num_to_try])
                vols = candidates@acrossb
                mask = vols > min_vol
                for c in candidates[mask]:
                    if has_Niggli_angles(a, b, c ,0.01):
                        _, new_tran = get_UB(a, b, c)
                        UB_list.append(new_tran)
    # if no valid UBs could be formed, return false and the original UB
    if len(UB_list) == 0:
        new_UB = UB
        return False, new_UB
    # sort the UB's in order of increasing total side length |a|+|b|+|c|
    UB_list.sort(key=abc_norm_sum)
    # keep only those UB's with total side length within .1% of the first one. This 
    # can't be much larger or "bad" UBs are made for some tests with 5% noise
    length_tol = 0.001
    short_list = []
    short_list.append(UB_list[0])
    total_length = abc_norm_sum(short_list[0])
    for i in range(1, len(UB_list)):
        next_length = abc_norm_sum(UB_list[i])
        if abs(next_length - total_length)/total_length < length_tol:
            short_list.append(UB_list[i])
        else:
            break
    # sort on the basis of difference of cell angles from 90 degrees 
    # and return the one with angles most different from 90
    short_list.sort(key=diff_from_90, reverse=True)
    new_UB = short_list[0]

    return True, new_UB