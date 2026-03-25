#!/usr/bin/env python3
"""Proof that derive-then-forget removes passphrase from process memory.

Scans raw process memory via /proc/self/mem (the same technique an attacker
with local access would use) and counts occurrences of the passphrase.

Demonstrates:
  1. OLD approach: caching EncryptionCredentials keeps the passphrase in
     process memory as readable bytes.
  2. NEW approach: caching DerivedKeyMaterial means the passphrase is no
     longer present — only the irreversible derived AES key remains.

Run:
    python tests/proof_derive_then_forget.py
"""

from __future__ import annotations

import gc
import sys

# Ensure the project root is on the path so imports work.
sys.path.insert(0, ".")

from progress_crypto import (
    DerivedKeyMaterial,
    EncryptionCredentials,
    derive_key_material,
    encrypt_with_derived_key,
)

PROJECT_DATA = {"tasks": [{"title": "demo"}], "saved_at": "2026-01-01T00:00:00"}


def _make_passphrase() -> str:
    """Build a fresh passphrase string object (simulates user keyboard input)."""
    # Constructed dynamically so the full string never appears as a code literal.
    return "".join(["My-Sup3r", "Secret-P@ss", "phrase-X7q", "9Zw2!demo"])


def _count_in_process_memory(needle: bytes) -> int:
    """Scan readable regions of /proc/self/mem for occurrences of needle."""
    count = 0
    with open("/proc/self/maps", "r") as maps:
        for line in maps:
            perms = line.split()[1]
            if "r" not in perms:
                continue
            addr_start, addr_end = line.split()[0].split("-")
            start = int(addr_start, 16)
            end = int(addr_end, 16)
            try:
                with open("/proc/self/mem", "rb") as mem:
                    mem.seek(start)
                    chunk = mem.read(end - start)
                    count += chunk.count(needle)
            except (OSError, ValueError, OverflowError):
                continue
    return count


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ------------------------------------------------------------------
# 0. Baseline — how many times does the needle appear with no caching?
# ------------------------------------------------------------------
needle = _make_passphrase().encode("utf-8")
baseline = _count_in_process_memory(needle)
print(f"\nBaseline: passphrase appears {baseline} time(s) in raw process memory")
print("  (from the needle variable itself and/or function code object)")

# ------------------------------------------------------------------
# 1. OLD approach — cache EncryptionCredentials (contains passphrase)
# ------------------------------------------------------------------
_print_section("OLD: caching EncryptionCredentials")

passphrase_from_ui = _make_passphrase()  # simulates QLineEdit.text()
creds = EncryptionCredentials(passphrase=passphrase_from_ui)

# Simulate what task_model.py USED to do: cache the credentials object.
cached_credentials = EncryptionCredentials(
    passphrase=creds.passphrase,
    use_yubikey=creds.use_yubikey,
    yubikey_slot=creds.yubikey_slot,
)

# Drop the original refs — only the cache remains (as in the old code).
del creds
del passphrase_from_ui
gc.collect()

old_count = _count_in_process_memory(needle)
old_extra = old_count - baseline
print(f"  Passphrase appears {old_count} time(s) in memory ({old_extra} extra vs baseline)")
assert old_extra > 0, "BUG: cached passphrase should add at least 1 copy"
print("  --> PASSPHRASE IS IN MEMORY (attackable via memory dump)")

# Clean up for the next test.
del cached_credentials
gc.collect()

# ------------------------------------------------------------------
# 2. NEW approach — derive-then-forget
# ------------------------------------------------------------------
_print_section("NEW: derive-then-forget (cache DerivedKeyMaterial)")

passphrase_from_ui = _make_passphrase()  # simulates QLineEdit.text()
creds = EncryptionCredentials(passphrase=passphrase_from_ui)
key_material: DerivedKeyMaterial = derive_key_material(creds)

# Verify encryption works with cached key material.
envelope = encrypt_with_derived_key(PROJECT_DATA, key_material)
assert "ciphertext" in envelope, "encryption failed"

# Drop credentials — only key_material is cached (no passphrase inside).
del creds
del passphrase_from_ui
gc.collect()

new_count = _count_in_process_memory(needle)
new_extra = new_count - baseline
print(f"  Passphrase appears {new_count} time(s) in memory ({new_extra} extra vs baseline)")
assert new_extra == 0, (
    f"FAIL: passphrase has {new_extra} extra copy(ies) after derive-then-forget!"
)
print("  --> PASSPHRASE IS NOT IN MEMORY (safe!)")

# Show what IS cached.
print(f"\n  Cached key (hex): {key_material.key.hex()[:32]}...")
print(f"  Cached salt (hex): {key_material.salt.hex()}")
print("  Original passphrase: not found in process memory")

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
_print_section("RESULT")
print("  OLD: passphrase stays in process memory        --> VULNERABLE to dump")
print("  NEW: only derived AES key in memory            --> SAFE")
print("  The passphrase cannot be recovered from the derived key (Argon2id).")
print()
