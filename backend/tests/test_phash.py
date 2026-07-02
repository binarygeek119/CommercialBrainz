"""Tests for pHash PostgreSQL BIGINT storage."""

from app.services.phash import hamming_distance, phash_as_unsigned, phash_to_db

# Example from production error: unsigned value out of signed int64 range
OUT_OF_RANGE_UNSIGNED = 18169723945908232640


def test_phash_to_db_fits_signed_bigint():
    signed = phash_to_db(OUT_OF_RANGE_UNSIGNED)
    assert -(2**63) <= signed < 2**63


def test_phash_round_trip_unsigned():
    signed = phash_to_db(OUT_OF_RANGE_UNSIGNED)
    assert phash_as_unsigned(signed) == OUT_OF_RANGE_UNSIGNED


def test_hamming_distance_uses_unsigned_bits():
    a = phash_to_db(OUT_OF_RANGE_UNSIGNED)
    b = phash_to_db(OUT_OF_RANGE_UNSIGNED)
    assert hamming_distance(a, b) == 0
