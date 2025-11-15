import numpy as np
from dataclasses import dataclass
from numpy.linalg import inv, norm
from .reduced import reduced_cell
from .orientedlattice import get_abc, get_UB
from .niggli import angle_cal


@dataclass
class ConventionalCell:
    """python version of ConventionalCell implemented in mantid 
    (https://github.com/mantidproject/mantid)
    Construct a ConventionalCell for the specified orientation matrix
    and the specified row of Table 2.  The form number must be between
    1 and 44.
    """
    # choose between 1 to 44
    form_num: int
    # maximum absolute difference between the scalers of reduced cell and conventional cell
    scalars_error: float
    # the cell type of the conventional cell
    cell_type: str
    # the centering type of the conventional cell
    centering: str
    # UB matrix of the reduced cell
    original_UB: np.ndarray
    # the basis transformation matix from reduced cell to conventional cell
    hkl_tran: np.ndarray=None
    # UB matrix of the conventional cell
    new_UB: np.ndarray=None

    @classmethod
    def conventional_cell(cls, form_num:int, UB:np.ndarray, 
                          allow_permutations: bool, lattice_par:list):
        """Geometry/Crystal/ConventionalCell::ConventionalCell - line 2774 to 2790"""
        form_0 = reduced_cell(0, *lattice_par)
        form_i = reduced_cell(form_num, *lattice_par)

        scalars_error = form_0.weighted_distance(form_i)
        cell_type = form_i.cell_type
        centering = form_i.centering

        hkl_tran = form_i.transform
        UB_tran = inv(hkl_tran)

        adjusted_UB = UB @ UB_tran

        if allow_permutations:
            if cell_type == 'TETRAGONAL':
                adjusted_UB = cls.standardize_tetragonal(adjusted_UB)
            elif cell_type == 'HEXAGONAL' or cell_type == 'RHOMBOHEDRAL':
                adjusted_UB = cls.standardize_hexagonal(adjusted_UB)
        
        return cls(form_num, 
                   scalars_error, 
                   cell_type, 
                   centering, 
                   UB, 
                   hkl_tran, 
                   adjusted_UB)
    
    @staticmethod
    def standardize_tetragonal(UB:np.ndarray):
        """Geometry/Crystal/ConventionalCell::StandardizeTetragonal - line 217 to 236"""
        success, a, b, c = get_abc(UB)

        if not success:
            raise ValueError("standardize_tetragonal(): not valid UB")
        
        a_b_diff = abs(norm(a) - norm(b)) / min(norm(a), norm(b))
        a_c_diff = abs(norm(a) - norm(c)) / min(norm(a), norm(c))
        b_c_diff = abs(norm(b) - norm(c)) / min(norm(b), norm(c))
        # if needed, change UB to have the two most nearly equal sides first.
        if a_c_diff <= a_b_diff and a_c_diff <= b_c_diff:
            _, new_UB = get_UB(c, a, b)
        elif b_c_diff <= a_b_diff and b_c_diff <= a_c_diff:
            _, new_UB = get_UB(b, c, a)
        else:
            new_UB = UB
        
        return new_UB
    
    @staticmethod
    def standardize_hexagonal(UB:np.ndarray):
        """Geometry/Crystal/ConventionalCell::StandardizeHexagonal - line 247 to 272"""
        success, a, b, c = get_abc(UB)

        if not success:
            raise ValueError("standardize_hexagonal(): not valid UB")
        
        alpha = np.degrees(angle_cal(b, c))
        beta = np.degrees(angle_cal(c, a))
        # make the non 90 degree angle last
        if abs(alpha - 90) > 20:
            _, new_UB = get_UB(b, c, a)
        elif abs(beta - 90) > 20:
            _, new_UB = get_UB(c, a, b)
        else:
            new_UB = UB
        # if the non 90 degree angle is about 60 degrees, make
        # it about 120 degrees.
        success, a, b, c = get_abc(new_UB)

        if not success:
            raise ValueError("standardize_hexagonal(): not valid UB")
        
        gamma = np.degrees(angle_cal(a, b))
        if abs(gamma - 60) < 10:
            a = -a
            c = -c
            _, new_UB = get_UB(a, b, c)

        return new_UB

        
