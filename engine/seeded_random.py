"""
Deterministic seeded PRNG using Mulberry32 algorithm.
Same seed → same operation every single time. Guarantees reproducibility.
"""


class SeededRandom:
    """Mulberry32 PRNG — fast, deterministic, no external dependencies."""

    def __init__(self, seed: int):
        self._state = seed & 0xFFFFFFFF

    def _next(self) -> int:
        self._state = (self._state + 0x6D2B79F5) & 0xFFFFFFFF
        z = self._state
        z = ((z ^ (z >> 15)) * (z | 1)) & 0xFFFFFFFF
        z ^= z + ((z ^ (z >> 7)) * (z | 61)) & 0xFFFFFFFF
        z = (z ^ (z >> 14)) & 0xFFFFFFFF
        return z

    def next_int(self, min_val: int, max_val: int) -> int:
        """Return a random integer in [min_val, max_val] inclusive."""
        return min_val + (self._next() % (max_val - min_val + 1))

    def next_choice(self, choices: list):
        """Pick a random element from a list."""
        return choices[self._next() % len(choices)]


def generate_operation(seed: int):
    """
    Generate a deterministic WriteOperation from a seed.
    The same seed ALWAYS produces the exact same operation.
    """
    from engine.types import WriteOperation

    rng = SeededRandom(seed)
    key_suffix = rng.next_int(1, 100)
    value = rng.next_int(1000, 99999)
    old_value = rng.next_int(1000, 99999)
    version = rng.next_int(1, 50)
    txn_num = rng.next_int(1000, 9999)

    return WriteOperation(
        txn_id=f"txn_{txn_num}",
        key=f"acct_{key_suffix:03d}",
        value=str(value),
        version=version,
        old_value=str(old_value),
    )
