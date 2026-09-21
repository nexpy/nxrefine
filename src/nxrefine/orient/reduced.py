import numpy as np
from dataclasses import dataclass


NUM_CELL_TYPES = 44

transformers = np.array([
    [[1, 0, 0], [0, 1, 0], [0, 0, 1]],       # 0
    [[1, -1, 1], [1, 1, -1], [-1, 1, 1]],    # 1
    [[1, -1, 0], [-1, 0, 1], [-1, -1, -1]],  # 2
    [[1, 0, 0], [0, 1, 0], [0, 0, 1]],       # 3
    [[1, -1, 0], [-1, 0, 1], [-1, -1, -1]],  # 4
    [[1, 0, 1], [1, 1, 0], [0, 1, 1]],       # 5
    [[0, 1, 1], [1, 0, 1], [1, 1, 0]],       # 6
    [[1, 0, 1], [1, 1, 0], [0, 1, 1]],       # 7
    [[-1, -1, 0], [-1, 0, -1], [0, -1, -1]], # 8
    [[1, 0, 0], [-1, 1, 0], [-1, -1, 3]],    # 9
    [[1, 1, 0], [1, -1, 0], [0, 0, -1]],     # 10
    [[1, 0, 0], [0, 1, 0], [0, 0, 1]],       # 11
    [[1, 0, 0], [0, 1, 0], [0, 0, 1]],       # 12
    [[1, 1, 0], [-1, 1, 0], [0, 0, 1]],      # 13
    [[1, 1, 0], [-1, 1, 0], [0, 0, 1]],      # 14
    [[1, 0, 0], [0, 1, 0], [1, 1, 2]],       # 15
    [[-1, -1, 0], [1, -1, 0], [1, 1, 2]],    # 16
    [[-1, 0, -1], [-1, -1, 0], [0, 1, 1]],   # 17
    [[0, -1, 1], [1, -1, -1], [1, 0, 0]],    # 18
    [[-1, 0, 0], [0, -1, 1], [-1, 1, 1]],    # 19
    [[0, 1, 1], [0, 1, -1], [-1, 0, 0]],     # 20
    [[0, 1, 0], [0, 0, 1], [1, 0, 0]],       # 21
    [[0, 1, 0], [0, 0, 1], [1, 0, 0]],       # 22
    [[0, 1, 1], [0, -1, 1], [1, 0, 0]],      # 23
    [[1, 2, 1], [0, -1, 1], [1, 0, 0]],      # 24
    [[0, 1, 1], [0, -1, 1], [1, 0, 0]],      # 25
    [[1, 0, 0], [-1, 2, 0], [-1, 0, 2]],     # 26
    [[0, -1, 1], [-1, 0, 0], [1, -1, -1]],   # 27
    [[-1, 0, 0], [-1, 0, 2], [0, 1, 0]],     # 28
    [[1, 0, 0], [1, -2, 0], [0, 0, -1]],     # 29
    [[0, 1, 0], [0, 1, -2], [-1, 0, 0]],     # 30
    [[1, 0, 0], [0, 1, 0], [0, 0, 1]],       # 31
    [[1, 0, 0], [0, 1, 0], [0, 0, 1]],       # 32
    [[1, 0, 0], [0, 1, 0], [0, 0, 1]],       # 33
    [[-1, 0, 0], [0, 0, -1], [0, -1, 0]],    # 34
    [[0, -1, 0], [-1, 0, 0], [0, 0, -1]],    # 35
    [[1, 0, 0], [-1, 0, -2], [0, 1, 0]],     # 36
    [[1, 0, 2], [1, 0, 0], [0, 1, 0]],       # 37
    [[-1, 0, 0], [1, 2, 0], [0, 0, -1]],     # 38
    [[-1, -2, 0], [-1, 0, 0], [0, 0, -1]],   # 39
    [[0, -1, 0], [0, 1, 2], [-1, 0, 0]],     # 40
    [[0, -1, -2], [0, -1, 0], [-1, 0, 0]],   # 41
    [[-1, 0, 0], [0, -1, 0], [1, 1, 2]],     # 42
    [[-1, 0, 0], [-1, -1, -2], [0, -1, 0]],  # 43
    [[1, 0, 0], [0, 1, 0], [0, 0, 1]]        # 44
])

modifiers = np.array([
    [[0, 0, -1], [0, 1, 0], [1, 0, 1]],
    [[-1, 0, -1], [0, 1, 0], [1, 0, 0]]
])

lattice_types = [
    'NONE',            # 0
    'CUBIC',           # 1
    'RHOMBOHEDRAL',    # 2
    'CUBIC',           # 3
    'RHOMBOHEDRAL',    # 4
    'CUBIC',           # 5
    'TETRAGONAL',      # 6
    'TETRAGONAL',      # 7
    'ORTHORHOMBIC',    # 8
    'RHOMBOHEDRAL',    # 9
    'MONOCLINIC',      # 10
    'TETRAGONAL',      # 11
    'HEXAGONAL',       # 12
    'ORTHORHOMBIC',    # 13
    'MONOCLINIC',      # 14
    'TETRAGONAL',      # 15
    'ORTHORHOMBIC',    # 16
    'MONOCLINIC',      # 17
    'TETRAGONAL',      # 18
    'ORTHORHOMBIC',    # 19
    'MONOCLINIC',      # 20
    'TETRAGONAL',      # 21
    'HEXAGONAL',       # 22
    'ORTHORHOMBIC',    # 23
    'RHOMBOHEDRAL',    # 24
    'MONOCLINIC',      # 25
    'ORTHORHOMBIC',    # 26
    'MONOCLINIC',      # 27
    'MONOCLINIC',      # 28
    'MONOCLINIC',      # 29
    'MONOCLINIC',      # 30
    'TRICLINIC',       # 31
    'ORTHORHOMBIC',    # 32
    'MONOCLINIC',      # 33
    'MONOCLINIC',      # 34
    'MONOCLINIC',      # 35
    'ORTHORHOMBIC',    # 36
    'MONOCLINIC',      # 37
    'ORTHORHOMBIC',    # 38
    'MONOCLINIC',      # 39
    'ORTHORHOMBIC',    # 40
    'MONOCLINIC',      # 41
    'ORTHORHOMBIC',    # 42
    'MONOCLINIC',      # 43
    'TRICLINIC'        # 44
]

center_types = [
    'NONE',         # 0
    'F_CENTERED',   # 1
    'R_CENTERED',   # 2
    'P_CENTERED',   # 3
    'R_CENTERED',   # 4
    'I_CENTERED',   # 5
    'I_CENTERED',   # 6
    'I_CENTERED',   # 7
    'I_CENTERED',   # 8
    'R_CENTERED',   # 9
    'C_CENTERED',   # 10
    'P_CENTERED',   # 11
    'P_CENTERED',   # 12
    'C_CENTERED',   # 13
    'C_CENTERED',   # 14
    'I_CENTERED',   # 15
    'F_CENTERED',   # 16
    'I_CENTERED',   # 17
    'I_CENTERED',   # 18
    'I_CENTERED',   # 19
    'C_CENTERED',   # 20
    'P_CENTERED',   # 21
    'P_CENTERED',   # 22
    'C_CENTERED',   # 23
    'R_CENTERED',   # 24
    'C_CENTERED',   # 25
    'F_CENTERED',   # 26
    'I_CENTERED',   # 27
    'C_CENTERED',   # 28
    'C_CENTERED',   # 29
    'C_CENTERED',   # 30
    'P_CENTERED',   # 31
    'P_CENTERED',   # 32
    'P_CENTERED',   # 33
    'P_CENTERED',   # 34
    'P_CENTERED',   # 35
    'C_CENTERED',   # 36
    'C_CENTERED',   # 37
    'C_CENTERED',   # 38
    'C_CENTERED',   # 39
    'C_CENTERED',   # 40
    'C_CENTERED',   # 41
    'I_CENTERED',   # 42
    'I_CENTERED',   # 43
    'P_CENTERED'    # 44
]

def reduced_cell(form_num:int, a:float, b:float, c:float, alpha:float, beta:float, gamma:float):
    rc = ReducedCell.initialize(form_num, a, b, c, alpha, beta, gamma)
    rc.get_scalers()
    return rc

def _norm_vals(scalar):
    """Geometry/Crystal/ReducedCell::norm_vals line 661 to 680"""
    # Use the side lengths themselves, instead of squares of sides
    # so errors correspond to errors in lattice positions
    a = np.sqrt(scalar[0])
    b = np.sqrt(scalar[1])
    c = np.sqrt(scalar[2])
    # Use law of cosines to interpret errors in dot products
    # interms of errors in lattice positions.
    d = np.sqrt(b * b + c * c - 2 * scalar[3])
    e = np.sqrt(a * a + c * c - 2 * scalar[4])
    f = np.sqrt(a * a + b * b - 2 * scalar[5])
    vals = np.array([a, b, c, d, e, f])
    return vals

@dataclass
class ReducedCell:
    # choose between 1 to 44
    form_num: int
    # dot product of a and a
    a_a: float
    # dot product of b and b
    b_b: float
    # dot product of c and c
    c_c: float
    # dot product of b and c
    b_c: float
    # dot product of a and c
    a_c: float
    # dot product of a and b
    a_b: float
    # the basis transformation matix from reduced cell to conventional cell
    transform: np.ndarray
    # the cell type of the conventional cell
    cell_type: str
    # the centering type of the conventional cell
    centering: str
    # header scalars
    scalars: np.ndarray=None

    @classmethod
    def initialize(cls, form_num:int, a:float, b:float, c:float, alpha:float, beta:float, gamma:float):
        """Geometry/Crystal/ReducedCell::ReducedCell line 220 to 273"""
        if a <= 0 or b <= 0 or c <= 0:
            raise ValueError("reduced_cell(): a, b, c must be positive")
        if alpha <= 0 or alpha >=180 or beta <= 0 or beta >= 180 or gamma <= 0 or gamma >= 180:
            raise ValueError("reduced_cell(): alpha, beta, gamma must be between 0 and 180 degrees")
        
        alpha = np.radians(alpha)
        beta = np.radians(beta)
        gamma = np.radians(gamma)

        if form_num > NUM_CELL_TYPES:
            raise ValueError("reduced_cell(): reduced form number must be no more than 44")
        
        a_a = a * a
        b_b = b * b
        c_c = c * c
        b_c = b * c * np.cos(alpha)
        a_c = a * c * np.cos(beta)
        a_b = a * b * np.cos(gamma)
        
        if form_num > 0:
            b_c = abs(b_c)
            a_c = abs(a_c)
            a_b = abs(a_b)

        transform = transformers[form_num]
        cell_type = lattice_types[form_num]
        centering = center_types[form_num]

        return cls(form_num, a_a, b_b, c_c, b_c, a_c, a_b, transform, cell_type, centering)

    def get_scalers(self):
        """Geometry/Crystal/ReducedCell::ReducedCell init line 275 to 541"""
        if self.form_num == 0:
            scalars = [self.a_a, self.b_b, self.c_c]
        elif self.form_num <= 8:
            scalars = [self.a_a, self.a_a, self.a_a]
        elif self.form_num <= 17:
            scalars = [self.a_a, self.a_a, self.c_c]
        elif self.form_num <= 25:
            scalars = [self.a_a, self.b_b, self.b_b]
        else:
            scalars = [self.a_a, self.b_b, self.c_c]

        if self.form_num == 0:
            scalars = scalars + [self.b_c, self.a_c, self.a_b]
        elif self.form_num == 1:
            scalars = scalars + [self.a_a/2, self.a_a/2, self.a_a/2]
        elif self.form_num == 2:
            scalars = scalars + [self.b_c, self.b_c, self.b_c]
        elif self.form_num == 3:
            scalars = scalars + [0, 0, 0]
        elif self.form_num == 4:
            scalars = scalars + [-abs(self.b_c), -abs(self.b_c), -abs(self.b_c)]
        elif self.form_num == 5:
            scalars = scalars + [-self.a_a/3, -self.a_a/3, -self.a_a/3]
        elif self.form_num == 6:
            value = (-self.a_a + abs(self.a_b)) / 2
            scalars = scalars + [value, value, -abs(self.a_b)]
        elif self.form_num == 7:
            value = (-self.a_a + abs(self.b_c)) / 2
            scalars = scalars + [-abs(self.b_c), value, value]
        elif self.form_num == 8:
            scalars = scalars + [-abs(self.b_c), -abs(self.a_c), -(abs(self.a_a) - abs(self.b_c) - abs(self.a_c))]
        elif self.form_num == 9:
            scalars = scalars + [self.a_a/2, self.a_a/2, self.a_a/2]
        elif self.form_num == 10:
            scalars = scalars + [self.b_c, self.b_c, self.a_b]
            self._foot_note_d()
        elif self.form_num == 11:
            scalars = scalars + [0, 0, 0]
        elif self.form_num == 12:
            scalars = scalars + [0, 0, -self.a_a/2]
        elif self.form_num == 13:
            scalars = scalars + [0, 0, -abs(self.a_b)]
        elif self.form_num == 14:
            scalars = scalars + [-abs(self.b_c), -abs(self.b_c), -abs(self.a_b)]
            self._foot_note_d()
        elif self.form_num == 15:
            scalars = scalars + [-self.a_a/2, -self.a_a/2, 0]
        elif self.form_num == 16:
            scalars = scalars + [-abs(self.b_c), -abs(self.b_c), -(self.a_a-2*abs(self.b_c))]
        elif self.form_num == 17:
            scalars = scalars + [-abs(self.b_c), -abs(self.a_c), -(self.a_a-abs(self.b_c)-abs(self.a_c))]
            self._foot_note_e()
        elif self.form_num == 18:
            scalars = scalars + [self.a_a/4, self.a_a/2, self.a_a/2]
        elif self.form_num == 19:
            scalars = scalars + [self.b_c, self.a_a/2, self.a_a/2]
        elif self.form_num == 20:
            scalars = scalars + [self.b_c, self.a_c, self.a_c]
            self._foot_note_b()
        elif self.form_num == 21:
            scalars = scalars + [0 ,0, 0]
        elif self.form_num == 22:
            scalars = scalars + [-self.b_b/2, 0, 0]
        elif self.form_num == 23:
            scalars = scalars + [-abs(self.b_c), 0, 0]
        elif self.form_num == 24:
            scalars = scalars + [-(self.b_b-self.a_a/3)/2, -self.a_a/3, -self.a_a/3]
        elif self.form_num == 25:
            scalars = scalars + [-abs(self.b_c), -abs(self.a_c), -abs(self.a_c)]
            self._foot_note_b()
        elif self.form_num == 26:
            scalars = scalars + [self.a_a/4, self.a_a/2, self.a_a/2]
        elif self.form_num == 27:
            scalars = scalars + [self.b_c, self.a_a/2, self.a_a/2]
            self._foot_note_f()
        elif self.form_num == 28:
            scalars = scalars + [self.a_b/2, self.a_a/2, self.a_b]
        elif self.form_num == 29:
            scalars = scalars + [self.a_c/2, self.a_c, self.a_a/2]
        elif self.form_num == 30:
            scalars = scalars + [self.b_b/2, self.a_b/2, self.a_b]
        elif self.form_num == 31:
            scalars = scalars + [self.b_c, self.a_c, self.a_b]
        elif self.form_num == 32:
            scalars = scalars + [0, 0, 0]
        elif self.form_num == 33:
            scalars = scalars + [0, -abs(self.a_c), 0]
        elif self.form_num == 34:
            scalars = scalars + [0, 0, -abs(self.a_b)]
        elif self.form_num == 35:
            scalars = scalars + [-abs(self.b_c), 0, 0]
        elif self.form_num == 36:
            scalars = scalars + [0, -self.a_a/2, 0]
        elif self.form_num == 37:
            scalars = scalars + [-abs(self.b_c), -self.a_a/2, 0]
            self._foot_note_c()
        elif self.form_num == 38:
            scalars = scalars + [0, 0, -self.a_a/2]
        elif self.form_num == 39:
            scalars = scalars + [-abs(self.b_c), 0, -self.a_a/2]
            self._foot_note_d()
        elif self.form_num == 40:
            scalars = scalars + [-self.b_b/2, 0, 0]
        elif self.form_num == 41:
            scalars = scalars + [-self.b_b/2, -abs(self.a_c), 0]
            self._foot_note_b()
        elif self.form_num == 42:
            scalars = scalars + [-self.b_b/2, -self.a_a/2, 0]
        elif self.form_num == 43:
            scalars = scalars + [-(self.b_b-abs(self.a_b))/2, -(self.a_a-abs(self.a_b))/2, -abs(self.a_b)]
        elif self.form_num == 44:
            scalars = scalars + [-abs(self.b_c), -abs(self.a_c), -abs(self.a_b)]

        self.scalars = np.array(scalars)

    def _foot_note_b(self):
        """Geometry/Crystal/ReducedCell::foot_note_b line 537 to 543"""
        if self.a_a < 4 * abs(self.a_c):
            self._permultiply(0)
            self.centering = 'I_CENTERED'

    def _foot_note_c(self):
        """Geometry/Crystal/ReducedCell::foot_note_c line 548 to 554"""
        if self.b_b < 4 * abs(self.b_c):
            self._permultiply(0)
            self.centering = 'I_CENTERED'
    
    def _foot_note_d(self):
        """Geometry/Crystal/ReducedCell::foot_note_d line 559 to 565"""
        if self.c_c < 4 * abs(self.b_c):
            self._permultiply(0)
            self.centering = 'I_CENTERED'

    def _foot_note_e(self):
        """Geometry/Crystal/ReducedCell::foot_note_e line 570 to 576"""
        if 3 * self.a_a < self.c_c + 2 * abs(self.a_c):
            self._permultiply(1)
            self.centering = 'C_CENTERED'

    def _foot_note_f(self):
        """Geometry/Crystal/ReducedCell::foot_note_f line 581 to 587"""
        if 3 * self.b_b < self.c_c + 2 * abs(self.b_c):
            self._permultiply(1)
            self.centering = 'C_CENTERED'

    def _permultiply(self, index:int):
        """Geometry/Crystal/ReducedCell::premultiply line 602 to 609"""
        self.transform = modifiers[index] @ self.transform

    def weighted_distance(self, form):
        """Geometry/Crystal/ReducedCell::WeightedDistance line 631 to 643"""
        vals_1 = _norm_vals(self.scalars)
        vals_2 = _norm_vals(form.scalars)

        max = (vals_1 - vals_2).max()
        return max
    
    