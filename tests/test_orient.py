import numpy as np
import pytest

from nxrefine.nxorient import UBMatrixFFT


def make_ubm(UB):
    ubm = UBMatrixFFT(min_d=1.0, max_d=12.0, q_vectors=np.zeros((5, 3)))
    ubm._UB = UB
    return ubm


class TestCheckUB:

    def test_defaults_to_current_UB(self):
        assert make_ubm(np.eye(3) * 0.1).check_UB()
        assert not make_ubm(np.zeros((3, 3))).check_UB()

    def test_checks_the_matrix_given(self):
        ubm = make_ubm(np.eye(3) * 0.1)
        assert not ubm.check_UB(np.zeros((3, 3)))
        assert not ubm.check_UB(np.full((3, 3), np.nan))


class TestOptimizeUB:

    def test_valid_indexing(self):
        UB = np.diag([0.1, 0.1, 0.1])
        hkl = [np.array(h, dtype=float) for h in
               ([1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 1])]
        qs = [UB @ h for h in hkl]
        _, new_UB = make_ubm(UB).optimize_UB(hkl, qs)
        assert np.allclose(new_UB, UB)

    def test_rejects_degenerate_UB(self):
        # Collinear indices give a rank-deficient UB, which must be rejected
        # even though the current UB is valid.
        UB = np.diag([0.1, 0.1, 0.1])
        hkl = [np.array([n, n, -n], dtype=float) for n in (1, 2, 3, 4)]
        qs = [UB @ h for h in hkl]
        with pytest.raises(RuntimeError):
            make_ubm(UB).optimize_UB(hkl, qs)
