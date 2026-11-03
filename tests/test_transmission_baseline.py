import numpy as np
from scipy.ndimage import median_filter

from nxrefine.nxutils import annulus_indices, capped_sum, robust_baseline


def make_series(n=1500, seed=0):
    rng = np.random.default_rng(seed)
    frames = np.arange(n)
    truth = 1000.0 * (1.4 - 0.4 * np.sin(np.pi * frames / n))
    data = truth + rng.normal(0.0, 10.0, n)
    for center, width, height in ((300, 25, 700), (800, 40, 500),
                                  (1200, 8, 900)):
        data += height * np.exp(-0.5 * ((frames - center) / width) ** 2)
    return truth, data


def test_robust_baseline_follows_the_lower_envelope():
    truth, data = make_series()
    fit = robust_baseline(data, knot_spacing=120)
    assert np.max(np.abs(fit / truth - 1.0)) < 0.03


def test_robust_baseline_beats_a_median_filter_on_wide_bursts():
    truth, data = make_series()
    fit = robust_baseline(data, knot_spacing=120)
    median = median_filter(data, size=31, mode='nearest')
    assert (np.max(np.abs(fit / truth - 1.0))
            < 0.5 * np.max(np.abs(median / truth - 1.0)))


def test_robust_baseline_symmetric_option_follows_the_data():
    frames = np.arange(600)
    data = 100.0 + 20.0 * np.sin(2 * np.pi * frames / 600)
    fit = robust_baseline(data, knot_spacing=60, upper_weight=1.0)
    np.testing.assert_allclose(fit, data, atol=1.0)


def test_robust_baseline_short_and_constant_input():
    np.testing.assert_allclose(robust_baseline(np.full(3, 5.0)), 5.0)
    np.testing.assert_allclose(robust_baseline(np.full(50, 5.0)), 5.0)
    assert robust_baseline(np.array([])).size == 0


def test_capped_sum_limits_bright_pixels():
    values = np.array([[0, 1, 2, 3, 50], [1, 1, 1, 1, 1]])
    np.testing.assert_allclose(capped_sum(values, 2), [7.0, 5.0])
    np.testing.assert_allclose(capped_sum(values, 2, scale=2.0), [14.0, 10.0])
    np.testing.assert_allclose(capped_sum(np.array([[-1, 5]]), 2), [2.0])


def test_capped_sum_has_no_jumps_for_low_counts():
    rng = np.random.default_rng(1)
    rates = np.linspace(0.45, 0.55, 40)
    sums = np.array([capped_sum(rng.poisson(rate, (1, 200000)), 2)[0]
                     for rate in rates])
    assert np.all(np.diff(sums) > -0.01 * sums[:-1])
    assert np.max(np.abs(np.diff(sums))) < 0.03 * sums[0]


def test_annulus_indices_use_an_integer_pixel_mask():
    pixel_mask = np.zeros((4, 4), dtype=np.int8)
    pixel_mask[0, 0] = 1
    outside = np.zeros((4, 4), dtype=bool)
    outside[3, :] = True
    indices = annulus_indices(pixel_mask, outside)
    expected = [i for i in range(16) if i != 0 and i // 4 != 3]
    assert indices.tolist() == expected
    assert annulus_indices(np.ones((2, 2), dtype=np.int8),
                           np.zeros((2, 2), dtype=bool)).size == 0
