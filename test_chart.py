#!/usr/bin/env python3
"""Quick test of the interactive burndown chart."""

import sys
from progress_list import main

if __name__ == "__main__":
    print("Starting Progress Tracker with Interactive Burndown Chart")
    print("=" * 60)
    print("Instructions:")
    print("1. Click 'Paste sample tasks' to add some tasks")
    print("2. The chart should appear immediately (wait ~2 seconds)")
    print("3. Check off tasks to see the blue line go down")
    print("4. Wait 10 seconds to see automatic snapshots")
    print("5. The chart shows:")
    print("   - Blue line/dot: Your actual progress")
    print("   - Green dashed line: Ideal linear progress")
    print()
    print("Debug output will show snapshot and chart updates below:")
    print("=" * 60)
    print()
    sys.exit(main())
