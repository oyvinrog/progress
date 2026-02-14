import os
import types

import pytest

import progress_crypto as pc


class DummyYubiKeyProvider:
    def __init__(self, response: bytes):
        self.response = response
        self.calls = []

    def hmac_challenge_response(self, slot: str, challenge: bytes) -> bytes:
        self.calls.append((slot, challenge))
        return self.response


def _credentials(passphrase="secret", use_yubikey=False, slot="2"):
    return pc.EncryptionCredentials(
        passphrase=passphrase,
        use_yubikey=use_yubikey,
        yubikey_slot=slot,
    )


def test_encrypt_decrypt_roundtrip_passphrase_only():
    payload = {"a": 1, "saved_at": "2026-02-14T00:00:00Z"}
    creds = _credentials(passphrase="pw", use_yubikey=False)
    envelope = pc.encrypt_project_data(payload, creds)
    out = pc.decrypt_project_data(envelope, creds)
    assert out == payload
    assert pc.is_encrypted_envelope(envelope) is True


def test_encrypt_decrypt_roundtrip_passphrase_and_yubikey(monkeypatch):
    provider = DummyYubiKeyProvider(b"x" * 20)
    payload = {"k": "v"}
    creds = _credentials(passphrase="pw", use_yubikey=True, slot="2")
    monkeypatch.setattr(pc.os, "urandom", lambda n: b"a" * n)
    envelope = pc.encrypt_project_data(payload, creds, yubikey_provider=provider)
    out = pc.decrypt_project_data(envelope, creds, yubikey_provider=provider)
    assert out == payload
    assert len(provider.calls) == 2


def test_encrypt_requires_at_least_one_credential():
    with pytest.raises(pc.CryptoError, match="At least one credential is required"):
        pc.encrypt_project_data({"x": 1}, _credentials(passphrase=None, use_yubikey=False))


def test_decrypt_rejects_invalid_envelope_shapes():
    creds = _credentials("pw")
    with pytest.raises(pc.CryptoError, match="Unsupported encrypted project version"):
        pc.decrypt_project_data({"version": "1.1"}, creds)
    with pytest.raises(pc.CryptoError, match="missing encryption metadata"):
        pc.decrypt_project_data({"version": "1.2", "encryption": None}, creds)


def test_decrypt_rejects_unsupported_cipher_and_kdf():
    creds = _credentials("pw")
    base = {
        "version": "1.2",
        "encryption": {"cipher": "BAD", "kdf": "Argon2id", "kdf_params": {}},
        "ciphertext": "",
    }
    with pytest.raises(pc.CryptoError, match="Unsupported cipher"):
        pc.decrypt_project_data(base, creds)

    base["encryption"]["cipher"] = "AES-256-GCM"
    base["encryption"]["kdf"] = "BAD"
    with pytest.raises(pc.CryptoError, match="Unsupported KDF"):
        pc.decrypt_project_data(base, creds)


def test_decrypt_rejects_missing_or_invalid_fields():
    creds = _credentials("pw")
    valid = pc.encrypt_project_data({"x": 1}, creds)

    missing = dict(valid)
    missing["encryption"] = dict(valid["encryption"])
    del missing["encryption"]["salt_b64"]
    with pytest.raises(pc.CryptoError, match="missing field"):
        pc.decrypt_project_data(missing, creds)

    bad = dict(valid)
    bad["encryption"] = dict(valid["encryption"])
    bad["encryption"]["nonce_b64"] = "not-base64"
    with pytest.raises(pc.CryptoError, match="invalid base64 data"):
        pc.decrypt_project_data(bad, creds)


def test_decrypt_rejects_missing_or_bad_aad():
    creds = _credentials("pw")
    envelope = pc.encrypt_project_data({"x": 1}, creds)

    missing = dict(envelope)
    missing["encryption"] = dict(envelope["encryption"])
    del missing["encryption"]["aad_b64"]
    with pytest.raises(pc.CryptoError, match="missing AAD"):
        pc.decrypt_project_data(missing, creds)

    bad = dict(envelope)
    bad["encryption"] = dict(envelope["encryption"])
    bad["encryption"]["aad_b64"] = "%%%%"
    with pytest.raises(pc.CryptoError, match="invalid AAD"):
        pc.decrypt_project_data(bad, creds)

    mismatch = dict(envelope)
    mismatch["encryption"] = dict(envelope["encryption"])
    mismatch["encryption"]["auth_mode"] = "yubikey"
    with pytest.raises(pc.CryptoError, match="integrity check failed"):
        pc.decrypt_project_data(mismatch, creds)


def test_decrypt_rejects_invalid_credentials():
    envelope = pc.encrypt_project_data({"x": 1}, _credentials("right"))
    with pytest.raises(pc.CryptoError, match="invalid credentials or corrupted file"):
        pc.decrypt_project_data(envelope, _credentials("wrong"))


def test_decrypt_rejects_non_json_payload(monkeypatch):
    class FakeAES:
        def __init__(self, _key):
            pass

        def decrypt(self, _nonce, _ciphertext, _aad):
            return b"\xff\xfe"

    creds = _credentials("pw")
    envelope = pc.encrypt_project_data({"x": 1}, creds)
    monkeypatch.setattr(pc, "AESGCM", FakeAES)
    with pytest.raises(pc.CryptoError, match="not valid JSON"):
        pc.decrypt_project_data(envelope, creds)


def test_decrypt_rejects_non_object_json(monkeypatch):
    class FakeAES:
        def __init__(self, _key):
            pass

        def decrypt(self, _nonce, _ciphertext, _aad):
            return b"[1,2,3]"

    creds = _credentials("pw")
    envelope = pc.encrypt_project_data({"x": 1}, creds)
    monkeypatch.setattr(pc, "AESGCM", FakeAES)
    with pytest.raises(pc.CryptoError, match="must be a JSON object"):
        pc.decrypt_project_data(envelope, creds)


def test_resolve_auth_mode_for_save_variants(monkeypatch):
    monkeypatch.setattr(pc.os, "urandom", lambda n: b"z" * n)
    assert pc._resolve_auth_mode_for_save(_credentials("pw", False)) == ("passphrase", None)
    assert pc._resolve_auth_mode_for_save(_credentials("pw", True)) == ("passphrase+yubikey", b"z" * 32)
    assert pc._resolve_auth_mode_for_save(_credentials(None, True)) == ("yubikey", b"z" * 32)


def test_build_secret_material_variants():
    provider = DummyYubiKeyProvider(b"y" * 20)
    assert pc._build_secret_material(_credentials("pw"), challenge=None, yubikey_provider=provider) == b"pw"
    assert pc._build_secret_material(
        _credentials(None, True), challenge=b"c" * 32, yubikey_provider=provider
    ) == b"y" * 20
    assert pc._build_secret_material(
        _credentials("pw", True), challenge=b"c" * 32, yubikey_provider=provider
    ) == b"pw\x00" + (b"y" * 20)


def test_build_secret_material_error_cases():
    provider = DummyYubiKeyProvider(b"y" * 20)
    with pytest.raises(pc.CryptoError, match="challenge is required"):
        pc._build_secret_material(_credentials(None, True), challenge=None, yubikey_provider=provider)
    with pytest.raises(pc.CryptoError, match="At least one credential is required"):
        pc._build_secret_material(_credentials(None, False), challenge=None, yubikey_provider=provider)


def test_build_secret_material_uses_default_provider(monkeypatch):
    provider = DummyYubiKeyProvider(b"d" * 20)
    monkeypatch.setattr(pc, "_default_yubikey_provider", lambda: provider)
    out = pc._build_secret_material(_credentials(None, True), challenge=b"q" * 32, yubikey_provider=None)
    assert out == b"d" * 20


def test_build_secret_material_for_load_paths():
    provider = DummyYubiKeyProvider(b"h" * 20)
    passphrase = pc._build_secret_material_for_load(
        _credentials("pw", False),
        {"auth_mode": "passphrase", "yubikey": {"slot": "2", "challenge_b64": ""}},
        yubikey_provider=provider,
    )
    assert passphrase == b"pw"

    challenge_b64 = pc._b64encode(b"c" * 32)
    yubikey_only = pc._build_secret_material_for_load(
        _credentials(None, False),
        {"auth_mode": "yubikey", "yubikey": {"slot": "1", "challenge_b64": challenge_b64}},
        yubikey_provider=provider,
    )
    assert yubikey_only == b"h" * 20
    assert provider.calls[-1][0] == "1"

    combo = pc._build_secret_material_for_load(
        _credentials("pw", False, "2"),
        {"auth_mode": "passphrase+yubikey", "yubikey": {"slot": "2", "challenge_b64": challenge_b64}},
        yubikey_provider=provider,
    )
    assert combo == b"pw\x00" + (b"h" * 20)


def test_build_secret_material_for_load_error_cases():
    with pytest.raises(pc.CryptoError, match="missing auth mode"):
        pc._build_secret_material_for_load(_credentials("pw"), {"yubikey": {}}, yubikey_provider=None)
    with pytest.raises(pc.CryptoError, match="missing yubikey metadata"):
        pc._build_secret_material_for_load(_credentials("pw"), {"auth_mode": "passphrase"}, yubikey_provider=None)
    with pytest.raises(pc.CryptoError, match="Unsupported auth mode"):
        pc._build_secret_material_for_load(
            _credentials("pw"), {"auth_mode": "something", "yubikey": {}}, yubikey_provider=None
        )


def test_normalize_kdf_params_defaults_and_coercion():
    defaults = pc._normalize_kdf_params(None)
    assert defaults == {"time_cost": 3, "memory_cost": 65536, "parallelism": 1, "hash_len": 32}
    out = pc._normalize_kdf_params({"time_cost": "4", "memory_cost": 1024, "parallelism": "2", "hash_len": "16"})
    assert out == {"time_cost": 4, "memory_cost": 1024, "parallelism": 2, "hash_len": 16}


def test_normalize_kdf_params_invalid():
    with pytest.raises(pc.CryptoError, match="Invalid KDF parameter time_cost"):
        pc._normalize_kdf_params({"time_cost": "bad"})


def test_require_crypto_dependencies_errors(monkeypatch):
    monkeypatch.setattr(pc, "AESGCM", None)
    with pytest.raises(pc.CryptoError, match="cryptography"):
        pc._require_crypto_dependencies()

    monkeypatch.setattr(pc, "AESGCM", object())
    monkeypatch.setattr(pc, "hash_secret_raw", None)
    with pytest.raises(pc.CryptoError, match="argon2-cffi"):
        pc._require_crypto_dependencies()


def test_slot_to_int_and_invalid():
    assert pc._slot_to_int("2") == 2
    with pytest.raises(pc.CryptoError, match="Invalid YubiKey slot"):
        pc._slot_to_int("bad")


def test_parse_hmac_response_variants():
    token = "ab" * 20
    assert pc._parse_hmac_response(f"result: {token}\n") == bytes.fromhex(token)
    assert pc._parse_hmac_response("0x" + token) == bytes.fromhex(token)


def test_parse_hmac_response_error_cases():
    with pytest.raises(pc.CryptoError, match="empty output"):
        pc._parse_hmac_response(" ")
    with pytest.raises(pc.CryptoError, match="Unexpected ykman challenge-response format"):
        pc._parse_hmac_response("not-hex")
    with pytest.raises(pc.CryptoError, match="Unexpected YubiKey response length"):
        pc._parse_hmac_response("aa")


def test_b64decode_invalid():
    with pytest.raises(ValueError, match="invalid base64"):
        pc._b64decode("%%")


def test_has_native_yubikey_api_true_and_false(monkeypatch):
    monkeypatch.setattr(pc, "list_all_devices", object())
    monkeypatch.setattr(pc, "OtpConnection", object())
    monkeypatch.setattr(pc, "YubiOtpSession", object())
    monkeypatch.setattr(pc, "SLOT", object())
    assert pc._has_native_yubikey_api() is True

    monkeypatch.setattr(pc, "SLOT", None)
    assert pc._has_native_yubikey_api() is False


def test_default_yubikey_provider_switch(monkeypatch):
    monkeypatch.setattr(pc, "_has_native_yubikey_api", lambda: True)
    assert isinstance(pc._default_yubikey_provider(), pc.YubikitYubiKeyProvider)
    monkeypatch.setattr(pc, "_has_native_yubikey_api", lambda: False)
    assert isinstance(pc._default_yubikey_provider(), pc.YkmanCliYubiKeyProvider)


def test_has_yubikey_cli_paths(monkeypatch):
    monkeypatch.setattr(pc, "_has_native_yubikey_api", lambda: True)
    assert pc.has_yubikey_cli() is True

    monkeypatch.setattr(pc, "_has_native_yubikey_api", lambda: False)
    monkeypatch.setattr(pc, "_resolve_ykman_binary", lambda raise_on_missing=False: "/tmp/ykman")
    assert pc.has_yubikey_cli() is True

    monkeypatch.setattr(pc, "_resolve_ykman_binary", lambda raise_on_missing=False: None)
    assert pc.has_yubikey_cli() is False


def test_resolve_ykman_binary_env_and_fallback(monkeypatch, tmp_path):
    env_path = tmp_path / "ykman.exe"
    env_path.write_text("bin")
    monkeypatch.setenv("YKMAN_PATH", str(env_path))
    monkeypatch.setattr(pc.os.path, "exists", lambda p: p == str(env_path))
    monkeypatch.setattr(pc.shutil, "which", lambda c: c)
    assert pc._resolve_ykman_binary() == str(env_path)

    monkeypatch.delenv("YKMAN_PATH", raising=False)
    monkeypatch.setattr(pc.os.path, "exists", lambda _p: False)
    assert pc._resolve_ykman_binary(raise_on_missing=False) is None
    with pytest.raises(pc.CryptoError, match="YubiKey CLI not found"):
        pc._resolve_ykman_binary(raise_on_missing=True)


def test_resolve_ykman_binary_defensive_empty_candidate_branch(monkeypatch):
    class ToggleBool:
        def __init__(self):
            self.calls = 0

        def strip(self):
            return self

        def __bool__(self):
            self.calls += 1
            return self.calls == 1

    monkeypatch.setattr(pc.os.environ, "get", lambda *_args, **_kwargs: ToggleBool())
    monkeypatch.setattr(pc.shutil, "which", lambda _c: None)
    monkeypatch.setattr(pc.os.path, "exists", lambda _p: False)
    assert pc._resolve_ykman_binary(raise_on_missing=False) is None


def test_yubikey_support_guidance_paths(monkeypatch):
    monkeypatch.setattr(pc, "_has_native_yubikey_api", lambda: True)
    assert "Yubico Python APIs" in pc.yubikey_support_guidance()

    monkeypatch.setattr(pc, "_has_native_yubikey_api", lambda: False)
    monkeypatch.setattr(pc, "_resolve_ykman_binary", lambda raise_on_missing=False: "/tmp/ykman")
    assert "detected via ykman" in pc.yubikey_support_guidance()

    monkeypatch.setattr(pc, "_resolve_ykman_binary", lambda raise_on_missing=False: None)
    monkeypatch.setattr(pc.platform, "system", lambda: "Windows")
    assert "Windows setup" in pc.yubikey_support_guidance()
    monkeypatch.setattr(pc.platform, "system", lambda: "Linux")
    assert "Linux setup" in pc.yubikey_support_guidance()
    monkeypatch.setattr(pc.platform, "system", lambda: "Darwin")
    assert "Install Yubico Python support" in pc.yubikey_support_guidance()


def test_ykman_cli_provider_success(monkeypatch):
    provider = pc.YkmanCliYubiKeyProvider()
    monkeypatch.setattr(pc, "_resolve_ykman_binary", lambda: "/usr/bin/ykman")
    completed = types.SimpleNamespace(returncode=0, stdout="ab" * 20, stderr="")
    monkeypatch.setattr(pc.subprocess, "run", lambda *args, **kwargs: completed)
    out = provider.hmac_challenge_response("2", b"\x01" * 32)
    assert out == bytes.fromhex("ab" * 20)


def test_ykman_cli_provider_error_paths(monkeypatch):
    provider = pc.YkmanCliYubiKeyProvider()

    with pytest.raises(pc.CryptoError, match="slot must be 1 or 2"):
        provider.hmac_challenge_response("3", b"x" * 32)

    monkeypatch.setattr(pc, "_resolve_ykman_binary", lambda: "/usr/bin/ykman")
    bad = types.SimpleNamespace(returncode=1, stdout="", stderr="boom")
    monkeypatch.setattr(pc.subprocess, "run", lambda *args, **kwargs: bad)
    with pytest.raises(pc.CryptoError, match="failed via ykman: boom"):
        provider.hmac_challenge_response("2", b"x" * 32)

    def _raise(*_args, **_kwargs):
        raise OSError("nope")

    monkeypatch.setattr(pc.subprocess, "run", _raise)
    with pytest.raises(pc.CryptoError, match="Failed to execute ykman CLI"):
        provider.hmac_challenge_response("2", b"x" * 32)


def test_yubikit_provider_missing_support(monkeypatch):
    provider = pc.YubikitYubiKeyProvider()
    monkeypatch.setattr(pc, "_has_native_yubikey_api", lambda: False)
    with pytest.raises(pc.CryptoError, match="Missing YubiKey Python API support"):
        provider.hmac_challenge_response("2", b"x" * 32)


def test_yubikit_provider_other_errors(monkeypatch):
    provider = pc.YubikitYubiKeyProvider()
    monkeypatch.setattr(pc, "_has_native_yubikey_api", lambda: True)
    monkeypatch.setattr(pc, "OtpConnection", object())

    with pytest.raises(pc.CryptoError, match="slot must be 1 or 2"):
        provider.hmac_challenge_response("9", b"x" * 32)

    monkeypatch.setattr(pc, "list_all_devices", lambda *_: [])
    with pytest.raises(pc.CryptoError, match="No YubiKey detected"):
        provider.hmac_challenge_response("2", b"x" * 32)


def test_yubikit_provider_response_length_error(monkeypatch):
    provider = pc.YubikitYubiKeyProvider()
    monkeypatch.setattr(pc, "_has_native_yubikey_api", lambda: True)
    monkeypatch.setattr(pc, "OtpConnection", object())
    monkeypatch.setattr(pc, "SLOT", lambda n: n)

    class FakeDevice:
        def open_connection(self, _conn):
            class Ctx:
                def __enter__(self_inner):
                    return object()

                def __exit__(self_inner, exc_type, exc, tb):
                    return False

            return Ctx()

    class FakeSession:
        def __init__(self, _connection):
            pass

        def calculate_hmac_sha1(self, _slot, _challenge):
            return b"x"

    monkeypatch.setattr(pc, "list_all_devices", lambda *_: [(FakeDevice(), None)])
    monkeypatch.setattr(pc, "YubiOtpSession", FakeSession)
    with pytest.raises(pc.CryptoError, match="Unexpected YubiKey response length"):
        provider.hmac_challenge_response("2", b"x" * 32)


def test_yubikit_provider_success(monkeypatch):
    provider = pc.YubikitYubiKeyProvider()
    monkeypatch.setattr(pc, "_has_native_yubikey_api", lambda: True)
    monkeypatch.setattr(pc, "OtpConnection", object())
    monkeypatch.setattr(pc, "SLOT", lambda n: n)

    class FakeDevice:
        def open_connection(self, _conn):
            class Ctx:
                def __enter__(self_inner):
                    return object()

                def __exit__(self_inner, exc_type, exc, tb):
                    return False

            return Ctx()

    class FakeSession:
        def __init__(self, _connection):
            pass

        def calculate_hmac_sha1(self, _slot, _challenge):
            return b"z" * 20

    monkeypatch.setattr(pc, "list_all_devices", lambda *_: [(FakeDevice(), None)])
    monkeypatch.setattr(pc, "YubiOtpSession", FakeSession)
    assert provider.hmac_challenge_response("2", b"x" * 32) == b"z" * 20


def test_yubikit_provider_runtime_error_wrapped(monkeypatch):
    provider = pc.YubikitYubiKeyProvider()
    monkeypatch.setattr(pc, "_has_native_yubikey_api", lambda: True)
    monkeypatch.setattr(pc, "OtpConnection", object())
    monkeypatch.setattr(pc, "SLOT", lambda n: n)

    class FakeDevice:
        def open_connection(self, _conn):
            raise RuntimeError("device failed")

    monkeypatch.setattr(pc, "list_all_devices", lambda *_: [(FakeDevice(), None)])
    with pytest.raises(pc.CryptoError, match="failed via yubikit API"):
        provider.hmac_challenge_response("2", b"x" * 32)
