import numpy as np
from numpy.linalg import det, inv
from dataclasses import dataclass

def get_UB(a:np.ndarray, b:np.ndarray, c:np.ndarray) -> tuple[bool, np.ndarray]:
    """Geometry/Crystal/OrientedLattice::GetUB - line 348 to 362
    
    Get the UB matrix corresponding to the real space edge vectors a,b,c.

    Parameters
    ----------
    a: np.ndarray
        The real space edge vector for side a of the unit cell
    b: np.ndarray
        The real space edge vector for side b of the unit cell
    c: np.ndarray
        The real space edge vector for side c of the unit cell
    """
    UB = np.array([a, b, c])
    try:
        UB = inv(UB)
    except np.linalg.LinAlgError:
        return False, UB
    return True, UB

def get_abc(UB:np.ndarray) -> tuple[bool, np.ndarray, np.ndarray, np.ndarray]:
    """Geometry/Crystal/OrientedLattice::GetABC - line 381 to 397
    
    Get the real space edge vectors a,b,c corresponding to the UB
    matrix. If the inverse of the matrix UB can be found, return True
    and the thress lattice vector a_dir, b_dir and c_dir.
    
    Parameters
    ----------
    UB: np.ndarray
        a 3x3 matrix contains a UB matrix
    """
    if UB.shape != (3, 3):
        raise ValueError("get_abc(): UB matrix NULL or not 3 by 3")
    
    try:
        UB_inverse = inv(UB)
    except np.linalg.LinAlgError:
        return False, None, None, None
    
    a_dir = UB_inverse[0]
    b_dir = UB_inverse[1]
    c_dir = UB_inverse[2]

    return True, a_dir, b_dir, c_dir

@dataclass
class UnitCellOrient:

    # input to this class
    Gstar: np.ndarray
    # length of lattice vectors
    a: float = None
    b: float = None
    c: float = None
    # angles of lattice in radians
    alpha: float = None
    beta: float = None
    gamma: float = None
    # length of reciprocal lattice vectors
    ra: float = None
    rb: float = None
    rc: float = None
    # angles of reciprocal lattice in radians
    ralpha: float = None
    rbeta: float = None
    rgamma: float = None
    # UB matrices
    Bmat: np.ndarray = None
    Bmat_inv: np.ndarray = None
    Umat: np.ndarray = None

    def calculate_B(self):
        """Geometry/Crystal/UnitCell::calculateB - line 813 to 833"""
        self.Bmat = np.array([
            [self.ra, self.rb*np.cos(self.rgamma), self.rc*np.cos(self.beta)],
            [0, self.rb*np.sin(self.rgamma), -self.rc*np.sin(self.rbeta)*np.cos(self.alpha)],
            [0, 0, 1/self.c]
        ])

        self.Bmat_inv = inv(self.Bmat)

    def calculate_reciprocal_lattice(self):
        """Geometry/Crystal/UnitCell::calculateReciprocalLattice - line 802 to 810"""
        self.ra = np.sqrt(self.Gstar[0, 0])
        self.rb = np.sqrt(self.Gstar[1, 1])
        self.rc = np.sqrt(self.Gstar[2, 2])

        def acos_threshold(x):
            return np.arccos(x) if abs(x) > 1e-15 else np.pi / 2
        
        self.ralpha = acos_threshold(self.Gstar[1, 2] / (self.rb * self.rc))
        self.rbeta = acos_threshold(self.Gstar[0, 2] / (self.ra * self.rc))
        self.rgamma = acos_threshold(self.Gstar[0, 1] / (self.ra * self.rb))

    def recalculate_from_Gstar(self):
        """Geometry/Crystal/UnitCell::recalculateFromGstar - line 836 to 858"""
        if self.Gstar.shape != (3, 3):
            raise ValueError(
                "recalculate_from_Gstar(): expected a 3x3 matrix, "
                f"but was given {self.Gstar.shape[0]}x{self.Gstar.shape[1]}"
            )
        
        if np.prod(np.diag(self.Gstar)) <= 0:
            raise ValueError("newGstar")
        
        self.calculate_reciprocal_lattice()

        Gstar_inv = inv(self.Gstar)

        self.a = np.sqrt(Gstar_inv[0, 0])
        self.b = np.sqrt(Gstar_inv[1, 1])
        self.c = np.sqrt(Gstar_inv[2, 2])

        self.alpha = np.arccos(Gstar_inv[1, 2] / self.b / self.c)
        self.beta = np.arccos(Gstar_inv[0, 2] / self.a / self.c)
        self.gamma = np.arccos(Gstar_inv[0, 1] / self.a / self.b)

        self.calculate_B()

def set_UB(UB:np.ndarray) -> UnitCellOrient:
    """Geometry/Crystal/OrientedLattice::setUB - line 115 to 127"""
    if abs(det(UB)) > 1e-10:
        newGstar = UB.T @ UB

        uco = UnitCellOrient(newGstar)
        uco.recalculate_from_Gstar()

        uco.Umat = UB @ uco.Bmat_inv
    
    else:
        raise ValueError("set_UB(): determinant of UB is too close to 0")

    return uco