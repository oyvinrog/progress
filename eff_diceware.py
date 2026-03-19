"""EFF Diceware passphrase generator.

Uses the EFF large wordlist (7776 words) to generate strong,
memorable passphrases via cryptographically secure random selection.

The wordlist is downloaded from the EFF website on first use and
cached locally for subsequent runs.

Each word contributes ~12.9 bits of entropy, so:
  6 words ≈ 77.5 bits
  7 words ≈ 90.5 bits
  8 words ≈ 103.4 bits
"""

import math
import os
import secrets
import sys
import urllib.error
import urllib.request
from typing import List, Tuple

_WORDLIST: List[str] = []

_EFF_URL = "https://www.eff.org/files/2016/07/18/eff_large_wordlist.txt"

_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "eff_large_wordlist.txt",
)

_EXPECTED_WORD_COUNT = 7776


def _download_wordlist() -> List[str]:
    """Download the EFF large wordlist and cache it to disk."""
    try:
        with urllib.request.urlopen(_EFF_URL, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError(
            f"Failed to download EFF wordlist from {_EFF_URL}: {exc}"
        ) from exc

    words: List[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        word = parts[-1].strip()
        if word:
            words.append(word)

    if len(words) != _EXPECTED_WORD_COUNT:
        raise RuntimeError(
            f"EFF wordlist has {len(words)} words, expected {_EXPECTED_WORD_COUNT}"
        )

    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as fh:
            fh.write("\n".join(words) + "\n")
    except OSError as exc:
        print(f"Warning: could not cache EFF wordlist: {exc}", file=sys.stderr)

    return words


def _load_wordlist() -> List[str]:
    """Load the EFF large wordlist, downloading on first use."""
    global _WORDLIST
    if _WORDLIST:
        return _WORDLIST

    if os.path.isfile(_CACHE_PATH):
        with open(_CACHE_PATH, encoding="utf-8") as fh:
            words = [line.strip() for line in fh if line.strip()]
        if len(words) == _EXPECTED_WORD_COUNT:
            _WORDLIST = words
            return _WORDLIST

    _WORDLIST = _download_wordlist()
    return _WORDLIST


def generate_passphrase(num_words: int = 6, separator: str = "-") -> Tuple[str, float]:
    """Generate a diceware passphrase and return (passphrase, entropy_bits).

    Parameters
    ----------
    num_words:
        Number of words to include (default 6, minimum 4).
    separator:
        Character(s) placed between words.

    Returns
    -------
    Tuple of (passphrase_string, entropy_bits).
    """
    num_words = max(4, num_words)
    wordlist = _load_wordlist()
    pool_size = len(wordlist)
    words = [secrets.choice(wordlist) for _ in range(num_words)]
    entropy_bits = num_words * math.log2(pool_size)
    return separator.join(words), entropy_bits
