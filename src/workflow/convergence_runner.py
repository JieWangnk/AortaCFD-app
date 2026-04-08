"""
Mesh Convergence Study Runner

Automates rigorous mesh convergence analysis using Richardson extrapolation
and Grid Convergence Index (GCI) methodology for patient-specific aortic CFD.

Features:
- Three systematically refined meshes (coarse → medium → fine)
- Automatic mapFields transfer between mesh levels
- Richardson extrapolation for mesh-independent solution
- GCI computation for uncertainty quantification
- Publication-ready convergence report

References:
- Roache, P.J. (1997). Quantification of Uncertainty in Computational Fluid Dynamics.
  Annual Review of Fluid Mechanics, 29, 123-160.
- Celik, I.B. et al. (2008). Procedure for Estimation and Reporting of Uncertainty
  Due to Discretization in CFD Applications. ASME J. Fluids Eng., 130(7).
"""

import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import sys

# Add src to path
src_path = str(Path(__file__).parent.parent)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from workflow.manager import WorkflowManager
from aortacfd_lib.utils.logger import Logger
from config.builder import ConfigBuilder, deep_merge


class ConvergenceStudyError(Exception):
    """Raised when convergence study encounters an error."""
    pass


class MeshConvergenceRunner:
    """
    Orchestrates automated mesh convergence studies using systematic refinement
    and formal uncertainty quantification.

    Workflow:
    1. Generate three meshes with constant refinement ratio (r=sqrt(2) or 2)
    2. Run coarse mesh to steady/quasi-steady state
    3. Map solution to medium mesh via mapFields, continue to convergence
    4. Map medium to fine mesh, continue to convergence
    5. Extract quantities of interest (pressure drop, WSS, flow metrics)
    6. Compute observed order of accuracy (p)
    7. Calculate Richardson extrapolated "exact" value
    8. Compute Grid Convergence Index (GCI) for medium and fine meshes
    9. Generate publication report with convergence metrics
    """

    def __init__(self, base_config_path: str):
        """
        Initialize convergence study runner.

        Args:
            base_config_path: Path to base configuration file
        """
        self.logger = Logger("MeshConvergence").get_logger()
        self.base_config_path = Path(base_config_path)

        if not self.base_config_path.exists():
            raise ConvergenceStudyError(f"Config file not found: {base_config_path}")

        # Load base configuration
        with open(self.base_config_path, 'r') as f:
            self.base_config = json.load(f)

        # Determine patient case directory (where STL files are located)
        # If config is in cases_input/patientX/config.json, use patientX
        # Otherwise use the patient_id from config
        if 'cases_input' in str(self.base_config_path):
            self.patient_case_dir = self.base_config_path.parent.name
        else:
            self.patient_case_dir = self.base_config.get('case_info', {}).get('patient_id', 'unknown')

        self.logger.info(f"Patient case directory: cases_input/{self.patient_case_dir}")

        # Validate convergence study requirements
        self._validate_config()

        # Setup directories
        self.output_dir = Path('output') / 'mesh_convergence' / self._get_study_id()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"✨ Mesh Convergence Study initialized")
        self.logger.info(f"📁 Output directory: {self.output_dir}")

    def _validate_config(self):
        """Validate that config is suitable for convergence study."""
        # Check for steady or quasi-steady setup
        bc_inlet = self.base_config.get('boundary_conditions', {}).get('inlet', {})
        inlet_type = bc_inlet.get('type', '').upper()

        if inlet_type == 'TIMEVARYING':
            self.logger.warning(
                "⚠️  Time-varying inlet detected. Convergence study will run multiple cycles.\n"
                "   Consider using CONSTANT inlet for pure mesh convergence (steady state)."
            )

        # Warn if already specifies mesh resolution
        if 'mesh' in self.base_config:
            mesh_cfg = self.base_config['mesh']
            has_resolution = any(key in mesh_cfg for key in [
                'cells_per_diameter', 'target_cell_size_mm', 'resolution_level'
            ])
            if has_resolution:
                self.logger.warning(
                    "⚠️  Mesh resolution specified in base config will be OVERRIDDEN\n"
                    "   by convergence study refinement levels."
                )

    def _get_study_id(self) -> str:
        """Generate unique study identifier."""
        patient_id = self.base_config.get('case_info', {}).get('patient_id', 'unknown')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{patient_id}_{timestamp}"

    def run_convergence_study(self,
                             refinement_ratio: float = 1.414,  # sqrt(2)
                             base_cells_per_diameter: int = 10,
                             steady_state: bool = True) -> Dict:
        """
        Execute complete mesh convergence study.

        Args:
            refinement_ratio: Ratio between successive mesh levels (default: √2 ≈ 1.414)
            base_cells_per_diameter: Coarsest mesh resolution (default: 10)
            steady_state: Use steady BC for pure mesh convergence (default: True)

        Returns:
            Dictionary containing convergence metrics and file paths
        """
        self.logger.info("=" * 70)
        self.logger.info("MESH CONVERGENCE STUDY")
        self.logger.info("=" * 70)
        self.logger.info(f"Refinement ratio: r = {refinement_ratio:.3f}")
        self.logger.info(f"Base resolution: {base_cells_per_diameter} cells/diameter")
        self.logger.info(f"Steady state mode: {steady_state}")
        self.logger.info("")

        # Step 1: Generate three mesh configurations
        mesh_configs = self._generate_mesh_configs(
            base_cells_per_diameter,
            refinement_ratio,
            steady_state
        )

        # Step 2: Run simulations sequentially with solution mapping
        simulation_results = self._run_sequential_simulations(mesh_configs)

        # Step 3: Extract quantities of interest from all meshes
        quantities = self._extract_quantities_of_interest(simulation_results)

        # Step 4: Compute convergence metrics (Richardson, GCI)
        convergence_metrics = self._compute_convergence_metrics(
            quantities,
            refinement_ratio
        )

        # Step 5: Generate convergence report
        report_path = self._generate_convergence_report(
            mesh_configs,
            simulation_results,
            quantities,
            convergence_metrics
        )

        self.logger.info("=" * 70)
        self.logger.info("✅ MESH CONVERGENCE STUDY COMPLETED")
        self.logger.info(f"📄 Report: {report_path}")
        self.logger.info("=" * 70)

        return {
            'study_dir': str(self.output_dir),
            'report': str(report_path),
            'mesh_configs': mesh_configs,
            'quantities': quantities,
            'convergence_metrics': convergence_metrics
        }

    def _generate_mesh_configs(self,
                              base_cpd: int,
                              ratio: float,
                              steady_state: bool) -> List[Dict]:
        """
        Generate three mesh configurations with systematic refinement.

        Returns list of dicts: [coarse_config, medium_config, fine_config]
        """
        # Calculate cells_per_diameter for each level
        # h3 (coarse), h2 = h3/r (medium), h1 = h3/r² (fine)
        # Use round() instead of int() to maintain consistent ratio
        cpd_coarse = base_cpd
        cpd_medium = round(base_cpd * ratio)
        cpd_fine = round(base_cpd * ratio * ratio)

        mesh_levels = [
            {'name': 'coarse', 'cpd': cpd_coarse, 'label': 'Mesh 3 (Coarse)'},
            {'name': 'medium', 'cpd': cpd_medium, 'label': 'Mesh 2 (Medium)'},
            {'name': 'fine', 'cpd': cpd_fine, 'label': 'Mesh 1 (Fine)'}
        ]

        configs = []
        for level in mesh_levels:
            config = self.base_config.copy()

            # Ensure geometry section exists (required by workflow tasks)
            if 'geometry' not in config:
                config['geometry'] = {}

            # Set case_name to point to actual patient directory with STL files
            config['geometry']['case_name'] = self.patient_case_dir

            # Set defaults for other geometry fields if not present
            config['geometry'].setdefault('scale_factor', 0.001)
            config['geometry'].setdefault('rotation', False)
            config['geometry'].setdefault('inlet_keywords_ordered', 'inlet')
            config['geometry'].setdefault('outlet_keywords_ordered', ['outlet1', 'outlet2', 'outlet3', 'outlet4'])
            config['geometry'].setdefault('wall_keywords_ordered', 'wall_aorta')

            # Override mesh resolution
            if 'mesh' not in config:
                config['mesh'] = {}
            config['mesh']['cells_per_diameter'] = level['cpd']

            # Ensure SNAPPY_SETTINGS exists with defaults
            if 'SNAPPY_SETTINGS' not in config['mesh']:
                config['mesh']['SNAPPY_SETTINGS'] = {
                    'parallel': config.get('computational', {}).get('parallel', True),
                    'nProcessors': config.get('computational', {}).get('max_processors', 4),
                    'addLayers': True,
                    'addLayer': 2,
                    'expansionRatio': 1.2,
                    'finalLayerThickness': 0.3,
                    'minThickness': 0.1,
                    'relativeSizes': True
                }

            # Set steady-state BC if requested
            if steady_state:
                config = self._apply_steady_bc(config)

            # Set convergence-appropriate numerics
            config = self._apply_convergence_numerics(config)

            # Create output directory for this mesh
            mesh_dir = self.output_dir / level['name']
            mesh_dir.mkdir(exist_ok=True)

            # Save config
            config_file = mesh_dir / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)

            configs.append({
                'level': level['name'],
                'cpd': level['cpd'],
                'label': level['label'],
                'config': config,
                'config_file': str(config_file),
                'output_dir': str(mesh_dir),
                'case_dir': str(mesh_dir / 'openfoam')
            })

            self.logger.info(f"✓ {level['label']}: {level['cpd']} cells/diameter → {mesh_dir}")

        # Store refinement ratio for later calculations
        r_32 = cpd_medium / cpd_coarse
        r_21 = cpd_fine / cpd_medium

        self.logger.info(f"\nRefinement ratios: r_32={r_32:.3f}, r_21={r_21:.3f}")

        return configs

    def _apply_steady_bc(self, config: Dict) -> Dict:
        """
        Modify config for steady-state convergence study.

        Changes:
        - Inlet: CONSTANT flow rate (no time variation)
        - Outlets: Fixed pressure (simplest for convergence)
        """
        # Compute mean flow rate if time-varying inlet exists (case-insensitive)
        inlet_bc = config['boundary_conditions']['inlet']
        if inlet_bc.get('type', '').upper() == 'TIMEVARYING':
            self.logger.info("⚙️  Converting time-varying inlet → CONSTANT (steady state)")

            # Use cardiac output to estimate mean flow
            co = config.get('case_info', {}).get('cardiac_output', 5.0)  # L/min
            mean_flow = co / 60.0 / 1000.0  # Convert to m³/s

            config['boundary_conditions']['inlet'] = {
                'type': 'CONSTANT',
                'flow_rate': mean_flow,
                'profile': 'plug',
                '_convergence_study': True
            }

        # Use fixed pressure outlets for simplicity
        config['boundary_conditions']['outlets'] = {
            'type': 'FIXEDPRESSURE',
            'pressure': 80,  # mmHg (typical diastolic)
            '_convergence_study': True
        }

        self.logger.info("⚙️  Using FIXEDPRESSURE outlets for mesh convergence")

        return config

    def _apply_convergence_numerics(self, config: Dict) -> Dict:
        """
        Set consistent numerics appropriate for convergence study.

        Uses 'accurate' profile with second-order schemes for all meshes.
        """
        if 'numerics' not in config:
            config['numerics'] = {}

        config['numerics']['profile'] = 'accurate'
        config['numerics']['_convergence_study'] = True

        # Increase simulation time for convergence
        if 'simulation_control' not in config:
            config['simulation_control'] = {}

        # For steady cases, run longer to ensure convergence
        config['simulation_control']['number_of_cycles'] = 10

        return config

    def _run_sequential_simulations(self, mesh_configs: List[Dict]) -> List[Dict]:
        """
        Run simulations sequentially: coarse → medium → fine

        Uses mapFields to transfer solution between levels.
        """
        results = []
        previous_case_dir = None

        for i, mesh_cfg in enumerate(mesh_configs):
            level = mesh_cfg['level']
            self.logger.info("")
            self.logger.info("=" * 70)
            self.logger.info(f"RUNNING {mesh_cfg['label'].upper()}")
            self.logger.info("=" * 70)

            # Run simulation
            case_dir = Path(mesh_cfg['case_dir'])
            case_dir.mkdir(parents=True, exist_ok=True)

            # Setup simulation using WorkflowManager
            sim_config = {
                'config': mesh_cfg['config'],
                'run_dir': Path(mesh_cfg['output_dir']),
                'case_dir': str(case_dir)
            }

            # Run full workflow (mesh + solve)
            self._run_simulation(sim_config)

            # Map fields from previous mesh if not first
            if previous_case_dir is not None:
                self.logger.info(f"🔄 Mapping fields from {mesh_configs[i-1]['level']} → {level}")
                self._map_fields(previous_case_dir, case_dir)

                # Re-run solver with mapped initial condition
                self.logger.info(f"♻️  Continuing simulation with mapped initial condition")
                self._run_solver_only(sim_config)

            # Store results
            results.append({
                'level': level,
                'case_dir': str(case_dir),
                'success': True
            })

            previous_case_dir = case_dir

        return results

    def _run_simulation(self, sim_config: Dict):
        """Run complete simulation workflow."""
        try:
            self.logger.info(f"🚀 Starting workflow: {sim_config['case_dir']}")
            manager = WorkflowManager(sim_config['config'])
            manager.context['case_directory'] = sim_config['case_dir']
            manager.context['patient_name'] = sim_config['config'].get('case_info', {}).get('patient_id', 'convergence')

            self.logger.info("   Running workflow: runAll")
            manager.run_workflow('runAll')
            self.logger.info("   ✓ Workflow completed successfully")
        except Exception as e:
            self.logger.error(f"❌ Simulation failed: {e}")
            import traceback
            traceback.print_exc()
            raise ConvergenceStudyError(f"Simulation failed: {e}")

    def _run_solver_only(self, sim_config: Dict):
        """Run solver only (for mapped cases)."""
        try:
            self.logger.info(f"🔄 Continuing solver: {sim_config['case_dir']}")
            manager = WorkflowManager(sim_config['config'])
            manager.context['case_directory'] = sim_config['case_dir']
            manager.context['patient_name'] = sim_config['config'].get('case_info', {}).get('patient_id', 'convergence')

            manager.run_workflow('run:solver')
            self.logger.info("   ✓ Solver completed")
        except Exception as e:
            self.logger.error(f"❌ Solver failed: {e}")
            import traceback
            traceback.print_exc()
            raise ConvergenceStudyError(f"Solver failed: {e}")

    def _map_fields(self, source_case: Path, target_case: Path):
        """
        Map solution fields from coarse mesh to fine mesh using mapFields.

        OpenFOAM mapFields usage:
            mapFields <sourceCase> -sourceTime <time> -consistent
        """
        # Find latest time in source case
        source_times = self._get_time_directories(source_case)
        if not source_times:
            raise ConvergenceStudyError(f"No time directories in source: {source_case}")

        latest_time = max(source_times)

        self.logger.info(f"   Source: {source_case} (t={latest_time})")
        self.logger.info(f"   Target: {target_case}")

        # Run mapFields
        cmd = [
            'mapFields',
            str(source_case),
            '-sourceTime', str(latest_time),
            '-consistent',
            '-case', str(target_case)
        ]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            self.logger.info("   ✓ mapFields completed successfully")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"mapFields failed: {e.stderr}")
            raise ConvergenceStudyError(f"Field mapping failed: {e}")

    def _get_time_directories(self, case_dir: Path) -> List[float]:
        """Get list of time directories (as floats)."""
        times = []
        for item in case_dir.iterdir():
            if item.is_dir():
                try:
                    t = float(item.name)
                    times.append(t)
                except ValueError:
                    continue
        return times

    def _extract_quantities_of_interest(self, simulation_results: List[Dict]) -> Dict:
        """
        Extract key quantities for convergence analysis.

        Quantities:
        - Mean pressure drop (inlet → outlet)
        - Volume-averaged velocity magnitude
        - Surface-averaged wall shear stress
        - Peak WSS
        """
        quantities = {}

        for result in simulation_results:
            level = result['level']
            case_dir = Path(result['case_dir'])

            self.logger.info(f"📊 Extracting quantities: {level}")

            # Use OpenFOAM postProcess utilities
            qoi = {
                'pressure_drop': self._compute_pressure_drop(case_dir),
                'avg_velocity': self._compute_avg_velocity(case_dir),
                'avg_wss': self._compute_avg_wss(case_dir),
                'peak_wss': self._compute_peak_wss(case_dir),
                'cell_count': self._get_cell_count(case_dir),
                'h_representative': self._compute_representative_h(case_dir)
            }

            quantities[level] = qoi

            self.logger.info(f"   ΔP = {qoi['pressure_drop']:.4f} Pa")
            self.logger.info(f"   <U> = {qoi['avg_velocity']:.6f} m/s")
            self.logger.info(f"   <WSS> = {qoi['avg_wss']:.4f} Pa")
            self.logger.info(f"   WSS_max = {qoi['peak_wss']:.4f} Pa")

        return quantities

    def _read_postprocessing_pressure(self, case_dir: Path, patch_name: str) -> list:
        """Read area-averaged pressure time series from postProcessing."""
        # Try common naming patterns: patchPressure, {patch}Pressure
        candidates = [
            case_dir / 'postProcessing' / f'{patch_name}Pressure' / '0' / 'surfaceFieldValue.dat',
            case_dir / 'postProcessing' / f'{patch_name}' / '0' / 'surfaceFieldValue.dat',
        ]
        for dat_path in candidates:
            if dat_path.exists():
                times, vals = [], []
                with open(dat_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('#') or not line:
                            continue
                        parts = line.split()
                        times.append(float(parts[0]))
                        vals.append(float(parts[1]))
                return list(zip(times, vals))
        return []

    def _find_outlet_patches(self, case_dir: Path) -> list:
        """Find all outlet patch names from postProcessing directories."""
        pp = case_dir / 'postProcessing'
        if not pp.exists():
            return []
        outlets = []
        for d in sorted(pp.iterdir()):
            name = d.name
            if 'outlet' in name.lower() and 'pressure' in name.lower():
                # Extract patch name: "outlet1Pressure" → "outlet1", "PAT003outlet1Pressure" → "PAT003outlet1"
                patch = name.replace('Pressure', '')
                outlets.append(patch)
        return outlets

    def _compute_pressure_drop(self, case_dir: Path) -> float:
        """
        Compute pressure drop from postProcessing area-averaged pressure data.

        Returns ΔP (kinematic, m²/s²) between inlet and the last outlet
        (descending aorta) at peak systole of the final cardiac cycle.
        """
        try:
            # Find inlet patch name
            pp = case_dir / 'postProcessing'
            if not pp.exists():
                self.logger.warning(f"No postProcessing directory in {case_dir}")
                return 0.0

            # Find inlet
            inlet_patch = None
            for d in pp.iterdir():
                if 'inlet' in d.name.lower() and 'pressure' in d.name.lower():
                    inlet_patch = d.name.replace('Pressure', '')
                    break

            if not inlet_patch:
                self.logger.warning("No inlet pressure postProcessing found")
                return 0.0

            inlet_data = self._read_postprocessing_pressure(case_dir, inlet_patch)
            if not inlet_data:
                self.logger.warning(f"No pressure data for {inlet_patch}")
                return 0.0

            # Find last outlet (descending aorta = highest-numbered outlet)
            outlets = self._find_outlet_patches(case_dir)
            if not outlets:
                self.logger.warning("No outlet pressure postProcessing found")
                return 0.0
            desc_aorta = outlets[-1]  # last outlet = descending aorta

            outlet_data = self._read_postprocessing_pressure(case_dir, desc_aorta)
            if not outlet_data:
                self.logger.warning(f"No pressure data for {desc_aorta}")
                return 0.0

            # Find peak inlet pressure in final cycle
            max_t = max(t for t, _ in inlet_data)
            cycle_period = self.config.get('cardiac_cycle', self.config.get('simulation_control', {}).get('cardiac_cycle_period', 1.0))
            cycle_start = max_t - cycle_period

            final_cycle = [(t, p) for t, p in inlet_data if t >= cycle_start]
            if not final_cycle:
                final_cycle = inlet_data

            t_peak, p_peak_inlet = max(final_cycle, key=lambda x: x[1])

            # Get outlet pressure at peak time
            closest_outlet = min(outlet_data, key=lambda x: abs(x[0] - t_peak))
            p_outlet = closest_outlet[1]

            delta_p = p_peak_inlet - p_outlet
            self.logger.info(f"  ΔP at t={t_peak:.4f}: inlet={p_peak_inlet:.4f} - {desc_aorta}={p_outlet:.4f} = {delta_p:.4f} m²/s²")
            return delta_p

        except Exception as e:
            self.logger.error(f"Error computing pressure drop: {e}")
            return 0.0

    def _compute_avg_velocity(self, case_dir: Path) -> float:
        """
        Compute mean inlet velocity at peak systole from boundaryData.

        Falls back to flow rate postProcessing if boundaryData unavailable.
        """
        try:
            # Try patchFlowRate postProcessing
            pp = case_dir / 'postProcessing'
            if pp.exists():
                for d in pp.iterdir():
                    if 'inlet' in d.name.lower() and 'flow' in d.name.lower():
                        dat = d / '0' / 'surfaceFieldValue.dat'
                        if dat.exists():
                            data = []
                            with open(dat) as f:
                                for line in f:
                                    line = line.strip()
                                    if line.startswith('#') or not line:
                                        continue
                                    parts = line.split()
                                    data.append((float(parts[0]), abs(float(parts[1]))))
                            if data:
                                # Get inlet area from pressure postProcessing header
                                inlet_area = self._get_patch_area(case_dir, 'inlet')
                                peak_q = max(v for _, v in data)
                                if inlet_area > 0:
                                    return peak_q / inlet_area
                                return peak_q / 1e-4  # rough fallback

            # Fallback: read boundaryData velocity
            bd = case_dir / 'constant' / 'boundaryData'
            if bd.exists():
                for inlet_dir in bd.iterdir():
                    if 'inlet' in inlet_dir.name.lower():
                        pts_file = inlet_dir / 'points'
                        if not pts_file.exists():
                            continue
                        with open(pts_file) as f:
                            n_pts = int(f.readline().strip())
                        # Find peak velocity in first cycle
                        best_u = 0.0
                        time_dirs = sorted(
                            [d for d in inlet_dir.iterdir() if d.is_dir() and d.name[0].isdigit()],
                            key=lambda x: float(x.name)
                        )
                        for td in time_dirs[:50]:  # sample first 50 time steps
                            u_file = td / 'U'
                            if not u_file.exists():
                                continue
                            vels = []
                            with open(u_file) as f:
                                for line in f:
                                    line = line.strip().strip('()')
                                    if line and line[0] in '(-0123456789':
                                        parts = line.split()
                                        if len(parts) == 3:
                                            try:
                                                mag = (float(parts[0])**2 + float(parts[1])**2 + float(parts[2])**2)**0.5
                                                vels.append(mag)
                                            except ValueError:
                                                pass
                            if len(vels) == n_pts:
                                u_avg = sum(vels) / len(vels)
                                best_u = max(best_u, u_avg)
                        if best_u > 0:
                            return best_u
            return 0.0
        except Exception as e:
            self.logger.error(f"Error computing velocity: {e}")
            return 0.0

    def _get_patch_area(self, case_dir: Path, patch_keyword: str) -> float:
        """Extract patch area from postProcessing surfaceFieldValue header."""
        pp = case_dir / 'postProcessing'
        if not pp.exists():
            return 0.0
        for d in pp.iterdir():
            if patch_keyword in d.name.lower() and 'pressure' in d.name.lower():
                dat = d / '0' / 'surfaceFieldValue.dat'
                if dat.exists():
                    with open(dat) as f:
                        for line in f:
                            if 'Area' in line:
                                return float(line.split(':')[-1].strip())
        return 0.0

    def _compute_avg_wss(self, case_dir: Path) -> float:
        """
        Compute surface-averaged WSS magnitude from the wallShearStress field
        at the last saved time step.
        """
        try:
            times = self._get_time_directories(case_dir)
            if not times:
                return 0.0

            latest_time = max(times)
            wss_file = case_dir / str(latest_time) / 'wallShearStress'

            if not wss_file.exists():
                self.logger.warning(f"wallShearStress field not found at t={latest_time}")
                return 0.0

            # Parse wallShearStress vector field on wall patch
            import re
            with open(wss_file, 'rb') as f:
                content = f.read().decode('ascii', errors='ignore')

            # Find wall patch data (look for the wall boundary)
            wall_patterns = ['wall_aorta', 'wall']
            for wall_name in wall_patterns:
                idx = content.find(wall_name)
                if idx >= 0:
                    # Extract vectors after this patch
                    block = content[idx:idx+50000]
                    vectors = re.findall(r'\(\s*([-\d.e]+)\s+([-\d.e]+)\s+([-\d.e]+)\s*\)', block)
                    if vectors:
                        mags = [(float(x)**2 + float(y)**2 + float(z)**2)**0.5 for x, y, z in vectors]
                        avg = sum(mags) / len(mags)
                        self.logger.info(f"  WSS from {len(mags)} wall faces: avg={avg:.4f} Pa")
                        return avg

            self.logger.warning("Could not parse wallShearStress field")
            return 0.0

        except Exception as e:
            self.logger.error(f"Error computing WSS: {e}")
            return 0.0

    def _compute_peak_wss(self, case_dir: Path) -> float:
        """Compute 99th percentile WSS from wallShearStress field."""
        try:
            times = self._get_time_directories(case_dir)
            if not times:
                return 0.0

            latest_time = max(times)
            wss_file = case_dir / str(latest_time) / 'wallShearStress'

            if not wss_file.exists():
                return 0.0

            import re
            with open(wss_file, 'rb') as f:
                content = f.read().decode('ascii', errors='ignore')

            wall_patterns = ['wall_aorta', 'wall']
            for wall_name in wall_patterns:
                idx = content.find(wall_name)
                if idx >= 0:
                    block = content[idx:idx+50000]
                    vectors = re.findall(r'\(\s*([-\d.e]+)\s+([-\d.e]+)\s+([-\d.e]+)\s*\)', block)
                    if vectors:
                        mags = sorted([(float(x)**2 + float(y)**2 + float(z)**2)**0.5 for x, y, z in vectors])
                        p99_idx = int(0.99 * len(mags))
                        return mags[p99_idx]
            return 0.0

        except Exception as e:
            self.logger.error(f"Error computing peak WSS: {e}")
            return 0.0

    def _get_cell_count(self, case_dir: Path) -> int:
        """Get total cell count from polyMesh/owner or checkMesh log."""
        try:
            # Primary: read from polyMesh/owner header
            owner = case_dir / 'constant' / 'polyMesh' / 'owner'
            if owner.exists():
                import re
                with open(owner, 'rb') as f:
                    header = f.read(2000).decode('ascii', errors='ignore')
                match = re.search(r'nCells:(\d+)', header)
                if match:
                    return int(match.group(1))

            # Fallback: checkMesh log
            for log_path in [case_dir / 'logs' / 'log.checkMesh', case_dir / 'log.checkMesh']:
                if log_path.exists():
                    import re
                    with open(log_path) as f:
                        content = f.read()
                    match = re.search(r'cells:\s+(\d+)', content)
                    if match:
                        return int(match.group(1))

            return 0

        except Exception as e:
            self.logger.error(f"Error getting cell count: {e}")
            return 0

    def _compute_representative_h(self, case_dir: Path) -> float:
        """
        Compute representative cell spacing h = (V_total / N_cells)^(1/3)
        """
        try:
            log_file = case_dir / 'logs' / 'log.checkMesh'
            if not log_file.exists():
                # Fallback to old location for compatibility
                log_file = case_dir / 'log.checkMesh'

            if log_file.exists():
                with open(log_file, 'r') as f:
                    content = f.read()

                import re
                # Extract total volume and cell count
                vol_match = re.search(r'Volume:\s+([\d.e+-]+)', content)
                cells_match = re.search(r'cells:\s+(\d+)', content)

                if vol_match and cells_match:
                    volume = float(vol_match.group(1))
                    cells = int(cells_match.group(1))
                    h = (volume / cells) ** (1/3)
                    return h

            # Fallback
            return 0.001

        except Exception as e:
            self.logger.error(f"Error computing h: {e}")
            return 0.001

    def _compute_convergence_metrics(self,
                                    quantities: Dict,
                                    refinement_ratio: float) -> Dict:
        """
        Compute Richardson extrapolation and GCI for all quantities.

        Returns dict with convergence metrics for each quantity.
        """
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("CONVERGENCE ANALYSIS")
        self.logger.info("=" * 70)

        metrics = {}

        # Extract values for each quantity
        for qty_name in ['pressure_drop', 'avg_velocity', 'avg_wss', 'peak_wss']:
            phi_3 = quantities['coarse'][qty_name]  # Coarse
            phi_2 = quantities['medium'][qty_name]  # Medium
            phi_1 = quantities['fine'][qty_name]    # Fine

            # Compute convergence metrics
            conv = self._richardson_extrapolation(phi_3, phi_2, phi_1, refinement_ratio)

            metrics[qty_name] = conv

            self.logger.info(f"\n{qty_name.upper()}:")
            self.logger.info(f"  Coarse (φ₃): {phi_3:.6f}")
            self.logger.info(f"  Medium (φ₂): {phi_2:.6f}")
            self.logger.info(f"  Fine (φ₁):   {phi_1:.6f}")
            self.logger.info(f"  Observed order (p): {conv['observed_order']:.3f}")
            self.logger.info(f"  Richardson extrapolated: {conv['phi_exact']:.6f}")
            self.logger.info(f"  GCI_medium: {conv['gci_medium']:.2f}%")
            self.logger.info(f"  GCI_fine:   {conv['gci_fine']:.2f}%")
            self.logger.info(f"  Convergence: {conv['convergence_status']}")

        return metrics

    def _richardson_extrapolation(self,
                                 phi_3: float,
                                 phi_2: float,
                                 phi_1: float,
                                 r: float) -> Dict:
        """
        Perform Richardson extrapolation and compute GCI.

        Args:
            phi_3: Coarse mesh value
            phi_2: Medium mesh value
            phi_1: Fine mesh value
            r: Refinement ratio (constant)

        Returns:
            Dict with observed order, extrapolated value, GCI values, convergence status
        """
        # Compute differences
        epsilon_32 = phi_3 - phi_2
        epsilon_21 = phi_2 - phi_1

        # Convergence ratio
        if abs(epsilon_21) < 1e-10:
            # Nearly converged
            return {
                'observed_order': float('inf'),
                'phi_exact': phi_1,
                'gci_fine': 0.0,
                'gci_medium': 0.0,
                'convergence_status': 'converged'
            }

        R = epsilon_32 / epsilon_21

        # Observed order of accuracy (solve: R = r^p)
        import math
        p = math.log(abs(R)) / math.log(r)

        # Richardson extrapolated value
        phi_exact = phi_1 + (phi_1 - phi_2) / (r**p - 1)

        # Grid Convergence Index (GCI)
        F_s = 1.25  # Safety factor (recommended for 3 grids)

        gci_fine = F_s * abs((phi_1 - phi_2) / phi_1) / (r**p - 1) * 100  # %
        gci_medium = F_s * abs((phi_2 - phi_3) / phi_2) / (r**p - 1) * 100  # %

        # Determine convergence status
        if 0 < R < 1:
            status = 'monotonic_convergence'
        elif R < 0:
            status = 'oscillatory_convergence'
        elif R > 1:
            status = 'divergence'
        else:
            status = 'unknown'

        return {
            'observed_order': p,
            'phi_exact': phi_exact,
            'gci_fine': gci_fine,
            'gci_medium': gci_medium,
            'convergence_ratio': R,
            'convergence_status': status
        }

    def _generate_convergence_report(self,
                                    mesh_configs: List[Dict],
                                    simulation_results: List[Dict],
                                    quantities: Dict,
                                    convergence_metrics: Dict) -> Path:
        """
        Generate publication-ready convergence report.

        Includes:
        - Mesh statistics table
        - Convergence metrics table
        - GCI values
        - Recommendations
        """
        report_path = self.output_dir / 'convergence_report.md'

        with open(report_path, 'w') as f:
            f.write("# Mesh Convergence Study Report\n\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Patient ID:** {self.base_config.get('case_info', {}).get('patient_id', 'N/A')}\n\n")

            # Mesh statistics
            f.write("## 1. Mesh Statistics\n\n")
            f.write("| Mesh | cells/diameter | Cell Count | h (mm) | Refinement Ratio |\n")
            f.write("|------|----------------|------------|--------|------------------|\n")

            for i, cfg in enumerate(mesh_configs):
                cpd = cfg['cpd']
                level = cfg['level']
                cell_count = quantities[level]['cell_count']
                h = quantities[level]['h_representative'] * 1000  # m → mm

                if i == 0:
                    r_text = "—"
                else:
                    r = cfg['cpd'] / mesh_configs[i-1]['cpd']
                    r_text = f"{r:.3f}"

                f.write(f"| {cfg['label']} | {cpd} | {cell_count:,} | {h:.4f} | {r_text} |\n")

            f.write("\n")

            # Convergence results
            f.write("## 2. Convergence Metrics\n\n")

            for qty_name, metrics in convergence_metrics.items():
                f.write(f"### {qty_name.replace('_', ' ').title()}\n\n")

                phi_3 = quantities['coarse'][qty_name]
                phi_2 = quantities['medium'][qty_name]
                phi_1 = quantities['fine'][qty_name]

                f.write("| Mesh | Value | Relative Difference | GCI (%) |\n")
                f.write("|------|-------|---------------------|----------|\n")
                f.write(f"| Coarse | {phi_3:.6f} | — | — |\n")

                diff_32 = abs((phi_2 - phi_3) / phi_2 * 100)
                f.write(f"| Medium | {phi_2:.6f} | {diff_32:.2f}% | {metrics['gci_medium']:.2f} |\n")

                diff_21 = abs((phi_1 - phi_2) / phi_1 * 100)
                f.write(f"| Fine | {phi_1:.6f} | {diff_21:.2f}% | {metrics['gci_fine']:.2f} |\n")

                f.write(f"| **Extrapolated** | **{metrics['phi_exact']:.6f}** | — | — |\n\n")

                f.write(f"- **Observed order of accuracy:** p = {metrics['observed_order']:.3f}\n")
                f.write(f"- **Convergence status:** {metrics['convergence_status']}\n")
                f.write(f"- **Convergence ratio:** R = {metrics.get('convergence_ratio', 0):.4f}\n\n")

            # Recommendations
            f.write("## 3. Recommendations\n\n")

            # Check if medium mesh is converged
            avg_gci_fine = sum(m['gci_fine'] for m in convergence_metrics.values()) / len(convergence_metrics)
            avg_gci_medium = sum(m['gci_medium'] for m in convergence_metrics.values()) / len(convergence_metrics)

            if avg_gci_fine < 3.0:
                f.write("✅ **Fine mesh is CONVERGED** (GCI < 3%)\n\n")
                f.write("The fine mesh provides mesh-independent results suitable for publication.\n\n")
            elif avg_gci_fine < 5.0:
                f.write("⚠️ **Fine mesh is ACCEPTABLE** (3% < GCI < 5%)\n\n")
                f.write("Results are acceptable for most applications but consider further refinement for high-precision studies.\n\n")
            else:
                f.write("❌ **Further refinement required** (GCI > 5%)\n\n")
                f.write("Consider generating an ultra-fine mesh or adjusting refinement strategy.\n\n")

            if avg_gci_medium < 5.0:
                f.write("✅ **Medium mesh is ADEQUATE** for routine analysis.\n\n")

            # Save raw data
            f.write("## 4. Raw Data\n\n")
            f.write("Full numerical results saved in:\n")
            f.write(f"- `{self.output_dir / 'convergence_data.json'}`\n\n")

        # Save JSON data
        json_data = {
            'mesh_configs': mesh_configs,
            'quantities': quantities,
            'convergence_metrics': convergence_metrics,
            'timestamp': datetime.now().isoformat()
        }

        with open(self.output_dir / 'convergence_data.json', 'w') as f:
            json.dump(json_data, f, indent=2)

        self.logger.info(f"📄 Report saved: {report_path}")

        return report_path


def main():
    """Command-line interface for convergence studies."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Run automated mesh convergence study for patient-specific CFD'
    )
    parser.add_argument('config', help='Path to base configuration file')
    parser.add_argument('--ratio', type=float, default=1.414,
                       help='Refinement ratio between meshes (default: √2 = 1.414)')
    parser.add_argument('--base-cpd', type=int, default=10,
                       help='Base cells_per_diameter for coarse mesh (default: 10)')
    parser.add_argument('--transient', action='store_true',
                       help='Use transient BC (default: converts to steady state)')

    args = parser.parse_args()

    # Run convergence study
    runner = MeshConvergenceRunner(args.config)
    results = runner.run_convergence_study(
        refinement_ratio=args.ratio,
        base_cells_per_diameter=args.base_cpd,
        steady_state=not args.transient
    )

    print("\n" + "=" * 70)
    print("✅ CONVERGENCE STUDY COMPLETE")
    print("=" * 70)
    print(f"Report: {results['report']}")
    print(f"Data:   {results['study_dir']}/convergence_data.json")
    print("=" * 70)


if __name__ == '__main__':
    main()
