#!/usr/bin/env python3
"""
Boundary Conditions Analysis and Auto-completion Tool

This script analyzes boundary_conditions.json files and provides:
1. Key parameter identification
2. Missing parameter detection  
3. Intelligent suggestions
4. Auto-completion capabilities
5. Template generation

Usage:
    python scripts/analyze_boundary_conditions.py --analyze data/CAD/PAT1_2024/boundary_conditions.json
    python scripts/analyze_boundary_conditions.py --complete data/CAD/PAT1_2024/boundary_conditions.json
    python scripts/analyze_boundary_conditions.py --template --case PAT1_2024 --csv BPM75.csv
"""

import argparse
import json
import sys
import os
from pathlib import Path

# Add src to path for imports
src_path = str(Path(__file__).parent.parent / "src")
sys.path.insert(0, src_path)

try:
    from aortacfd_lib.config_helper import BoundaryConditionsHelper
except ImportError:
    print("Error: Could not import BoundaryConditionsHelper. Make sure you're running from project root.")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Boundary Conditions Analysis Tool")
    parser.add_argument("--analyze", help="Analyze existing boundary conditions file")
    parser.add_argument("--complete", help="Auto-complete boundary conditions file")
    parser.add_argument("--template", action="store_true", help="Create template config")
    parser.add_argument("--case", help="Case name for template creation")
    parser.add_argument("--csv", help="CSV file name for template creation")
    parser.add_argument("--output", help="Output file path (default: overwrite input)")
    
    args = parser.parse_args()
    helper = BoundaryConditionsHelper()
    
    if args.analyze:
        analyze_config(helper, args.analyze)
    elif args.complete:
        complete_config(helper, args.complete, args.output)
    elif args.template:
        if not args.case or not args.csv:
            print("Error: --case and --csv are required for template creation")
            sys.exit(1)
        create_template(helper, args.case, args.csv, args.output)
    else:
        parser.print_help()

def analyze_config(helper: BoundaryConditionsHelper, file_path: str):
    """Analyze boundary conditions configuration."""
    print(f"🔍 Analyzing: {file_path}")
    print("=" * 60)
    
    analysis = helper.analyze_boundary_conditions(file_path)
    
    if "error" in analysis:
        print(f"❌ Error: {analysis['error']}")
        return
    
    # Print key parameters
    print("📋 KEY PARAMETERS:")
    for param, value in analysis["key_parameters"].items():
        status = "✅" if value != "unknown" and value != "missing" else "❌"
        print(f"  {status} {param}: {value}")
    
    print(f"\n📊 COMPLETENESS: {analysis['completeness']:.1f}%")
    
    # Print missing parameters
    if analysis["missing_parameters"]:
        print(f"\n❌ MISSING PARAMETERS ({len(analysis['missing_parameters'])}):")
        for param in analysis["missing_parameters"]:
            print(f"  • {param}")
    else:
        print(f"\n✅ All critical parameters present!")
    
    # Print suggestions
    if analysis["suggestions"]:
        print(f"\n💡 SUGGESTIONS ({len(analysis['suggestions'])}):")
        for i, suggestion in enumerate(analysis["suggestions"], 1):
            print(f"  {i}. {suggestion}")

def complete_config(helper: BoundaryConditionsHelper, file_path: str, output_path: str = None):
    """Auto-complete boundary conditions configuration."""
    print(f"🔧 Auto-completing: {file_path}")
    
    try:
        with open(file_path, 'r') as f:
            partial_config = json.load(f)
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return
    
    completed_config = helper.auto_complete_config(partial_config)
    
    output_file = output_path or file_path
    try:
        with open(output_file, 'w') as f:
            json.dump(completed_config, f, indent=2)
        print(f"✅ Completed configuration saved to: {output_file}")
    except Exception as e:
        print(f"❌ Error writing file: {e}")
        return
    
    # Show what was added
    print("\n📝 AUTO-COMPLETED PARAMETERS:")
    _show_config_diff(partial_config, completed_config)

def create_template(helper: BoundaryConditionsHelper, case_name: str, csv_file: str, output_path: str = None):
    """Create template boundary conditions configuration."""
    print(f"📋 Creating template for case: {case_name}")
    
    template_config = helper.create_template_config(case_name, csv_file)
    
    output_file = output_path or f"data/CAD/{case_name}/boundary_conditions_template.json"
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    try:
        with open(output_file, 'w') as f:
            json.dump(template_config, f, indent=2)
        print(f"✅ Template created: {output_file}")
    except Exception as e:
        print(f"❌ Error creating template: {e}")
        return
    
    print("\n📋 TEMPLATE STRUCTURE:")
    _print_config_structure(template_config)

def _show_config_diff(original: dict, completed: dict, prefix: str = ""):
    """Show differences between original and completed configurations."""
    for key, value in completed.items():
        current_path = f"{prefix}.{key}" if prefix else key
        
        if key not in original:
            if isinstance(value, dict):
                print(f"  + {current_path}/ (section added)")
                _show_config_diff({}, value, current_path)
            else:
                print(f"  + {current_path}: {value}")
        elif isinstance(value, dict) and isinstance(original[key], dict):
            _show_config_diff(original[key], value, current_path)

def _print_config_structure(config: dict, indent: int = 0):
    """Print configuration structure in a readable format."""
    for key, value in config.items():
        if isinstance(value, dict):
            print("  " * indent + f"📁 {key}/")
            _print_config_structure(value, indent + 1)
        else:
            print("  " * indent + f"📄 {key}: {value}")

if __name__ == "__main__":
    main()