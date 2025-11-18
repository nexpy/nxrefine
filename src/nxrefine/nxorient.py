import math
import numpy as np
from numpy.linalg import inv, norm, det, lstsq
from dataclasses import dataclass
from scipy.signal import argrelextrema
from itertools import combinations
from .orient.niggli import make_Niggli_UB
from .orient.orientedlattice import set_UB
from .orient.scalar_utils import get_cells, remove_high_error_forms


def _polar_to_cartesian(psi:float, phi:float) -> tuple[float, float, float]:
    """convert polar cooridinates to Cartesian coordinates"""
    y = -np.cos(psi)
    z = -np.sin(psi)*np.sin(phi)
    x = np.sin(psi)*np.cos(phi)
    return x, y, z

@dataclass
class UBMatrixFFT:
    """python version of FindUBUsingFFT implemented in mantid 
    (https://github.com/mantidproject/mantid)
    """

    # lower bound on lattice parameters a, b, c
    min_d: float
    # upper bound on lattice parameters a, b, c
    max_d: float
    # the resolution of the search through possible orientations, unit: radian
    dir_step_size: float = 0.03
    # the number of grid point along the projection direction
    fft_num: int = 512
    # indexing tolerance
    tolerance: float = 0.15 * 0.75
    # iterations to refine UB
    iterations: int = 4
    # reciprocal lattice coordinates in sample frame, n x 3 array
    q_vectors: np.ndarray = None
    # maximum magnitude of the q vectors
    _q_max: float = None
    # polar coordinates that defines the angle between the X-ray beam and the chosen direction
    # 0 < psi < pi/2, n x 3 array
    _psi_list: np.ndarray = None
    # polar coordinates to define the projection directions, 0 < phi < 2*pi, n x 3 array
    _phi_list: list[np.ndarray] = None
    # projecton directions, n x 3 array
    _t_list: np.ndarray = None
    # q vector projection values to the directions
    _p_list: np.ndarray = None
    # projected array
    _fj_list: np.ndarray = None
    # fft of the projected array
    _magnitude_fft: np.ndarray = None
    # max fft magnitudes of all directions
    _max_fft_val: np.ndarray = None
    # the selected projection directions
    _directions: list = None
    # the orientation matrix UB
    _UB: np.ndarray = None
    # U matrix
    Umat: np.ndarray = None
    # B matrix
    Bmat: np.ndarray = None

    def initialize(self) -> None:
        """initialize and store all the parameters to find the UB matrix"""
        if self.q_vectors is None or self.q_vectors.shape[0] < 4:
            raise ValueError("initialize(): Four or more indexed peaks needed to find UB")
        self._make_hemisphere_directions()
        self._projection_list_cal()
        self._max_mag_fft_cal()

    def find_UB(self) -> float:
        """Geometry/Crystal/IndexingUtils::Find_UB - line 451 to 524"""
        if self.min_d >= self.max_d or self.min_d <= 0:
            raise ValueError("find_UB(): Need 0 < min_d < max_d")
        
        if self.tolerance <= 0:
            raise ValueError("find_UB(): tolerance must be positive")
        
        if self.dir_step_size <=0:
            raise ValueError("find_UB(): dir_step_size must be positive")
        
        self.initialize()

        max_indexed = self._scan_fft_directions()

        if max_indexed == 0:
            raise ValueError("find_UB(): Could not find any a,b,c vectors to index Qs")
        
        if len(self._directions) < 3:
            raise ValueError("find_UB(): Could not find enough a,b,c vectors")
        
        self._directions.sort(key=lambda t: norm(t))

        min_vol = self.min_d * self.min_d * self.min_d / 4.0
        if not self._form_UB_from_abc_vectors(min_vol):
            raise ValueError("find_UB(): Could not form UB matrix from a, b, c vectors")
        # repeatedly refine UB
        if self.q_vectors.shape[0] >= 5:
            _, miller_ind, indexed_qs, fit_error = self.get_indexed_peaks()

            for i in range(self.iterations):
                try:
                    fit_error, temp_UB = self.optimize_UB(miller_ind, indexed_qs)
                    self._UB = temp_UB
                    _, miller_ind, indexed_qs, fit_error = self.get_indexed_peaks()
                except Exception:
                    # failed to improve with all peaks, so just keep the UB we had
                    pass
        
        success, new_UB = make_Niggli_UB(self._UB)
        if success:
            self._UB = new_UB

        return fit_error

    def _scan_fft_directions(self) -> int:
        """Geometry/Crystal/IndexingUtils::FFTScanFor_Directions - line 1454 to 1568"""
        # find the indices of directions with the 500 largest fft values
        temp_idx = np.argsort(self._max_fft_val)[::-1][0:500]
        max_mag_fft = self._max_fft_val.max()
        if self._max_fft_val[temp_idx].min() >= max_mag_fft/2:
            threshold = self._max_fft_val[temp_idx].min()
        else:
            threshold = self._max_fft_val[temp_idx][self._max_fft_val[temp_idx] < max_mag_fft/2].max()

        temp_dirs_idx = []
        for i, elem in enumerate(self._max_fft_val):
            if elem >= threshold:
                temp_dirs_idx.append(i)
        # Scan through temp_dirs and use the FFT to find the cell edge length that corresponds
        # to the max_mag_fft. Only keep directions with length nearly in bounds
        temp_dirs_2 = []
        for idx in temp_dirs_idx:
            position = self._get_first_max_index(threshold, idx)
            if position > 0:
                q_val = self._q_max / position
                d_val = 1 / q_val
                if d_val > 0.8*self.min_d and d_val <= 1.2*self.max_d:
                    temp_dirs_2.append(self._t_list[idx]*d_val)
        # look at how many peaks were indexed for each of the initial directions
        max_indexed = 0
        num_indexed_list = []
        for dir in temp_dirs_2:
            num_indexed = self._num_indexed_1D(dir)
            if num_indexed > max_indexed:
                max_indexed = num_indexed
            num_indexed_list.append(num_indexed)
        # only keep original directions that index at least 50% of max num indexed
        temp_dirs = []
        for i, elem in enumerate(num_indexed_list):
            if elem >= 0.5*max_indexed:
                temp_dirs.append(temp_dirs_2[i])
        # refine directions and again find the max number indexed, for the optimized directions
        max_indexed = 0
        for i, dir in enumerate(temp_dirs):
            num_indexed, index_vals, indexed_qs = self._get_indexed_peaks_1D(dir)
            try:
                for _ in range(5): 
                    _, best_vec = self._optimize_direction(index_vals, indexed_qs)
                    num_indexed, index_vals, indexed_qs = self._get_indexed_peaks_1D(best_vec)
                    if num_indexed > max_indexed:
                        max_indexed = num_indexed
                temp_dirs[i] = best_vec
            except Exception:
                # don't continue to refine if the direction fails to optimize properly
                pass
        # discard those with length out of bounds
        temp_dirs_2 = []
        for dir in temp_dirs:
            length = norm(dir)
            if length >= 0.8*self.min_d and length <= 1.2*self.max_d:
                temp_dirs_2.append(dir)
        # only keep directions that index at least 75% of the max number of peaks
        temp_dirs = []
        for dir in temp_dirs_2:
            num_indexed = self._num_indexed_1D(dir)
            if num_indexed > max_indexed*0.75:
                temp_dirs.append(dir)
        temp_dirs.sort(key=lambda t: norm(t))
        # discard duplicates
        len_tol = 0.1   # 10% tolerance for lengths
        ang_tol = 5.0   # 5 degree tolerance for angles
        self._discard_duplicates(temp_dirs, len_tol, ang_tol)
        return max_indexed
    
    def _make_hemisphere_directions(self) -> None:
        """Geometry/Crystal/IndexingUtils::MakeHemisphereDirections - line 2588 to 2623"""
        self._psi_list = np.arange(0, np.pi/2, self.dir_step_size, dtype=np.float32)

        direction_list = []
        phi_list = []
        for psi in self._psi_list:
            r = np.sin(psi)
            n_phi = round(2*np.pi*r/self.dir_step_size)
            if n_phi == 0:
                phi_values = np.array([0.0])
            else:
                phi_step = 2*np.pi / n_phi
                if abs(psi -np.pi/2) < self.dir_step_size/2:
                    n_phi //= 2
                phi_values = np.arange(n_phi) * phi_step

            phi_list.append(phi_values)
            for phi in phi_values:
                direction_list.append(_polar_to_cartesian(psi, phi))

        self._t_list = np.array(direction_list)
        self._phi_list = phi_list
    
    def _projection(self, data:np.ndarray, idx_factor:float) -> np.ndarray:
        """project onto one direction
        Geometry/Crystal/IndexingUtils::GetMagFFT - line 1601 to 1609

        Parameters
        ----------
        data: np.ndarray

        idx_factor: float

        """
        proj = np.zeros(self.fft_num, dtype=np.float32)
        for elem in data*idx_factor:
            idx = math.floor(abs(elem))
            if idx < self.fft_num:
                proj[idx] += 1
            else: # this should not happen, but trap it in case of rounding errors
                proj[idx-1] += 1
        return proj

    def _projection_list_cal(self) -> None:
        """project onto all directions"""
        self._p_list = (self.q_vectors@self._t_list.T).T
        self._fj_list = np.zeros((self._p_list.shape[0], self.fft_num), dtype=np.float32)

        self._q_max = norm(self.q_vectors, axis=1).max() * 1.1
        idx_factor = self.fft_num / self._q_max

        for i in range(self._p_list.shape[0]):
            self._fj_list[i] += self._projection(self._p_list[i], idx_factor)
    
    def _max_mag_fft_cal(self) -> None:
        """Geometry/Crystal/IndexingUtils::GetMagFFT"""
        fft_fj_list = np.fft.rfft(self._fj_list, axis=1)
        self._magnitude_fft = np.abs(fft_fj_list)

        dc_end = 5
        self._max_fft_val = np.max(self._magnitude_fft[:, dc_end::], axis=1)
    
    def _get_first_max_index(self, threshold:float, idx:int) -> float:
        """Geometry/Crystal/IndexingUtils::GetFirstMaxIndex - line 1640 to 1674"""
        local_min = argrelextrema(self._magnitude_fft[idx], np.less)[0]
        local_max = argrelextrema(self._magnitude_fft[idx], np.greater)[0]
        # find first local min below threshold
        m = 0
        find_min = False
        for idxmin in local_min:
            if self._magnitude_fft[idx][idxmin] < threshold:
                m = int(idxmin)
                find_min = True
                break

        if not find_min:
            return -1
        # find next local max above threshold
        find_max=False
        for idxmax in local_max:
            if idxmax <= m:
                continue  

            if self._magnitude_fft[idx][idxmax] > threshold:
                m = int(idxmax)
                find_max = True
                break

        if not find_max:
            return -1
                
        sum = 0
        w_sum = 0
        for i in range(m-2, min(self.fft_num, m+3)):
            sum += i * self._magnitude_fft[idx][i]
            w_sum += self._magnitude_fft[idx][i]
        return sum/w_sum
    
    def _num_indexed_1D(self, dir:np.ndarray) -> int:
        """Geometry/Crystal/IndexingUtils::NumberIndexed_1D - line 2207 to 2222"""
        if norm(dir) == 0:
            return 0
        
        count = 0
        for q in self.q_vectors:
            proj_value = np.dot(dir, q)
            error = abs(proj_value - round(proj_value))
            if error <= self.tolerance:
                count += 1
        return count
    
    def _num_indexed_3D(self, a_dir:np.ndarray, b_dir:np.ndarray, c_dir:np.ndarray):
        """Geometry/Crystal/IndexingUtils::NumberIndexed_3D - line 2245 to 2263"""
        if norm(a_dir)==0 or norm(b_dir)==0 or norm(c_dir)==0:
            return 0
        
        count = 0
        for q in self.q_vectors:
            hkl_vec = np.array([a_dir, b_dir, c_dir]) @ q
            if self._valid_index(hkl_vec):
                count += 1
        return count
    
    def _valid_index(self, hkl:np.ndarray) -> bool:
        """Geometry/Crystal/IndexingUtils::ValidIndex - line 2047 to 2052"""
        if round(hkl[0], 4)==0 and round(hkl[1], 4)==0 and round(hkl[2], 4)==0:
            return False
        return (self._within_tol(hkl[0]) and self._within_tol(hkl[1]) and self._within_tol(hkl[2]))
    
    def _within_tol(self, val:float) -> bool:
        """Geometry/Crystal/IndexingUtils::withinTol - line 2025 to 2032"""
        my_val = abs(val)
        if (my_val - math.floor(my_val)) < self.tolerance:
            return True
        if (math.floor(my_val+1.) - my_val) < self.tolerance:
            return True
        return False
    
    def _get_indexed_peaks_1D(self, dir:np.ndarray) -> tuple[int, list[int], list[np.ndarray]]:
        """Geometry/Crystal/IndexingUtils::GetIndexedPeaks_1D - line 2392 to 2420"""
        num_indexed = 0
        index_vals = []
        indexed_qs = []

        fit_error = 0
        if norm(dir) == 0:
            # special case, zero vector will NOT index any peaks, even
            # through dot product with Q vectors is always an integer!
            return 0
        
        for q in self.q_vectors:
            proj_value = np.dot(dir, q)
            nearest_int = round(proj_value)
            error = abs(proj_value - nearest_int)
            if error < self.tolerance:
                fit_error += error * error
                indexed_qs.append(q)
                index_vals.append(int(nearest_int))
                num_indexed += 1
        
        return num_indexed, index_vals, indexed_qs
    
    def get_indexed_peaks(self) -> tuple[int, list[np.ndarray], list[np.ndarray], float]:
        """Geometry/Crystal/IndexingUtils::GetIndexedPeaks - line 2528 to 2568"""
        num_indexed = 0
        miller_indices = []
        indexed_qs = []
        fit_error = 0
        
        if self.check_UB():
            UB_inverse = inv(self._UB)
        else:
            raise RuntimeError("get_indexed_peaks(): The UB in get_indexed_peaks() is not valid")
        
        for q in self.q_vectors:
            hkl = UB_inverse @ q
            if self._valid_index(hkl):
                for i in range(3):
                    error = hkl[i] - round(hkl[i])
                    fit_error += error * error
                indexed_qs.append(q)
                miller_indices.append(np.array([round(hkl[0]), round(hkl[1]), round(hkl[2])]))
                num_indexed += 1

        return num_indexed, miller_indices, indexed_qs, fit_error
    
    def _optimize_direction(self, index_values:list[int], 
                            indexed_qs:list[np.ndarray]) -> tuple[float, np.ndarray]:
        """Geometry/Crystal/IndexingUtils::Optimize_Direction - line 1027 to 1098"""
        if len(index_values) < 3:
            raise ValueError("_optimize_direction(): Three or more indexed values needed for _optimize_direction.")
        
        if len(index_values) != len(indexed_qs):
            raise ValueError("_optimize_direction(): Number of index_values != number of indexed q vectors.")

        sum_sq_error = 0
        # Need more understanding of this Q, R decomposition
        H_transpose = np.array(indexed_qs)
        indices = np.array(index_values)

        try:
            best_vec, residuals, rank, s = lstsq(H_transpose, indices, rcond=None)
        except np.linalg.LinAlgError as e:
            raise RuntimeError("_optimize_direction(): QR decomposition failed: invalid hkl values") from e

         # Check solution validity
        if not np.all(np.isfinite(best_vec)):
            raise RuntimeError("_optimize_direction(): Failed to find best_vec, invalid indexes or Q values")

        # If NumPy didn’t return residuals (e.g. underdetermined system), compute manually
        if residuals.size > 0:
            sum_sq_error = residuals[0]  # np.linalg.lstsq returns sum of squared residuals
        else:
            residual = H_transpose @ best_vec - indices
            sum_sq_error = np.sum(residual**2)

        return sum_sq_error, best_vec
    
    def _discard_duplicates(self, directs:list[np.ndarray], len_tol:float, ang_tol:float) -> None:
        """Geometry/Crystal/IndexingUtils::DiscardDuplicates - line 1919 to 1993"""
        self._directions = []
        zero_vec = np.zeros(3)
        
        for i, dir in enumerate(directs):
            current_length = norm(dir)
            if current_length == 0:  # skip any zero vectors
                continue

            temp = [dir]
            for j in range(i+1, len(directs)):
                next_dir = directs[j]
                next_length = norm(next_dir)
                if next_length == 0:
                    continue

                if abs(next_length - current_length) / current_length < len_tol:
                    cos_angle = np.dot(dir, next_dir) / (current_length  * next_length)
                    cos_angle = np.clip(cos_angle, -1.0, 1.0)
                    angle = np.degrees(np.arccos(cos_angle))
                    if angle < ang_tol or angle > (180 - ang_tol):
                        temp.append(next_dir)
                        directs[j] = zero_vec
                else:
                    break
            # Now scan through temp list to find the one that indexes most
            best = max(temp, key=self._num_indexed_1D, default=None)
            if best is not None and self._num_indexed_1D(best) > 0:
                self._directions.append(best)
    
    def _form_UB_from_abc_vectors(self, min_vol:float) -> bool:
        """Geometry/Crystal/IndexingUtils::FormUB_From_abc_Vectors line 1803 to 1857"""
        best = None

        for a_temp, b_temp, c_temp in combinations(self._directions, 3):
            vol = abs(np.dot(np.cross(a_temp, b_temp), c_temp))

            if vol <= min_vol:
                continue

            num_indexed = self._num_indexed_3D(a_temp, b_temp, c_temp)
            # requiring 20% more indexed with longer edge lengths, favors the smaller unit cells
            if best is None or num_indexed > 1.2 * best[0]:
                best = (num_indexed, a_temp, b_temp, c_temp)

        if not best or best[0] <= 0:
            return False

        # force a, b, c to be right handed
        _, a_dir, b_dir, c_dir = best
        if np.dot(np.cross(a_dir, b_dir), c_dir) < 0:
            c_dir = -c_dir
        # now build the UB from a, b, c
        if not self._get_UB(a_dir, b_dir, c_dir):
            raise RuntimeError("_form_UB_from_abc_vectors(): UB could not be formed, invert matrix failed")
        
        return True
    
    def _get_UB(self, a_dir:np.ndarray, b_dir:np.ndarray, c_dir:np.ndarray) -> bool:
        """Geometry/Crystal/OrientedLattice::GetUB line 1803 to 1857"""
        self._UB = np.array([a_dir, b_dir, c_dir])
        try:
            self._UB = inv(self._UB)
        except np.linalg.LinAlgError:
            self._UB = None
            return False
        
        return True

    def check_UB(self) -> bool:
        """Geometry/Crystal/IndexingUtils::CheckUB - line 2130 to 2146
        
        Check whether or not the specified matrix is reasonable for an orientation
        matrix.  In particular, check that it is a 3x3 matrix without any nan or
        infinite values and that its determinant is within a reasonable range, for
        an orientation matrix.
        """
        if self._UB.shape != (3, 3):
            return False
        
        if not np.all(np.isfinite(self._UB)):
            return False
        
        detm = det(self._UB) 
        return not (abs(detm) > 10 or abs(detm) < 1e-12)

    def optimize_UB(self, hkl_vectors:list[np.ndarray], 
                    indexed_qs:list[np.ndarray]) -> tuple[float, np.ndarray]:
        """Geometry/Crystal/IndexingUtils::Optimize_UB - line 644 to 725"""
        if len(hkl_vectors) < 3:
            raise ValueError("optimize_UB(): Three or more indexed peaks needed to find UB")
        if len(hkl_vectors) != len(indexed_qs):
            raise ValueError("optimize_UB(): Number of hkl_vectors != number of q_vectors")
        
        sum_sq_error = 0
        found_UB = True
        H_transpose = np.array(hkl_vectors)
        qs = np.array(indexed_qs)
        temp_UB = np.zeros((3, 3))

        for row in range(3):
            q = qs[:, row]
            UB_row, residuals, rank, s = lstsq(H_transpose, q, rcond=None)

            if not np.all(np.isfinite(UB_row)):
                found_UB = False

            temp_UB[row] += UB_row

            if residuals.size > 0:
                sum_sq_error += residuals[0]
            else:
                res = q - H_transpose@UB_row
                sum_sq_error += np.sum(res**2)

        if not found_UB:
            raise RuntimeError("optimize_UB(): Failed to find UB, invalid hkl or Q values")
        
        if not self.check_UB():
            raise RuntimeError("optimize_UB(): the optimize UB is not valid")

        return sum_sq_error, temp_UB

    def get_lattice_parameters(self, optional_UB:np.ndarray=None) -> tuple[bool, np.ndarray]:
        """Geometry/Crystal/IndexingUtils::GetLatticeParameters - line 2774 to 2790"""
        if optional_UB is None:
            o_lattice = set_UB(self._UB)

            lattice_par = [o_lattice.a, 
                        o_lattice.b, 
                        o_lattice.c, 
                        np.degrees(o_lattice.alpha), 
                        np.degrees(o_lattice.beta), 
                        np.degrees(o_lattice.gamma)]
            
        else:
            o_lattice = set_UB(optional_UB)

            lattice_par = [o_lattice.a, 
                        o_lattice.b, 
                        o_lattice.c, 
                        np.degrees(o_lattice.alpha), 
                        np.degrees(o_lattice.beta), 
                        np.degrees(o_lattice.gamma)]
        
        return lattice_par
    
    def get_Umat_and_Bmat(self):
        o_lattice = set_UB(self._UB)
        self.Umat = o_lattice.Umat
        self.Bmat = o_lattice.Bmat
    
    def get_possible_cells(self, best_only:bool, 
                            allowPermutations:bool, 
                            max_scalar_error:float=0.2) -> dict:
        """Crystal/ShowPossibleCells/ShowPossibleCells::exec"""
        cells = get_cells(self._UB, best_only, allowPermutations)
        remove_high_error_forms(cells, max_scalar_error)
        return cells
