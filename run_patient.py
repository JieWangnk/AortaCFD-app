#!/usr/bin/env python3
"""
AortaCFD Patient Runner - Modular CFD Workflow
===============================================

Clean interface for patient-specific CFD simulations with step-by-step control:

WORKFLOW STEPS:
1. case        - Create case structure and configuration files
2. mesh        - Generate mesh (blockMesh, surfaceFeatures, snappyHexMesh)
3. boundary    - Setup boundary conditions and flow data
4. solver      - Run CFD solver (pimpleFoam/foamRun)
5. reconstruct - Reconstruct parallel case from processor directories
6. post        - Execute post-processing
7. all         - Complete workflow (default)

EXAMPLES:
    python run_patient.py patient1                          # Complete workflow
    python run_patient.py patient1 --step mesh              # Only meshing
    python run_patient.py patient1 --step case --step mesh  # Multiple steps
    python run_patient.py patient1 --step reconstruct       # Reconstruct decomposed case
    python run_patient.py --list                            # List available patients
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