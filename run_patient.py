#!/usr/bin/env python3
"""AortaCFD single-case entrypoint.

Examples:
    python run_patient.py BPM120
    python run_patient.py BPM120 --steps case,mesh,boundary
    python run_patient.py BPM120 --update output/BPM120/run_xxx --steps solver
    python run_patient.py --postprocess output/BPM120/run_xxx
    python run_patient.py --list
"""

import sys
from pathlib import Path

# Add src to path
src_path = str(Path(__file__).parent / 'src')
sys.path.insert(0, src_path)

try:
    from patient_runner.cli import main
except ImportError as e:
    print(f"❌ Import error: {e}")
    print(f"   Tried to import from: {src_path}")
    print("   Please ensure all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)


if __name__ == "__main__":
    main()