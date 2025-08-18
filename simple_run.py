#!/usr/bin/env python3
"""
AortaCFD Simple Runner - One Command CFD Analysis
================================================

The easiest way to run AortaCFD:
1. Put your STL files in a folder
2. Run: python simple_run.py /path/to/your/files
3. Get results!

That's it! No configuration needed.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
import argparse

# Add src to path - safer approach
src_path = Path(__file__).parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from config.builder import ConfigBuilder
    from workflow.manager import WorkflowManager
    from aortacfd_lib.utils.logger import Logger
    from aortacfd_lib.utils.security import SecurityValidator, ResourceValidator, ConfigurationValidator
except ImportError as e:
    print(f"❌ Critical import error: {e}")
    print(f"   Source path: {src_path}")
    print("   Please ensure the application is properly installed:")
    print("   pip install -r requirements.txt")
    sys.exit(1)


class AortaCFDValidationError(Exception):
    """Raised when input validation fails."""
    pass

class AortaCFDSimulationError(Exception):
    """Raised when simulation execution fails."""
    pass

class AortaCFDConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass

class SimpleRunner:
    """
    Simplified AortaCFD runner - handles everything automatically.
    """
    
    def __init__(self):
        self.logger = Logger("SimpleRunner").get_logger()
        self.security_validator = SecurityValidator()
        self.resource_validator = ResourceValidator()
        self.config_validator = ConfigurationValidator()
        
    def _is_safe_path(self, path: Path) -> bool:
        """Validate that path is safe and doesn't contain malicious components."""
        # Convert to string for analysis
        path_str = str(path)
        
        # Check for path traversal attempts
        dangerous_patterns = ['..', '~', '$', '|', ';', '&', '`']
        if any(pattern in path_str for pattern in dangerous_patterns):
            return False
            
        # Ensure absolute path doesn't escape reasonable bounds
        try:
            # On Unix systems, reject paths that go above /tmp, /home, /opt, or current dir
            allowed_prefixes = ['/tmp', '/home', '/opt', str(Path.cwd())]
            if not any(path_str.startswith(prefix) for prefix in allowed_prefixes):
                # Allow relative paths that resolve to safe locations
                if not path.is_absolute():
                    return True
                return False
        except (OSError, ValueError):
            return False
            
        return True
        
    def run(self, input_folder: str, output_folder: str = None, options: dict = None):
        """
        Run complete CFD analysis with minimal input.
        
        Args:
            input_folder: Folder containing STL files (and optionally flow data CSV)
            output_folder: Where to save results (optional)
            options: Optional configuration overrides
        
        Returns:
            Path to results folder
        """
        print("\n" + "="*60)
        print("🚀 AortaCFD Simple Runner")
        print("="*60)
        
        # Step 1: Validate and prepare input
        print("\n📁 Checking input files...")
        case_data = self._prepare_case(input_folder)
        if not case_data['valid']:
            print(f"❌ Error: {case_data['error']}")
            return None
        
        print(f"✅ Found: {len(case_data['stl_files'])} STL files")
        if case_data.get('flow_data'):
            print(f"✅ Found: Flow data CSV")
        
        # Step 2: Auto-configure
        print("\n⚙️  Auto-configuring simulation...")
        config = self._auto_configure(case_data, options)
        print(f"✅ Configuration: {config['profile_type']} profile")
        print(f"✅ Mesh quality: {config['mesh_quality']}")
        
        # Step 3: Run simulation
        print("\n🔄 Running CFD simulation...")
        print("This may take 10-30 minutes depending on your system...")
        
        try:
            self._run_simulation(config)
        except AortaCFDSimulationError as e:
            print(f"\n❌ Simulation failed: {e}")
            self.logger.error(f"Simulation error: {e}")
            return None
        except AortaCFDConfigurationError as e:
            print(f"\n❌ Configuration error: {e}")
            self.logger.error(f"Configuration error: {e}")
            return None
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            self.logger.error(f"Unexpected error: {e}")
            return None
        
        # Step 4: Generate results
        print("\n📊 Generating results...")
        results_path = self._generate_results(config, output_folder)
        
        print("\n" + "="*60)
        print("✅ SIMULATION COMPLETE!")
        print("="*60)
        print(f"\n📁 Results saved to: {results_path}")
        print(f"📊 Open report: {results_path}/simulation_report.html")
        print(f"📈 Figures: {results_path}/figures/")
        print(f"📦 Data: {results_path}/data/")
        
        return results_path
    
    def _prepare_case(self, input_folder: str) -> dict:
        """Prepare case from input folder with validation."""
        # Validate and sanitize input path
        try:
            input_path = Path(input_folder).resolve()
        except (OSError, ValueError) as e:
            return {'valid': False, 'error': f"Invalid path: {e}"}
        
        # Security check: ensure path is not trying to escape expected bounds
        if not self.security_validator.validate_directory_path(input_path):
            return {'valid': False, 'error': "Path contains unsafe components"}
        
        if not input_path.exists():
            return {'valid': False, 'error': f"Folder not found: {input_folder}"}
        
        if not input_path.is_dir():
            return {'valid': False, 'error': f"Path is not a directory: {input_folder}"}
        
        # Find and validate files
        stl_files = list(input_path.glob('*.stl')) + list(input_path.glob('*.STL'))
        csv_files = list(input_path.glob('*.csv')) + list(input_path.glob('*.CSV'))
        
        if not stl_files:
            return {'valid': False, 'error': "No STL files found in folder"}
        
        # Validate STL files
        valid_stl_files = []
        for stl_file in stl_files:
            if self.security_validator.validate_file_path(stl_file, ['.stl', '.STL']):
                valid_stl_files.append(stl_file)
            else:
                print(f"⚠️  Skipping potentially unsafe STL file: {stl_file.name}")
        
        if not valid_stl_files:
            return {'valid': False, 'error': "No valid STL files found (failed security validation)"}
        
        stl_files = valid_stl_files
        
        # Auto-classify STL files
        classified = self._classify_stl_files(stl_files)
        
        if not classified.get('inlet'):
            return {'valid': False, 'error': "Could not identify inlet STL file"}
        
        if not classified.get('wall'):
            return {'valid': False, 'error': "Could not identify wall/aorta STL file"}
        
        # Create case directory
        case_name = f"case_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        case_dir = Path('cases_input') / case_name
        case_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy files with proper naming
        for file_type, source_path in classified.items():
            if file_type == 'wall':
                dest_name = 'wall_aorta.stl'
            else:
                dest_name = f"{file_type}.stl"
            
            dest_path = case_dir / dest_name
            shutil.copy2(source_path, dest_path)
        
        # Handle flow data
        flow_data = None
        if csv_files:
            flow_source = csv_files[0]
            flow_dest = case_dir / 'flow_data.csv'
            shutil.copy2(flow_source, flow_dest)
            flow_data = str(flow_dest)
        else:
            # Generate default flow data
            self._generate_default_flow(case_dir)
            flow_data = str(case_dir / 'flow_data.csv')
        
        # Create boundary conditions
        self._create_boundary_conditions(case_dir, len(classified.get('outlets', [])))
        
        return {
            'valid': True,
            'case_name': case_name,
            'case_dir': str(case_dir),
            'stl_files': classified,
            'flow_data': flow_data
        }
    
    def _classify_stl_files(self, stl_files: list) -> dict:
        """Auto-classify STL files based on naming."""
        classified = {'outlets': []}
        
        for stl_file in stl_files:
            name = stl_file.stem.lower()
            
            # Detect inlet
            if any(word in name for word in ['inlet', 'inflow', 'root', 'ascending']):
                classified['inlet'] = stl_file
            # Detect wall
            elif any(word in name for word in ['wall', 'aorta', 'vessel', 'surface']):
                classified['wall'] = stl_file
            # Detect outlets
            elif any(word in name for word in ['outlet', 'outflow', 'branch']):
                classified['outlets'].append(stl_file)
            # Unknown - classify by size
            else:
                size = stl_file.stat().st_size
                if size > 500_000:  # Likely wall
                    if 'wall' not in classified:
                        classified['wall'] = stl_file
                else:  # Likely inlet/outlet
                    if 'inlet' not in classified:
                        classified['inlet'] = stl_file
                    else:
                        classified['outlets'].append(stl_file)
        
        # Number outlets
        numbered_outlets = {}
        for i, outlet in enumerate(classified.get('outlets', []), 1):
            numbered_outlets[f'outlet{i}'] = outlet
        
        classified.update(numbered_outlets)
        del classified['outlets']
        
        return classified
    
    def _auto_configure(self, case_data: dict, options: dict = None) -> dict:
        """Automatically configure simulation with resource validation."""
        # Check system resources
        resources = self.resource_validator.check_system_resources()
        
        if not resources.get('system_ready', False):
            if 'error' in resources:
                raise AortaCFDConfigurationError(f"Cannot check system resources: {resources['error']}")
            else:
                warnings = []
                if not resources.get('memory_sufficient', True):
                    warnings.append(f"Low memory: {resources.get('memory_available_gb', 0):.1f}GB available")
                if not resources.get('disk_sufficient', True):
                    warnings.append(f"Low disk space: {resources.get('disk_free_gb', 0):.1f}GB available")
                
                print(f"⚠️  System resource warnings: {'; '.join(warnings)}")
                print("   Proceeding with conservative settings...")
        
        # Get resource values
        cpu_count = resources.get('cpu_count', 1)
        memory_gb = resources.get('memory_available_gb', 2.0)
        
        # Choose profile based on resources
        if memory_gb < 4:
            profile = 'sim_laminar_coarse'
            mesh_quality = 'coarse'
        elif memory_gb < 8:
            profile = 'sim_laminar_coarse'
            mesh_quality = 'medium'
        elif memory_gb < 16:
            profile = 'sim_laminar_fine'
            mesh_quality = 'fine'
        else:
            profile = 'sim_laminar_fine'
            mesh_quality = 'high'
        
        # Override with user options
        if options:
            profile = options.get('profile', profile)
            mesh_quality = options.get('quality', mesh_quality)
        
        # Build configuration
        builder = ConfigBuilder()
        config = builder.build(
            case_name=case_data['case_name'],
            sim_profile_name=profile
        )
        
        # Validate configuration
        validation_result = self.config_validator.validate_simulation_config(config)
        if not validation_result['valid']:
            raise AortaCFDConfigurationError(f"Invalid configuration: {validation_result['errors']}")
        
        if validation_result['warnings']:
            for warning in validation_result['warnings']:
                print(f"⚠️  Configuration warning: {warning}")
        
        # Add metadata
        config['profile_type'] = profile
        config['mesh_quality'] = mesh_quality
        config['system_info'] = {
            'cpu_cores': cpu_count,
            'memory_gb': memory_gb,
            'resources': resources
        }
        
        # Optimize for system
        if cpu_count >= 4:
            config['mesh']['SNAPPY_SETTINGS']['parallel'] = True
            config['mesh']['SNAPPY_SETTINGS']['nProcessors'] = min(cpu_count - 1, 8)
        
        return config
    
    def _run_simulation(self, config: dict) -> bool:
        """Run the CFD simulation with proper error handling."""
        try:
            manager = WorkflowManager(config)
            
            # Define simple workflow
            tasks = [
                'CreateCaseStructureTask',
                'GenerateMeshDictTask',
                'PrepareBoundaryConditionsTask',
                'GeneratePhysicalPropsTask',
                'GenerateNumericsDictTask', 
                'GenerateSolverDictTask',
                'GenerateControlDictTask',
                'RunMeshingTask',
                'RunSolverTask'
            ]
            
            for i, task in enumerate(tasks, 1):
                print(f"  [{i}/{len(tasks)}] {task}...")
                try:
                    success = manager.run_single_task(task)
                    if not success:
                        raise AortaCFDSimulationError(f"Task failed: {task}")
                except Exception as e:
                    self.logger.error(f"Task {task} failed: {e}")
                    raise AortaCFDSimulationError(f"Failed at: {task} - {e}")
            
            if 'case_directory' not in manager.context:
                raise AortaCFDSimulationError("No case directory created")
                
            config['output_directory'] = manager.context['case_directory']
            return True
            
        except AortaCFDSimulationError:
            raise
        except ImportError as e:
            raise AortaCFDConfigurationError(f"Missing dependencies: {e}")
        except KeyError as e:
            raise AortaCFDConfigurationError(f"Invalid configuration: missing {e}")
        except (OSError, IOError) as e:
            raise AortaCFDSimulationError(f"File system error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in simulation: {e}")
            raise AortaCFDSimulationError(f"Unexpected simulation error: {e}")
    
    def _generate_results(self, config: dict, output_folder: str = None) -> str:
        """Generate results and reports."""
        case_dir = config.get('output_directory')
        
        if not case_dir:
            return None
        
        # Create results directory
        if output_folder:
            results_dir = Path(output_folder) / config['geometry']['case_name']
        else:
            results_dir = Path('results') / config['geometry']['case_name']
        
        results_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate report
        try:
            from aortacfd_lib.simulation_reporter import create_simulation_report
            report_path = create_simulation_report(case_dir, str(results_dir))
            
            # Copy key files to results
            shutil.copytree(
                Path(case_dir) / 'postProcessing',
                results_dir / 'data',
                dirs_exist_ok=True
            )
            
            # Create summary file
            summary = {
                'case_name': config['geometry']['case_name'],
                'profile': config['profile_type'],
                'mesh_quality': config['mesh_quality'],
                'simulation_time': datetime.now().isoformat(),
                'case_directory': str(case_dir),
                'report': str(report_path)
            }
            
            with open(results_dir / 'summary.json', 'w') as f:
                json.dump(summary, f, indent=2)
                
        except Exception as e:
            print(f"⚠️  Warning: Could not generate full report: {e}")
        
        return str(results_dir)
    
    def _generate_default_flow(self, case_dir: Path):
        """Generate physiologically realistic default flow data."""
        import numpy as np
        
        # Cardiac cycle: 0.8 seconds (75 BPM)
        time = np.linspace(0, 0.8, 100)
        
        # Realistic aortic flow waveform
        flow = 90 + 260 * np.sin(2 * np.pi * time / 0.8) * np.exp(-5 * time / 0.8)
        flow[flow < 20] = 20
        
        # Save as CSV
        with open(case_dir / 'flow_data.csv', 'w') as f:
            f.write("Time[s],Flow[ml/s]\n")
            for t, q in zip(time, flow):
                f.write(f"{t:.4f},{q:.2f}\n")
    
    def _create_boundary_conditions(self, case_dir: Path, num_outlets: int):
        """Create automatic boundary conditions."""
        # Note: num_outlets parameter available for future outlet-specific logic
        bc = {
            "inlet": {
                "type": "TIMEVARYING",
                "csv_file": "flow_data.csv",
                "data_type": "flow_rate",
                "profile": "plug_flow"
            },
            "outlets": {
                "type": "3EWINDKESSEL",
                "windkessel_settings": {
                    "systolic_pressure": 120,
                    "diastolic_pressure": 80,
                    "methodology": "murray_law_automatic"
                }
            }
        }
        
        with open(case_dir / 'boundary_conditions.json', 'w') as f:
            json.dump(bc, f, indent=2)


def main():
    """Main entry point for simple runner."""
    parser = argparse.ArgumentParser(
        description="AortaCFD Simple Runner - The easiest way to run CFD simulations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
    
    # Simplest usage - just point to your STL files:
    python simple_run.py /path/to/stl/files
    
    # Specify output location:
    python simple_run.py /path/to/stl/files --output /path/to/results
    
    # Choose quality level:
    python simple_run.py /path/to/stl/files --quality high
    
    # Quick test run:
    python simple_run.py /path/to/stl/files --quality coarse --quick

FILE NAMING:
    For automatic detection, name your STL files with these keywords:
    - Inlet: 'inlet', 'inflow', 'root'
    - Wall: 'wall', 'aorta', 'vessel'
    - Outlets: 'outlet', 'outflow', 'branch'
    
    Example: inlet.stl, wall_aorta.stl, outlet1.stl, outlet2.stl

FLOW DATA:
    Include a CSV file with columns: Time[s], Flow[ml/s]
    If not provided, physiologically realistic flow will be generated.
        """
    )
    
    parser.add_argument('input_folder',
                       help='Folder containing your STL files')
    parser.add_argument('--output', '-o',
                       help='Output folder for results (default: ./results/)')
    parser.add_argument('--quality', '-q',
                       choices=['coarse', 'medium', 'fine', 'high'],
                       default='auto',
                       help='Mesh quality (default: auto-detect based on system)')
    parser.add_argument('--quick',
                       action='store_true',
                       help='Quick test run with minimal settings')
    
    args = parser.parse_args()
    
    # Prepare options
    options = {}
    if args.quality != 'auto':
        quality_map = {
            'coarse': 'sim_laminar_coarse',
            'medium': 'sim_laminar_coarse',
            'fine': 'sim_laminar_fine',
            'high': 'sim_laminar_fine'
        }
        options['profile'] = quality_map[args.quality]
        options['quality'] = args.quality
    
    if args.quick:
        options['profile'] = 'sim_laminar_coarse'
        options['quality'] = 'coarse'
    
    # Run simulation
    runner = SimpleRunner()
    results = runner.run(
        input_folder=args.input_folder,
        output_folder=args.output,
        options=options
    )
    
    if results:
        print("\n✅ Success! Your results are ready.")
        print(f"📊 View report: file://{Path(results).absolute()}/simulation_report.html")
        sys.exit(0)
    else:
        print("\n❌ Simulation failed. Check the logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()