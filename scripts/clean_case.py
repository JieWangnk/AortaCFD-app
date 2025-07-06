#!/usr/bin/env python3
"""
Case Cleaning Utility

This script helps clean OpenFOAM case directories to ensure fresh runs
when switching between different templates or configurations.

Usage:
    python scripts/clean_case.py --case PAT1_2024 --all
    python scripts/clean_case.py --case PAT1_2024 --mesh-only
    python scripts/clean_case.py --case PAT1_2024 --restart
"""

import argparse
import shutil
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="OpenFOAM Case Cleaning Utility")
    parser.add_argument("--case", required=True, help="Case name")
    parser.add_argument("--all", action="store_true", help="Clean everything (full restart)")
    parser.add_argument("--mesh-only", action="store_true", help="Clean only mesh-related files")
    parser.add_argument("--restart", action="store_true", help="Clean for restart (keep mesh)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    
    args = parser.parse_args()
    
    case_dir = Path(f"output/OPENFOAM/{args.case}_medium")
    
    if not case_dir.exists():
        print(f"❌ Case directory not found: {case_dir}")
        return
    
    if args.all:
        clean_all(case_dir, args.dry_run)
    elif args.mesh_only:
        clean_mesh_only(case_dir, args.dry_run)
    elif args.restart:
        clean_for_restart(case_dir, args.dry_run)
    else:
        parser.print_help()

def clean_all(case_dir: Path, dry_run: bool = False):
    """Clean everything - full restart."""
    print(f"🧹 Cleaning everything in {case_dir}")
    
    if dry_run:
        print("🔍 DRY RUN - would delete:")
        print(f"  - Entire directory: {case_dir}")
        return
    
    if case_dir.exists():
        shutil.rmtree(case_dir)
        print(f"✅ Deleted: {case_dir}")
    else:
        print(f"ℹ️  Directory already clean: {case_dir}")

def clean_mesh_only(case_dir: Path, dry_run: bool = False):
    """Clean only mesh-related files."""
    print(f"🔧 Cleaning mesh files in {case_dir}")
    
    mesh_items = [
        "constant/polyMesh",
        "constant/triSurface/*.eMesh",
        "processor*",
        "log.blockMesh",
        "log.snappyHexMesh", 
        "log.surfaceFeatures",
        "log.decomposePar*",
        "log.reconstructPar*",
        "log.checkMesh",
        "log.transformPoints",
        "*.obj"
    ]
    
    delete_items(case_dir, mesh_items, dry_run, "mesh")

def clean_for_restart(case_dir: Path, dry_run: bool = False):
    """Clean for restart - keep mesh, remove solution."""
    print(f"🔄 Cleaning for restart in {case_dir}")
    
    restart_items = [
        "[0-9]*",  # Time directories
        "postProcessing",
        "log.solver",
        "log.reconstructPar",
        "log.decomposePar",
        "processor*/[0-9]*"
    ]
    
    delete_items(case_dir, restart_items, dry_run, "solution")

def delete_items(case_dir: Path, patterns: list, dry_run: bool, item_type: str):
    """Delete items matching patterns."""
    deleted_count = 0
    
    for pattern in patterns:
        items = list(case_dir.glob(pattern))
        for item in items:
            if dry_run:
                print(f"  - Would delete: {item.relative_to(case_dir)}")
            else:
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    deleted_count += 1
                    print(f"  ✅ Deleted: {item.relative_to(case_dir)}")
                except Exception as e:
                    print(f"  ❌ Failed to delete {item.relative_to(case_dir)}: {e}")
    
    if not dry_run:
        print(f"✅ Cleaned {deleted_count} {item_type} items")

if __name__ == "__main__":
    main()