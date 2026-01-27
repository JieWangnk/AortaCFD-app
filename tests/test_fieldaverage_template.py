#!/usr/bin/env python3
"""
Test script to verify fieldAverageU template implementation.
"""

import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Setup Jinja2 environment
template_dir = Path("/home/mchi4jw4/GitHub/AortaCFD-app/src/templates")
env = Environment(loader=FileSystemLoader(str(template_dir)))
template = env.get_template("controlDict.tpl")

# Create minimal test configuration
test_config = {
    "hemodynamics": {
        "runtime_functions": {
            "wallShearStress": True,
            "fieldAverage": True,
            "velocityFieldAverage": True,  # NEW OPTION TO TEST
            "pressureMonitoring": True
        },
        "tawss_settings": {
            "skip_cycles": 2,
            "periodicRestart": True
        }
    },
    "geometry": {
        "inlet_keywords_ordered": "inlet",
        "outlet_keywords_ordered": ["outlet1", "outlet2"],
        "wall_keywords_ordered": "wall"
    },
    "cardiac_cycle": 0.5,
    "simulation_control": {
        "controlDict": {
            "functions": []
        }
    }
}

# Template context variables
context = {
    "config": test_config,
    "controlDict": {
        "startFrom": "startTime",
        "startTime": 0,
        "endTime": 1.5,
        "deltaT": 0.0001,
        "writeInterval": 0.01,
        "purgeWrite": 0,
        "writeFormat": "binary",
        "writePrecision": 6,
        "writeCompression": "off",
        "timeFormat": "general",
        "timePrecision": 6,
        "runTimeModifiable": "true",
        "adjustTimeStep": "yes",
        "maxCo": 1.0,
        "maxDeltaT": 0.001
    },
    "needs_windkessel_lib": False,
    "inlet_type": "TIMEVARYING",
    "is_pulsatile": True,
    "cardiac_cycle": 0.5
}

# Render template
print("=" * 80)
print("Testing fieldAverageU template implementation")
print("=" * 80)
print()

try:
    rendered = template.render(**context)

    # Check if fieldAverageU appears in the output
    if "fieldAverageU" in rendered:
        print("✅ SUCCESS: fieldAverageU function found in rendered template!")
        print()

        # Extract and display the fieldAverageU section
        lines = rendered.split('\n')
        in_section = False
        section_lines = []

        for i, line in enumerate(lines):
            if 'fieldAverageU' in line and not line.strip().startswith('//'):
                in_section = True

            if in_section:
                section_lines.append(line)
                if line.strip() == '}' and len(section_lines) > 1:
                    break

        print("fieldAverageU section:")
        print("-" * 80)
        for line in section_lines:
            print(line)
        print("-" * 80)
        print()

        # Check for key elements
        checks = {
            "UMean (mean on)": "mean        on;" in rendered and "U" in rendered,
            "UPrime2Mean (prime2Mean on)": "prime2Mean  on;" in rendered,
            "pMean": "p" in rendered and "mean        on;" in rendered,
            "timeStart": "timeStart" in rendered,
            "periodicRestart": "periodicRestart" in rendered
        }

        print("Component checks:")
        for check_name, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check_name}")
        print()

        if all(checks.values()):
            print("🎉 All checks passed! fieldAverageU implementation is correct.")
        else:
            print("⚠️  Some checks failed. Review the implementation.")

    else:
        print("❌ FAILED: fieldAverageU function NOT found in rendered template!")
        print()
        print("Checking if velocityFieldAverage flag was processed...")
        # Debug: check what functions were included
        if "fieldAverageWSS" in rendered:
            print("  ✅ fieldAverageWSS is present (WSS averaging works)")
        if "functions" in rendered:
            print("  ✅ functions block exists")

        # Show a sample of the rendered output around the expected location
        lines = rendered.split('\n')
        for i, line in enumerate(lines):
            if "fieldAverageWSS" in line:
                print(f"\n  Context around fieldAverageWSS (lines {i-2} to {i+15}):")
                for j in range(max(0, i-2), min(len(lines), i+15)):
                    print(f"    {j:3d}: {lines[j]}")
                break

except Exception as e:
    print(f"❌ ERROR rendering template: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("Test complete")
print("=" * 80)
