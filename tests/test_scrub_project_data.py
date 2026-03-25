"""Tests for memory-scrubbing of plaintext project data."""

import json

import pytest

import progress_crypto as pc
from actiondraw.model import DiagramModel
from task_model import ProjectManager, TabModel, TaskModel


# ---------------------------------------------------------------------------
# DerivedKeyMaterial.scrub()
# ---------------------------------------------------------------------------

class TestDerivedKeyMaterialScrub:
    def test_scrub_zeros_key(self):
        key = bytearray(b"\xaa" * 32)
        mat = pc.DerivedKeyMaterial(
            key=key,
            salt=b"\xbb" * 16,
            kdf_params={"time_cost": 3, "memory_cost": 65536, "parallelism": 1, "hash_len": 32},
            auth_mode="passphrase",
            yubikey_enabled=False,
            yubikey_slot="2",
            yubikey_challenge_b64="",
        )
        assert any(b != 0 for b in mat.key)
        mat.scrub()
        assert all(b == 0 for b in mat.key)

    def test_scrub_is_idempotent(self):
        mat = pc.DerivedKeyMaterial(
            key=bytearray(32),
            salt=b"\x00" * 16,
            kdf_params={"time_cost": 3, "memory_cost": 65536, "parallelism": 1, "hash_len": 32},
            auth_mode="passphrase",
            yubikey_enabled=False,
            yubikey_slot="2",
            yubikey_challenge_b64="",
        )
        mat.scrub()
        mat.scrub()  # should not raise
        assert all(b == 0 for b in mat.key)


# ---------------------------------------------------------------------------
# bytearray key works with AESGCM encrypt/decrypt
# ---------------------------------------------------------------------------

class TestByteArrayKeyEncryption:
    def test_encrypt_decrypt_roundtrip_with_bytearray_key(self):
        payload = {"tasks": [{"title": "test"}], "saved_at": "2026-01-01T00:00:00"}
        creds = pc.EncryptionCredentials(passphrase="test-pw")
        key_material = pc.derive_key_material(creds)
        assert isinstance(key_material.key, bytearray)

        envelope = pc.encrypt_with_derived_key(payload, key_material)
        assert "ciphertext" in envelope

        # Decrypt using the original credentials.
        decrypted = pc.decrypt_project_data(envelope, creds)
        assert decrypted == payload

    def test_decrypt_and_derive_returns_bytearray_key(self):
        payload = {"x": 1, "saved_at": "2026-01-01T00:00:00"}
        creds = pc.EncryptionCredentials(passphrase="pw")
        envelope = pc.encrypt_project_data(payload, creds)

        data, key_material = pc.decrypt_and_derive_key_material(envelope, creds)
        assert isinstance(key_material.key, bytearray)
        assert data == payload


# ---------------------------------------------------------------------------
# ProjectManager.scrubProjectData()
# ---------------------------------------------------------------------------

class TestScrubProjectData:
    @pytest.fixture
    def models(self, app):
        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        pm = ProjectManager(task_model, diagram_model, tab_model)
        return pm, task_model, diagram_model, tab_model

    def test_scrub_clears_models(self, models):
        pm, task_model, diagram_model, tab_model = models

        # Add some data.
        task_model.addTask("Secret task")
        diagram_model.from_dict({
            "items": [{"id": "box_0", "item_type": "box", "x": 0, "y": 0,
                        "width": 100, "height": 60, "text": "Secret box",
                        "task_index": -1, "color": "#fff", "text_color": "#000"}],
            "edges": [],
            "strokes": [],
        })

        assert task_model.rowCount() > 0
        assert diagram_model.count > 0

        pm.scrubProjectData()

        assert task_model.rowCount() == 0
        assert diagram_model.count == 0

    def test_scrub_zeros_cached_key(self, models):
        pm, *_ = models

        key_material = pc.DerivedKeyMaterial(
            key=bytearray(b"\xff" * 32),
            salt=b"\x00" * 16,
            kdf_params={"time_cost": 3, "memory_cost": 65536, "parallelism": 1, "hash_len": 32},
            auth_mode="passphrase",
            yubikey_enabled=False,
            yubikey_slot="2",
            yubikey_challenge_b64="",
        )
        pm._cached_key_material = key_material

        pm.scrubProjectData()

        # Key material reference is dropped.
        assert pm._cached_key_material is None
        # The original object's key was zeroed in-place.
        assert all(b == 0 for b in key_material.key)

    def test_scrub_clears_snapshot(self, models):
        pm, *_ = models

        pm._last_saved_snapshot = '{"tasks": [{"title": "secret"}]}'
        pm.scrubProjectData()
        assert pm._last_saved_snapshot == ""

    def test_scrub_is_safe_when_already_empty(self, models):
        pm, *_ = models
        # Should not raise on a fresh/empty project manager.
        pm.scrubProjectData()

    def test_load_project_scrubs_before_load(self, models, tmp_path):
        pm, task_model, diagram_model, tab_model = models

        # Create a project file.
        project_data = {
            "version": "1.1",
            "saved_at": "2026-01-01T00:00:00",
            "tabs": [{
                "name": "Tab1",
                "tasks": {"tasks": [{"title": "Task A", "completed": False, "time_spent": 0.0}]},
                "diagram": {"items": [], "edges": [], "strokes": []},
            }],
            "active_tab": 0,
        }
        project_file = tmp_path / "test.progress"
        project_file.write_text(json.dumps(project_data))

        # Set up cached key material that should get scrubbed on load.
        old_key = bytearray(b"\xee" * 32)
        pm._cached_key_material = pc.DerivedKeyMaterial(
            key=old_key,
            salt=b"\x00" * 16,
            kdf_params={"time_cost": 3, "memory_cost": 65536, "parallelism": 1, "hash_len": 32},
            auth_mode="passphrase",
            yubikey_enabled=False,
            yubikey_slot="2",
            yubikey_challenge_b64="",
        )

        pm.loadProject(str(project_file))

        # Old key was zeroed.
        assert all(b == 0 for b in old_key)
        # New project loaded successfully.
        assert task_model.rowCount() == 1
