"""
Parallel processing infrastructure for running multiple patient cases simultaneously.
"""

import os
import json
import time
import queue
import threading
import multiprocessing
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

from .core import PatientCaseRunner, PatientSimulationError
from aortacfd_lib.utils.logger import Logger


class JobStatus(Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PatientJob:
    """Represents a single patient processing job."""
    patient_id: str
    options: Dict = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result_path: Optional[str] = None
    error_message: Optional[str] = None
    progress: float = 0.0
    current_step: str = ""
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'patient_id': self.patient_id,
            'options': self.options,
            'status': self.status.value,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'result_path': self.result_path,
            'error_message': self.error_message,
            'progress': self.progress,
            'current_step': self.current_step,
            'duration': self.duration
        }


class ProgressTracker:
    """Thread-safe progress tracking for parallel jobs."""
    
    def __init__(self):
        self.jobs: Dict[str, PatientJob] = {}
        self.lock = threading.Lock()
        self.callbacks: List[Callable] = []
        
    def add_job(self, job: PatientJob):
        """Add a job to track."""
        with self.lock:
            self.jobs[job.patient_id] = job
            self._notify_callbacks('job_added', job)
    
    def update_job(self, patient_id: str, **kwargs):
        """Update job properties."""
        with self.lock:
            if patient_id in self.jobs:
                job = self.jobs[patient_id]
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                self._notify_callbacks('job_updated', job)
    
    def get_job(self, patient_id: str) -> Optional[PatientJob]:
        """Get job by patient ID."""
        with self.lock:
            return self.jobs.get(patient_id)
    
    def get_all_jobs(self) -> List[PatientJob]:
        """Get all tracked jobs."""
        with self.lock:
            return list(self.jobs.values())
    
    def get_summary(self) -> dict:
        """Get summary statistics."""
        with self.lock:
            total = len(self.jobs)
            by_status = {}
            for job in self.jobs.values():
                status = job.status.value
                by_status[status] = by_status.get(status, 0) + 1
            
            return {
                'total': total,
                'by_status': by_status,
                'pending': by_status.get('pending', 0),
                'running': by_status.get('running', 0),
                'completed': by_status.get('completed', 0),
                'failed': by_status.get('failed', 0),
                'cancelled': by_status.get('cancelled', 0)
            }
    
    def register_callback(self, callback: Callable):
        """Register a progress callback."""
        self.callbacks.append(callback)
    
    def _notify_callbacks(self, event: str, job: PatientJob):
        """Notify registered callbacks."""
        for callback in self.callbacks:
            try:
                callback(event, job)
            except Exception:
                pass  # Ignore callback errors


class ParallelPatientProcessor:
    """
    Parallel processor for running multiple patient cases simultaneously.
    
    Features:
    - Configurable worker pool size
    - Job queue management
    - Progress tracking
    - Error handling and recovery
    - Resource management
    """
    
    def __init__(self, max_workers: Optional[int] = None, use_processes: bool = True):
        """
        Initialize parallel processor.
        
        Args:
            max_workers: Maximum number of parallel workers (None for auto)
            use_processes: Use process pool (True) or thread pool (False)
        """
        self.logger = Logger("ParallelProcessor").get_logger()
        
        # Determine worker count
        if max_workers is None:
            max_workers = min(4, (multiprocessing.cpu_count() + 1) // 2)
        self.max_workers = max_workers
        self.use_processes = use_processes
        
        # Progress tracking
        self.tracker = ProgressTracker()
        
        # Results storage
        self.results: Dict[str, dict] = {}
        
        self.logger.info(f"Initialized with {max_workers} workers (processes={use_processes})")
    
    def process_patients(self, 
                         patient_ids: List[str],
                         options: Optional[Dict] = None,
                         progress_callback: Optional[Callable] = None) -> Dict[str, dict]:
        """
        Process multiple patients in parallel.
        
        Args:
            patient_ids: List of patient IDs to process
            options: Options to apply to all patients
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary mapping patient_id to results
        """
        if not patient_ids:
            return {}
        
        # Register progress callback
        if progress_callback:
            self.tracker.register_callback(progress_callback)
        
        # Create jobs
        jobs = []
        for patient_id in patient_ids:
            job = PatientJob(patient_id=patient_id, options=options or {})
            jobs.append(job)
            self.tracker.add_job(job)
        
        self.logger.info(f"Starting parallel processing of {len(jobs)} patients")
        
        # Choose executor type
        ExecutorClass = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
        
        # Process jobs in parallel
        with ExecutorClass(max_workers=self.max_workers) as executor:
            # Submit all jobs
            future_to_job = {}
            for job in jobs:
                future = executor.submit(self._process_single_patient, job)
                future_to_job[future] = job
            
            # Process completed jobs
            for future in as_completed(future_to_job):
                job = future_to_job[future]
                
                try:
                    result = future.result()
                    self.results[job.patient_id] = result
                    
                    # Update job status
                    self.tracker.update_job(
                        job.patient_id,
                        status=JobStatus.COMPLETED,
                        end_time=datetime.now(),
                        result_path=result.get('result_path'),
                        progress=100.0
                    )
                    
                    self.logger.info(f"Completed: {job.patient_id}")
                    
                except Exception as e:
                    # Handle job failure
                    self.tracker.update_job(
                        job.patient_id,
                        status=JobStatus.FAILED,
                        end_time=datetime.now(),
                        error_message=str(e)
                    )
                    
                    self.results[job.patient_id] = {
                        'status': 'failed',
                        'error': str(e)
                    }
                    
                    self.logger.error(f"Failed: {job.patient_id} - {e}")
        
        # Generate summary
        summary = self._generate_summary()
        
        return {
            'results': self.results,
            'summary': summary
        }
    
    def _process_single_patient(self, job: PatientJob) -> dict:
        """
        Process a single patient (runs in worker).
        
        Args:
            job: Patient job to process
            
        Returns:
            Result dictionary
        """
        # Update job status
        self.tracker.update_job(
            job.patient_id,
            status=JobStatus.RUNNING,
            start_time=datetime.now(),
            progress=0.0
        )
        
        try:
            # Create runner instance
            runner = PatientCaseRunner()
            
            # Simulate progress updates for different steps
            steps = ['case', 'mesh', 'boundary', 'solver', 'post']
            step_progress = 100.0 / len(steps)
            
            # Process with step tracking
            result_path = None
            
            # For actual implementation, we'd track real progress
            # Here we'll run the complete workflow
            if 'workflow_step' in job.options:
                # Run specific step
                workflow_step = job.options['workflow_step']
                self.tracker.update_job(
                    job.patient_id,
                    current_step=workflow_step,
                    progress=50.0
                )
                
                case_info = runner.load_patient_case(job.patient_id)
                sim_config = runner.prepare_simulation(case_info, job.options)
                success = runner.run_workflow_step(sim_config, workflow_step)
                
                if success:
                    result_path = runner.generate_results_summary(case_info, sim_config)
                else:
                    raise PatientSimulationError(f"Workflow step {workflow_step} failed")
                    
            else:
                # Run complete workflow
                current_progress = 0.0
                for i, step in enumerate(steps):
                    self.tracker.update_job(
                        job.patient_id,
                        current_step=step,
                        progress=current_progress
                    )
                    current_progress += step_progress
                    time.sleep(0.1)  # Small delay for demo
                
                # Run actual patient case
                result_path = runner.run_patient_case(job.patient_id, job.options)
            
            return {
                'status': 'completed',
                'result_path': result_path,
                'patient_id': job.patient_id
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
                'patient_id': job.patient_id
            }
    
    def _generate_summary(self) -> dict:
        """Generate processing summary."""
        stats = self.tracker.get_summary()
        jobs = self.tracker.get_all_jobs()
        
        # Calculate timing statistics
        durations = [j.duration for j in jobs if j.duration is not None]
        
        summary = {
            'total_patients': stats['total'],
            'completed': stats['completed'],
            'failed': stats['failed'],
            'success_rate': (stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0,
            'timing': {
                'total_duration': sum(durations) if durations else 0,
                'average_duration': sum(durations) / len(durations) if durations else 0,
                'min_duration': min(durations) if durations else 0,
                'max_duration': max(durations) if durations else 0
            },
            'timestamp': datetime.now().isoformat()
        }
        
        return summary
    
    def save_results(self, output_file: Path):
        """Save results to JSON file."""
        output_data = {
            'results': self.results,
            'jobs': [job.to_dict() for job in self.tracker.get_all_jobs()],
            'summary': self._generate_summary()
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        self.logger.info(f"Results saved to {output_file}")


class BatchProcessor:
    """
    High-level batch processor for patient cases.
    
    Provides convenient interface for batch processing with
    automatic resource management and error recovery.
    """
    
    def __init__(self):
        self.logger = Logger("BatchProcessor").get_logger()
        
    def process_batch(self,
                      patient_ids: List[str],
                      options: Optional[Dict] = None,
                      max_workers: Optional[int] = None,
                      save_results: bool = True) -> dict:
        """
        Process a batch of patients with automatic management.
        
        Args:
            patient_ids: List of patient IDs
            options: Processing options
            max_workers: Max parallel workers
            save_results: Save results to file
            
        Returns:
            Processing results dictionary
        """
        start_time = datetime.now()
        
        # Create processor
        processor = ParallelPatientProcessor(max_workers=max_workers)
        
        # Setup progress monitoring
        def progress_callback(event: str, job: PatientJob):
            if event == 'job_updated' and job.status == JobStatus.RUNNING:
                print(f"  📊 {job.patient_id}: {job.current_step} ({job.progress:.0f}%)")
            elif event == 'job_updated' and job.status == JobStatus.COMPLETED:
                print(f"  ✅ {job.patient_id}: Completed")
            elif event == 'job_updated' and job.status == JobStatus.FAILED:
                print(f"  ❌ {job.patient_id}: Failed - {job.error_message}")
        
        print(f"\n🚀 Starting batch processing of {len(patient_ids)} patients")
        print(f"   Workers: {processor.max_workers}")
        print("="*60)
        
        # Process batch
        results = processor.process_patients(
            patient_ids,
            options,
            progress_callback
        )
        
        # Save results if requested
        if save_results:
            output_dir = Path('output/batch_results')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = output_dir / f"batch_{timestamp}.json"
            processor.save_results(output_file)
            
            print(f"\n📁 Results saved to: {output_file}")
        
        # Print summary
        summary = results['summary']
        duration = (datetime.now() - start_time).total_seconds()
        
        print("\n" + "="*60)
        print("📊 BATCH PROCESSING SUMMARY")
        print("="*60)
        print(f"Total Patients: {summary['total_patients']}")
        print(f"Completed: {summary['completed']} ({summary['success_rate']:.1f}%)")
        print(f"Failed: {summary['failed']}")
        print(f"Total Duration: {duration:.1f}s")
        print(f"Average per Patient: {summary['timing']['average_duration']:.1f}s")
        print("="*60)
        
        return results


def run_parallel_patients(patient_ids: List[str], 
                          options: Optional[Dict] = None,
                          max_workers: Optional[int] = None) -> dict:
    """
    Convenience function for parallel patient processing.
    
    Args:
        patient_ids: List of patient IDs
        options: Processing options
        max_workers: Maximum workers
        
    Returns:
        Processing results
    """
    processor = BatchProcessor()
    return processor.process_batch(patient_ids, options, max_workers)