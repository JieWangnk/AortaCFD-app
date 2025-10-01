#!/usr/bin/env python3
"""
Performance Profiler for AortaCFD Pipeline
Measures computational performance metrics for publication
"""

import time
import psutil
import json
import os
import sys
import tracemalloc
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.append(str(Path(__file__).parent.parent))
from src.workflow.manager import WorkflowManager
from src.config.builder import ConfigBuilder


class PerformanceProfiler:
    """Profile AortaCFD pipeline performance metrics"""

    def __init__(self, output_dir: Path = Path("benchmarks/results")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.metrics = {
            'timestamp': datetime.now().isoformat(),
            'system_info': self._get_system_info(),
            'pipeline_metrics': [],
            'task_metrics': {},
            'mesh_metrics': {},
            'solver_metrics': {}
        }

    def _get_system_info(self) -> Dict[str, Any]:
        """Collect system information"""
        return {
            'cpu_count': psutil.cpu_count(),
            'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
            'platform': sys.platform,
            'python_version': sys.version
        }

    def profile_pipeline(self, patient_name: str, quick_mode: bool = True) -> Dict[str, Any]:
        """Profile complete pipeline execution"""
        print(f"\n{'='*60}")
        print(f"Profiling AortaCFD Pipeline for {patient_name}")
        print(f"{'='*60}\n")

        # Start memory tracking
        tracemalloc.start()

        # Initialize metrics
        pipeline_start = time.time()
        task_timings = {}
        memory_peaks = {}

        # Monitor individual workflow tasks
        original_execute = WorkflowManager.execute_task

        def monitored_execute(self, task_name, *args, **kwargs):
            task_start = time.time()
            memory_before = psutil.Process().memory_info().rss / (1024**2)  # MB

            result = original_execute(self, task_name, *args, **kwargs)

            task_end = time.time()
            memory_after = psutil.Process().memory_info().rss / (1024**2)  # MB

            task_timings[task_name] = {
                'duration_seconds': task_end - task_start,
                'memory_before_mb': memory_before,
                'memory_after_mb': memory_after,
                'memory_delta_mb': memory_after - memory_before
            }

            print(f"  ✓ {task_name}: {task_end - task_start:.2f}s, "
                  f"Memory Δ: {memory_after - memory_before:.2f}MB")

            return result

        # Patch the execute method
        WorkflowManager.execute_task = monitored_execute

        try:
            # Build configuration
            config = ConfigBuilder.build_config(
                patient_name=patient_name,
                quick=quick_mode
            )

            # Run workflow
            workflow = WorkflowManager(config)
            workflow.run_workflow()

            # Collect final metrics
            pipeline_end = time.time()
            current, peak = tracemalloc.get_traced_memory()

            self.metrics['pipeline_metrics'] = {
                'patient_name': patient_name,
                'total_time_seconds': pipeline_end - pipeline_start,
                'total_time_minutes': (pipeline_end - pipeline_start) / 60,
                'peak_memory_mb': peak / (1024**2),
                'current_memory_mb': current / (1024**2),
                'quick_mode': quick_mode,
                'success': True
            }

            self.metrics['task_metrics'] = task_timings

            # Analyze mesh quality if available
            self._analyze_mesh_quality(config)

            # Analyze solver convergence if available
            self._analyze_solver_convergence(config)

        except Exception as e:
            self.metrics['pipeline_metrics']['success'] = False
            self.metrics['pipeline_metrics']['error'] = str(e)
            print(f"Error during profiling: {e}")

        finally:
            # Restore original method
            WorkflowManager.execute_task = original_execute
            tracemalloc.stop()

        # Save metrics
        self._save_metrics()

        return self.metrics

    def _analyze_mesh_quality(self, config):
        """Extract mesh quality metrics from checkMesh output"""
        case_dir = Path(config['paths']['case_dir'])
        checkmesh_log = case_dir / "log.checkMesh"

        if checkmesh_log.exists():
            with open(checkmesh_log, 'r') as f:
                content = f.read()

            # Extract key metrics
            metrics = {}

            # Cell count
            if "cells:" in content:
                for line in content.split('\n'):
                    if "cells:" in line and "nCells:" not in line:
                        try:
                            metrics['total_cells'] = int(line.split()[-1])
                        except:
                            pass

            # Extract quality metrics
            quality_indicators = [
                'Mesh non-orthogonality Max',
                'Max skewness',
                'Max aspect ratio'
            ]

            for indicator in quality_indicators:
                if indicator in content:
                    for line in content.split('\n'):
                        if indicator in line:
                            try:
                                value = float(line.split()[-1])
                                metrics[indicator.lower().replace(' ', '_')] = value
                            except:
                                pass

            self.metrics['mesh_metrics'] = metrics

    def _analyze_solver_convergence(self, config):
        """Analyze solver convergence from log files"""
        case_dir = Path(config['paths']['case_dir'])

        # Look for solver logs
        solver_logs = list(case_dir.glob("log.*"))

        convergence_data = {}
        for log_file in solver_logs:
            if 'checkMesh' not in log_file.name:
                # Extract residuals
                residuals = self._extract_residuals(log_file)
                if residuals:
                    convergence_data[log_file.name] = {
                        'iterations': len(residuals),
                        'final_residual': residuals[-1] if residuals else None
                    }

        self.metrics['solver_metrics'] = convergence_data

    def _extract_residuals(self, log_file: Path) -> List[float]:
        """Extract residual values from solver log"""
        residuals = []
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    if 'residual' in line.lower() and '=' in line:
                        try:
                            # Extract numerical value after '='
                            value = float(line.split('=')[-1].split()[0].strip(','))
                            residuals.append(value)
                        except:
                            pass
        except:
            pass
        return residuals

    def _save_metrics(self):
        """Save metrics to JSON and generate summary"""
        # Save JSON
        json_file = self.output_dir / f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)

        print(f"\nMetrics saved to: {json_file}")

        # Generate summary report
        self._generate_summary_report()

    def _generate_summary_report(self):
        """Generate human-readable summary report"""
        report_file = self.output_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        with open(report_file, 'w') as f:
            f.write("="*60 + "\n")
            f.write("AortaCFD Performance Profiling Report\n")
            f.write("="*60 + "\n\n")

            # System info
            f.write("System Information:\n")
            f.write("-"*40 + "\n")
            for key, value in self.metrics['system_info'].items():
                f.write(f"  {key}: {value}\n")

            # Pipeline metrics
            f.write("\nPipeline Performance:\n")
            f.write("-"*40 + "\n")
            if self.metrics['pipeline_metrics']:
                pm = self.metrics['pipeline_metrics']
                f.write(f"  Total Time: {pm.get('total_time_minutes', 0):.2f} minutes\n")
                f.write(f"  Peak Memory: {pm.get('peak_memory_mb', 0):.2f} MB\n")
                f.write(f"  Success: {pm.get('success', False)}\n")

            # Task breakdown
            f.write("\nTask Breakdown:\n")
            f.write("-"*40 + "\n")
            for task, metrics in self.metrics['task_metrics'].items():
                f.write(f"  {task}:\n")
                f.write(f"    Duration: {metrics['duration_seconds']:.2f}s\n")
                f.write(f"    Memory Delta: {metrics['memory_delta_mb']:.2f}MB\n")

            # Mesh metrics
            if self.metrics['mesh_metrics']:
                f.write("\nMesh Quality:\n")
                f.write("-"*40 + "\n")
                for key, value in self.metrics['mesh_metrics'].items():
                    f.write(f"  {key}: {value}\n")

        print(f"Summary report saved to: {report_file}")

    def compare_with_manual(self, manual_time_minutes: float = 120):
        """Compare automated vs manual workflow times"""
        if not self.metrics['pipeline_metrics']:
            print("No pipeline metrics available for comparison")
            return

        auto_time = self.metrics['pipeline_metrics'].get('total_time_minutes', 0)
        speedup = manual_time_minutes / auto_time if auto_time > 0 else 0

        comparison = {
            'manual_time_minutes': manual_time_minutes,
            'automated_time_minutes': auto_time,
            'speedup_factor': speedup,
            'time_saved_minutes': manual_time_minutes - auto_time,
            'efficiency_gain_percent': ((manual_time_minutes - auto_time) / manual_time_minutes * 100)
        }

        print("\n" + "="*60)
        print("Manual vs Automated Comparison")
        print("="*60)
        print(f"Manual Workflow:    {manual_time_minutes:.1f} minutes")
        print(f"Automated Pipeline: {auto_time:.1f} minutes")
        print(f"Speedup Factor:     {speedup:.1f}x")
        print(f"Time Saved:         {comparison['time_saved_minutes']:.1f} minutes")
        print(f"Efficiency Gain:    {comparison['efficiency_gain_percent']:.1f}%")

        return comparison


def run_benchmark_suite(patients: List[str] = None):
    """Run complete benchmark suite for publication"""

    if patients is None:
        # Use example patients
        patients = ['patient1']  # Add more patients as available

    profiler = PerformanceProfiler()

    all_results = []
    for patient in patients:
        print(f"\nBenchmarking {patient}...")
        metrics = profiler.profile_pipeline(patient, quick_mode=True)
        all_results.append(metrics)

        # Compare with typical manual workflow time
        profiler.compare_with_manual(manual_time_minutes=120)

    # Generate comparative plots
    generate_benchmark_plots(all_results)

    return all_results


def generate_benchmark_plots(results: List[Dict]):
    """Generate publication-quality benchmark plots"""
    output_dir = Path("benchmarks/figures")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set publication style
    plt.style.use('seaborn-v0_8-paper')
    sns.set_palette("husl")

    # Extract data for plotting
    task_times = {}
    for result in results:
        for task, metrics in result.get('task_metrics', {}).items():
            if task not in task_times:
                task_times[task] = []
            task_times[task].append(metrics['duration_seconds'])

    # Create task timing bar plot
    if task_times:
        fig, ax = plt.subplots(figsize=(10, 6))
        tasks = list(task_times.keys())
        times = [sum(task_times[t])/len(task_times[t]) for t in tasks]

        bars = ax.barh(tasks, times)
        ax.set_xlabel('Average Time (seconds)')
        ax.set_title('AortaCFD Pipeline Task Performance')
        ax.grid(axis='x', alpha=0.3)

        # Add value labels
        for bar in bars:
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2,
                   f'{width:.1f}s', ha='left', va='center')

        plt.tight_layout()
        plt.savefig(output_dir / 'task_performance.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(output_dir / 'task_performance.png', dpi=300, bbox_inches='tight')
        print(f"\nFigures saved to {output_dir}")


if __name__ == "__main__":
    # Run benchmarking suite
    import argparse

    parser = argparse.ArgumentParser(description='Benchmark AortaCFD Pipeline')
    parser.add_argument('--patient', type=str, default='patient1',
                       help='Patient name to benchmark')
    parser.add_argument('--quick', action='store_true',
                       help='Run in quick mode')
    parser.add_argument('--suite', action='store_true',
                       help='Run complete benchmark suite')

    args = parser.parse_args()

    if args.suite:
        run_benchmark_suite()
    else:
        profiler = PerformanceProfiler()
        profiler.profile_pipeline(args.patient, quick_mode=args.quick)
        profiler.compare_with_manual()