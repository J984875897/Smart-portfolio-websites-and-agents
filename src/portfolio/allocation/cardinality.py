"""Target holding count is a research gate, not a constructed portfolio."""
from dataclasses import dataclass
from numbers import Integral


@dataclass(frozen=True)
class CardinalityResult:
    k: object
    n: int
    ratio: float | None
    minimum_n: int | None
    shortfall: int | None
    status: str
    message: str


def check_cardinality(k, n):
    if isinstance(n, bool) or not isinstance(n, Integral) or n < 0:
        raise ValueError('N must be a nonnegative integer')
    n = int(n)
    if isinstance(k, bool) or not isinstance(k, Integral) or not 20 <= k <= 100:
        return CardinalityResult(k, n, None, None, None, 'invalid_k', 'K 必须为 20–100 的整数')
    k = int(k)
    minimum = (10*k+2)//3
    passed = 10*k <= 3*n
    return CardinalityResult(k, n, k/n if n else None, minimum, max(0, minimum-n),
                             'passed' if passed else 'pool_too_small',
                             '数量条件通过；尚未生成组合' if passed else '候选产品池过小')
