#!/usr/bin/env python3
"""Simple test to reproduce the password issue."""

from progress_list import TaskModel, get_state_file_path
import sys
from PySide6.QtWidgets import QApplication

# Clean slate
state_file = get_state_file_path()
if state_file.exists():
    state_file.unlink()
    print("Removed existing state file")

PASSWORD = "mypassword123"

print("\n=== STEP 1: Create app and save state ===")
app1 = QApplication(sys.argv)
model1 = TaskModel(password=PASSWORD)
model1.addTask("Test Task 1")
model1.addTask("Test Task 2")
model1.toggleComplete(0, True)

print(f"Created model with {len(model1._tasks)} tasks")
for i, task in enumerate(model1._tasks):
    print(f"  Task {i}: {task.title} - {'✓' if task.completed else '☐'}")

success = model1.save_state()
print(f"Save result: {success}")
print(f"State file exists: {state_file.exists()}")

# Don't delete the app yet - reuse it
print("\n=== STEP 2: Load state in same app instance ===")
model2 = TaskModel()

print(f"Has saved state: {model2.hasSavedState()}")

success = model2.loadStateWithPassword(PASSWORD)
print(f"Load result: {success}")

if success:
    print(f"Loaded {len(model2._tasks)} tasks:")
    for i, task in enumerate(model2._tasks):
        print(f"  Task {i}: {task.title} - {'✓' if task.completed else '☐'}")
    print("\n✅ TEST PASSED")
else:
    print("\n✗ TEST FAILED - Could not load state")
    print("\nTrying with wrong password:")
    model3 = TaskModel()
    success3 = model3.loadStateWithPassword("wrongpassword")
    print(f"Wrong password result: {success3} (should be False)")

# Cleanup
if state_file.exists():
    state_file.unlink()
    print("\nCleaned up test state file")
