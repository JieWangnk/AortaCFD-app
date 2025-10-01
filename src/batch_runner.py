#!/usr/bin/env python3
"""
Batch runner for processing multiple patient cases in parallel.

Usage:
    python batch_runner.py --patients patient1 patient2 patient3
    python batch_runner.py --all
    python batch_runner.py --pattern "patient[1-3]"
    python batch_runner.py --file patient_list.txt
"""

import sys
import argparse
import json
import re
from pathlib import Path
from typing import List, Optional

# Add src to path
src_path = str(Path(__file__).parent)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from patient_runner.core import PatientCaseRunner
from patient_runner.parallel_processor import BatchProcessor, ParallelPatientProcessor


def parse_patient_pattern(pattern: str, available_patients: List[str]) -> List[str]:
    """
    Parse patient pattern and return matching patient IDs.
    
    Examples:
        "patient[1-3]" -> ["patient1", "patient2", "patient3"]
        "patient*" -> all patients
        "patient[1,3,5]" -> ["patient1", "patient3", "patient5"]
    """
    # Handle range pattern: patient[1-3]
    range_match = re.match(r'(\w+)\[(\d+)-(\d+)\]', pattern)
    if range_match:
        prefix = range_match.group(1)
        start = int(range_match.group(2))
        end = int(range_match.group(3))
        patients = []
        for i in range(start, end + 1):
            patient_id = f"{prefix}{i}"
            if patient_id in available_patients:
                patients.append(patient_id)
        return patients
    
    # Handle list pattern: patient[1,3,5]
    list_match = re.match(r'(\w+)\[([\d,]+)\]', pattern)
    if list_match:
        prefix = list_match.group(1)
        numbers = list_match.group(2).split(',')
        patients = []
        for num in numbers:
            patient_id = f"{prefix}{num.strip()}"
            if patient_id in available_patients:
                patients.append(patient_id)
        return patients
    
    # Handle wildcard pattern
    if '*' in pattern:
        regex_pattern = pattern.replace('*', '.*')
        regex = re.compile(regex_pattern)
        return [p for p in available_patients if regex.match(p)]
    
    # Direct match
    if pattern in available_patients:
        return [pattern]
    
    return []


def load_patient_list_from_file(file_path: Path) -> List[str]:
    """Load patient IDs from a text file (one per line)."""
    if not file_path.exists():
        raise FileNotFoundError(f"Patient list file not found: {file_path}")
    
    patients = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):  # Skip comments
                patients.append(line)
    
    return patients


def main():
    """Main entry point for batch processing."""
    parser = argparse.ArgumentParser(
        description="Batch processor for AortaCFD patient cases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
    # Process specific patients:
    python batch_runner.py --patients patient1 patient2 patient3
    
    # Process all available patients:
    python batch_runner.py --all
    
    # Process patients matching pattern:
    python batch_runner.py --pattern "patient[1-5]"
    
    # Process patients from file:
    python batch_runner.py --file patient_list.txt
    
    # With custom options:
    python batch_runner.py --all --workers 2 --quick
    
    # Run specific workflow step:
    python batch_runner.py --all --step mesh
    
WORKFLOW STEPS:
    case     - Create case structure
    mesh     - Generate mesh
    boundary - Setup boundary conditions
    solver   - Run CFD solver
    post     - Post-processing
    all      - Complete workflow (default)
        """
    )
    
    # Patient selection
    selection_group = parser.add_mutually_exclusive_group(required=True)
    selection_group.add_argument('--patients', '-p', nargs='+',
                                help='List of patient IDs to process')
    selection_group.add_argument('--all', '-a', action='store_true',
                                help='Process all available patients')
    selection_group.add_argument('--pattern', 
                                help='Pattern for patient selection (e.g., "patient[1-3]")')
    selection_group.add_argument('--file', '-f', type=Path,
                                help='File containing patient IDs (one per line)')
    
    # Processing options
    parser.add_argument('--workers', '-w', type=int,
                       help='Number of parallel workers (default: auto)')
    parser.add_argument('--step', choices=['case', 'mesh', 'boundary', 'solver', 'post', 'all'],
                       default='all', help='Workflow step to run')
    parser.add_argument('--quick', action='store_true',
                       help='Use quick/coarse settings for testing')
    parser.add_argument('--profile', choices=['sim_laminar_coarse', 'sim_laminar_fine'],
                       help='Simulation profile to use')
    parser.add_argument('--overwrite', action='store_true',
                       help='Overwrite existing results')
    parser.add_argument('--sequential', action='store_true',
                       help='Process patients sequentially (no parallelization)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be processed without running')
    parser.add_argument('--output', '-o', type=Path,
                       help='Output directory for batch results')
    
    args = parser.parse_args()
    
    # Get available patients
    runner = PatientCaseRunner()
    available_patients = runner.list_available_patients()
    
    if not available_patients:
        print("❌ No patient cases found in cases_input/")
        sys.exit(1)
    
    # Determine patients to process
    patients_to_process = []
    
    if args.all:
        patients_to_process = available_patients
    elif args.patients:
        # Validate patient IDs
        for patient_id in args.patients:
            if patient_id in available_patients:
                patients_to_process.append(patient_id)
            else:
                print(f"⚠️  Warning: Patient '{patient_id}' not found")
    elif args.pattern:
        patients_to_process = parse_patient_pattern(args.pattern, available_patients)
        if not patients_to_process:
            print(f"❌ No patients match pattern: {args.pattern}")
            sys.exit(1)
    elif args.file:
        try:
            file_patients = load_patient_list_from_file(args.file)
            for patient_id in file_patients:
                if patient_id in available_patients:
                    patients_to_process.append(patient_id)
                else:
                    print(f"⚠️  Warning: Patient '{patient_id}' from file not found")
        except FileNotFoundError as e:
            print(f"❌ {e}")
            sys.exit(1)
    
    if not patients_to_process:
        print("❌ No valid patients to process")
        sys.exit(1)
    
    # Remove duplicates while preserving order
    patients_to_process = list(dict.fromkeys(patients_to_process))
    
    # Prepare processing options
    options = {}
    if args.quick:
        options['profile'] = 'sim_laminar_coarse'
    if args.profile:
        options['profile'] = args.profile
    if args.overwrite:
        options['overwrite'] = True
    
    # Map step to workflow command
    if args.step != 'all':
        step_mapping = {
            'case': 'setup:dict',
            'mesh': 'run:mesh',
            'boundary': 'setup:bc',
            'solver': 'run:solver',
            'post': 'execute_post'
        }
        options['workflow_step'] = step_mapping[args.step]
    
    # Display processing plan
    print("\n" + "="*60)
    print("🏥 AortaCFD Batch Processing")
    print("="*60)
    print(f"📋 Patients to process: {len(patients_to_process)}")
    for patient in patients_to_process[:5]:  # Show first 5
        print(f"   • {patient}")
    if len(patients_to_process) > 5:
        print(f"   ... and {len(patients_to_process) - 5} more")
    
    print(f"\n⚙️  Configuration:")
    print(f"   Workflow step: {args.step}")
    print(f"   Workers: {args.workers or 'auto'}")
    print(f"   Mode: {'sequential' if args.sequential else 'parallel'}")
    if options:
        print(f"   Options: {options}")
    print("="*60)
    
    # Dry run - just show what would be done
    if args.dry_run:
        print("\n🔍 DRY RUN - No processing will occur")
        print(f"Would process {len(patients_to_process)} patients")
        sys.exit(0)
    
    # Confirm before processing
    if len(patients_to_process) > 5 and not args.all:
        response = input(f"\n⚠️  Process {len(patients_to_process)} patients? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled.")
            sys.exit(0)
    
    # Process patients
    try:
        if args.sequential:
            # Sequential processing
            print("\n📊 Processing patients sequentially...")
            results = {}
            for i, patient_id in enumerate(patients_to_process, 1):
                print(f"\n[{i}/{len(patients_to_process)}] Processing {patient_id}...")
                try:
                    runner = PatientCaseRunner()
                    result_path = runner.run_patient_case(patient_id, options)
                    results[patient_id] = {
                        'status': 'completed',
                        'result_path': result_path
                    }
                    print(f"   ✅ Completed: {patient_id}")
                except Exception as e:
                    results[patient_id] = {
                        'status': 'failed',
                        'error': str(e)
                    }
                    print(f"   ❌ Failed: {patient_id} - {e}")
            
            # Summary
            completed = sum(1 for r in results.values() if r['status'] == 'completed')
            print(f"\n{'='*60}")
            print(f"Completed: {completed}/{len(patients_to_process)}")
            
        else:
            # Parallel processing
            processor = BatchProcessor()
            results = processor.process_batch(
                patients_to_process,
                options=options,
                max_workers=args.workers,
                save_results=True
            )
            
            # Save additional output if specified
            if args.output:
                output_path = args.output
                output_path.mkdir(parents=True, exist_ok=True)
                
                # Save detailed results
                results_file = output_path / 'batch_results.json'
                with open(results_file, 'w') as f:
                    json.dump(results, f, indent=2)
                
                print(f"\n📁 Additional results saved to: {results_file}")
        
        print("\n✅ Batch processing completed!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Batch processing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()