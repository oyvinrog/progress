#!/usr/bin/env python3
"""Test save/load functionality without GUI."""

from progress_list import TaskModel, Task, get_state_file_path
import os

def test_save_load():
    """Test saving and loading state."""
    state_file = get_state_file_path()
    
    # Clean up any existing state
    if state_file.exists():
        state_file.unlink()
        print(f"Removed existing state file: {state_file}")
    
    # Create a model with some tasks
    print("\n=== Creating model with tasks ===")
    model1 = TaskModel(password="test_password")
    model1.addTask("Task 1")
    model1.addTask("Task 2")
    model1.addTask("Task 3")
    model1.toggleComplete(0, True)  # Complete first task
    
    print(f"Created {len(model1._tasks)} tasks")
    for i, task in enumerate(model1._tasks):
        print(f"  {i}: {task.title} - {'✓' if task.completed else '☐'}")
    
    # Save state
    print("\n=== Saving state ===")
    success = model1.save_state()
    print(f"Save successful: {success}")
    print(f"State file exists: {state_file.exists()}")
    print(f"State file size: {state_file.stat().st_size if state_file.exists() else 0} bytes")
    
    # Load state
    print("\n=== Loading state ===")
    model2 = TaskModel.load_state("test_password")
    
    if model2:
        print(f"Loaded {len(model2._tasks)} tasks")
        for i, task in enumerate(model2._tasks):
            print(f"  {i}: {task.title} - {'✓' if task.completed else '☐'}")
        
        # Verify data matches
        assert len(model2._tasks) == len(model1._tasks), "Task count mismatch"
        for i, (t1, t2) in enumerate(zip(model1._tasks, model2._tasks)):
            assert t1.title == t2.title, f"Task {i} title mismatch"
            assert t1.completed == t2.completed, f"Task {i} completed mismatch"
        
        print("\n✅ Save/Load test PASSED!")
        return True
    else:
        print("\n✗ Failed to load state")
        return False

def test_wrong_password():
    """Test that wrong password fails."""
    print("\n=== Testing wrong password ===")
    model = TaskModel.load_state("wrong_password")
    if model is None:
        print("✅ Wrong password correctly rejected")
        return True
    else:
        print("✗ ERROR: Wrong password should have failed!")
        return False

if __name__ == "__main__":
    try:
        success = test_save_load() and test_wrong_password()
        
        # Clean up
        state_file = get_state_file_path()
        if state_file.exists():
            state_file.unlink()
            print(f"\nCleaned up test state file")
        
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
