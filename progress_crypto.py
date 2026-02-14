"""Encryption helpers for .progress project persistence."""

from __future__ import annotations

import base64
import binascii
import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

try:  # pragma: no cover - import availability depends on environment
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception:  # pragma: no cover - import availability depends on environment
    InvalidTag = Exception  # type: ignore[assignment]
    AESGCM = None  # type: ignore[assignment]

try:  # pragma: no cover - import availability depends on environment
    from argon2.low_level import Type, hash_secret_raw
except Exception:  # pragma: no cover - import availability depends on environment
    Type = None  # type: ignore[assignment]
    hash_secret_raw = None  # type: ignore[assignment]


class CryptoError(Exception):
    """Raised when encryption/decryption or credential steps fail."""


@dataclass
class EncryptionCredentials:
    """User credentials used to derive the file encryption key."""

    passphrase: Optional[str] = None
    use_yubikey: bool = False
    yubikey_slot: str = "2"


class YubiKeyProvider(Protocol):
    """Interface for obtaining deterministic challenge-response bytes from YubiKey."""

    def hmac_challenge_response(self, slot: str, challenge: bytes) -> bytes:
        ...


class YkmanCliYubiKeyProvider:
    """YubiKey challenge-response provider backed by the `ykman` CLI."""

    def hmac_challenge_response(self, slot: str, challenge: bytes) -> bytes:
        slot_number = _slot_to_int(slot)
        if slot_number not in (1, 2):
            raise CryptoError("YubiKey slot must be 1 or 2")

        ykman_bin = _resolve_ykman_binary()
        challenge_hex = challenge.hex()
        cmd = [ykman_bin, "otp", "calculate", str(slot_number), challenge_hex]
        try:
            completed = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:  # pragma: no cover - environment dependent
            raise CryptoError(f"Failed to execute ykman CLI: {exc}") from exc

        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            stdout = (completed.stdout or "").strip()
            detail = stderr or stdout or f"exit code {completed.returncode}"
            raise CryptoError(f"YubiKey challenge-response failed via ykman: {detail}")

        return _parse_hmac_response(completed.stdout)


def has_yubikey_cli() -> bool:
    """Return True when the ykman CLI is available."""

    return _resolve_ykman_binary(raise_on_missing=False) is not None


def yubikey_support_guidance() -> str:
    """Return OS-specific setup guidance for enabling YubiKey mode."""

    detected = _resolve_ykman_binary(raise_on_missing=False)
    if detected:
        return f"YubiKey support detected via ykman at: {detected}"

    system = platform.system().lower()
    if system == "windows":
        return (
            "YubiKey mode is unavailable: ykman CLI not found.\n\n"
            "Windows (no-admin option):\n"
            "1. Download a portable ykman.exe build.\n"
            "2. Set YKMAN_PATH to that executable before launching the app.\n"
            "   Example (cmd): set YKMAN_PATH=C:\\tools\\ykman\\ykman.exe\n"
            "3. Reopen the app and choose YubiKey mode again.\n\n"
            "Without ykman, use passphrase-only encryption."
        )
    if system == "linux":
        return (
            "YubiKey mode is unavailable: ykman CLI not found.\n\n"
            "Linux setup:\n"
            "1. Install tools: sudo apt update && sudo apt install -y yubikey-manager pcscd\n"
            "2. Ensure service is running: systemctl --user start pcscd (or system service)\n"
            "3. Reopen the app and choose YubiKey mode again.\n\n"
            "Without ykman, use passphrase-only encryption."
        )
    return (
        "YubiKey mode is unavailable: ykman CLI not found.\n\n"
        "Install Yubico ykman CLI or set YKMAN_PATH to the ykman executable,\n"
        "then reopen the app and try YubiKey mode again.\n\n"
        "Without ykman, use passphrase-only encryption."
    )


def encrypt_project_data(
    project_data: Dict[str, Any],
    credentials: EncryptionCredentials,
    *,
    kdf_params: Optional[Dict[str, int]] = None,
    yubikey_provider: Optional[YubiKeyProvider] = None,
) -> Dict[str, Any]:
    """Encrypt plain project JSON payload into the v1.2 envelope format."""
    _require_crypto_dependencies()

    normalized_kdf = _normalize_kdf_params(kdf_params)
    auth_mode, challenge = _resolve_auth_mode_for_save(credentials)
    secret_material = _build_secret_material(
        credentials,
        challenge=challenge,
        yubikey_provider=yubikey_provider,
    )

    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key_argon2id(secret_material, salt, normalized_kdf)

    metadata: Dict[str, Any] = {
        "cipher": "AES-256-GCM",
        "kdf": "Argon2id",
        "kdf_params": normalized_kdf,
        "salt_b64": _b64encode(salt),
        "nonce_b64": _b64encode(nonce),
        "auth_mode": auth_mode,
        "yubikey": {
            "enabled": credentials.use_yubikey,
            "slot": credentials.yubikey_slot,
            "challenge_b64": _b64encode(challenge) if challenge is not None else "",
        },
    }

    aad = _build_aad("1.2", metadata)
    metadata["aad_b64"] = _b64encode(aad)

    plaintext = json.dumps(project_data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)

    return {
        "version": "1.2",
        "saved_at": project_data.get("saved_at"),
        "encryption": metadata,
        "ciphertext": _b64encode(ciphertext),
    }


def decrypt_project_data(
    envelope: Dict[str, Any],
    credentials: EncryptionCredentials,
    *,
    yubikey_provider: Optional[YubiKeyProvider] = None,
) -> Dict[str, Any]:
    """Decrypt an encrypted v1.2 envelope into plain project JSON payload."""
    _require_crypto_dependencies()

    if envelope.get("version") != "1.2":
        raise CryptoError("Unsupported encrypted project version")

    encryption = envelope.get("encryption")
    if not isinstance(encryption, dict):
        raise CryptoError("Encrypted project missing encryption metadata")

    if encryption.get("cipher") != "AES-256-GCM":
        raise CryptoError("Unsupported cipher")
    if encryption.get("kdf") != "Argon2id":
        raise CryptoError("Unsupported KDF")

    kdf_params = _normalize_kdf_params(encryption.get("kdf_params"))

    try:
        salt = _b64decode(encryption["salt_b64"])
        nonce = _b64decode(encryption["nonce_b64"])
        ciphertext = _b64decode(envelope["ciphertext"])
    except KeyError as exc:
        raise CryptoError(f"Encrypted project missing field: {exc}") from exc
    except ValueError as exc:
        raise CryptoError(f"Encrypted project contains invalid base64 data: {exc}") from exc

    expected_aad = _build_aad("1.2", {k: v for k, v in encryption.items() if k != "aad_b64"})
    aad_b64 = encryption.get("aad_b64")
    if not isinstance(aad_b64, str):
        raise CryptoError("Encrypted project missing AAD")

    try:
        aad = _b64decode(aad_b64)
    except ValueError as exc:
        raise CryptoError(f"Encrypted project has invalid AAD: {exc}") from exc

    if aad != expected_aad:
        raise CryptoError("Encrypted project metadata integrity check failed")

    secret_material = _build_secret_material_for_load(
        credentials,
        encryption,
        yubikey_provider=yubikey_provider,
    )

    key = _derive_key_argon2id(secret_material, salt, kdf_params)

    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise CryptoError("Unable to decrypt project: invalid credentials or corrupted file") from exc

    try:
        payload = json.loads(plaintext.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise CryptoError(f"Decrypted payload is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise CryptoError("Decrypted payload must be a JSON object")

    return payload


def is_encrypted_envelope(project_data: Dict[str, Any]) -> bool:
    """Return True if the loaded JSON payload is an encrypted envelope."""

    return (
        isinstance(project_data, dict)
        and isinstance(project_data.get("encryption"), dict)
        and isinstance(project_data.get("ciphertext"), str)
    )


def _resolve_auth_mode_for_save(credentials: EncryptionCredentials) -> tuple[str, Optional[bytes]]:
    passphrase = (credentials.passphrase or "").strip()
    if passphrase and credentials.use_yubikey:
        return "passphrase+yubikey", os.urandom(32)
    if passphrase:
        return "passphrase", None
    if credentials.use_yubikey:
        return "yubikey", os.urandom(32)
    raise CryptoError("At least one credential is required")


def _build_secret_material_for_load(
    credentials: EncryptionCredentials,
    encryption: Dict[str, Any],
    *,
    yubikey_provider: Optional[YubiKeyProvider],
) -> bytes:
    auth_mode = encryption.get("auth_mode")
    yk_meta = encryption.get("yubikey")
    if not isinstance(auth_mode, str):
        raise CryptoError("Encrypted project missing auth mode")
    if not isinstance(yk_meta, dict):
        raise CryptoError("Encrypted project missing yubikey metadata")

    challenge_b64 = yk_meta.get("challenge_b64", "")
    challenge = b""
    if challenge_b64:
        challenge = _b64decode(str(challenge_b64))

    if auth_mode == "passphrase":
        return _build_secret_material(credentials, challenge=None, yubikey_provider=yubikey_provider)

    if auth_mode == "yubikey":
        return _build_secret_material(
            EncryptionCredentials(passphrase=None, use_yubikey=True, yubikey_slot=str(yk_meta.get("slot", "2"))),
            challenge=challenge,
            yubikey_provider=yubikey_provider,
        )

    if auth_mode == "passphrase+yubikey":
        return _build_secret_material(
            EncryptionCredentials(
                passphrase=credentials.passphrase,
                use_yubikey=True,
                yubikey_slot=str(yk_meta.get("slot", credentials.yubikey_slot)),
            ),
            challenge=challenge,
            yubikey_provider=yubikey_provider,
        )

    raise CryptoError("Unsupported auth mode")


def _build_secret_material(
    credentials: EncryptionCredentials,
    *,
    challenge: Optional[bytes],
    yubikey_provider: Optional[YubiKeyProvider],
) -> bytes:
    passphrase_bytes = (credentials.passphrase or "").encode("utf-8")

    yubikey_bytes = b""
    if credentials.use_yubikey:
        if challenge is None:
            raise CryptoError("YubiKey challenge is required")
        provider = yubikey_provider or YkmanCliYubiKeyProvider()
        yubikey_bytes = provider.hmac_challenge_response(credentials.yubikey_slot, challenge)

    if passphrase_bytes and yubikey_bytes:
        return passphrase_bytes + b"\x00" + yubikey_bytes
    if passphrase_bytes:
        return passphrase_bytes
    if yubikey_bytes:
        return yubikey_bytes

    raise CryptoError("At least one credential is required")


def _derive_key_argon2id(secret_material: bytes, salt: bytes, params: Dict[str, int]) -> bytes:
    _require_crypto_dependencies()
    return hash_secret_raw(
        secret=secret_material,
        salt=salt,
        time_cost=params["time_cost"],
        memory_cost=params["memory_cost"],
        parallelism=params["parallelism"],
        hash_len=params["hash_len"],
        type=Type.ID,
    )


def _normalize_kdf_params(raw: Optional[Dict[str, Any]]) -> Dict[str, int]:
    defaults = {
        "time_cost": 3,
        "memory_cost": 65536,
        "parallelism": 1,
        "hash_len": 32,
    }
    if not isinstance(raw, dict):
        return defaults

    normalized = dict(defaults)
    for key in defaults:
        value = raw.get(key)
        if value is not None:
            try:
                normalized[key] = int(value)
            except (TypeError, ValueError) as exc:
                raise CryptoError(f"Invalid KDF parameter {key}: {value}") from exc
    return normalized


def _require_crypto_dependencies() -> None:
    if AESGCM is None:
        raise CryptoError("Missing dependency: cryptography is required for encrypted project support")
    if hash_secret_raw is None or Type is None:
        raise CryptoError("Missing dependency: argon2-cffi is required for encrypted project support")


def _build_aad(version: str, metadata: Dict[str, Any]) -> bytes:
    payload = {
        "version": version,
        "encryption": metadata,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _slot_to_int(slot: str) -> int:
    try:
        return int(slot)
    except (TypeError, ValueError) as exc:
        raise CryptoError(f"Invalid YubiKey slot: {slot}") from exc


def _resolve_ykman_binary(*, raise_on_missing: bool = True) -> Optional[str]:
    configured = os.environ.get("YKMAN_PATH", "").strip()
    candidates = [configured] if configured else []
    candidates.extend(["ykman", "ykman.exe"])
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate) if os.path.sep not in candidate else candidate
        if resolved and os.path.exists(resolved):
            return resolved
    if raise_on_missing:
        raise CryptoError(
            "YubiKey CLI not found. Install ykman or set YKMAN_PATH, "
            "or use passphrase-only mode."
        )
    return None


def _parse_hmac_response(output: str) -> bytes:
    cleaned = (output or "").strip()
    if not cleaned:
        raise CryptoError("YubiKey challenge-response returned empty output")

    # ykman output is typically a hex digest. Extract the first 40-hex token.
    token_match = re.search(r"\b([0-9a-fA-F]{40})\b", cleaned)
    token = token_match.group(1) if token_match else cleaned.splitlines()[-1].strip()
    if token.startswith("0x"):
        token = token[2:]
    token = token.replace(" ", "")

    try:
        response = binascii.unhexlify(token)
    except (binascii.Error, ValueError) as exc:
        raise CryptoError(
            f"Unexpected ykman challenge-response format: {cleaned}"
        ) from exc

    if len(response) != 20:
        raise CryptoError(f"Unexpected YubiKey response length: {len(response)}")
    return response


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except Exception as exc:
        raise ValueError("invalid base64") from exc
