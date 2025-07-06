#!/usr/bin/env python3
"""
Template Testing Helper

This script helps you test different boundary condition templates by:
1. Showing available templates
2. Switching active configuration
3. Running simulations with different templates
4. Comparing results

Usage:
    python scripts/test_templates.py --list
    python scripts/test_templates.py --use 1 --case PAT1_2024
    python scripts/test_templates.py --run 1 --case PAT1_2024 --profile sim_laminar_coarse
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Boundary Conditions Template Tester")
    parser.add_argument("--list", action="store_true", help="List available templates")
    parser.add_argument("--use", type=int, help="Switch to template number (1-5)")
    parser.add_argument("--run", type=int, help="Run simulation with template number")
    parser.add_argument("--case", default="PAT1_2024", help="Case name")
    parser.add_argument("--profile", help="Profile name (auto-detected if not specified)")
    parser.add_argument("--of-version", default="12", help="OpenFOAM version")
    
    args = parser.parse_args()
    
    if args.list:
        list_templates(args.case)
    elif args.use:
        switch_template(args.use, args.case)
    elif args.run:
        run_with_template(args.run, args.case, args.profile, args.of_version)
    else:
        parser.print_help()

def list_templates(case_name):
    """List all available templates with descriptions."""
    print(f"🔍 Available templates for {case_name}:")
    print("=" * 80)
    
    templates = get_available_templates(case_name)
    for i, (template_file, info) in enumerate(templates.items(), 1):
        print(f"\n📋 TEMPLATE {i}: {template_file}")
        print(f"   Description: {info['description']}")
        print(f"   Profile: {info['profile']}")
        print(f"   Mesh: {info['refinement_level']}")
        print(f"   Inlet: {info['inlet_profile']}")
        print(f"   Outlets: {info['outlet_type']}")
        print(f"   Runtime: ~{info['runtime']} min")

def switch_template(template_num, case_name):
    """Switch active boundary_conditions.json to specified template."""
    case_dir = Path(f"data/CAD/{case_name}")
    source_file = case_dir / f"boundary_conditions{template_num}.json"
    target_file = case_dir / "boundary_conditions.json"
    
    if not source_file.exists():
        print(f"❌ Template {template_num} not found: {source_file}")
        return
    
    # Backup current config
    if target_file.exists():
        backup_file = case_dir / "boundary_conditions_backup.json"
        shutil.copy2(target_file, backup_file)
        print(f"📦 Backed up current config to: {backup_file}")
    
    # Copy template
    shutil.copy2(source_file, target_file)
    print(f"✅ Switched to template {template_num}")
    
    # Show template info
    with open(source_file, 'r') as f:
        config = json.load(f)
    
    print(f"\n📋 ACTIVE CONFIGURATION:")
    print(f"   Description: {config.get('_description', 'No description')}")
    print(f"   Recommended profile: {config.get('_profile_recommendation', 'Not specified')}")

def run_with_template(template_num, case_name, profile, of_version):
    """Run simulation with specified template."""
    # Switch to template first
    switch_template(template_num, case_name)
    
    # Clean case for fresh run (especially important when mesh settings change)
    print(f"🧹 Cleaning case for fresh run...")
    clean_cmd = ["python", "scripts/clean_case.py", "--case", case_name, "--all"]
    try:
        subprocess.run(clean_cmd, check=True, capture_output=True)
        print(f"✅ Case cleaned successfully")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Warning: Case cleaning failed, continuing anyway")
    
    # Auto-detect profile if not specified
    if not profile:
        with open(f"data/CAD/{case_name}/boundary_conditions{template_num}.json", 'r') as f:
            config = json.load(f)
        profile = config.get('_profile_recommendation', 'sim_laminar_fine')
        print(f"🤖 Auto-detected profile: {profile}")
    
    # Run simulation
    cmd = [
        "python", "app.py", "runAll", 
        "--case", case_name,
        "--profile", profile,
        "--openfoam-version", of_version
    ]
    
    print(f"🚀 Running simulation with template {template_num}...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Simulation completed successfully!")
        print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ Simulation failed!")
        print(f"Error: {e.stderr}")

def get_available_templates(case_name):
    """Get information about available templates."""
    case_dir = Path(f"data/CAD/{case_name}")
    templates = {}
    
    for i in range(1, 6):
        template_file = case_dir / f"boundary_conditions{i}.json"
        if template_file.exists():
            try:
                with open(template_file, 'r') as f:
                    config = json.load(f)
                
                templates[f"boundary_conditions{i}.json"] = {
                    "description": config.get("_description", "No description"),
                    "profile": config.get("_profile_recommendation", "Not specified"),
                    "refinement_level": config.get("geometry", {}).get("refinement_level", "unknown"),
                    "inlet_profile": config.get("inlet", {}).get("profile", "unknown"),
                    "outlet_type": config.get("outlets", {}).get("type", "unknown"),
                    "runtime": config.get("simulation_control", {}).get("target_runtime_minutes", "unknown")
                }
            except Exception as e:
                templates[f"boundary_conditions{i}.json"] = {
                    "description": f"Error reading file: {e}",
                    "profile": "unknown",
                    "refinement_level": "unknown",
                    "inlet_profile": "unknown", 
                    "outlet_type": "unknown",
                    "runtime": "unknown"
                }
    
    return templates

if __name__ == "__main__":
    main()