"""
Iterative Mesh Quality Improvement Workflow
============================================

CF-Mesh inspired iterative mesh quality improvement for snappyHexMesh.

CF-Mesh achieves high quality through massive iteration counts:
- Pre-mapping: 500 iterations x 2 phases
- Surface mapping: 500 iterations x 5+ passes
- Untangling: 100 iterations x multiple stages (reduces bad faces 590 -> 0)

This module provides:
1. Automatic parameter adjustment based on mesh quality issues
2. Iterative retry workflow when quality is poor
3. Integration with smoothMesh post-processing
4. Quality history tracking for optimization

Usage:
    from aortacfd_lib.mesh_improvement import MeshImprovementWorkflow

    workflow = MeshImprovementWorkflow(config, case_dir)
    final_quality = workflow.run_iterative_improvement(
        max_retries=2,
        enable_smoothmesh=True
    )

Author: AortaCFD Team
Status: EXPERIMENTAL - API may change
"""

import os
import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

from .utils.mesh_quality import (
    MeshQualityAnalyzer,
    MeshQualityMetrics,
    MeshQualityTier
)
from .utils.logger import Logger


@dataclass
class MeshAttemptResult:
    """Result of a single meshing attempt."""
    attempt_number: int
    quality_tier: MeshQualityTier
    metrics: MeshQualityMetrics
    parameters_used: Dict[str, Any]
    smoothmesh_applied: bool = False
    success: bool = True
    notes: List[str] = field(default_factory=list)


@dataclass
class MeshImprovementResult:
    """Final result of iterative mesh improvement workflow."""
    final_tier: MeshQualityTier
    final_metrics: MeshQualityMetrics
    total_attempts: int
    attempts: List[MeshAttemptResult]
    improvement_achieved: bool
    parameters_used: Dict[str, Any]
    smoothmesh_applied: bool = False


class MeshImprovementWorkflow:
    """
    Iterative mesh quality improvement workflow inspired by CF-Mesh.

    This class implements an iterative approach to mesh quality improvement:
    1. Run snappyHexMesh with current settings
    2. Analyze quality via checkMesh
    3. If quality is POOR/CRITICAL:
       a. Optionally run smoothMesh for centroidal smoothing
       b. If still poor, adjust parameters and retry
    4. Track quality improvement across attempts

    Attributes:
        config: OpenFOAM case configuration dictionary
        case_dir: Path to OpenFOAM case directory
        log: Logger instance
        quality_history: List of MeshAttemptResult for each attempt
    """

    # Maximum parameter values (safety limits)
    MAX_PARAMETERS = {
        'nSolveIter': 250,
        'nSmoothPatch': 15,
        'nSmoothSurfaceNormals': 50,
        'nLayerIter': 150,
        'nSmoothScale': 12,
    }

    def __init__(self, config: dict, case_dir: str):
        """
        Initialize mesh improvement workflow.

        Args:
            config: Full configuration dictionary
            case_dir: Path to OpenFOAM case directory
        """
        self.config = config
        self.case_dir = case_dir
        self.log = Logger("mesh_improvement").get_logger()
        self.quality_history: List[MeshAttemptResult] = []

    def analyze_current_quality(self) -> MeshAttemptResult:
        """
        Analyze current mesh quality from checkMesh log.

        Returns:
            MeshAttemptResult with current quality assessment
        """
        analyzer = MeshQualityAnalyzer(self.case_dir)
        log_path = os.path.join(self.case_dir, "log.checkMesh")

        if not os.path.exists(log_path):
            self.log.warning(f"checkMesh log not found: {log_path}")
            metrics = MeshQualityMetrics(mesh_ok=False)
            metrics.errors.append("checkMesh log not found")
            return MeshAttemptResult(
                attempt_number=len(self.quality_history) + 1,
                quality_tier=MeshQualityTier.CRITICAL,
                metrics=metrics,
                parameters_used=self._get_current_parameters(),
                success=False
            )

        with open(log_path, 'r') as f:
            output = f.read()

        metrics = analyzer._parse_checkmesh_output(output)
        tier = analyzer.get_quality_tier(metrics)

        return MeshAttemptResult(
            attempt_number=len(self.quality_history) + 1,
            quality_tier=tier,
            metrics=metrics,
            parameters_used=self._get_current_parameters(),
            success=metrics.mesh_ok
        )

    def get_improved_parameters(self, current_result: MeshAttemptResult) -> Dict[str, Any]:
        """
        Calculate improved parameters based on current quality issues.

        Uses progressive escalation - each retry increases iterations further.

        Args:
            current_result: Result from current meshing attempt

        Returns:
            Dictionary of improved snappyHexMesh parameters
        """
        analyzer = MeshQualityAnalyzer(self.case_dir)
        recommendations = analyzer.get_snappy_parameter_recommendations(current_result.metrics)

        # Start with recommended parameters
        improved = {k: v for k, v in recommendations.items() if not k.startswith('_')}

        # Escalate based on attempt number (progressive increase)
        attempt = current_result.attempt_number
        escalation_factor = 1 + (attempt - 1) * 0.5  # 1.0, 1.5, 2.0, ...

        for param in ['nSolveIter', 'nSmoothPatch', 'nSmoothSurfaceNormals', 'nLayerIter']:
            if param in improved:
                max_val = self.MAX_PARAMETERS.get(param, improved[param] * 2)
                improved[param] = min(int(improved[param] * escalation_factor), max_val)

        # Log changes
        self.log.info(f"Adjusted parameters for retry attempt {attempt + 1}:")
        for param, value in improved.items():
            current_val = current_result.parameters_used.get(param, 'default')
            self.log.info(f"  {param}: {current_val} -> {value}")

        return improved

    def update_config_parameters(self, new_params: Dict[str, Any]) -> dict:
        """
        Update configuration with new snappyHexMesh parameters.

        Args:
            new_params: Dictionary of parameter overrides

        Returns:
            Updated configuration dictionary
        """
        updated_config = copy.deepcopy(self.config)

        if 'mesh' not in updated_config:
            updated_config['mesh'] = {}
        if 'SNAPPY_SETTINGS' not in updated_config['mesh']:
            updated_config['mesh']['SNAPPY_SETTINGS'] = {}

        updated_config['mesh']['SNAPPY_SETTINGS'].update(new_params)

        return updated_config

    def should_retry(self, result: MeshAttemptResult, max_retries: int) -> bool:
        """
        Determine if another retry attempt should be made.

        Args:
            result: Current attempt result
            max_retries: Maximum number of retry attempts

        Returns:
            True if should retry, False otherwise
        """
        if result.attempt_number > max_retries:
            return False

        if result.quality_tier in [MeshQualityTier.EXCELLENT, MeshQualityTier.GOOD]:
            return False

        # Check if we're making progress
        if len(self.quality_history) >= 2:
            prev_metrics = self.quality_history[-2].metrics
            curr_metrics = result.metrics

            # No improvement in key metrics - don't retry
            if (curr_metrics.max_skewness >= prev_metrics.max_skewness and
                curr_metrics.max_non_orthogonality >= prev_metrics.max_non_orthogonality):
                self.log.warning("No improvement detected - stopping retry attempts")
                return False

        return True

    def calculate_improvement(self) -> float:
        """
        Calculate overall quality improvement as a percentage.

        Returns:
            Percentage improvement (positive = better, negative = worse)
        """
        if len(self.quality_history) < 2:
            return 0.0

        initial = self.quality_history[0].metrics
        final = self.quality_history[-1].metrics

        # Use max skewness as primary improvement metric
        if initial.max_skewness > 0:
            improvement = (initial.max_skewness - final.max_skewness) / initial.max_skewness * 100
            return improvement

        return 0.0

    def _get_current_parameters(self) -> Dict[str, Any]:
        """Extract current snappyHexMesh parameters from config."""
        return self.config.get('mesh', {}).get('SNAPPY_SETTINGS', {}).copy()

    def generate_report(self) -> str:
        """
        Generate a summary report of the mesh improvement workflow.

        Returns:
            Formatted string report
        """
        if not self.quality_history:
            return "No mesh improvement attempts recorded."

        report = []
        report.append("=" * 70)
        report.append("MESH IMPROVEMENT WORKFLOW REPORT")
        report.append("=" * 70)
        report.append("")

        for attempt in self.quality_history:
            report.append(f"Attempt {attempt.attempt_number}:")
            report.append(f"  Quality Tier: {attempt.quality_tier.value}")
            report.append(f"  Max Skewness: {attempt.metrics.max_skewness:.2f}")
            report.append(f"  Max Non-Ortho: {attempt.metrics.max_non_orthogonality:.1f}°")
            report.append(f"  Max Aspect: {attempt.metrics.max_aspect_ratio:.1f}")
            if attempt.smoothmesh_applied:
                report.append("  smoothMesh: Applied")
            if attempt.notes:
                for note in attempt.notes:
                    report.append(f"  Note: {note}")
            report.append("")

        # Summary
        initial = self.quality_history[0]
        final = self.quality_history[-1]

        report.append("-" * 70)
        report.append("SUMMARY")
        report.append("-" * 70)
        report.append(f"Total Attempts: {len(self.quality_history)}")
        report.append(f"Initial Quality: {initial.quality_tier.value}")
        report.append(f"Final Quality: {final.quality_tier.value}")

        improvement = self.calculate_improvement()
        if improvement > 0:
            report.append(f"Skewness Improvement: {improvement:.1f}%")
        elif improvement < 0:
            report.append(f"Skewness Degradation: {abs(improvement):.1f}%")
        else:
            report.append("Skewness: No change")

        report.append("")
        report.append("=" * 70)

        return "\n".join(report)


def get_preset_for_quality(tier: MeshQualityTier) -> str:
    """
    Get recommended mesh quality preset based on current tier.

    Args:
        tier: Current mesh quality tier

    Returns:
        Recommended preset name ('draft', 'standard', 'high_quality')
    """
    mapping = {
        MeshQualityTier.EXCELLENT: 'standard',
        MeshQualityTier.GOOD: 'standard',
        MeshQualityTier.FAIR: 'standard',
        MeshQualityTier.POOR: 'high_quality',
        MeshQualityTier.CRITICAL: 'high_quality',
    }
    return mapping.get(tier, 'standard')
