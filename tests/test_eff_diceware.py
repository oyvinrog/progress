"""Tests for EFF diceware passphrase generator."""

import math

import eff_diceware
from eff_diceware import _load_wordlist, generate_passphrase


def test_wordlist_loads_7776_words():
    words = _load_wordlist()
    assert len(words) == 7776


def test_wordlist_contains_only_lowercase_alpha():
    for word in _load_wordlist():
        assert word == word.lower()
        assert word.isalpha() or "-" in word or "'" in word, f"unexpected chars in: {word}"


def test_generate_returns_correct_word_count():
    for n in (4, 6, 8):
        passphrase, _bits = generate_passphrase(num_words=n)
        assert len(passphrase.split("-")) == n


def test_generate_minimum_is_four_words():
    passphrase, _bits = generate_passphrase(num_words=2)
    assert len(passphrase.split("-")) == 4


def test_generate_entropy_bits_correct():
    _passphrase, bits = generate_passphrase(num_words=6)
    expected = 6 * math.log2(7776)
    assert abs(bits - expected) < 0.01


def test_generate_uses_custom_separator():
    passphrase, _ = generate_passphrase(num_words=5, separator=" ")
    assert " " in passphrase
    assert len(passphrase.split(" ")) == 5


def test_generate_produces_different_passphrases():
    results = {generate_passphrase(num_words=6)[0] for _ in range(10)}
    assert len(results) > 1


def test_downloads_when_cache_missing(tmp_path, monkeypatch):
    """When the cache file is absent, _load_wordlist downloads and caches it."""
    cache_file = tmp_path / "eff_large_wordlist.txt"
    monkeypatch.setattr(eff_diceware, "_CACHE_PATH", str(cache_file))
    monkeypatch.setattr(eff_diceware, "_WORDLIST", [])

    words = _load_wordlist()
    assert len(words) == 7776
    assert cache_file.exists()
    cached_lines = [l for l in cache_file.read_text().splitlines() if l.strip()]
    assert len(cached_lines) == 7776


def test_redownloads_when_cache_corrupted(tmp_path, monkeypatch):
    """When the cache file has wrong word count, it re-downloads."""
    cache_file = tmp_path / "eff_large_wordlist.txt"
    cache_file.write_text("bad\ndata\n")
    monkeypatch.setattr(eff_diceware, "_CACHE_PATH", str(cache_file))
    monkeypatch.setattr(eff_diceware, "_WORDLIST", [])

    words = _load_wordlist()
    assert len(words) == 7776
    cached_lines = [l for l in cache_file.read_text().splitlines() if l.strip()]
    assert len(cached_lines) == 7776
