import pytest


@pytest.mark.parametrize('k,n,valid', [(20,66,False),(20,67,True),(30,99,False),(30,100,True),(50,166,False),(50,167,True),(100,333,False),(100,334,True)])
def test_boundaries(k, n, valid):
    from portfolio.allocation.cardinality import check_cardinality
    r = check_cardinality(k, n)
    assert (r.status == 'passed') is valid
    assert r.minimum_n == (10*k+2)//3
    assert r.shortfall == max(0, r.minimum_n-n)
    assert r.ratio == k/n
    if not valid: assert '候选产品池过小' in r.message


@pytest.mark.parametrize('k', [True, False, 30.0, 30.5, '30', None, 19, 101])
def test_invalid_k(k):
    from portfolio.allocation.cardinality import check_cardinality
    assert check_cardinality(k, 100).status == 'invalid_k'


def test_empty():
    from portfolio.allocation.cardinality import check_cardinality
    r = check_cardinality(30, 0)
    assert r.ratio is None and r.shortfall == 100 and r.status == 'pool_too_small'


@pytest.mark.parametrize('n', [-1, True, 100.0, None])
def test_invalid_n(n):
    from portfolio.allocation.cardinality import check_cardinality
    with pytest.raises(ValueError): check_cardinality(30, n)
