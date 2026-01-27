#!/usr/bin/env python3
"""
Test backward compatibility - configs without velocityFieldAverage should still work.
"""

import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Setup Jinja2 environment
template_dir = Path("/home/mchi4jw4/GitHub/AortaCFD-app/src/templates")
env = Environment(loader=FileSystemLoader(str(template_dir)))
template = env.get_template("controlDict.tpl")

# Test 1: Old config WITHOUT velocityFieldAverage option
print("=" * 80)
print("Test 1: Old config WITHOUT velocityFieldAverage (backward compatibility)")
print("=" * 80)

old_config = {
    "hemodynamics": {
        "runtime_functions": {
            "wallShearStress": True,
            "fieldAverage": True,
            # NO velocityFieldAverage option
            "pressureMonitoring": True
        },
        "tawss_settings": {
            "skip_cycles": 2,
            "periodicRestart": True
        }
    },
    "geometry": {
        "inlet_keywords_ordered": "inlet",
        "outlet_keywords_ordered": ["outlet1"],
        "wall_keywords_ordered": "wall"
    },
    "cardiac_cycle": 0.8,
    "simulation_control": {
        "controlDict": {
            "functions": []
        }
    }
}

context_old = {
    "config": old_config,
    "controlDict": {
        "endTime": 1.5,
        "deltaT": 0.0001,
        "maxCo": 1.0
    },
    "needs_windkessel_lib": False,
    "inlet_type": "TIMEVARYING",
    "is_pulsatile": True,
    "cardiac_cycle": 0.8
}

try:
    rendered_old = template.render(**context_old)

    has_wss = "fieldAverageWSS" in rendered_old
    has_velocity_avg = "fieldAverageU" in rendered_old

    if has_wss and not has_velocity_avg:
        print("✅ PASS: Old config works correctly")
        print("  - fieldAverageWSS: Present (as expected)")
        print("  - fieldAverageU: NOT present (correct, option was not set)")
    else:
        print("❌ FAIL: Unexpected behavior")
        print(f"  - fieldAverageWSS: {'Present' if has_wss else 'MISSING'}")
        print(f"  - fieldAverageU: {'Present (UNEXPECTED)' if has_velocity_avg else 'Not present'}")

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 2: Config with velocityFieldAverage = false (explicitly disabled)
print("=" * 80)
print("Test 2: Config with velocityFieldAverage = false (explicitly disabled)")
print("=" * 80)

disabled_config = {
    "hemodynamics": {
        "runtime_functions": {
            "wallShearStress": True,
            "fieldAverage": True,
            "velocityFieldAverage": False,  # Explicitly disabled
            "pressureMonitoring": True
        },
        "tawss_settings": {
            "skip_cycles": 2,
            "periodicRestart": True
        }
    },
    "geometry": {
        "inlet_keywords_ordered": "inlet",
        "outlet_keywords_ordered": ["outlet1"],
        "wall_keywords_ordered": "wall"
    },
    "cardiac_cycle": 0.8,
    "simulation_control": {
        "controlDict": {
            "functions": []
        }
    }
}

context_disabled = {
    "config": disabled_config,
    "controlDict": {
        "endTime": 1.5,
        "deltaT": 0.0001,
        "maxCo": 1.0
    },
    "needs_windkessel_lib": False,
    "inlet_type": "TIMEVARYING",
    "is_pulsatile": True,
    "cardiac_cycle": 0.8
}

try:
    rendered_disabled = template.render(**context_disabled)

    has_wss = "fieldAverageWSS" in rendered_disabled
    has_velocity_avg = "fieldAverageU" in rendered_disabled

    if has_wss and not has_velocity_avg:
        print("✅ PASS: Explicitly disabled works correctly")
        print("  - fieldAverageWSS: Present (as expected)")
        print("  - fieldAverageU: NOT present (correct, option = false)")
    else:
        print("❌ FAIL: Unexpected behavior")
        print(f"  - fieldAverageWSS: {'Present' if has_wss else 'MISSING'}")
        print(f"  - fieldAverageU: {'Present (UNEXPECTED)' if has_velocity_avg else 'Not present'}")

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 3: Config with velocityFieldAverage = true (enabled)
print("=" * 80)
print("Test 3: Config with velocityFieldAverage = true (enabled)")
print("=" * 80)

enabled_config = {
    "hemodynamics": {
        "runtime_functions": {
            "wallShearStress": True,
            "fieldAverage": True,
            "velocityFieldAverage": True,  # Explicitly enabled
            "pressureMonitoring": True
        },
        "tawss_settings": {
            "skip_cycles": 2,
            "periodicRestart": True
        }
    },
    "geometry": {
        "inlet_keywords_ordered": "inlet",
        "outlet_keywords_ordered": ["outlet1"],
        "wall_keywords_ordered": "wall"
    },
    "cardiac_cycle": 0.8,
    "simulation_control": {
        "controlDict": {
            "functions": []
        }
    }
}

context_enabled = {
    "config": enabled_config,
    "controlDict": {
        "endTime": 1.5,
        "deltaT": 0.0001,
        "maxCo": 1.0
    },
    "needs_windkessel_lib": False,
    "inlet_type": "TIMEVARYING",
    "is_pulsatile": True,
    "cardiac_cycle": 0.8
}

try:
    rendered_enabled = template.render(**context_enabled)

    has_wss = "fieldAverageWSS" in rendered_enabled
    has_velocity_avg = "fieldAverageU" in rendered_enabled
    has_umean = "UMean" in rendered_enabled or "mean        on;" in rendered_enabled
    has_uprime2mean = "prime2Mean  on;" in rendered_enabled

    if has_wss and has_velocity_avg and has_umean and has_uprime2mean:
        print("✅ PASS: Enabled config works correctly")
        print("  - fieldAverageWSS: Present")
        print("  - fieldAverageU: Present")
        print("  - UMean computation: Enabled")
        print("  - UPrime2Mean computation: Enabled")
    else:
        print("❌ FAIL: Some features missing")
        print(f"  - fieldAverageWSS: {'Present' if has_wss else 'MISSING'}")
        print(f"  - fieldAverageU: {'Present' if has_velocity_avg else 'MISSING'}")
        print(f"  - UMean: {'Enabled' if has_umean else 'MISSING'}")
        print(f"  - UPrime2Mean: {'Enabled' if has_uprime2mean else 'MISSING'}")

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 4: Non-pulsatile flow (should NOT enable fieldAverageU even if requested)
print("=" * 80)
print("Test 4: Non-pulsatile flow (fieldAverageU should NOT be enabled)")
print("=" * 80)

steady_config = {
    "hemodynamics": {
        "runtime_functions": {
            "wallShearStress": True,
            "fieldAverage": False,
            "velocityFieldAverage": True,  # Requested, but flow is steady
            "pressureMonitoring": True
        }
    },
    "geometry": {
        "inlet_keywords_ordered": "inlet",
        "outlet_keywords_ordered": ["outlet1"],
        "wall_keywords_ordered": "wall"
    },
    "simulation_control": {
        "controlDict": {
            "functions": []
        }
    }
}

context_steady = {
    "config": steady_config,
    "controlDict": {
        "endTime": 1.5,
        "deltaT": 0.0001,
        "maxCo": 1.0
    },
    "needs_windkessel_lib": False,
    "inlet_type": "CONSTANT",  # NOT pulsatile
    "is_pulsatile": False,
    "cardiac_cycle": 0.8
}

try:
    rendered_steady = template.render(**context_steady)

    has_velocity_avg = "fieldAverageU" in rendered_steady

    if not has_velocity_avg:
        print("✅ PASS: fieldAverageU correctly NOT enabled for steady flow")
        print("  - fieldAverageU: NOT present (correct, requires pulsatile flow)")
    else:
        print("❌ FAIL: fieldAverageU should NOT be enabled for steady flow")
        print("  - fieldAverageU: Present (INCORRECT)")

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("Summary: All backward compatibility tests complete")
print("=" * 80)
