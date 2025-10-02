"""
Publication-Quality Report Generator
===================================

Creates comprehensive, publication-ready reports with:
- IEEE/Nature/Elsevier journal formatting
- Statistical analysis and validation
- High-quality figures and tables
- LaTeX and Word-compatible outputs
- Automated literature citations
"""

import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import rcParams
import seaborn as sns
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Union
from jinja2 import Template, Environment, FileSystemLoader
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

from .hemodynamic_analyzer import HemodynamicAnalyzer
from .utils.logger import Logger

logger = Logger("publication_reporter").get_logger()

# Publication formatting settings
JOURNAL_STYLES = {
    'nature': {
        'figure_width': 3.5,  # inches (single column)
        'figure_width_double': 7.0,  # inches (double column)
        'font_family': 'Arial',
        'font_size': 8,
        'dpi': 300,
        'format': 'png'
    },
    'ieee': {
        'figure_width': 3.5,
        'figure_width_double': 7.0,
        'font_family': 'Times New Roman',
        'font_size': 8,
        'dpi': 600,
        'format': 'eps'
    },
    'elsevier': {
        'figure_width': 3.5,
        'figure_width_double': 7.16,
        'font_family': 'Times New Roman',
        'font_size': 10,
        'dpi': 300,
        'format': 'tiff'
    }
}


class PublicationReporter:
    """
    Generate publication-quality reports and manuscripts.
    
    This class creates comprehensive reports suitable for:
    - Peer-reviewed journal submissions
    - Conference presentations
    - Clinical research documentation
    - Grant applications
    """
    
    def __init__(self, case_directory: str, study_config: Dict = None):
        """
        Initialize publication reporter.
        
        Args:
            case_directory: Path to simulation case
            study_config: Study metadata and configuration
        """
        self.case_dir = Path(case_directory)
        self.study_config = study_config or {}
        self.log = logger
        
        # Initialize hemodynamic analyzer
        self.hemodynamic_analyzer = HemodynamicAnalyzer(case_directory)
        
        # Results storage
        self.analysis_results = {}
        self.figures = {}
        self.tables = {}
        
        # Study metadata
        self.study_metadata = {
            'title': self.study_config.get('title', 'Patient-Specific Aortic Flow Analysis'),
            'authors': self.study_config.get('authors', ['Author Name']),
            'institution': self.study_config.get('institution', 'Research Institution'),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'case_id': self.case_dir.name
        }
        
        logger.info(f"Initialized publication reporter for: {self.study_metadata['title']}")
    
    def run_comprehensive_analysis(self) -> Dict:
        """
        Run complete hemodynamic analysis for publication.
        
        Returns:
            Dictionary with all analysis results
        """
        logger.info("Running comprehensive hemodynamic analysis...")
        
        # Wall shear stress analysis
        self.analysis_results['wss'] = self.hemodynamic_analyzer.analyze_wall_shear_stress()
        
        # Velocity profile analysis
        self.analysis_results['velocity'] = self.hemodynamic_analyzer.analyze_velocity_profiles()
        
        # Pressure analysis
        self.analysis_results['pressure'] = self.hemodynamic_analyzer.analyze_pressure_distribution()
        
        # Hemodynamic indices
        self.analysis_results['indices'] = self.hemodynamic_analyzer.calculate_hemodynamic_indices()
        
        # Statistical analysis
        self.analysis_results['statistics'] = self._perform_statistical_analysis()
        
        # Validation metrics
        self.analysis_results['validation'] = self._calculate_validation_metrics()
        
        logger.info("Comprehensive analysis completed")
        return self.analysis_results
    
    def generate_manuscript(self, 
                          journal_style: str = 'nature',
                          output_dir: str = None,
                          include_methods: bool = True,
                          include_validation: bool = True) -> Dict[str, str]:
        """
        Generate complete manuscript with figures and tables.
        
        Args:
            journal_style: Target journal formatting ('nature', 'ieee', 'elsevier')
            output_dir: Output directory for manuscript files
            include_methods: Whether to include detailed methods section
            include_validation: Whether to include validation studies
        
        Returns:
            Dictionary with paths to generated files
        """
        if output_dir is None:
            output_dir = f"publication_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Set journal style
        style_config = JOURNAL_STYLES.get(journal_style, JOURNAL_STYLES['nature'])
        self._configure_matplotlib_style(style_config)
        
        logger.info(f"Generating manuscript in {journal_style} style...")
        
        # Generate figures
        figures_dir = output_path / 'figures'
        self.figures = self._generate_publication_figures(figures_dir, style_config)
        
        # Generate tables
        tables_dir = output_path / 'tables'
        self.tables = self._generate_publication_tables(tables_dir)
        
        # Generate manuscript text
        manuscript_files = self._generate_manuscript_text(
            output_path, 
            include_methods, 
            include_validation
        )
        
        # Generate supplementary materials
        supp_files = self._generate_supplementary_materials(output_path / 'supplementary')
        
        # Create submission package
        submission_package = {
            'manuscript': manuscript_files,
            'figures': self.figures,
            'tables': self.tables,
            'supplementary': supp_files,
            'metadata': str(output_path / 'submission_metadata.json')
        }
        
        # Save submission metadata
        with open(output_path / 'submission_metadata.json', 'w') as f:
            json.dump({
                'study_metadata': self.study_metadata,
                'analysis_summary': self._generate_analysis_summary(),
                'file_manifest': submission_package
            }, f, indent=2, default=str)
        
        logger.info(f"Manuscript generation completed: {output_path}")
        return submission_package
    
    def generate_conference_presentation(self, 
                                       output_dir: str = None,
                                       template: str = 'modern') -> str:
        """
        Generate conference presentation slides.
        
        Args:
            output_dir: Output directory
            template: Presentation template style
        
        Returns:
            Path to generated presentation
        """
        if output_dir is None:
            output_dir = f"presentation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate presentation-quality figures
        figures_dir = output_path / 'figures'
        presentation_figures = self._generate_presentation_figures(figures_dir)
        
        # Generate slides
        slides_file = self._generate_presentation_slides(output_path, presentation_figures, template)
        
        logger.info(f"Conference presentation generated: {slides_file}")
        return str(slides_file)
    
    def generate_clinical_report(self, 
                               patient_id: str = None,
                               output_dir: str = None) -> str:
        """
        Generate clinical report for healthcare providers.
        
        Args:
            patient_id: Patient identifier
            output_dir: Output directory
        
        Returns:
            Path to clinical report
        """
        if output_dir is None:
            output_dir = f"clinical_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate clinical summary
        clinical_summary = self._generate_clinical_summary(patient_id)
        
        # Generate clinical figures
        clinical_figures = self._generate_clinical_figures(output_path / 'figures')
        
        # Generate clinical report
        report_file = self._generate_clinical_report_document(
            output_path, 
            clinical_summary, 
            clinical_figures
        )
        
        logger.info(f"Clinical report generated: {report_file}")
        return str(report_file)
    
    def _perform_statistical_analysis(self) -> Dict:
        """Perform comprehensive statistical analysis."""
        logger.info("Performing statistical analysis...")
        
        stats_results = {
            'descriptive_statistics': {},
            'hypothesis_tests': {},
            'confidence_intervals': {},
            'effect_sizes': {}
        }
        
        # Extract numerical data for analysis
        wss_data = self.analysis_results.get('wss', {})
        velocity_data = self.analysis_results.get('velocity', {})
        pressure_data = self.analysis_results.get('pressure', {})
        
        # Descriptive statistics for WSS
        if wss_data:
            for patch_name, patch_data in wss_data.get('patches', {}).items():
                tawss = patch_data.get('tawss', [])
                if len(tawss) > 0:
                    stats_results['descriptive_statistics'][f'{patch_name}_tawss'] = {
                        'mean': np.mean(tawss),
                        'std': np.std(tawss),
                        'median': np.median(tawss),
                        'q25': np.percentile(tawss, 25),
                        'q75': np.percentile(tawss, 75),
                        'min': np.min(tawss),
                        'max': np.max(tawss)
                    }
        
        # Statistical tests
        stats_results['hypothesis_tests'] = self._perform_hypothesis_tests()
        
        # Confidence intervals
        stats_results['confidence_intervals'] = self._calculate_confidence_intervals()
        
        return stats_results
    
    def _calculate_validation_metrics(self) -> Dict:
        """Calculate validation and verification metrics."""
        logger.info("Calculating validation metrics...")
        
        validation_results = {
            'mesh_independence': self._check_mesh_independence(),
            'time_step_independence': self._check_time_step_independence(),
            'convergence_metrics': self._calculate_convergence_metrics(),
            'mass_conservation': self._check_mass_conservation(),
            'energy_conservation': self._check_energy_conservation(),
            'literature_comparison': self._compare_with_literature()
        }
        
        return validation_results
    
    def _generate_publication_figures(self, output_dir: Path, style_config: Dict) -> Dict[str, str]:
        """Generate all publication-quality figures."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        figures = {}
        
        # Figure 1: Geometry and mesh
        fig1_path = self._create_geometry_mesh_figure(output_dir, style_config)
        figures['geometry_mesh'] = str(fig1_path)
        
        # Figure 2: WSS analysis
        fig2_path = self._create_wss_analysis_figure(output_dir, style_config)
        figures['wss_analysis'] = str(fig2_path)
        
        # Figure 3: Velocity profiles
        fig3_path = self._create_velocity_figure(output_dir, style_config)
        figures['velocity_profiles'] = str(fig3_path)
        
        # Figure 4: Pressure distribution
        fig4_path = self._create_pressure_figure(output_dir, style_config)
        figures['pressure_distribution'] = str(fig4_path)
        
        # Figure 5: Hemodynamic indices
        fig5_path = self._create_indices_figure(output_dir, style_config)
        figures['hemodynamic_indices'] = str(fig5_path)
        
        # Figure 6: Validation results
        fig6_path = self._create_validation_figure(output_dir, style_config)
        figures['validation'] = str(fig6_path)
        
        return figures
    
    def _generate_publication_tables(self, output_dir: Path) -> Dict[str, str]:
        """Generate publication-quality tables."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        tables = {}
        
        # Table 1: Simulation parameters
        table1_path = self._create_simulation_parameters_table(output_dir)
        tables['simulation_parameters'] = str(table1_path)
        
        # Table 2: Hemodynamic indices
        table2_path = self._create_hemodynamic_indices_table(output_dir)
        tables['hemodynamic_indices'] = str(table2_path)
        
        # Table 3: Statistical analysis
        table3_path = self._create_statistical_analysis_table(output_dir)
        tables['statistical_analysis'] = str(table3_path)
        
        # Table 4: Validation metrics
        table4_path = self._create_validation_metrics_table(output_dir)
        tables['validation_metrics'] = str(table4_path)
        
        return tables
    
    def _generate_manuscript_text(self, 
                                output_dir: Path,
                                include_methods: bool,
                                include_validation: bool) -> Dict[str, str]:
        """Generate manuscript text sections."""
        
        # Load manuscript templates
        template_dir = Path(__file__).parent / 'templates' / 'manuscript'
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        
        manuscript_files = {}
        
        # Abstract
        abstract_template = env.get_template('abstract.tex')
        abstract_content = abstract_template.render(
            study_metadata=self.study_metadata,
            analysis_results=self.analysis_results
        )
        abstract_file = output_dir / 'abstract.tex'
        with open(abstract_file, 'w') as f:
            f.write(abstract_content)
        manuscript_files['abstract'] = str(abstract_file)
        
        # Introduction
        intro_template = env.get_template('introduction.tex')
        intro_content = intro_template.render(
            study_metadata=self.study_metadata
        )
        intro_file = output_dir / 'introduction.tex'
        with open(intro_file, 'w') as f:
            f.write(intro_content)
        manuscript_files['introduction'] = str(intro_file)
        
        # Methods
        if include_methods:
            methods_template = env.get_template('methods.tex')
            methods_content = methods_template.render(
                study_metadata=self.study_metadata,
                simulation_config=self.study_config
            )
            methods_file = output_dir / 'methods.tex'
            with open(methods_file, 'w') as f:
                f.write(methods_content)
            manuscript_files['methods'] = str(methods_file)
        
        # Results
        results_template = env.get_template('results.tex')
        results_content = results_template.render(
            analysis_results=self.analysis_results,
            figures=self.figures,
            tables=self.tables
        )
        results_file = output_dir / 'results.tex'
        with open(results_file, 'w') as f:
            f.write(results_content)
        manuscript_files['results'] = str(results_file)
        
        # Discussion
        discussion_template = env.get_template('discussion.tex')
        discussion_content = discussion_template.render(
            analysis_results=self.analysis_results,
            validation_results=self.analysis_results.get('validation', {})
        )
        discussion_file = output_dir / 'discussion.tex'
        with open(discussion_file, 'w') as f:
            f.write(discussion_content)
        manuscript_files['discussion'] = str(discussion_file)
        
        # Main manuscript file
        main_template = env.get_template('main.tex')
        main_content = main_template.render(
            study_metadata=self.study_metadata,
            manuscript_files=manuscript_files,
            include_methods=include_methods,
            include_validation=include_validation
        )
        main_file = output_dir / 'manuscript.tex'
        with open(main_file, 'w') as f:
            f.write(main_content)
        manuscript_files['main'] = str(main_file)
        
        return manuscript_files
    
    def _configure_matplotlib_style(self, style_config: Dict):
        """Configure matplotlib for publication-quality figures."""
        plt.style.use('default')
        
        rcParams.update({
            'font.family': style_config['font_family'],
            'font.size': style_config['font_size'],
            'axes.linewidth': 0.5,
            'axes.labelsize': style_config['font_size'],
            'axes.titlesize': style_config['font_size'] + 1,
            'xtick.labelsize': style_config['font_size'] - 1,
            'ytick.labelsize': style_config['font_size'] - 1,
            'legend.fontsize': style_config['font_size'] - 1,
            'figure.titlesize': style_config['font_size'] + 2,
            'lines.linewidth': 1.0,
            'patch.linewidth': 0.5,
            'figure.dpi': 100,
            'savefig.dpi': style_config['dpi'],
            'savefig.format': style_config['format'],
            'savefig.bbox': 'tight',
            'savefig.pad_inches': 0.05
        })
    
    def _generate_analysis_summary(self) -> Dict:
        """Generate executive summary of analysis results."""
        summary = {
            'case_information': {
                'case_id': self.study_metadata['case_id'],
                'analysis_date': self.study_metadata['date'],
                'total_time_steps': len(self.hemodynamic_analyzer.time_steps or []),
            },
            'key_findings': {},
            'clinical_significance': {},
            'recommendations': []
        }
        
        # Extract key findings from analysis results
        if 'wss' in self.analysis_results:
            wss_data = self.analysis_results['wss']
            summary['key_findings']['max_wss'] = self._extract_max_wss(wss_data)
            summary['key_findings']['avg_wss'] = self._extract_avg_wss(wss_data)
        
        if 'indices' in self.analysis_results:
            indices = self.analysis_results['indices']
            summary['key_findings']['reynolds_number'] = indices.get('reynolds_number')
            summary['key_findings']['womersley_number'] = indices.get('womersley_number')
        
        return summary
    
    def _create_wss_analysis_figure(self, output_dir: Path, style_config: Dict) -> Path:
        """Create comprehensive WSS analysis figure."""
        fig = plt.figure(figsize=(style_config['figure_width_double'], 8))
        
        # Create subplot layout
        gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)
        
        # TAWSS distribution
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.set_title('A) TAWSS Distribution', fontweight='bold', loc='left')
        ax1.set_xlabel('Position (mm)')
        ax1.set_ylabel('TAWSS (Pa)')
        
        # OSI distribution
        ax2 = fig.add_subplot(gs[0, 1])
        ax2.set_title('B) OSI Distribution', fontweight='bold', loc='left')
        ax2.set_xlabel('Position (mm)')
        ax2.set_ylabel('OSI')
        
        # RRT distribution
        ax3 = fig.add_subplot(gs[0, 2])
        ax3.set_title('C) RRT Distribution', fontweight='bold', loc='left')
        ax3.set_xlabel('Position (mm)')
        ax3.set_ylabel('RRT (Pa⁻¹)')
        
        # WSS temporal variation
        ax4 = fig.add_subplot(gs[1, :])
        ax4.set_title('D) WSS Temporal Variation at Key Locations', fontweight='bold', loc='left')
        ax4.set_xlabel('Time (s)')
        ax4.set_ylabel('WSS (Pa)')
        
        # Add sample data visualization (replace with actual data)
        x = np.linspace(0, 100, 100)
        ax1.plot(x, np.sin(x/10) + 2, 'b-', linewidth=1.5)
        ax2.plot(x, 0.1 * np.sin(x/5) + 0.2, 'r-', linewidth=1.5)
        ax3.plot(x, np.exp(-x/50) + 0.1, 'g-', linewidth=1.5)
        
        t = np.linspace(0, 0.8, 100)
        ax4.plot(t, np.sin(2*np.pi*t) + 2, 'b-', label='Inlet', linewidth=1.5)
        ax4.plot(t, 0.8*np.sin(2*np.pi*t) + 1.5, 'r-', label='Stenosis', linewidth=1.5)
        ax4.legend()
        
        fig_path = output_dir / f'wss_analysis.{style_config["format"]}'
        plt.savefig(fig_path, dpi=style_config['dpi'], bbox_inches='tight')
        plt.close()
        
        return fig_path
    
    def generate_statistical_report(self, output_dir: str = None) -> str:
        """
        Generate comprehensive statistical analysis report.
        
        Args:
            output_dir: Output directory for statistical report
        
        Returns:
            Path to statistical report
        """
        if output_dir is None:
            output_dir = f"statistical_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Perform comprehensive statistical analysis
        stats_results = self._perform_detailed_statistical_analysis()
        
        # Generate statistical plots
        stats_figures = self._generate_statistical_figures(output_path / 'figures')
        
        # Generate statistical tables
        stats_tables = self._generate_statistical_tables(output_path / 'tables')
        
        # Generate statistical report document
        report_file = self._generate_statistical_report_document(
            output_path,
            stats_results,
            stats_figures,
            stats_tables
        )
        
        logger.info(f"Statistical analysis report generated: {report_file}")
        return str(report_file)