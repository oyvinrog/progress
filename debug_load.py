#!/usr/bin/env python3
"""Debug script to test loading state in GUI context."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from progress_list import TaskModel, get_state_file_path

def test_load_in_gui_context():
    """Test loading state with GUI context."""
    state_file = get_state_file_path()
    
    if not state_file.exists():
        print("No saved state file exists. Create one first by running the app and saving.")
        return
    
    print(f"State file: {state_file}")
    print(f"State file size: {state_file.stat().st_size} bytes")
    
    # Try to read the raw encrypted data
    encrypted_data = state_file.read_bytes()
    print(f"Successfully read {len(encrypted_data)} bytes")
    
    # Get password from user
    password = input("Enter password: ")
    
    print("\n=== Creating QApplication ===")
    app = QApplication(sys.argv)
    
    print("\n=== Creating TaskModel ===")
    model = TaskModel()
    
    print("\n=== Loading state with password ===")
    success = model.loadStateWithPassword(password)
    
    print(f"\nLoad successful: {success}")
    if success:
        print(f"Loaded {len(model._tasks)} tasks:")
        for i, task in enumerate(model._tasks):
            print(f"  {i}: {task.title} - {'✓' if task.completed else '☐'}")
    else:
        print("Failed to load state")
        
        # Try manual decryption to see the real error
        print("\n=== Attempting manual decryption for debugging ===")
        try:
            from progress_list import decrypt_data
            state = decrypt_data(encrypted_data, password)
            print("Manual decryption successful!")
            print(f"State keys: {state.keys()}")
        except Exception as e:
            print(f"Manual decryption failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_load_in_gui_context()
