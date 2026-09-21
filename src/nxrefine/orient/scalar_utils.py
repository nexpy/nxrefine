import numpy as np
from numpy.linalg import norm
from .conventional import ConventionalCell
from .orientedlattice import get_abc, get_UB, set_UB
from .niggli import angle_cal
from .reduced import reduced_cell
from .conventional import ConventionalCell


NUM_CELL_TYPES = 44

BRAVAIS_TYPE = [
    'CUBIC', # F
    'CUBIC', # I
    'CUBIC', # P

    'HEXAGONAL', # P

    'RHOMBOHEDRAL', # R

    'TETRAGONAL', # I
    'TETRAGONAL', # P

    'ORTHORHOMBIC', # F
    'ORTHORHOMBIC', # I
    'ORTHORHOMBIC', # C
    'ORTHORHOMBIC', # P

    'MONOCLINIC', # C
    'MONOCLINIC', # I
    'MONOCLINIC', # P

    'TRICLINIC' # P
]

BRAVAIS_CENTERING = [
    'F_CENTERED', # cubic
    'I_CENTERED', # cubic
    'P_CENTERED', # cubic

    'P_CENTERED', # hexagonal

    'R_CENTERED', # rhombohedral

    'I_CENTERED', # tetragonal
    'P_CENTERED', # tetragonal

    'F_CENTERED', # orthorhombic
    'I_CENTERED', # orthorhombic
    'C_CENTERED', # orthorhombic
    'P_CENTERED', # orthorhombic

    'C_CENTERED', # monoclinic
    'I_CENTERED', # monoclinic
    'P_CENTERED', # monoclinic

    'P_CENTERED' # triclinic
]

def get_cells(UB:np.ndarray, best_only:bool, allowPermutations:bool):
    """Geometry/Crystal/ScalarUtils::GetCells - line 91 to 107"""
    num_lattices = 15
    results = []
    for i in range(num_lattices):
        temp = get_cells_by_cell_type(UB, BRAVAIS_TYPE[i], BRAVAIS_CENTERING[i], allowPermutations)
        if best_only:
            cell_info = get_cell_best_error(temp, True)
            temp = [cell_info]

        for elem in temp:
            results = add_if_best(results, elem)

    return results

def get_cells_by_cell_type(UB:np.ndarray, cell_type:str, centering:str, allowPermutations:bool):
    """Geometry/Crystal/ScalarUtils::GetCells - line 135 to 157"""
    if allowPermutations:
        angle_tolerance = 2.0
        length_factor = 1.05
        UB_list = get_related_UBs(UB, length_factor, angle_tolerance)
    else:
        # Get exact form requested and not permutations
        UB_list = [UB]

    results = []
    for elem in UB_list:
        temp = get_cells_UB_only(elem, cell_type, centering, allowPermutations)
        for cell in temp:
            results = add_if_best(results, cell)

    return results
    

def get_related_UBs(UB:np.ndarray, factor:float, angle_tolerance:float) -> list[np.ndarray]:
    """Geometry/Crystal/ScalarUtils::GetRelatedUBs - line 339 to 404"""
    _, a_vec, b_vec, c_vec = get_abc(UB)
    m_a_vec = -a_vec
    m_b_vec = -b_vec
    m_c_vec = -c_vec
    # make list of reflections of all pairs of sides.
    # note: These preserve the ordering of magnitudes: |a|<=|b|<=|c|
    reflections = np.array([
        [a_vec, b_vec, c_vec],
        [m_a_vec, m_b_vec, c_vec],
        [m_a_vec, b_vec, m_c_vec],
        [a_vec, m_b_vec, m_c_vec]
    ])
    # make list of the angles that are not changed by each of the reflections. If
    # that angle is close to 90 degrees, then we may need to switch between all angles
    # >= 90 and all angles < 90. An angle near 90 degrees may be mis-categorized 
    # due to errors in the data.
    alpha = np.degrees(angle_cal(b_vec, c_vec))
    beta = np.degrees(angle_cal(c_vec, a_vec))
    gamma = np.degrees(angle_cal(a_vec, b_vec))
    angles = [90.0, gamma, beta, alpha]

    results = []
    for i in range(4):
        # if nearly 90, try related cell +cell <-> -cell
        if abs(angles[i] - 90) < angle_tolerance:
            a_temp = reflections[i, 0]
            b_temp = reflections[i, 1]
            c_temp = reflections[i, 2]
            # for each accepted reflection, try all modified premutations that preserve the
            # handedness AND keep the cell edges nearly ordered as a <= b <= c.
            m_a_temp = -a_temp
            m_b_temp = -b_temp
            m_c_temp = -c_temp

            permutations = np.array([
                [a_temp, b_temp, c_temp],
                [m_a_temp, c_temp, b_temp],
                [b_temp, c_temp, a_temp],
                [m_b_temp, a_temp, c_temp],
                [c_temp, a_temp, b_temp],
                [m_c_temp, b_temp, a_temp]
            ])

            for j in range(6):
                a = permutations[j, 0]
                b = permutations[j, 1]
                c = permutations[j, 2]
                # could be Niggli within experimental error
                if norm(a) <= factor * norm(b) and norm(b) <= factor * norm(c):
                    _, temp_UB = get_UB(a, b, c)
                    results.append(temp_UB)

    return results

def get_cells_UB_only(UB:np.ndarray, cell_type:str, centering:str, 
                      allowPermutations:bool) -> list[ConventionalCell]:
    """Geometry/Crystal/ScalarUtils::GetCellsUBOnly - line 182 to 199"""
    lp = set_UB(UB)
    lattice_par = [lp.a, lp.b, lp.c, np.degrees(lp.alpha), np.degrees(lp.beta), np.degrees(lp.gamma)]

    results = []
    for i in range(NUM_CELL_TYPES + 1):
        rcell = reduced_cell(i, *lattice_par)
        if rcell.centering == centering and rcell.cell_type == cell_type:
            cell_info = ConventionalCell.conventional_cell(i, UB, allowPermutations, lattice_par)
            results.append(cell_info)

    return results

def add_if_best(results:list[ConventionalCell], cell_info:ConventionalCell) -> list[ConventionalCell]:
    """Geometry/Crystal/ScalarUtils::AddIfBest - line 419 to 436"""
    form_num = cell_info.form_num
    new_error = cell_info.scalars_error
    done = False

    for i in range(len(results)):
        if results[i].form_num == form_num:
            done = True
            if results[i].scalars_error > new_error:
                results[i] = cell_info
            break
    
    if not done:
        results.append(cell_info)

    return results

def get_cell_best_error(cell_list:list[ConventionalCell], use_triclinic:bool):
    """Geometry/Crystal/ScalarUtils::GetCellBestError - line 280 to 304"""
    if len(cell_list) == 0:
        raise ValueError("get_cell_best_error(): list is empty")
    
    cell_info = cell_list[0]
    min_error = 1.0e20
    min_found = False
    for cell in cell_list:
        cell_type = cell.cell_type
        error = cell.scalars_error
        if (use_triclinic or cell_type != 'TRICLINIC') and error < min_error:
            cell_info = cell
            min_error = error
            min_found = True

    if not min_found:
        raise ValueError("get_cell_best_error(): no allowed form with min error")
    
    return cell_info

def remove_high_error_forms(cell_list:list[ConventionalCell], level:float):
    """Geometry/Crystal/ScalarUtils::RemoveHighErrorForms - line 259 to 265"""
    if len(cell_list) == 0:
        return cell_list
    
    cell_list[:] = [cell for cell in cell_list if cell.scalars_error <= level]
    
