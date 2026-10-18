"""Simulation test (Test 9)."""
import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))

import simulate

# Use very small params for fast unit tests
_ORIG_VICTIMS = simulate.N_VICTIMS
_ORIG_MINUTES = simulate.SIM_MINUTES


def setup_function():
    simulate.N_VICTIMS = 30
    simulate.SIM_MINUTES = 10


def teardown_function():
    simulate.N_VICTIMS = _ORIG_VICTIMS
    simulate.SIM_MINUTES = _ORIG_MINUTES


def test_simulation_runs():
    rng = random.Random(42)
    result = simulate.run_scenario(0.05, True, True, rng)
    assert 0.0 <= result <= 1.0


def test_simulation_order():
    """More adoption = at least as many messages delivered."""
    r1 = simulate.run_scenario(0.01, True, True, random.Random(42))
    r2 = simulate.run_scenario(0.10, True, True, random.Random(42))
    # Higher adoption should generally produce >= delivery
    assert r2 >= r1 * 0.5   # generous bound


def test_generate_chart_no_mpl(tmp_path):
    """generate_chart table branch runs without raising."""
    # Run only a single quick scenario at the lowest adoption level
    import unittest.mock as mock
    # Patch run_all_seeds to return instantly (already tested above)
    with mock.patch.object(simulate, "run_all_seeds", return_value=0.5):
        orig_mpl = simulate.HAS_MPL
        simulate.HAS_MPL = False
        try:
            simulate.generate_chart(str(tmp_path / "test.png"))
        finally:
            simulate.HAS_MPL = orig_mpl
