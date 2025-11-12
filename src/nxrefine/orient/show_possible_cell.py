import numpy as np
import pandas as pd
from .scalar_utils import get_cells, remove_high_error_forms

def show_possible_cells(UB: np.ndarray, best_only:bool, 
                        allowPermutations:bool, max_scalar_error:float=0.2):
    """Crystal/ShowPossibleCells/ShowPossibleCells::exec"""
    cell_list = get_cells(UB, best_only, allowPermutations)
    remove_high_error_forms(cell_list, max_scalar_error)
    
    form_nums = []
    errors = []
    cell_types = []
    centerings = []
    for cell in cell_list:
        form_nums.append(cell.form_num)
        errors.append(cell.scalars_error)
        cell_types.append(cell.cell_type)
        centerings.append(cell.centering)

    df = pd.DataFrame({
        'form number': form_nums,
        'error': errors,
        'cell type': cell_types,
        'centering': centerings
    })
    df.sort_values(by='error', ascending=False, inplace=True)
    
    return df