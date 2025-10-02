"""
Quantitative Analysis Module for Publication-Quality CFD
========================================================

Provides comprehensive quantitative analysis tools including:
- Statistical analysis and hypothesis testing
- Uncertainty quantification
- Sensitivity analysis
- Mesh convergence studies
- Validation against experimental data
- Literature comparison
"""

import numpy as np
import pandas as pd
import scipy.stats as stats
from scipy import integrate, interpolate
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Optional, Callable
from pathlib import Path
import json
import warnings
from dataclasses import dataclass

from .utils.logger import Logger

logger = Logger("quantitative_analysis").get_logger()


@dataclass
class ConvergenceStudy:
    """Data structure for mesh/time convergence studies."""
    mesh_sizes: List[int]
    time_steps: List[float]
    variables: Dict[str, List[float]]
    convergence_rates: Dict[str, float]
    extrapolated_values: Dict[str, float]
    uncertainties: Dict[str, float]


@dataclass
class ValidationMetrics:
    """Validation metrics against experimental/reference data."""
    correlation_coefficient: float
    rmse: float
    mean_absolute_error: float
    bias: float
    limits_of_agreement: Tuple[float, float]
    concordance_correlation: float


class QuantitativeAnalyzer:
    """
    Comprehensive quantitative analysis for CFD validation and verification.
    
    This class provides tools for:
    - Mesh independence studies
    - Time step convergence analysis
    - Uncertainty quantification
    - Statistical validation
    - Literature comparison
    """
    
    def __init__(self, case_directories: List[str] = None):
        """
        Initialize quantitative analyzer.
        
        Args:
            case_directories: List of case directories for comparative analysis
        """
        self.case_dirs = case_directories or []
        self.log = logger
        
        # Analysis results storage
        self.convergence_studies = {}
        self.validation_results = {}
        self.uncertainty_analysis = {}
        self.statistical_tests = {}
        
        logger.info("Initialized quantitative analyzer")
    
    def perform_mesh_convergence_study(self, 
                                     mesh_cases: List[str],
                                     variables: List[str] = None,
                                     convergence_order: int = 2) -> ConvergenceStudy:
        """
        Perform comprehensive mesh convergence study.
        
        Args:
            mesh_cases: List of case directories with different mesh resolutions
            variables: Variables to analyze (e.g., ['velocity', 'pressure', 'wss'])
            convergence_order: Expected convergence order for extrapolation
        
        Returns:
            ConvergenceStudy object with convergence analysis results
        """
        if variables is None:
            variables = ['velocity_magnitude', 'pressure', 'wall_shear_stress']
        
        logger.info(f"Performing mesh convergence study for {len(mesh_cases)} cases")
        
        # Extract mesh sizes and solution data
        mesh_sizes = []
        solution_data = {var: [] for var in variables}
        
        for case_dir in mesh_cases:
            mesh_size = self._extract_mesh_size(case_dir)
            mesh_sizes.append(mesh_size)
            
            for var in variables:
                var_data = self._extract_variable_data(case_dir, var)
                solution_data[var].append(var_data)
        
        # Sort by mesh size
        sorted_indices = np.argsort(mesh_sizes)
        mesh_sizes = [mesh_sizes[i] for i in sorted_indices]
        for var in variables:
            solution_data[var] = [solution_data[var][i] for i in sorted_indices]
        
        # Calculate convergence rates
        convergence_rates = {}
        extrapolated_values = {}
        uncertainties = {}
        
        for var in variables:
            # Richardson extrapolation
            conv_rate, extrap_value, uncertainty = self._richardson_extrapolation(
                mesh_sizes, solution_data[var], convergence_order
            )
            
            convergence_rates[var] = conv_rate
            extrapolated_values[var] = extrap_value
            uncertainties[var] = uncertainty
        
        convergence_study = ConvergenceStudy(
            mesh_sizes=mesh_sizes,
            time_steps=[],  # Not applicable for mesh study
            variables=solution_data,
            convergence_rates=convergence_rates,
            extrapolated_values=extrapolated_values,
            uncertainties=uncertainties
        )
        
        self.convergence_studies['mesh'] = convergence_study
        logger.info("Mesh convergence study completed")
        
        return convergence_study
    
    def perform_time_convergence_study(self,
                                     time_cases: List[str],
                                     variables: List[str] = None) -> ConvergenceStudy:
        """
        Perform time step convergence study.
        
        Args:
            time_cases: List of case directories with different time steps
            variables: Variables to analyze
        
        Returns:
            ConvergenceStudy object with temporal convergence results
        """
        if variables is None:
            variables = ['velocity_magnitude', 'pressure', 'wall_shear_stress']
        
        logger.info(f"Performing time convergence study for {len(time_cases)} cases")
        
        # Extract time steps and solution data
        time_steps = []
        solution_data = {var: [] for var in variables}
        
        for case_dir in time_cases:
            dt = self._extract_time_step(case_dir)
            time_steps.append(dt)
            
            for var in variables:
                var_data = self._extract_temporal_variable_data(case_dir, var)
                solution_data[var].append(var_data)
        
        # Sort by time step
        sorted_indices = np.argsort(time_steps)
        time_steps = [time_steps[i] for i in sorted_indices]
        for var in variables:
            solution_data[var] = [solution_data[var][i] for i in sorted_indices]
        
        # Calculate temporal convergence
        convergence_rates = {}
        extrapolated_values = {}
        uncertainties = {}
        
        for var in variables:
            conv_rate, extrap_value, uncertainty = self._temporal_convergence_analysis(
                time_steps, solution_data[var]
            )
            
            convergence_rates[var] = conv_rate
            extrapolated_values[var] = extrap_value
            uncertainties[var] = uncertainty
        
        convergence_study = ConvergenceStudy(
            mesh_sizes=[],  # Not applicable for time study
            time_steps=time_steps,
            variables=solution_data,
            convergence_rates=convergence_rates,
            extrapolated_values=extrapolated_values,
            uncertainties=uncertainties
        )
        
        self.convergence_studies['time'] = convergence_study
        logger.info("Time convergence study completed")
        
        return convergence_study
    
    def validate_against_experimental_data(self,
                                         simulation_data: Dict[str, np.ndarray],
                                         experimental_data: Dict[str, np.ndarray],
                                         variables: List[str] = None) -> Dict[str, ValidationMetrics]:
        """
        Validate simulation results against experimental data.
        
        Args:
            simulation_data: Dictionary of simulation results
            experimental_data: Dictionary of experimental measurements
            variables: Variables to validate
        
        Returns:
            Dictionary of validation metrics for each variable
        """
        if variables is None:
            variables = list(simulation_data.keys())
        
        logger.info(f"Validating against experimental data for {len(variables)} variables")
        
        validation_results = {}
        
        for var in variables:
            if var not in simulation_data or var not in experimental_data:
                logger.warning(f"Variable {var} not found in both datasets")
                continue
            
            sim_values = simulation_data[var]
            exp_values = experimental_data[var]
            
            # Interpolate to common points if needed
            if len(sim_values) != len(exp_values):
                sim_values, exp_values = self._interpolate_to_common_points(
                    sim_values, exp_values
                )
            
            # Calculate validation metrics
            metrics = self._calculate_validation_metrics(sim_values, exp_values)
            validation_results[var] = metrics
            
            logger.info(f"Validation metrics for {var}: R²={metrics.correlation_coefficient:.3f}, "
                       f"RMSE={metrics.rmse:.3f}")
        
        self.validation_results['experimental'] = validation_results
        return validation_results
    
    def perform_uncertainty_quantification(self,
                                         parameter_ranges: Dict[str, Tuple[float, float]],
                                         n_samples: int = 100,
                                         method: str = 'monte_carlo') -> Dict:
        """
        Perform uncertainty quantification using Monte Carlo or other methods.
        
        Args:
            parameter_ranges: Dictionary of parameter names to (min, max) ranges
            n_samples: Number of samples for uncertainty analysis
            method: UQ method ('monte_carlo', 'polynomial_chaos')
        
        Returns:
            Dictionary with uncertainty analysis results
        """
        logger.info(f"Performing uncertainty quantification with {n_samples} samples")
        
        if method == 'monte_carlo':
            results = self._monte_carlo_uncertainty(parameter_ranges, n_samples)
        elif method == 'polynomial_chaos':
            results = self._polynomial_chaos_uncertainty(parameter_ranges, n_samples)
        else:
            raise ValueError(f"Unknown UQ method: {method}")
        
        self.uncertainty_analysis[method] = results
        return results
    
    def perform_sensitivity_analysis(self,
                                   parameters: Dict[str, np.ndarray],
                                   outputs: Dict[str, np.ndarray],
                                   method: str = 'sobol') -> Dict:
        """
        Perform global sensitivity analysis.
        
        Args:
            parameters: Dictionary of parameter samples
            outputs: Dictionary of corresponding output values
            method: Sensitivity analysis method ('sobol', 'morris')
        
        Returns:
            Dictionary with sensitivity indices
        """
        logger.info(f"Performing {method} sensitivity analysis")
        
        if method == 'sobol':
            sensitivity_indices = self._sobol_sensitivity_analysis(parameters, outputs)
        elif method == 'morris':
            sensitivity_indices = self._morris_sensitivity_analysis(parameters, outputs)
        else:
            raise ValueError(f"Unknown sensitivity method: {method}")
        
        return sensitivity_indices
    
    def compare_with_literature(self,
                              literature_data: Dict[str, Dict],
                              simulation_results: Dict[str, float],
                              confidence_level: float = 0.95) -> Dict:
        """
        Compare simulation results with literature values.
        
        Args:
            literature_data: Dictionary with literature values and uncertainties
            simulation_results: Dictionary with simulation results
            confidence_level: Confidence level for statistical tests
        
        Returns:
            Dictionary with comparison results and statistical tests
        """
        logger.info("Comparing results with literature data")
        
        comparison_results = {}
        
        for param_name in simulation_results.keys():
            if param_name not in literature_data:
                continue
            
            lit_data = literature_data[param_name]
            sim_value = simulation_results[param_name]
            
            # Statistical comparison
            comparison = self._statistical_comparison_with_literature(
                sim_value, lit_data, confidence_level
            )
            
            comparison_results[param_name] = comparison
        
        return comparison_results
    
    def generate_convergence_plots(self, output_dir: str) -> Dict[str, str]:
        """Generate convergence study plots."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        plot_files = {}
        
        # Mesh convergence plots
        if 'mesh' in self.convergence_studies:
            mesh_plot = self._plot_mesh_convergence(output_path)
            plot_files['mesh_convergence'] = str(mesh_plot)
        
        # Time convergence plots
        if 'time' in self.convergence_studies:
            time_plot = self._plot_time_convergence(output_path)
            plot_files['time_convergence'] = str(time_plot)
        
        return plot_files
    
    def generate_validation_plots(self, output_dir: str) -> Dict[str, str]:
        """Generate validation plots."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        plot_files = {}
        
        # Experimental validation plots
        if 'experimental' in self.validation_results:
            exp_plot = self._plot_experimental_validation(output_path)
            plot_files['experimental_validation'] = str(exp_plot)
        
        # Literature comparison plots
        if hasattr(self, 'literature_comparison'):
            lit_plot = self._plot_literature_comparison(output_path)
            plot_files['literature_comparison'] = str(lit_plot)
        
        return plot_files
    
    # Private methods for calculations
    def _richardson_extrapolation(self, 
                                mesh_sizes: List[int],
                                solutions: List[float],
                                convergence_order: int) -> Tuple[float, float, float]:
        """Perform Richardson extrapolation for mesh convergence."""
        if len(mesh_sizes) < 3:
            logger.warning("Need at least 3 mesh sizes for Richardson extrapolation")
            return 0.0, solutions[-1], 0.0
        
        # Calculate mesh spacing (h = 1/sqrt(N) for 2D, h = 1/N^(1/3) for 3D)
        h = [1.0 / (n ** (1/3)) for n in mesh_sizes]
        
        # Use finest three solutions
        h1, h2, h3 = h[-3:]
        f1, f2, f3 = solutions[-3:]
        
        # Calculate observed convergence order
        if h1 != h2 and h2 != h3:
            p_obs = np.log((f3 - f2) / (f2 - f1)) / np.log(h3/h2)
        else:
            p_obs = convergence_order
        
        # Richardson extrapolation to h=0
        if p_obs != 0:
            f_extrap = f1 + (f1 - f2) / ((h2/h1)**p_obs - 1)
        else:
            f_extrap = f1
        
        # Grid convergence index (uncertainty)
        if p_obs > 0:
            gci = 1.25 * abs((f1 - f2) / f1) / ((h2/h1)**p_obs - 1)
        else:
            gci = 0.0
        
        return p_obs, f_extrap, gci
    
    def _calculate_validation_metrics(self, 
                                    simulation: np.ndarray,
                                    experimental: np.ndarray) -> ValidationMetrics:
        """Calculate comprehensive validation metrics."""
        # Remove NaN values
        valid_mask = ~(np.isnan(simulation) | np.isnan(experimental))
        sim = simulation[valid_mask]
        exp = experimental[valid_mask]
        
        if len(sim) == 0:
            logger.warning("No valid data points for validation")
            return ValidationMetrics(0, np.inf, np.inf, 0, (0, 0), 0)
        
        # Correlation coefficient (R²)
        correlation = stats.pearsonr(sim, exp)[0] ** 2
        
        # Root mean square error
        rmse = np.sqrt(np.mean((sim - exp) ** 2))
        
        # Mean absolute error
        mae = np.mean(np.abs(sim - exp))
        
        # Bias
        bias = np.mean(sim - exp)
        
        # Limits of agreement (Bland-Altman)
        diff = sim - exp
        mean_diff = np.mean(diff)
        std_diff = np.std(diff)
        loa_lower = mean_diff - 1.96 * std_diff
        loa_upper = mean_diff + 1.96 * std_diff
        
        # Concordance correlation coefficient
        mean_sim = np.mean(sim)
        mean_exp = np.mean(exp)
        var_sim = np.var(sim)
        var_exp = np.var(exp)
        cov_sim_exp = np.cov(sim, exp)[0, 1]
        
        ccc = (2 * cov_sim_exp) / (var_sim + var_exp + (mean_sim - mean_exp)**2)
        
        return ValidationMetrics(
            correlation_coefficient=correlation,
            rmse=rmse,
            mean_absolute_error=mae,
            bias=bias,
            limits_of_agreement=(loa_lower, loa_upper),
            concordance_correlation=ccc
        )
    
    def _monte_carlo_uncertainty(self, 
                               parameter_ranges: Dict[str, Tuple[float, float]],
                               n_samples: int) -> Dict:
        """Perform Monte Carlo uncertainty quantification."""
        # Generate parameter samples
        parameters = {}
        for param_name, (min_val, max_val) in parameter_ranges.items():
            parameters[param_name] = np.random.uniform(min_val, max_val, n_samples)
        
        # This would need to be coupled with actual CFD simulations
        # For now, return placeholder structure
        results = {
            'parameter_samples': parameters,
            'output_statistics': {},
            'sensitivity_indices': {},
            'confidence_intervals': {}
        }
        
        return results
    
    def _plot_mesh_convergence(self, output_dir: Path) -> Path:
        """Create mesh convergence plot."""
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        
        convergence_study = self.convergence_studies['mesh']
        
        # Convergence plot
        ax1 = axes[0]
        mesh_sizes = convergence_study.mesh_sizes
        h = [1.0 / (n ** (1/3)) for n in mesh_sizes]  # Characteristic mesh size
        
        for var_name, var_data in convergence_study.variables.items():
            ax1.loglog(h, var_data, 'o-', label=var_name)
        
        ax1.set_xlabel('Mesh size h')
        ax1.set_ylabel('Solution value')
        ax1.set_title('Mesh Convergence Study')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Convergence rate plot
        ax2 = axes[1]
        var_names = list(convergence_study.convergence_rates.keys())
        conv_rates = list(convergence_study.convergence_rates.values())
        
        bars = ax2.bar(var_names, conv_rates)
        ax2.axhline(y=2.0, color='r', linestyle='--', label='Theoretical (2nd order)')
        ax2.set_ylabel('Convergence Rate')
        ax2.set_title('Observed Convergence Rates')
        ax2.legend()
        
        # Add uncertainty bands
        for i, (var_name, uncertainty) in enumerate(convergence_study.uncertainties.items()):
            if uncertainty > 0:
                ax2.errorbar(i, conv_rates[i], yerr=uncertainty, 
                           fmt='none', color='black', capsize=5)
        
        plt.tight_layout()
        plot_path = output_dir / 'mesh_convergence.png'
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return plot_path