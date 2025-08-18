"""
Publication-Quality Workflow Tasks
==================================

Task implementations for generating publication-quality results
comparable to SimVascular and other commercial CFD packages.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional

try:
    from ..base_task import Task, logger
    from ...aortacfd_lib.hemodynamic_analyzer import HemodynamicAnalyzer
    from ...aortacfd_lib.publication_reporter import PublicationReporter
    from ...aortacfd_lib.quantitative_analysis import QuantitativeAnalyzer
except ImportError:
    from workflow.base_task import Task, logger
    from aortacfd_lib.hemodynamic_analyzer import HemodynamicAnalyzer
    from aortacfd_lib.publication_reporter import PublicationReporter
    from aortacfd_lib.quantitative_analysis import QuantitativeAnalyzer


class PublicationAnalysisTask(Task):
    """
    Comprehensive publication-quality hemodynamic analysis.
    
    This task performs all analyses required for peer-reviewed publication:
    - Wall shear stress analysis (TAWSS, OSI, RRT)
    - Velocity profile analysis
    - Pressure distribution analysis
    - Hemodynamic indices calculation
    - Statistical analysis
    - Validation studies
    """
    
    def execute(self, context: dict) -> bool:
        """Execute comprehensive hemodynamic analysis."""
        try:
            case_dir = context['case_directory']
            self.log.info("Starting publication-quality hemodynamic analysis...")
            
            # Initialize hemodynamic analyzer
            analyzer = HemodynamicAnalyzer(case_dir)
            
            # Perform comprehensive analysis
            results = {
                'wss_analysis': analyzer.analyze_wall_shear_stress(),
                'velocity_analysis': analyzer.analyze_velocity_profiles(),
                'pressure_analysis': analyzer.analyze_pressure_distribution(),
                'hemodynamic_indices': analyzer.calculate_hemodynamic_indices()
            }
            
            # Store results in context for downstream tasks
            context['hemodynamic_analysis_results'] = results
            
            # Generate publication-quality plots
            output_dir = os.path.join(case_dir, 'publication_analysis')
            figures = analyzer.generate_publication_plots(output_dir, dpi=300)
            context['analysis_figures'] = figures
            
            # Export data for further analysis
            exported_data = analyzer.export_publication_data(output_dir)
            context['exported_data'] = exported_data
            
            self.log.info(f"Hemodynamic analysis completed. Results saved to: {output_dir}")
            return True
            
        except Exception as e:
            self.log.error(f"Publication analysis failed: {e}")
            return False


class ValidationStudyTask(Task):
    """
    Comprehensive validation and verification studies.
    
    Performs:
    - Mesh convergence studies
    - Time step convergence studies
    - Experimental validation
    - Literature comparison
    - Uncertainty quantification
    """
    
    def execute(self, context: dict) -> bool:
        """Execute validation studies."""
        try:
            case_dir = context['case_directory']
            self.log.info("Starting validation and verification studies...")
            
            # Initialize quantitative analyzer
            analyzer = QuantitativeAnalyzer([case_dir])
            
            validation_results = {}
            
            # Mesh convergence study (if multiple mesh cases available)
            mesh_cases = self._find_mesh_convergence_cases(case_dir)
            if len(mesh_cases) >= 3:
                self.log.info("Performing mesh convergence study...")
                mesh_study = analyzer.perform_mesh_convergence_study(mesh_cases)
                validation_results['mesh_convergence'] = mesh_study
            else:
                self.log.warning("Insufficient mesh cases for convergence study")
            
            # Time step convergence study (if multiple time step cases available)
            time_cases = self._find_time_convergence_cases(case_dir)
            if len(time_cases) >= 3:
                self.log.info("Performing time step convergence study...")
                time_study = analyzer.perform_time_convergence_study(time_cases)
                validation_results['time_convergence'] = time_study
            else:
                self.log.warning("Insufficient time step cases for convergence study")
            
            # Experimental validation (if experimental data available)
            exp_data_path = os.path.join(case_dir, 'experimental_validation.json')
            if os.path.exists(exp_data_path):
                self.log.info("Performing experimental validation...")
                with open(exp_data_path, 'r') as f:
                    exp_data = json.load(f)
                
                sim_data = self._extract_simulation_data_for_validation(case_dir)
                exp_validation = analyzer.validate_against_experimental_data(sim_data, exp_data)
                validation_results['experimental_validation'] = exp_validation
            
            # Literature comparison
            lit_data_path = os.path.join(case_dir, 'literature_comparison.json')
            if os.path.exists(lit_data_path):
                self.log.info("Performing literature comparison...")
                with open(lit_data_path, 'r') as f:
                    lit_data = json.load(f)
                
                sim_results = context.get('hemodynamic_analysis_results', {})
                indices = sim_results.get('hemodynamic_indices', {})
                lit_comparison = analyzer.compare_with_literature(lit_data, indices)
                validation_results['literature_comparison'] = lit_comparison
            
            # Uncertainty quantification
            uq_config = self.config.get('uncertainty_quantification', {})
            if uq_config.get('enabled', False):
                self.log.info("Performing uncertainty quantification...")
                param_ranges = uq_config.get('parameter_ranges', {})
                n_samples = uq_config.get('n_samples', 100)
                uq_results = analyzer.perform_uncertainty_quantification(param_ranges, n_samples)
                validation_results['uncertainty_quantification'] = uq_results
            
            # Store validation results
            context['validation_results'] = validation_results
            
            # Generate validation plots
            output_dir = os.path.join(case_dir, 'validation_studies')
            convergence_plots = analyzer.generate_convergence_plots(output_dir)
            validation_plots = analyzer.generate_validation_plots(output_dir)
            
            context['validation_figures'] = {**convergence_plots, **validation_plots}
            
            self.log.info(f"Validation studies completed. Results saved to: {output_dir}")
            return True
            
        except Exception as e:
            self.log.error(f"Validation studies failed: {e}")
            return False
    
    def _find_mesh_convergence_cases(self, base_case_dir: str) -> List[str]:
        """Find mesh convergence study cases."""
        base_path = Path(base_case_dir)
        parent_dir = base_path.parent
        case_name = base_path.name
        
        # Look for cases with mesh refinement suffixes
        mesh_cases = []
        for suffix in ['_coarse', '_medium', '_fine', '_extrafine']:
            candidate = parent_dir / f"{case_name}{suffix}"
            if candidate.exists() and candidate.is_dir():
                mesh_cases.append(str(candidate))
        
        return sorted(mesh_cases)
    
    def _find_time_convergence_cases(self, base_case_dir: str) -> List[str]:
        """Find time step convergence study cases."""
        base_path = Path(base_case_dir)
        parent_dir = base_path.parent
        case_name = base_path.name
        
        # Look for cases with time step suffixes
        time_cases = []
        for suffix in ['_dt1', '_dt2', '_dt4', '_dt8']:
            candidate = parent_dir / f"{case_name}{suffix}"
            if candidate.exists() and candidate.is_dir():
                time_cases.append(str(candidate))
        
        return sorted(time_cases)
    
    def _extract_simulation_data_for_validation(self, case_dir: str) -> Dict:
        """Extract simulation data for validation against experiments."""
        # This would extract specific data points corresponding to experimental measurements
        # Implementation depends on the specific experimental setup
        return {
            'velocity_profiles': [],
            'pressure_measurements': [],
            'flow_rates': []
        }


class ManuscriptGenerationTask(Task):
    """
    Generate complete manuscript with figures, tables, and text.
    
    Creates publication-ready documents including:
    - LaTeX manuscript
    - High-resolution figures
    - Statistical tables
    - Supplementary materials
    """
    
    def execute(self, context: dict) -> bool:
        """Generate publication manuscript."""
        try:
            case_dir = context['case_directory']
            self.log.info("Generating publication manuscript...")
            
            # Get study configuration
            study_config = self.config.get('publication', {})
            
            # Initialize publication reporter
            reporter = PublicationReporter(case_dir, study_config)
            
            # Run comprehensive analysis if not already done
            if 'hemodynamic_analysis_results' not in context:
                self.log.info("Running comprehensive analysis for manuscript...")
                reporter.run_comprehensive_analysis()
            
            # Generate manuscript
            journal_style = study_config.get('journal_style', 'nature')
            output_dir = os.path.join(case_dir, 'manuscript_submission')
            
            manuscript_files = reporter.generate_manuscript(
                journal_style=journal_style,
                output_dir=output_dir,
                include_methods=study_config.get('include_methods', True),
                include_validation=study_config.get('include_validation', True)
            )
            
            context['manuscript_files'] = manuscript_files
            
            self.log.info(f"Manuscript generated successfully: {output_dir}")
            return True
            
        except Exception as e:
            self.log.error(f"Manuscript generation failed: {e}")
            return False


class ConferencePresentationTask(Task):
    """Generate conference presentation materials."""
    
    def execute(self, context: dict) -> bool:
        """Generate conference presentation."""
        try:
            case_dir = context['case_directory']
            self.log.info("Generating conference presentation...")
            
            # Get presentation configuration
            presentation_config = self.config.get('presentation', {})
            
            # Initialize publication reporter
            reporter = PublicationReporter(case_dir, presentation_config)
            
            # Generate presentation
            template = presentation_config.get('template', 'modern')
            output_dir = os.path.join(case_dir, 'conference_presentation')
            
            presentation_file = reporter.generate_conference_presentation(
                output_dir=output_dir,
                template=template
            )
            
            context['presentation_file'] = presentation_file
            
            self.log.info(f"Conference presentation generated: {presentation_file}")
            return True
            
        except Exception as e:
            self.log.error(f"Conference presentation generation failed: {e}")
            return False


class ClinicalReportTask(Task):
    """Generate clinical report for healthcare providers."""
    
    def execute(self, context: dict) -> bool:
        """Generate clinical report."""
        try:
            case_dir = context['case_directory']
            self.log.info("Generating clinical report...")
            
            # Get clinical configuration
            clinical_config = self.config.get('clinical', {})
            patient_id = clinical_config.get('patient_id')
            
            # Initialize publication reporter
            reporter = PublicationReporter(case_dir, clinical_config)
            
            # Generate clinical report
            output_dir = os.path.join(case_dir, 'clinical_report')
            
            report_file = reporter.generate_clinical_report(
                patient_id=patient_id,
                output_dir=output_dir
            )
            
            context['clinical_report_file'] = report_file
            
            self.log.info(f"Clinical report generated: {report_file}")
            return True
            
        except Exception as e:
            self.log.error(f"Clinical report generation failed: {e}")
            return False


class StatisticalAnalysisTask(Task):
    """Comprehensive statistical analysis for publication."""
    
    def execute(self, context: dict) -> bool:
        """Execute statistical analysis."""
        try:
            case_dir = context['case_directory']
            self.log.info("Performing comprehensive statistical analysis...")
            
            # Initialize publication reporter
            reporter = PublicationReporter(case_dir, self.config)
            
            # Generate statistical analysis report
            output_dir = os.path.join(case_dir, 'statistical_analysis')
            
            stats_report = reporter.generate_statistical_report(output_dir)
            
            context['statistical_report'] = stats_report
            
            self.log.info(f"Statistical analysis completed: {stats_report}")
            return True
            
        except Exception as e:
            self.log.error(f"Statistical analysis failed: {e}")
            return False