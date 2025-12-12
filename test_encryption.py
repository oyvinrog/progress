#!/usr/bin/env python3
"""Test script for encryption functionality."""

from progress_list import encrypt_data, decrypt_data, get_state_file_path
import os

def test_encryption():
    """Test encryption and decryption."""
    # Test data
    test_data = {
        'version': 1,
        'tasks': [
            {'title': 'Test Task', 'completed': False, 'time_spent': 5.0},
        ],
        'snapshots': [],
        'start_time': '2025-12-12T10:00:00',
    }
    
    password = "test_password_123"
    
    print("Testing encryption...")
    try:
        # Encrypt
        encrypted = encrypt_data(test_data, password)
        print(f"✓ Encryption successful, size: {len(encrypted)} bytes")
        
        # Decrypt
        decrypted = decrypt_data(encrypted, password)
        print(f"✓ Decryption successful")
        
        # Verify
        assert decrypted == test_data, "Data mismatch after encryption/decryption"
        print("✓ Data integrity verified")
        
        # Test wrong password
        try:
            wrong_decrypt = decrypt_data(encrypted, "wrong_password")
            print("✗ ERROR: Wrong password should have failed!")
            return False
        except Exception:
            print("✓ Wrong password correctly rejected")
        
        print("\n✅ All encryption tests passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_state_file_path():
    """Test state file path generation."""
    path = get_state_file_path()
    print(f"\nState file will be saved to: {path}")
    print(f"Parent directory exists: {path.parent.exists()}")
    return True

if __name__ == "__main__":
    success = test_encryption() and test_state_file_path()
    exit(0 if success else 1)
