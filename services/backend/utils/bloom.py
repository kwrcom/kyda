import hashlib
import math
from typing import Iterable


class RedisBackedBloom:
    """Small Redis-backed Bloom filter implementation.

    This class is intentionally minimal to keep dependencies light for the example.
    It uses several hash functions (SHA-256 with different salts) and maps them
    into a Redis bitmap using SETBIT/GETBIT from a Redis client.

    Methods expect a `redis_client` implementing setbit/getbit commands and
    a key name to store the bitmap.
    """

    def __init__(self, redis_client, key: str = "bloom:blacklist", size_bits: int = 10_000_000, num_hashes: int = 7):
        self.redis = redis_client
        self.key = key
        self.size = int(size_bits)
        self.k = int(num_hashes)

    def _hashes(self, value: str) -> Iterable[int]:
        # use SHA-256 with different salts to produce multiple hashes
        for i in range(self.k):
            h = hashlib.sha256()
            h.update(value.encode("utf-8"))
            h.update(i.to_bytes(2, "big"))
            digest = int.from_bytes(h.digest(), "big")
            yield digest % self.size

    def add(self, value: str):
        for bit in self._hashes(value):
            # SETBIT key offset value -> sets single bit
            self.redis.setbit(self.key, bit, 1)

    def contains(self, value: str) -> bool:
        # returns True if the value is probably present (may be false positive)
        for bit in self._hashes(value):
            if self.redis.getbit(self.key, bit) == 0:
                return False
        return True

    def clear(self):
        # remove the underlying key
        self.redis.delete(self.key)
