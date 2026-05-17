#!/usr/bin/env python3
"""AortaCFD batch entrypoint (Block C of the parametric-study workflow).

Three compute tiers, same code path:

  1. Local single (one case)           python run_patient.py <case>
  2. Local parallel (workstation)      python run_batch.py --cases A B C --workers N
  3. HPC SLURM job array               python run_batch.py --cases A B C --slurm --partition X

After the SLURM script is generated, transfer + submit + download via
``scripts/hpc/{upload,status,download}.sh`` (copy ``hpc.conf`` to a per-cluster
``<sitename>.conf`` and edit for your environment — see
``scripts/hpc/README.md`` and ``scripts/hpc/example_cluster.conf``).

Common patterns:
    # Run all cases under cases_input/ locally with 2 workers
    python run_batch.py --workers 2

    # Run a specific subset, resuming after a previous failure
    python run_batch.py --cases A B C --workers 4 --resume

    # Run the same patient with several configs
    python run_batch.py --config-list BPM120:config_mesh10.json BPM120:config_mesh12.json -w 2

    # Preview commands without executing (sanity-check before HPC submission)
    python run_batch.py --cases sobol_demo_* --dry-run

    # Generate a SLURM job-array script for HPC
    python run_batch.py --cases sobol_demo_* --slurm --partition multicore
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

from aortacfd_lib import __version__ as _aortacfd_version


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
              output_id  - name used for output directory (e.g. "0014_H_AO_COA_mesh10").
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

def _load_cluster_conf(path: Optional[str]) -> Dict[str, str]:
    """Read scripts/hpc/<sitename>.conf (bash KEY=VALUE pairs) into a dict.

    Returns an empty dict if path is None or the file does not exist.
    Only the keys the SLURM template uses are looked at; others are ignored.
    """
    if not path:
        return {}
    p = Path(path)
    if not p.is_file():
        print(f'Warning: --cluster-conf file not found: {path}')
        return {}
    out: Dict[str, str] = {}
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key, _, val = line.partition('=')
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        # strip trailing comments after the value (e.g. `HPC_NCORES=32  # comment`)
        if '#' in val:
            val = val.split('#', 1)[0].strip().strip('"').strip("'")
        out[key] = val
    return out


def _render_template(text: str, vars_: Dict[str, str]) -> str:
    """Substitute ``%%KEY%%`` tokens in the template text with the values from ``vars_``.

    Token format: ``%%CASES%%``, ``%%PARTITION%%`` etc. Deliberately
    non-bash-like so it cannot collide with the many ``$VAR`` references
    a SLURM script typically has.

    Unknown ``%%...%%`` tokens are left in place (a warning is printed).
    """
    rendered = text
    for key, val in vars_.items():
        rendered = rendered.replace(f'%%{key}%%', val)
    # Detect leftover unresolved tokens
    import re
    leftover = re.findall(r'%%([A-Z][A-Z0-9_]*)%%', rendered)
    for tok in set(leftover):
        print(f'Warning: template token %%{tok}%% not substituted '
              f'(not in cluster conf or CLI args).')
    return rendered


# Default built-in template — used when --slurm-template is not given.
# Same tokens as a user-provided template would use; rendered by
# the same _render_template path. Edit this if you want to change the
# default look-and-feel for all clusters.
_DEFAULT_SLURM_TEMPLATE = """#!/bin/bash
#SBATCH --job-name=%%JOB_NAME%%
#SBATCH --array=0-%%ARRAY_MAX%%
#SBATCH --partition=%%PARTITION%%
#SBATCH --time=%%TIME_LIMIT%%
#SBATCH --cpus-per-task=%%CPUS_PER_TASK%%
#SBATCH --mem-per-cpu=%%MEM_PER_CPU%%
#SBATCH --output=output/slurm_%A_%a.log
#SBATCH --error=output/slurm_%A_%a.err

# ── AortaCFD SLURM Batch Script ──
# Generated: %%GENERATED_AT%%
# Cases:     %%N_CASES%%

%%CLUSTER_ENV_SETUP%%

# Resolve the repo root (= submission directory).
REPO_ROOT="${SLURM_SUBMIT_DIR:-$PWD}"
cd "$REPO_ROOT"

# Activate the AortaCFD venv if it exists locally; otherwise rely on the
# system python (must have the AortaCFD package importable).
if [[ -f "$REPO_ROOT/venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$REPO_ROOT/venv/bin/activate"
fi

# Fail fast if OpenFOAM 12 is not actually on PATH yet.
command -v foamRun >/dev/null 2>&1 || {
    echo "ERROR: foamRun not on PATH. Did you forget --cluster-conf or to source OpenFOAM?"
    exit 64
}

CASES=(%%CASES%%)
CASE_ID="${CASES[$SLURM_ARRAY_TASK_ID]}"

echo "=== AortaCFD SLURM Job ==="
echo "Job array ID : $SLURM_ARRAY_JOB_ID"
echo "Task index   : $SLURM_ARRAY_TASK_ID"
echo "Case         : $CASE_ID"
echo "Node         : $(hostname)"
echo "Start time   : $(date)"
echo "=========================="

python run_patient.py "$CASE_ID" --steps %%STEPS%%%%CONFIG_FLAG%%

echo "=== Finished: $CASE_ID at $(date) ==="
"""


def _build_cluster_env_setup(conf: Dict[str, str], conf_path: Optional[str]) -> str:
    """Build the `module load + foam source` block injected into the default template."""
    of_module = conf.get('HPC_OF_MODULE', '')
    if of_module:
        return (f'# ── Cluster environment (from {conf_path}) ──\n'
                f'module purge\n'
                f'module load {of_module}\n'
                f'source "${{foamDotFile:-/opt/openfoam12/etc/bashrc}}"')
    return ('# ── Cluster environment ──\n'
            '# No --cluster-conf passed. Add `module load <openfoam-module>`\n'
            '# + `source $foamDotFile` here, OR regenerate with\n'
            '# --cluster-conf scripts/hpc/<sitename>.conf.')


def generate_slurm_script(
    cases: List[str],
    steps: str,
    config_override: Optional[str],
    partition: str = 'batch',
    time_limit: str = '24:00:00',
    cpus_per_task: int = 8,
    mem_per_cpu: str = '4G',
    output_script: str = 'batch_submit.sh',
    cluster_conf: Optional[str] = None,
    slurm_template: Optional[str] = None,
    job_name: str = 'AortaCFD-batch',
) -> str:
    """
    Generate a SLURM job-array script that submits one job per case.

    The script is built by token-substitution on a template (the default
    is in ``_DEFAULT_SLURM_TEMPLATE``; pass ``slurm_template`` to use your
    own). Token syntax: ``%%KEY%%``. Available tokens:

      %%JOB_NAME%%, %%ARRAY_MAX%%, %%N_CASES%%, %%PARTITION%%,
      %%TIME_LIMIT%%, %%CPUS_PER_TASK%%, %%MEM_PER_CPU%%,
      %%CASES%%, %%STEPS%%, %%CONFIG_FLAG%%, %%GENERATED_AT%%,
      %%CLUSTER_ENV_SETUP%% (the `module load` block, injected from conf),
      plus any HPC_* key from the cluster conf as %%HPC_PARTITION%% etc.

    User-supplied templates can use any subset of the tokens. Unknown
    bash ``$VAR`` references pass through untouched.
    """
    n_cases = len(cases)
    config_flag = f' --config {config_override}' if config_override else ''
    conf = _load_cluster_conf(cluster_conf)
    cluster_env_setup = _build_cluster_env_setup(conf, cluster_conf)

    vars_: Dict[str, str] = {
        'JOB_NAME': job_name,
        'ARRAY_MAX': str(n_cases - 1),
        'N_CASES': str(n_cases),
        'PARTITION': partition,
        'TIME_LIMIT': time_limit,
        'CPUS_PER_TASK': str(cpus_per_task),
        'MEM_PER_CPU': mem_per_cpu,
        'CASES': ' '.join(f'"{c}"' for c in cases),
        'STEPS': steps,
        'CONFIG_FLAG': config_flag,
        'GENERATED_AT': datetime.now().isoformat(),
        'CLUSTER_ENV_SETUP': cluster_env_setup,
    }
    # Also expose every HPC_* key from the conf, so user templates can
    # reference things like %%HPC_ACCOUNT%% directly.
    for k, v in conf.items():
        vars_.setdefault(k, v)

    if slurm_template:
        tpath = Path(slurm_template)
        if not tpath.is_file():
            raise FileNotFoundError(f'--slurm-template file not found: {slurm_template}')
        template_text = tpath.read_text()
        print(f'Using user template: {slurm_template}')
    else:
        template_text = _DEFAULT_SLURM_TEMPLATE

    rendered = _render_template(template_text, vars_)

    with open(output_script, 'w') as f:
        f.write(rendered)
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

    parser.add_argument(
        '--version', '-V', action='version',
        version=f'AortaCFD {_aortacfd_version}',
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
              'Format: CASE_ID:config_file.json (e.g. 0014_H_AO_COA:config_mesh10.json). '
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
    parser.add_argument(
        '--cluster-conf', default=None, metavar='PATH',
        help=('Path to a scripts/hpc/<sitename>.conf with HPC_OF_MODULE etc. '
              'Used to inject `module load` + OpenFOAM environment into the '
              'generated SLURM script. See scripts/hpc/example_cluster.conf.'),
    )
    parser.add_argument(
        '--slurm-template', default=None, metavar='PATH',
        help=('Path to a custom SLURM template (with %%TOKEN%% placeholders). '
              'Use this to support clusters that need different #SBATCH '
              'directives, module systems, MPI launchers, or accounting. '
              'See scripts/hpc/template_slurm.example.sh for the token list.'),
    )

    # Output
    parser.add_argument(
        '--dry-run', action='store_true',
        help='List cases that would be run without executing',
    )
    parser.add_argument(
        '--resume', action='store_true',
        help='Skip cases that have already completed successfully '
             '(checks output/<case>/*/manifest.json status=ok, or falls back '
             'to qoi_summary.json existence). Useful after partial batch failure.',
    )

    return parser


def _is_case_done(output_id: str, output_root: str = 'output') -> bool:
    """Return True if a previous run of this case completed successfully.

    A case counts as "done" if any of its run directories under
    ``<output_root>/<output_id>/`` has either:
      - a ``manifest.json`` with ``status`` == ``"ok"``, OR
      - a ``qoi_summary.json`` anywhere underneath (legacy fallback).
    """
    out_dir = Path(output_root) / output_id
    if not out_dir.exists():
        return False
    for run_dir in out_dir.iterdir():
        if not run_dir.is_dir():
            continue
        manifest = run_dir / 'manifest.json'
        if manifest.exists():
            try:
                if json.loads(manifest.read_text()).get('status') == 'ok':
                    return True
            except Exception:
                pass
        if any(run_dir.rglob('qoi_summary.json')):
            return True
    return False


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    cases_dir = Path(args.cases_dir)

    # ── Build job list: list of (output_id, patient_id, config_path | None) ──
    # output_id  = directory name under output/ (e.g. "0014_H_AO_COA_mesh10")
    # patient_id = actual case dir under cases_input/ (e.g. "0014_H_AO_COA")
    jobs: List[Tuple[str, str, Optional[str]]] = []

    if args.config_list:
        # --config-list 0014_H_AO_COA:config_mesh10.json 0014_H_AO_COA:config_mesh12.json ...
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
            # output_id: "0014_H_AO_COA_mesh10" from "config_mesh10.json"
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

    # ── Apply --resume: filter out completed cases ──
    if args.resume:
        skipped = [oid for oid, _, _ in jobs if _is_case_done(oid)]
        jobs = [(oid, pid, cfg) for oid, pid, cfg in jobs if oid not in skipped]
        if skipped:
            print(f'\n[--resume] Skipping {len(skipped)} already-completed case(s):')
            for s in skipped:
                print(f'  - {s}')
        if not jobs:
            print('\n[--resume] All requested cases already completed. Nothing to do.')
            sys.exit(0)

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
        print(f'\n[DRY RUN] Would execute {len(jobs)} job(s):')
        for output_id, patient_id, cfg in jobs:
            cfg_arg = f' --config {cfg}' if cfg else ''
            profile_arg = f' --profile {args.profile}' if args.profile else ''
            steps_arg = f' --steps {args.steps}' if args.steps != 'all' else ''
            print(f'  python run_patient.py {patient_id}{steps_arg}{cfg_arg}{profile_arg}'
                  f'   # -> output/{output_id}/')
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
            cluster_conf=args.cluster_conf,
            slurm_template=args.slurm_template,
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
