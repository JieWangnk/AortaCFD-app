#!/usr/bin/env python3
"""AortaCFD batch entrypoint.

Runs multiple cases locally with multiprocessing or generates a SLURM job-array
script for cluster execution. Successful local runs are followed by cohort QoI
aggregation scoped to the current batch outputs.

Examples:
    python run_batch.py
    python run_batch.py --cases PAT002 PAT003 --workers 2
    python run_batch.py --steps case,mesh,boundary
    python run_batch.py --config-list PAT002:config_mesh10.json PAT002:config_mesh12.json -w 2
    python run_batch.py --slurm
"""

import sys
import os
import json
import logging
import argparse
import multiprocessing
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Add src to path
src_path = str(Path(__file__).parent / 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)


# ---------------------------------------------------------------------------
# Worker function (must be top-level for pickling by multiprocessing)
# ---------------------------------------------------------------------------

def _run_single_case(args: Tuple[str, str, Dict]) -> Dict:
    """
    Execute a single patient case in a worker process.

    This function runs in a subprocess spawned by multiprocessing.Pool.
    It resets the singleton Logger to avoid file-handle conflicts between
    workers, then creates its own PatientCaseRunner instance.

    Args:
        args: Tuple of (output_id, patient_id, options_dict).
              output_id  - name used for output directory (e.g. "PAT002_mesh10").
                           For normal runs this equals patient_id.
              patient_id - actual case directory name under cases_input/.

    Returns:
        Dict with keys: output_id, patient_id, success, result_path|error, elapsed_s
    """
    output_id, patient_id, options = args
    t0 = datetime.now()

    # --- Ensure src is on sys.path inside the worker ---
    worker_src = str(Path(__file__).parent / 'src')
    if worker_src not in sys.path:
        sys.path.insert(0, worker_src)

    try:
        # Reset the singleton Logger so this worker gets its own file handle
        from aortacfd_lib.utils.logger import Logger
        Logger.reset_singleton()

        # Per-run log file under output/<output_id>/
        log_dir = Path('output') / output_id
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / f"batch_{output_id}.log")
        Logger(module_name="AortaCFD", log_file=log_file)

        from patient_runner.core import PatientCaseRunner
        runner = PatientCaseRunner()

        # Extract workflow_step(s) - may be comma-separated for multi-step
        workflow_step = options.pop('workflow_step', 'runAll')
        config_path = options.pop('config', None)

        # Load case using patient_id for STL/config discovery, output_id for output dir.
        # When output_id differs from patient_id (multi-config runs), the output goes
        # to output/<output_id>/ instead of output/<patient_id>/.
        case_info = runner.load_patient_case(
            patient_id, config_path=config_path, output_id=output_id
        )
        sim_config = runner.prepare_simulation(case_info, options)

        # Run each workflow step sequentially
        steps = workflow_step.split(',')
        for step_cmd in steps:
            step_cmd = step_cmd.strip()
            case_dir = options.get('case_dir')
            success = runner.run_workflow_step(sim_config, step_cmd, case_dir=case_dir)
            if not success:
                raise RuntimeError(f"Workflow step '{step_cmd}' failed")

        result_path = runner.generate_results_summary(case_info, sim_config)

        elapsed = (datetime.now() - t0).total_seconds()
        return {
            'output_id': output_id,
            'patient_id': patient_id,
            'success': True,
            'result_path': result_path,
            'elapsed_s': elapsed,
        }

    except Exception as exc:
        elapsed = (datetime.now() - t0).total_seconds()
        return {
            'output_id': output_id,
            'patient_id': patient_id,
            'success': False,
            'error': str(exc),
            'elapsed_s': elapsed,
        }


# ---------------------------------------------------------------------------
# Case discovery
# ---------------------------------------------------------------------------

def discover_cases(cases_dir: Path) -> List[str]:
    """
    Discover valid patient cases in ``cases_dir``.

    A valid case is a subdirectory containing at least one ``*.stl`` file
    and a ``config.json``.
    """
    if not cases_dir.is_dir():
        return []

    cases = []
    for item in sorted(cases_dir.iterdir()):
        if not item.is_dir():
            continue
        has_stl = any(item.glob('*.stl'))
        has_config = (item / 'config.json').is_file()
        if has_stl and has_config:
            cases.append(item.name)
    return cases


# ---------------------------------------------------------------------------
# SLURM script generation
# ---------------------------------------------------------------------------

def generate_slurm_script(
    cases: List[str],
    steps: str,
    config_override: Optional[str],
    partition: str = 'batch',
    time_limit: str = '24:00:00',
    cpus_per_task: int = 8,
    mem_per_cpu: str = '4G',
    output_script: str = 'batch_submit.sh',
) -> str:
    """
    Generate a SLURM job-array script that submits one job per case.

    Each array element runs ``python run_patient.py <case_id> --steps <steps>``.
    """
    case_list_str = ' '.join(f'"{c}"' for c in cases)
    n_cases = len(cases)

    config_flag = f' --config {config_override}' if config_override else ''

    script = f"""#!/bin/bash
#SBATCH --job-name=AortaCFD-batch
#SBATCH --array=0-{n_cases - 1}
#SBATCH --partition={partition}
#SBATCH --time={time_limit}
#SBATCH --cpus-per-task={cpus_per_task}
#SBATCH --mem-per-cpu={mem_per_cpu}
#SBATCH --output=output/slurm_%A_%a.log
#SBATCH --error=output/slurm_%A_%a.err

# ── AortaCFD SLURM Batch Script ──
# Generated: {datetime.now().isoformat()}
# Cases: {n_cases}

CASES=({case_list_str})
CASE_ID="${{CASES[$SLURM_ARRAY_TASK_ID]}}"

echo "=== AortaCFD SLURM Job ==="
echo "Job array ID : $SLURM_ARRAY_JOB_ID"
echo "Task index   : $SLURM_ARRAY_TASK_ID"
echo "Case         : $CASE_ID"
echo "Node         : $(hostname)"
echo "Start time   : $(date)"
echo "=========================="

python run_patient.py "$CASE_ID" --steps {steps}{config_flag}

echo "=== Finished: $CASE_ID at $(date) ==="
"""

    with open(output_script, 'w') as f:
        f.write(script)
    os.chmod(output_script, 0o755)

    return output_script


# ---------------------------------------------------------------------------
# Batch summary
# ---------------------------------------------------------------------------

def _print_summary(results: List[Dict]) -> None:
    """Print a summary table of batch execution results."""
    succeeded = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print('\n' + '=' * 70)
    print('BATCH EXECUTION SUMMARY')
    print('=' * 70)
    print(f'  Total cases : {len(results)}')
    print(f'  Succeeded   : {len(succeeded)}')
    print(f'  Failed      : {len(failed)}')
    print('-' * 70)

    for r in results:
        status = 'OK' if r['success'] else 'FAIL'
        elapsed = f"{r['elapsed_s']:.1f}s"
        detail = r.get('result_path', r.get('error', ''))
        print(f'  [{status:4s}] {r["output_id"]:<30s}  {elapsed:>8s}  {detail}')

    print('=' * 70)

    # Write machine-readable summary
    summary_path = Path('output') / 'batch_summary.json'
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total': len(results),
            'succeeded': len(succeeded),
            'failed': len(failed),
            'results': results,
        }, f, indent=2)
    print(f'\nSummary written to: {summary_path}')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='run_batch.py',
        description='AortaCFD Batch Runner - parallel multi-case execution',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Case selection
    parser.add_argument(
        '--cases', nargs='+', metavar='ID',
        help='Patient IDs to run (default: all cases in cases_input/)',
    )
    parser.add_argument(
        '--cases-dir', default='cases_input', metavar='DIR',
        help='Directory containing patient case folders (default: cases_input)',
    )

    # Workflow control
    parser.add_argument(
        '--steps', '-s', default='all', metavar='STEPS',
        help='Comma-separated workflow steps (default: all)',
    )
    parser.add_argument(
        '--config', '-c', metavar='PATH',
        help='Config JSON override applied to every case',
    )
    parser.add_argument(
        '--config-list', nargs='+', metavar='CASE:CONFIG',
        help=('Run the same patient with multiple configs. '
              'Format: CASE_ID:config_file.json (e.g. PAT002:config_mesh10.json). '
              'Config paths are relative to cases_input/CASE_ID/.'),
    )
    parser.add_argument(
        '--profile', metavar='NAME',
        help='Override simulation profile for all cases',
    )

    # Parallelism (local)
    parser.add_argument(
        '--workers', '-w', type=int, default=None, metavar='N',
        help='Max parallel workers (default: number of cases, capped at CPU count)',
    )

    # HPC / SLURM
    parser.add_argument(
        '--slurm', action='store_true',
        help='Generate a SLURM job-array script instead of running locally',
    )
    parser.add_argument(
        '--partition', default='batch',
        help='SLURM partition (default: batch)',
    )
    parser.add_argument(
        '--time-limit', default='24:00:00',
        help='SLURM wall-clock limit per case (default: 24:00:00)',
    )
    parser.add_argument(
        '--cpus-per-task', type=int, default=8,
        help='SLURM CPUs per task (default: 8)',
    )
    parser.add_argument(
        '--mem-per-cpu', default='4G',
        help='SLURM memory per CPU (default: 4G)',
    )

    # Output
    parser.add_argument(
        '--dry-run', action='store_true',
        help='List cases that would be run without executing',
    )

    return parser


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    cases_dir = Path(args.cases_dir)

    # ── Build job list: list of (output_id, patient_id, config_path | None) ──
    # output_id  = directory name under output/ (e.g. "PAT002_mesh10")
    # patient_id = actual case dir under cases_input/ (e.g. "PAT002")
    jobs: List[Tuple[str, str, Optional[str]]] = []

    if args.config_list:
        # --config-list PAT002:config_mesh10.json PAT002:config_mesh12.json ...
        for entry in args.config_list:
            if ':' not in entry:
                print(f'Error: --config-list entries must be CASE_ID:CONFIG_FILE, got: {entry}')
                sys.exit(1)
            case_id, config_name = entry.split(':', 1)
            if not (cases_dir / case_id).is_dir():
                print(f'Error: case directory not found: {cases_dir / case_id}')
                sys.exit(1)
            config_path = str(cases_dir / case_id / config_name)
            if not Path(config_path).is_file():
                print(f'Error: config file not found: {config_path}')
                sys.exit(1)
            # output_id: "PAT002_mesh10" from "config_mesh10.json"
            suffix = Path(config_name).stem.replace('config_', '')
            output_id = f'{case_id}_{suffix}'
            jobs.append((output_id, case_id, config_path))
    else:
        # Discover or validate cases (each uses its default config.json)
        if args.cases:
            cases = args.cases
            missing = [c for c in cases if not (cases_dir / c).is_dir()]
            if missing:
                print(f'Error: case directories not found: {missing}')
                sys.exit(1)
        else:
            cases = discover_cases(cases_dir)
            if not cases:
                print(f'No valid cases found in {cases_dir}/')
                sys.exit(1)

        for case_id in cases:
            jobs.append((case_id, case_id, args.config))

    # ── Print header ──
    print(f'\nAortaCFD Batch Runner')
    print(f'{"=" * 50}')
    print(f'Cases directory : {cases_dir}/')
    print(f'Jobs ({len(jobs)}):')
    for output_id, pid, cfg in jobs:
        cfg_display = cfg or f'{cases_dir}/{pid}/config.json'
        print(f'  - {output_id:<25s}  config: {cfg_display}')
    print(f'Steps           : {args.steps}')
    if args.profile:
        print(f'Profile override: {args.profile}')

    # ── Dry run ──
    if args.dry_run:
        print(f'\n[DRY RUN] Would execute {len(jobs)} jobs.')
        sys.exit(0)

    # ── SLURM mode ──
    if args.slurm:
        # For config-list mode, generate one job per entry
        slurm_cases = [oid for oid, _, _ in jobs]
        script = generate_slurm_script(
            cases=slurm_cases,
            steps=args.steps,
            config_override=args.config,
            partition=args.partition,
            time_limit=args.time_limit,
            cpus_per_task=args.cpus_per_task,
            mem_per_cpu=args.mem_per_cpu,
        )
        print(f'\nSLURM job-array script generated: {script}')
        print(f'Submit with:  sbatch {script}')
        sys.exit(0)

    # ── Local parallel execution with multiprocessing.Pool ──

    # Map CLI step names to workflow commands (same mapping as cli.py)
    step_mapping = {
        'case': 'setup:dict',
        'mesh': 'run:mesh',
        'boundary': 'setup:bc',
        'regenerate-numerics': 'setup:regenerate-numerics',
        'solver': 'run:solver',
        'reconstruct': 'run:reconstruct',
        'hemodynamics': 'run:hemodynamics',
        'post': 'execute_post',
        'all': 'runAll',
    }

    # Parse the steps string into workflow commands
    if args.steps == 'all':
        workflow_step = 'runAll'
    else:
        parsed_steps = [s.strip() for s in args.steps.split(',')]
        invalid = [s for s in parsed_steps if s not in step_mapping]
        if invalid:
            print(f'Error: invalid steps: {invalid}')
            print(f'Valid steps: {", ".join(sorted(step_mapping.keys()))}')
            sys.exit(1)
        workflow_step = ','.join(step_mapping[s] for s in parsed_steps)

    # Build worker arguments: list of (output_id, patient_id, options)
    worker_args = []
    for output_id, patient_id, config_path in jobs:
        opts = {'workflow_step': workflow_step}
        if config_path:
            opts['config'] = config_path
        if args.profile:
            opts['profile'] = args.profile
        worker_args.append((output_id, patient_id, opts))

    # Determine worker count
    max_workers = args.workers or len(jobs)
    max_workers = min(max_workers, len(jobs), multiprocessing.cpu_count())

    print(f'Workers         : {max_workers}')
    print(f'{"=" * 50}\n')

    # Reset the main-process logger before forking
    try:
        from aortacfd_lib.utils.logger import Logger
        Logger.reset_singleton()
    except ImportError:
        pass

    # Execute in parallel
    with multiprocessing.Pool(processes=max_workers) as pool:
        results = pool.map(_run_single_case, worker_args)

    # Print summary
    _print_summary(results)

    # Aggregate QoI across succeeded cases (scoped to this batch only)
    succeeded_dirs = [f'output/{r["output_id"]}' for r in results if r['success']]
    if succeeded_dirs:
        try:
            from scripts.compare_cohort import aggregate_qoi
            path = aggregate_qoi('output', run_dirs=succeeded_dirs)
            print(f'\nCohort QoI comparison: {path}')
        except Exception as e:
            print(f'\nNote: QoI comparison skipped ({e})')

    # Exit with error code if any case failed
    any_failed = any(not r['success'] for r in results)
    sys.exit(1 if any_failed else 0)


if __name__ == '__main__':
    main()
