"""
Test suite for mesh_improvement.py module.

Tests cover:
- MeshAttemptResult dataclass
- MeshImprovementResult dataclass
- MeshImprovementWorkflow class methods
- get_preset_for_quality function
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestMeshAttemptResult:
    """Test MeshAttemptResult dataclass."""

    def test_create_basic_result(self):
        """Test creating a basic MeshAttemptResult."""
        from aortacfd_lib.mesh_improvement import MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        metrics = MeshQualityMetrics(mesh_ok=True)
        result = MeshAttemptResult(
            attempt_number=1,
            quality_tier=MeshQualityTier.GOOD,
            metrics=metrics,
            parameters_used={'nSolveIter': 50}
        )

        assert result.attempt_number == 1
        assert result.quality_tier == MeshQualityTier.GOOD
        assert result.parameters_used == {'nSolveIter': 50}
        assert result.smoothmesh_applied is False
        assert result.success is True
        assert result.notes == []

    def test_result_with_notes(self):
        """Test MeshAttemptResult with notes."""
        from aortacfd_lib.mesh_improvement import MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        metrics = MeshQualityMetrics(mesh_ok=False)
        result = MeshAttemptResult(
            attempt_number=2,
            quality_tier=MeshQualityTier.POOR,
            metrics=metrics,
            parameters_used={},
            success=False,
            notes=['High skewness detected', 'Consider refining mesh']
        )

        assert result.success is False
        assert len(result.notes) == 2


class TestMeshImprovementResult:
    """Test MeshImprovementResult dataclass."""

    def test_create_improvement_result(self):
        """Test creating a MeshImprovementResult."""
        from aortacfd_lib.mesh_improvement import MeshImprovementResult, MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        metrics = MeshQualityMetrics(mesh_ok=True)
        attempt = MeshAttemptResult(
            attempt_number=1,
            quality_tier=MeshQualityTier.GOOD,
            metrics=metrics,
            parameters_used={}
        )

        result = MeshImprovementResult(
            final_tier=MeshQualityTier.GOOD,
            final_metrics=metrics,
            total_attempts=1,
            attempts=[attempt],
            improvement_achieved=True,
            parameters_used={'nSolveIter': 100}
        )

        assert result.final_tier == MeshQualityTier.GOOD
        assert result.total_attempts == 1
        assert result.improvement_achieved is True
        assert result.smoothmesh_applied is False


class TestMeshImprovementWorkflow:
    """Test MeshImprovementWorkflow class."""

    @pytest.fixture
    def workflow(self, tmp_path):
        """Create a MeshImprovementWorkflow instance."""
        from aortacfd_lib.mesh_improvement import MeshImprovementWorkflow

        config = {
            'mesh': {
                'SNAPPY_SETTINGS': {
                    'nSolveIter': 50,
                    'nSmoothPatch': 5
                }
            }
        }

        with patch('aortacfd_lib.mesh_improvement.Logger'):
            workflow = MeshImprovementWorkflow(config, str(tmp_path))

        return workflow

    def test_init(self, workflow, tmp_path):
        """Test workflow initialization."""
        assert workflow.case_dir == str(tmp_path)
        assert workflow.quality_history == []
        assert 'mesh' in workflow.config

    def test_get_current_parameters(self, workflow):
        """Test extracting current parameters from config."""
        params = workflow._get_current_parameters()

        assert params['nSolveIter'] == 50
        assert params['nSmoothPatch'] == 5

    def test_get_current_parameters_empty_config(self, tmp_path):
        """Test _get_current_parameters with empty config."""
        from aortacfd_lib.mesh_improvement import MeshImprovementWorkflow

        with patch('aortacfd_lib.mesh_improvement.Logger'):
            workflow = MeshImprovementWorkflow({}, str(tmp_path))

        params = workflow._get_current_parameters()
        assert params == {}

    def test_update_config_parameters(self, workflow):
        """Test updating config with new parameters."""
        new_params = {'nSolveIter': 100, 'nSmoothPatch': 10}

        updated_config = workflow.update_config_parameters(new_params)

        assert updated_config['mesh']['SNAPPY_SETTINGS']['nSolveIter'] == 100
        assert updated_config['mesh']['SNAPPY_SETTINGS']['nSmoothPatch'] == 10
        # Original config should be unchanged
        assert workflow.config['mesh']['SNAPPY_SETTINGS']['nSolveIter'] == 50

    def test_update_config_parameters_creates_structure(self, tmp_path):
        """Test update_config_parameters creates mesh structure if missing."""
        from aortacfd_lib.mesh_improvement import MeshImprovementWorkflow

        with patch('aortacfd_lib.mesh_improvement.Logger'):
            workflow = MeshImprovementWorkflow({}, str(tmp_path))

        new_params = {'nSolveIter': 100}
        updated_config = workflow.update_config_parameters(new_params)

        assert 'mesh' in updated_config
        assert 'SNAPPY_SETTINGS' in updated_config['mesh']
        assert updated_config['mesh']['SNAPPY_SETTINGS']['nSolveIter'] == 100

    def test_should_retry_exceeds_max_retries(self, workflow):
        """Test should_retry returns False when max retries exceeded."""
        from aortacfd_lib.mesh_improvement import MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        metrics = MeshQualityMetrics(mesh_ok=False)
        result = MeshAttemptResult(
            attempt_number=3,
            quality_tier=MeshQualityTier.POOR,
            metrics=metrics,
            parameters_used={}
        )

        should_retry = workflow.should_retry(result, max_retries=2)
        assert should_retry is False

    def test_should_retry_good_quality(self, workflow):
        """Test should_retry returns False for good quality."""
        from aortacfd_lib.mesh_improvement import MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        metrics = MeshQualityMetrics(mesh_ok=True)
        result = MeshAttemptResult(
            attempt_number=1,
            quality_tier=MeshQualityTier.GOOD,
            metrics=metrics,
            parameters_used={}
        )

        should_retry = workflow.should_retry(result, max_retries=3)
        assert should_retry is False

    def test_should_retry_excellent_quality(self, workflow):
        """Test should_retry returns False for excellent quality."""
        from aortacfd_lib.mesh_improvement import MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        metrics = MeshQualityMetrics(mesh_ok=True)
        result = MeshAttemptResult(
            attempt_number=1,
            quality_tier=MeshQualityTier.EXCELLENT,
            metrics=metrics,
            parameters_used={}
        )

        should_retry = workflow.should_retry(result, max_retries=3)
        assert should_retry is False

    def test_should_retry_poor_quality(self, workflow):
        """Test should_retry returns True for poor quality with attempts remaining."""
        from aortacfd_lib.mesh_improvement import MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        metrics = MeshQualityMetrics(mesh_ok=False)
        result = MeshAttemptResult(
            attempt_number=1,
            quality_tier=MeshQualityTier.POOR,
            metrics=metrics,
            parameters_used={}
        )

        should_retry = workflow.should_retry(result, max_retries=3)
        assert should_retry is True

    def test_should_retry_no_improvement(self, workflow):
        """Test should_retry returns False when no improvement detected."""
        from aortacfd_lib.mesh_improvement import MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        # First attempt
        metrics1 = MeshQualityMetrics(mesh_ok=False)
        metrics1.max_skewness = 5.0
        metrics1.max_non_orthogonality = 70.0
        result1 = MeshAttemptResult(
            attempt_number=1,
            quality_tier=MeshQualityTier.POOR,
            metrics=metrics1,
            parameters_used={}
        )
        workflow.quality_history.append(result1)

        # Second attempt - no improvement
        metrics2 = MeshQualityMetrics(mesh_ok=False)
        metrics2.max_skewness = 5.5  # Worse
        metrics2.max_non_orthogonality = 72.0  # Worse
        result2 = MeshAttemptResult(
            attempt_number=2,
            quality_tier=MeshQualityTier.POOR,
            metrics=metrics2,
            parameters_used={}
        )
        workflow.quality_history.append(result2)

        should_retry = workflow.should_retry(result2, max_retries=5)
        assert should_retry is False

    def test_calculate_improvement_no_history(self, workflow):
        """Test calculate_improvement with no history."""
        improvement = workflow.calculate_improvement()
        assert improvement == 0.0

    def test_calculate_improvement_single_attempt(self, workflow):
        """Test calculate_improvement with single attempt."""
        from aortacfd_lib.mesh_improvement import MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        metrics = MeshQualityMetrics(mesh_ok=True)
        result = MeshAttemptResult(
            attempt_number=1,
            quality_tier=MeshQualityTier.FAIR,
            metrics=metrics,
            parameters_used={}
        )
        workflow.quality_history.append(result)

        improvement = workflow.calculate_improvement()
        assert improvement == 0.0

    def test_calculate_improvement_positive(self, workflow):
        """Test calculate_improvement with positive improvement."""
        from aortacfd_lib.mesh_improvement import MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        # Initial - worse quality
        metrics1 = MeshQualityMetrics(mesh_ok=True)
        metrics1.max_skewness = 4.0
        result1 = MeshAttemptResult(
            attempt_number=1,
            quality_tier=MeshQualityTier.POOR,
            metrics=metrics1,
            parameters_used={}
        )
        workflow.quality_history.append(result1)

        # Final - better quality
        metrics2 = MeshQualityMetrics(mesh_ok=True)
        metrics2.max_skewness = 2.0  # 50% improvement
        result2 = MeshAttemptResult(
            attempt_number=2,
            quality_tier=MeshQualityTier.FAIR,
            metrics=metrics2,
            parameters_used={}
        )
        workflow.quality_history.append(result2)

        improvement = workflow.calculate_improvement()
        assert improvement == pytest.approx(50.0)

    def test_calculate_improvement_negative(self, workflow):
        """Test calculate_improvement with degradation."""
        from aortacfd_lib.mesh_improvement import MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        # Initial - better quality
        metrics1 = MeshQualityMetrics(mesh_ok=True)
        metrics1.max_skewness = 2.0
        result1 = MeshAttemptResult(
            attempt_number=1,
            quality_tier=MeshQualityTier.FAIR,
            metrics=metrics1,
            parameters_used={}
        )
        workflow.quality_history.append(result1)

        # Final - worse quality
        metrics2 = MeshQualityMetrics(mesh_ok=True)
        metrics2.max_skewness = 3.0  # 50% degradation
        result2 = MeshAttemptResult(
            attempt_number=2,
            quality_tier=MeshQualityTier.POOR,
            metrics=metrics2,
            parameters_used={}
        )
        workflow.quality_history.append(result2)

        improvement = workflow.calculate_improvement()
        assert improvement == pytest.approx(-50.0)

    def test_analyze_current_quality_no_log(self, workflow, tmp_path):
        """Test analyze_current_quality when checkMesh log doesn't exist."""
        result = workflow.analyze_current_quality()

        from aortacfd_lib.utils.mesh_quality import MeshQualityTier
        assert result.quality_tier == MeshQualityTier.CRITICAL
        assert result.success is False
        assert 'checkMesh log not found' in result.metrics.errors

    def test_analyze_current_quality_with_log(self, workflow, tmp_path):
        """Test analyze_current_quality with valid checkMesh log."""
        # Create a mock checkMesh log
        log_content = """
Checking geometry...

    Overall domain bounding box (0 0 0) (0.1 0.1 0.1)
    Mesh has 3 geometric (non-empty/wedge) directions (1 1 1)
    Mesh has 3 solution (non-empty) directions (1 1 1)
    Boundary openness (1e-16 1e-16 1e-16) OK.
    Max cell openness = 1e-10 OK.
    Max aspect ratio = 15.5 OK.
    Minimum face area = 1e-6. Maximum face area = 1e-4.  Face area magnitudes OK.
    Min volume = 1e-9. Max volume = 1e-7.  Total volume = 0.001.  Cell volumes OK.
    Mesh non-orthogonality Max: 55.5 average: 10
    Non-orthogonality check OK.
    Max skewness = 2.5 OK.

Checking topology...

    Boundary definition OK.
    Cell to face addressing OK.
    Point usage OK.
    Upper triangular ordering OK.
    Face vertices OK.
    Number of regions: 1 (OK).

Mesh OK.
"""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        log_path = logs_dir / "log.checkMesh"
        log_path.write_text(log_content)

        with patch('aortacfd_lib.mesh_improvement.MeshQualityAnalyzer') as mock_analyzer:
            mock_instance = MagicMock()
            from aortacfd_lib.utils.mesh_quality import MeshQualityMetrics, MeshQualityTier
            mock_metrics = MeshQualityMetrics(mesh_ok=True)
            mock_metrics.max_skewness = 2.5
            mock_metrics.max_non_orthogonality = 55.5
            mock_metrics.max_aspect_ratio = 15.5
            mock_instance._parse_checkmesh_output.return_value = mock_metrics
            mock_instance.get_quality_tier.return_value = MeshQualityTier.FAIR
            mock_analyzer.return_value = mock_instance

            result = workflow.analyze_current_quality()

            assert result.quality_tier == MeshQualityTier.FAIR
            assert result.metrics.max_skewness == 2.5

    def test_get_improved_parameters(self, workflow):
        """Test get_improved_parameters escalates values."""
        from aortacfd_lib.mesh_improvement import MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        metrics = MeshQualityMetrics(mesh_ok=False)
        metrics.max_skewness = 5.0
        result = MeshAttemptResult(
            attempt_number=1,
            quality_tier=MeshQualityTier.POOR,
            metrics=metrics,
            parameters_used={'nSolveIter': 50}
        )

        with patch('aortacfd_lib.mesh_improvement.MeshQualityAnalyzer') as mock_analyzer:
            mock_instance = MagicMock()
            mock_instance.get_snappy_parameter_recommendations.return_value = {
                'nSolveIter': 100,
                'nSmoothPatch': 8
            }
            mock_analyzer.return_value = mock_instance

            improved = workflow.get_improved_parameters(result)

            assert 'nSolveIter' in improved
            assert improved['nSolveIter'] >= 100  # Should be escalated

    def test_generate_report_no_history(self, workflow):
        """Test generate_report with no attempts."""
        report = workflow.generate_report()
        assert "No mesh improvement attempts recorded" in report

    def test_generate_report_with_attempts(self, workflow):
        """Test generate_report with multiple attempts."""
        from aortacfd_lib.mesh_improvement import MeshAttemptResult
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier, MeshQualityMetrics

        # First attempt
        metrics1 = MeshQualityMetrics(mesh_ok=True)
        metrics1.max_skewness = 4.0
        metrics1.max_non_orthogonality = 65.0
        metrics1.max_aspect_ratio = 25.0
        result1 = MeshAttemptResult(
            attempt_number=1,
            quality_tier=MeshQualityTier.POOR,
            metrics=metrics1,
            parameters_used={},
            notes=['Initial attempt']
        )
        workflow.quality_history.append(result1)

        # Second attempt with improvement
        metrics2 = MeshQualityMetrics(mesh_ok=True)
        metrics2.max_skewness = 2.0
        metrics2.max_non_orthogonality = 55.0
        metrics2.max_aspect_ratio = 20.0
        result2 = MeshAttemptResult(
            attempt_number=2,
            quality_tier=MeshQualityTier.FAIR,
            metrics=metrics2,
            parameters_used={},
            smoothmesh_applied=True
        )
        workflow.quality_history.append(result2)

        report = workflow.generate_report()

        assert "MESH IMPROVEMENT WORKFLOW REPORT" in report
        assert "Attempt 1:" in report
        assert "Attempt 2:" in report
        assert "SUMMARY" in report
        assert "Total Attempts: 2" in report
        assert "smoothMesh: Applied" in report
        assert "Improvement" in report  # Skewness improvement


class TestGetPresetForQuality:
    """Test get_preset_for_quality function."""

    def test_excellent_returns_standard(self):
        """Test that excellent quality returns standard preset."""
        from aortacfd_lib.mesh_improvement import get_preset_for_quality
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier

        preset = get_preset_for_quality(MeshQualityTier.EXCELLENT)
        assert preset == 'standard'

    def test_good_returns_standard(self):
        """Test that good quality returns standard preset."""
        from aortacfd_lib.mesh_improvement import get_preset_for_quality
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier

        preset = get_preset_for_quality(MeshQualityTier.GOOD)
        assert preset == 'standard'

    def test_fair_returns_standard(self):
        """Test that fair quality returns standard preset."""
        from aortacfd_lib.mesh_improvement import get_preset_for_quality
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier

        preset = get_preset_for_quality(MeshQualityTier.FAIR)
        assert preset == 'standard'

    def test_poor_returns_high_quality(self):
        """Test that poor quality returns high_quality preset."""
        from aortacfd_lib.mesh_improvement import get_preset_for_quality
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier

        preset = get_preset_for_quality(MeshQualityTier.POOR)
        assert preset == 'high_quality'

    def test_critical_returns_high_quality(self):
        """Test that critical quality returns high_quality preset."""
        from aortacfd_lib.mesh_improvement import get_preset_for_quality
        from aortacfd_lib.utils.mesh_quality import MeshQualityTier

        preset = get_preset_for_quality(MeshQualityTier.CRITICAL)
        assert preset == 'high_quality'


class TestMaxParameters:
    """Test MAX_PARAMETERS class attribute."""

    def test_max_parameters_exist(self):
        """Test that MAX_PARAMETERS contains expected keys."""
        from aortacfd_lib.mesh_improvement import MeshImprovementWorkflow

        assert 'nSolveIter' in MeshImprovementWorkflow.MAX_PARAMETERS
        assert 'nSmoothPatch' in MeshImprovementWorkflow.MAX_PARAMETERS
        assert 'nLayerIter' in MeshImprovementWorkflow.MAX_PARAMETERS

    def test_max_parameters_are_reasonable(self):
        """Test that MAX_PARAMETERS values are reasonable."""
        from aortacfd_lib.mesh_improvement import MeshImprovementWorkflow

        assert MeshImprovementWorkflow.MAX_PARAMETERS['nSolveIter'] > 0
        assert MeshImprovementWorkflow.MAX_PARAMETERS['nSolveIter'] <= 500


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
