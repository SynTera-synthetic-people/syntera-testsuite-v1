import pytest
from ml_engine.comparison_engine import ComparisonEngine

@pytest.fixture
def engine():
    return ComparisonEngine()

def test_chi_square(engine):
    result = engine.chi_square_test([42, 33, 18, 7], [40, 35, 20, 5])
    assert "chi2" in result
    assert "tier" in result

def test_compare_distributions(engine):
    result = engine.compare_distributions([1, 2, 3], [1, 2, 3])
    assert "overall_tier" in result
    assert "tests" in result

