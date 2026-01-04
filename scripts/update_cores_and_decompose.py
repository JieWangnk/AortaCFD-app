#!/usr/bin/env python3
"""Update all sensitivity cases to use 32 cores and re-decompose."""
import os
import subprocess
import glob

ROOT = "/home/mchi4jw4/GitHub/AortaCFD-app"
NCORES = 32

# All case directories
WK_CASES = sorted(glob.glob(f"{ROOT}/output/BPM120/windkessel_sensitivity/*/"))
PROFILE_CASES = sorted(glob.glob(f"{ROOT}/output/BPM120/profile_sensitivity/*/"))

ALL_CASES = [d for d in WK_CASES + PROFILE_CASES if os.path.isdir(d) and os.path.exists(f"{d}/system/decomposeParDict")]

def update_decompose_par_dict(case_dir, ncores):
    """Update decomposeParDict to use specified number of cores."""
    decompose_file = os.path.join(case_dir, "system", "decomposeParDict")

    content = f'''/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  12
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      decomposeParDict;
}}

numberOfSubdomains  {ncores};

method              scotch;

// ************************************************************************* //
'''

    with open(decompose_file, 'w') as f:
        f.write(content)

    return True

def decompose_case(case_dir):
    """Run decomposePar on the case."""
    case_name = os.path.basename(case_dir.rstrip('/'))

    # Remove old processor directories
    for proc_dir in glob.glob(f"{case_dir}/processor*"):
        subprocess.run(["rm", "-rf", proc_dir], check=True)

    # Run decomposePar
    result = subprocess.run(
        ["decomposePar"],
        cwd=case_dir,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(f"  ✅ {case_name}: decomposed to {NCORES} cores")
        return True
    else:
        print(f"  ❌ {case_name}: decomposePar failed")
        if result.stderr:
            print(f"     Error: {result.stderr[:200]}")
        return False

def main():
    print(f"=" * 60)
    print(f"Updating all cases to {NCORES} cores")
    print(f"=" * 60)
    print(f"Total cases: {len(ALL_CASES)}")
    print()

    success_count = 0

    for case_dir in ALL_CASES:
        case_name = os.path.basename(case_dir.rstrip('/'))
        print(f"Processing: {case_name}")

        # Update decomposeParDict
        update_decompose_par_dict(case_dir, NCORES)

        # Re-decompose
        if decompose_case(case_dir):
            success_count += 1

    print()
    print(f"=" * 60)
    print(f"Completed: {success_count}/{len(ALL_CASES)} cases")
    print(f"=" * 60)

    return 0 if success_count == len(ALL_CASES) else 1

if __name__ == "__main__":
    exit(main())
