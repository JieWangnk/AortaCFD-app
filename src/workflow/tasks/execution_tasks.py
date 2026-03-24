import os
import re
import shutil
import threading
import time

from ..base_task import Task, AortaCFDError, logger
from aortacfd_lib.utils.runner import run_command, CommandExecutionError
from aortacfd_lib.utils.validation import MeshQualityChecker
from aortacfd_lib.utils.logger import Logger

class ExecuteMeshingTask(Task):
    """Runs the external meshing commands. STLs are pre-scaled to meters during case setup."""

    def execute(self, context: dict) -> bool:
        """This task contains the execution logic from your original run_mesh method."""
        logger.info("Executing OpenFOAM meshing commands...")
        case_dir = context["case_directory"]
        snappy_settings = self.config.get("mesh", {}).get("SNAPPY_SETTINGS", {})

        try:
            run_command(self.config, ["blockMesh"], case_dir, "log.blockMesh")
            run_command(self.config, ["surfaceFeatures"], case_dir, "log.surfaceFeatures")

            # surfaceFeatures creates closeness files WITHOUT .stl in name:
            #   wall_aorta.closeness.internalPointCloseness
            # But snappyHexMesh expects .stl in name (matching geometry entry):
            #   wall_aorta.stl.closeness.internalPointCloseness
            # Rename them here so both serial and parallel paths work.
            self._rename_closeness_files_for_snappy(case_dir)

            if snappy_settings.get("parallel"):
                n_proc = snappy_settings.get("nProcessors", 1)

                # Temporarily override decomposeParDict for parallel meshing
                self._override_decompose_par_dict(case_dir, n_proc)

                # Use -noFields to only decompose geometry (mesh), not field data
                # Field files (0/p, 0/U) expect post-snappyHexMesh patches, not blockMesh "world" patch
                run_command(self.config, ["decomposePar", "-force", "-noFields"], case_dir, "log.decomposePar.preMesh")

                # Distribute closeness files to processor directories for parallel span refinement
                self._distribute_closeness_files(case_dir, n_proc)

                run_command(
                    self.config,
                    ["mpirun", "-np", str(n_proc), "snappyHexMesh", "-parallel", "-overwrite"],
                    case_dir,
                    "log.snappyHexMesh",
                )
                run_command(self.config, ["reconstructPar", "-constant"], case_dir, "log.reconstructPar")

                # Clean up processor directories to save disk space
                self._cleanup_processor_directories(case_dir)

                # Restore original decomposeParDict (using run_settings.subdomains for solver)
                solver_subdomains = self.config.get("run_settings", {}).get("subdomains", 1)
                self._override_decompose_par_dict(case_dir, solver_subdomains)
            else:
                run_command(self.config, ["snappyHexMesh", "-overwrite"], case_dir, "log.snappyHexMesh")

            run_command(self.config, ["checkMesh"], case_dir, "log.checkMesh")

            # Analyze mesh quality; if layers caused problems, retry with relaxed settings
            mesh_result = self._check_mesh_quality(case_dir)
            if mesh_result:
                Logger.console(f"     Mesh: {mesh_result}")

            if self._mesh_needs_layer_retry(case_dir):
                self._retry_with_relaxed_layers(case_dir, snappy_settings)

            # Check if mesh quality is compatible with requested numerics profile
            self._check_numerics_compatibility(case_dir)

            # Check if mesh quality supports the selected turbulence model
            self._check_turbulence_model_compatibility(case_dir)

            logger.info("Mesh is already in SI units (meters) - no post-mesh scaling needed")

        except CommandExecutionError as e:
            logger.error(f"Meshing failed: {e}")
            return False
        
        # Create .foam file for easy ParaView loading
        self._create_foam_file(case_dir)
            
        logger.info("Meshing commands completed successfully.")
        return True
    
    def _create_foam_file(self, case_dir: str):
        """
        Creates a .foam file in the case directory for easy ParaView loading.
        This is a standard practice in OpenFOAM workflows.
        """
        foam_file_path = os.path.join(case_dir, f"{os.path.basename(case_dir)}.foam")
        try:
            with open(foam_file_path, 'w') as f:
                f.write("// OpenFOAM case file for ParaView\n")
                f.write("// Created automatically after mesh generation\n")
            logger.info(f"Created .foam file: {foam_file_path}")
        except OSError as e:
            logger.warning(f"Could not create .foam file: {e}")

    def _check_mesh_quality(self, case_dir: str) -> str:
        """
        Analyze mesh quality and provide alerts/recommendations.
        This helps identify potential simulation stability issues early.

        Returns:
            Summary string for console output (e.g., "125,432 cells, quality OK")
        """
        try:
            # Use new validation-based quality checker
            quality_checker = MeshQualityChecker(case_dir)
            result = quality_checker.validate_mesh_quality()

            # Log warnings
            for warning in result.warnings:
                logger.warning(f"Mesh quality warning: {warning}")

            # Log errors
            if not result.is_valid:
                for error in result.errors:
                    logger.error(f"Mesh quality error: {error}")
                logger.error("Mesh quality issues detected. Simulation may be unstable.")
                logger.warning("Consider:")
                logger.warning("  - Refining mesh settings")
                logger.warning("  - Using 'draft' profile with 1st order numerics")
                logger.warning("  - Reviewing geometry for sharp features")
                # Don't abort - let user decide whether to proceed
                return f"{result.cell_count:,} cells (quality issues)"
            else:
                if len(result.warnings) == 0:
                    logger.info("Mesh quality validation passed - no issues detected")
                    return f"{result.cell_count:,} cells, quality OK"
                else:
                    logger.info("Mesh quality acceptable with minor warnings")
                    return f"{result.cell_count:,} cells (minor warnings)"

        except Exception as e:
            logger.warning(f"Could not analyze mesh quality: {e}")
            logger.warning("Proceeding without mesh quality check")
            return ""

    def _check_numerics_compatibility(self, case_dir: str):
        """
        Check if mesh quality supports the requested numerics profile.

        Warns if the mesh is too poor for 2nd-order schemes. This prevents
        the common failure mode: user requests 'standard' or 'precise' but
        the mesh has high skewness/non-orthogonality and the solver diverges.
        """
        profile = self.config.get("numerics", {}).get("profile", "standard")
        if profile == "robust":
            return  # Robust handles any mesh

        try:
            quality_checker = MeshQualityChecker(case_dir)
            result = quality_checker.validate_mesh_quality()

            if not result.is_valid:
                logger.warning("=" * 60)
                logger.warning(f"MESH QUALITY vs NUMERICS MISMATCH")
                logger.warning(f"  Profile '{profile}' uses 2nd-order schemes")
                logger.warning(f"  but mesh quality has issues that may cause divergence.")
                logger.warning(f"  Consider: --steps regenerate-numerics (auto-adjusts)")
                logger.warning(f"  Or switch to: \"profile\": \"robust\" in config.json")
                logger.warning("=" * 60)
                Logger.console(f"     WARNING: mesh quality may be too poor for '{profile}' profile")
        except Exception:
            pass  # Don't block meshing for QC failures

    def _check_turbulence_model_compatibility(self, case_dir: str):
        """
        Check if mesh quality supports the selected turbulence model (RANS/LES).

        RANS k-omega SST has a production term P_k = nut * |S|^2 that amplifies
        any mesh-induced velocity gradient error. On snappyHexMesh meshes with
        polyhedral transition cells, this is a guaranteed instability source.

        LES subgrid models (WALE, Smagorinsky) compute eddy viscosity from velocity
        gradients — poor mesh quality corrupts the estimate and causes nut blowup.

        This check runs after checkMesh and provides actionable warnings.
        """
        physics = self.config.get("physics", {})
        sim_type = physics.get("simulation_type", "laminar").lower()
        if sim_type == "laminar":
            return

        try:
            from aortacfd_lib.physics_advisor import (
                check_mesh_turbulence_compatibility,
                estimate_reynolds_number,
            )

            # Parse mesh metrics from checkMesh
            quality_checker = MeshQualityChecker(case_dir)
            result = quality_checker.validate_mesh_quality()

            # Build metrics dict from checkMesh
            checkmesh_log = os.path.join(case_dir, "logs", "log.checkMesh")
            mesh_metrics = None
            if os.path.exists(checkmesh_log):
                with open(checkmesh_log, 'r') as f:
                    content = f.read()
                mesh_metrics = quality_checker._parse_checkmesh_output(content)

            # Run compatibility check
            warnings = check_mesh_turbulence_compatibility(
                self.config, sim_type, mesh_metrics
            )

            if warnings:
                logger.warning("=" * 65)
                logger.warning(f"MESH QUALITY vs {sim_type.upper()} COMPATIBILITY")
                logger.warning("=" * 65)
                for w in warnings:
                    logger.warning(f"  {w}")

                # Also check Re
                Re = estimate_reynolds_number(self.config)
                if Re is not None and Re < 4000:
                    logger.warning(
                        f"  Estimated Re_peak = {Re:.0f}. Consider switching to "
                        f"laminar (scientifically defensible for aortic Re < 4000)."
                    )

                logger.warning("=" * 65)
                Logger.console(
                    f"     WARNING: mesh quality may cause {sim_type.upper()} instability "
                    f"(see log for details)"
                )

        except Exception as e:
            logger.debug(f"Turbulence model compatibility check skipped: {e}")

    def _mesh_needs_layer_retry(self, case_dir: str) -> bool:
        """Check if mesh quality issues are likely caused by boundary layer extrusion."""
        snappy_log = os.path.join(case_dir, "logs", "log.snappyHexMesh")
        if not os.path.exists(snappy_log):
            return False

        try:
            content = open(snappy_log, errors="replace").read()
            # snappyHexMesh reports these when layers cause problems
            layer_issues = [
                "Illegal cells after layer addition",
                "Could not find a surface",
                "negative volume",
                "Reducing layer thickness",
            ]
            has_layer_problem = any(msg in content for msg in layer_issues)

            # Also check if checkMesh found failed cells
            checkmesh_log = os.path.join(case_dir, "logs", "log.checkMesh")
            has_failed_mesh = False
            if os.path.exists(checkmesh_log):
                cm = open(checkmesh_log, errors="replace").read()
                has_failed_mesh = "***FAILED***" in cm or "Mesh has" not in cm

            # Only retry if layers are enabled
            layers_enabled = self.config.get("mesh", {}).get("SNAPPY_SETTINGS", {}).get("addLayers", True)

            return layers_enabled and (has_layer_problem or has_failed_mesh)
        except Exception:
            return False

    def _retry_with_relaxed_layers(self, case_dir: str, snappy_settings: dict):
        """
        Re-run snappyHexMesh with progressively relaxed boundary layer settings.

        Strategy:
          Attempt 1 (already done): original settings
          Attempt 2: reduce layers by 30%, increase finalLayerThickness by 30%
          Attempt 3: reduce layers by 60%, relax quality constraints
          Attempt 4: disable layers entirely

        Each attempt re-runs snappyHexMesh and checkMesh. Stops at first success.
        """
        snappy_dict_path = os.path.join(case_dir, "system", "snappyHexMeshDict")
        if not os.path.exists(snappy_dict_path):
            return

        original_content = open(snappy_dict_path).read()
        original_layers = snappy_settings.get("addLayer", 5)

        retry_configs = [
            {
                "label": "reduce layers 30%",
                "n_layers": max(2, int(original_layers * 0.7)),
                "final_thickness_factor": 1.3,
                "disable": False,
            },
            {
                "label": "reduce layers 60% + relax quality",
                "n_layers": max(1, int(original_layers * 0.4)),
                "final_thickness_factor": 1.6,
                "disable": False,
            },
            {
                "label": "disable boundary layers",
                "n_layers": 0,
                "final_thickness_factor": 1.0,
                "disable": True,
            },
        ]

        for attempt, cfg in enumerate(retry_configs, start=2):
            logger.info("=" * 60)
            logger.info(f"MESH LAYER RETRY (attempt {attempt}/4): {cfg['label']}")
            logger.info("=" * 60)
            Logger.console(f"     Mesh retry #{attempt}: {cfg['label']}")

            # Modify snappyHexMeshDict on disk
            modified = original_content
            if cfg["disable"]:
                modified = re.sub(
                    r'(addLayers\s+)(true|false)',
                    r'\g<1>false',
                    modified,
                    flags=re.IGNORECASE,
                )
            else:
                # Reduce nSurfaceLayers
                modified = re.sub(
                    r'(nSurfaceLayers\s+)\d+',
                    rf'\g<1>{cfg["n_layers"]}',
                    modified,
                )
                # Increase finalLayerThickness (more room for layers to fit)
                def _scale_thickness(m):
                    old_val = float(m.group(2))
                    new_val = min(0.8, old_val * cfg["final_thickness_factor"])
                    return f'{m.group(1)}{new_val:.4f}'
                modified = re.sub(
                    r'(finalLayerThickness\s+)([\d.]+)',
                    _scale_thickness,
                    modified,
                )

            with open(snappy_dict_path, "w") as f:
                f.write(modified)

            # Re-run snappyHexMesh
            try:
                if snappy_settings.get("parallel"):
                    n_proc = snappy_settings.get("nProcessors", 1)
                    run_command(self.config, ["decomposePar", "-force", "-noFields"], case_dir, "log.decomposePar.preMesh")
                    self._distribute_closeness_files(case_dir, n_proc)
                    run_command(
                        self.config,
                        ["mpirun", "-np", str(n_proc), "snappyHexMesh", "-parallel", "-overwrite"],
                        case_dir, f"log.snappyHexMesh.retry{attempt}",
                    )
                    run_command(self.config, ["reconstructPar", "-constant"], case_dir, "log.reconstructPar")
                    self._cleanup_processor_directories(case_dir)
                else:
                    run_command(self.config, ["snappyHexMesh", "-overwrite"], case_dir, f"log.snappyHexMesh.retry{attempt}")

                run_command(self.config, ["checkMesh"], case_dir, "log.checkMesh")

                # Check if quality is now acceptable
                if not self._mesh_needs_layer_retry(case_dir):
                    mesh_result = self._check_mesh_quality(case_dir)
                    Logger.console(f"     Mesh retry #{attempt} succeeded: {mesh_result}")
                    logger.info(f"Layer retry attempt {attempt} succeeded")
                    return
                else:
                    logger.info(f"Layer retry attempt {attempt}: still has issues, trying next")

            except CommandExecutionError:
                logger.warning(f"Layer retry attempt {attempt} failed, trying next")

        # All retries exhausted; restore original and proceed with whatever we have
        with open(snappy_dict_path, "w") as f:
            f.write(original_content)
        logger.warning("All layer retry attempts exhausted. Proceeding with current mesh.")
        Logger.console("     WARNING: mesh layer issues not fully resolved")

    def _rename_closeness_files_for_snappy(self, case_dir: str):
        """
        Rename closeness files so snappyHexMesh can find them.

        surfaceFeatures creates:  wall_aorta.closeness.internalPointCloseness
        snappyHexMesh expects:    wall_aorta.stl.closeness.internalPointCloseness
        (because geometry is referenced as "wall_aorta.stl" in snappyHexMeshDict)
        """
        import glob
        import re

        tri_surface_dir = os.path.join(case_dir, "constant", "triSurface")
        closeness_files = glob.glob(os.path.join(tri_surface_dir, "*.closeness.*"))

        renamed = 0
        for old_path in closeness_files:
            basename = os.path.basename(old_path)
            if ".stl.closeness." in basename:
                continue  # Already has .stl
            new_basename = re.sub(r'\.closeness\.', '.stl.closeness.', basename)
            new_path = os.path.join(tri_surface_dir, new_basename)
            try:
                os.rename(old_path, new_path)
                renamed += 1
            except OSError as e:
                logger.warning(f"Could not rename {old_path}: {e}")

        if renamed > 0:
            logger.info(f"Renamed {renamed} closeness files for snappyHexMesh compatibility")

    def _distribute_closeness_files(self, case_dir: str, n_proc: int):
        """
        Copy closeness files to processor directories for parallel meshing.

        Files are already renamed with .stl by _rename_closeness_files_for_snappy(),
        so we just copy them as-is to each processor's triSurface directory.
        """
        import glob

        tri_surface_dir = os.path.join(case_dir, "constant", "triSurface")
        closeness_files = glob.glob(os.path.join(tri_surface_dir, "*.stl.closeness.*"))

        if not closeness_files:
            logger.warning("No closeness files found - span refinement may not work")
            return

        logger.info(f"Distributing {len(closeness_files)} closeness files to {n_proc} processor directories...")

        for i in range(n_proc):
            proc_tri_dir = os.path.join(case_dir, f"processor{i}", "constant", "triSurface")
            os.makedirs(proc_tri_dir, exist_ok=True)

            for src_file in closeness_files:
                dst_file = os.path.join(proc_tri_dir, os.path.basename(src_file))
                try:
                    shutil.copy2(src_file, dst_file)
                except OSError as e:
                    logger.warning(f"Could not copy {src_file} to processor{i}: {e}")

        logger.info("Closeness files distributed to processor directories")

    def _cleanup_processor_directories(self, case_dir: str):
        """
        Remove processor* directories after parallel meshing to save disk space.

        After reconstructPar -constant, the mesh is consolidated in constant/polyMesh
        and the processor directories are no longer needed.
        """
        import glob

        processor_dirs = glob.glob(os.path.join(case_dir, "processor*"))

        if not processor_dirs:
            return

        # Calculate total size before deletion
        total_size = 0
        for proc_dir in processor_dirs:
            for dirpath, dirnames, filenames in os.walk(proc_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        pass

        # Remove directories
        removed_count = 0
        for proc_dir in processor_dirs:
            try:
                shutil.rmtree(proc_dir)
                removed_count += 1
            except OSError as e:
                logger.warning(f"Could not remove {proc_dir}: {e}")

        # Format size for display
        if total_size > 1024 * 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024 * 1024):.1f} GB"
        elif total_size > 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{total_size / 1024:.1f} KB"

        logger.info(f"🧹 Cleaned up {removed_count} processor directories (freed {size_str})")

    def _override_decompose_par_dict(self, case_dir: str, n_subdomains: int):
        """
        Temporarily modify decomposeParDict to use a specific number of subdomains.

        This allows different processor counts for meshing vs solving:
        - Parallel meshing: uses SNAPPY_SETTINGS.nProcessors
        - Parallel solving: uses run_settings.subdomains

        Args:
            case_dir: Path to OpenFOAM case directory
            n_subdomains: Number of subdomains to set
        """
        import re

        decompose_dict_path = os.path.join(case_dir, "system", "decomposeParDict")

        if not os.path.exists(decompose_dict_path):
            logger.warning(f"decomposeParDict not found at {decompose_dict_path}")
            return

        try:
            # Read current file
            with open(decompose_dict_path, 'r') as f:
                content = f.read()

            # Replace numberOfSubdomains
            content = re.sub(
                r'numberOfSubdomains\s+\d+;',
                f'numberOfSubdomains  {n_subdomains};',
                content
            )

            # Replace n coefficients (for simple and hierarchical methods)
            content = re.sub(
                r'\bn\s+\(1 1 \d+\);',
                f'n               (1 1 {n_subdomains});',
                content
            )

            # Write back
            with open(decompose_dict_path, 'w') as f:
                f.write(content)

            logger.info(f"Updated decomposeParDict: numberOfSubdomains = {n_subdomains}")

        except Exception as e:
            logger.warning(f"Could not update decomposeParDict: {e}")

class ExecuteSolverTask(Task):
    """Runs the OpenFOAM 12 solver (foamRun with incompressibleFluid)."""

    def execute(self, context: dict) -> bool:
        """Run the OpenFOAM solver with pre-flight validation."""
        logger.info("Executing OpenFOAM 12 solver...")
        case_dir = context["case_directory"]
        run_settings = self.config.get("run_settings", {})

        # Pre-flight: check that boundary conditions are physically valid
        self._preflight_check(case_dir)

        solver_cmd = self.config["simulation_control"]["controlDict"].get("application", "foamRun")
        logger.info(f"Using OpenFOAM 12 solver: {solver_cmd} (incompressibleFluid)")

        try:
            if run_settings.get("solution_type") == "parallel":
                n_proc = run_settings.get("subdomains", 1)
                run_command(self.config, ["decomposePar", "-force"], case_dir, "log.decomposePar")
                run_command(self.config, ["mpirun", "-np", str(n_proc), solver_cmd, "-parallel"], case_dir, "log.solver")

                # Handle reconstruction based on skip_reconstruction flag
                skip_reconstruction = run_settings.get("skip_reconstruction", False)
                if skip_reconstruction:
                    logger.info("⏭️  Skipping reconstruction (skip_reconstruction=True)")
                    logger.info("📂 Case remains in decomposed state (processor directories)")
                    logger.info("💡 Use 'reconstructPar' manually if needed, or run: python run_patient.py <patient> --step reconstruct")
                    context["case_decomposed"] = True  # Flag for downstream tasks
                else:
                    logger.info("🔄 Reconstructing case...")
                    run_command(self.config, ["reconstructPar"], case_dir, "log.reconstructPar")
                    context["case_decomposed"] = False

                    # Clean up processor directories to save disk space
                    cleanup_processors = run_settings.get("cleanup_processors", True)
                    if cleanup_processors:
                        self._cleanup_processor_directories(case_dir)
            else:
                run_command(self.config, [solver_cmd], case_dir, "log.solver")
                context["case_decomposed"] = False

        except CommandExecutionError as e:
            logger.error(f"Solver execution failed: {e}")
            # Check log for specific failure reason
            diagnosis = self._diagnose_solver_failure(case_dir)
            if diagnosis:
                logger.error(f"Diagnosis: {diagnosis}")
                Logger.console(f"     SOLVER FAILED: {diagnosis}")
            return False

        # Post-solver health check: scan log for hidden divergence
        diagnosis = self._diagnose_solver_failure(case_dir)
        if diagnosis:
            logger.warning(f"Solver completed but with issues: {diagnosis}")
            Logger.console(f"     WARNING: {diagnosis}")
        else:
            logger.info("Solver execution completed successfully.")
            Logger.console("     Solver completed")
        return True

    def _diagnose_solver_failure(self, case_dir: str) -> str:
        """
        Scan solver log for divergence indicators and return a human-readable diagnosis.

        Checks for:
        - NaN / Infinity in solution fields
        - FOAM FATAL ERROR
        - Extreme Courant numbers
        - Solver not converging (residuals stuck)
        - Very few timesteps completed

        Returns:
            Diagnosis string, or empty string if log looks healthy.
        """
        log_path = os.path.join(case_dir, "logs", "log.solver")
        if not os.path.exists(log_path):
            return ""

        try:
            # Read last portion of log (divergence happens at the end)
            with open(log_path, "r", errors="replace") as f:
                # Read last 500KB to catch end-of-run issues
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 512_000))
                tail = f.read()

            # Check for fatal indicators
            if "FOAM FATAL ERROR" in tail or "FOAM FATAL IO ERROR" in tail:
                # Extract the error message
                m = re.search(r'FOAM FATAL (?:IO )?ERROR[:\s]*\n(.*?)(?:\n\n|\nFrom )', tail, re.DOTALL)
                msg = m.group(1).strip()[:200] if m else "see log.solver"
                return f"OpenFOAM fatal error: {msg}"

            if "nan" in tail.lower() or "Nan" in tail:
                # Find which field diverged
                nan_fields = set()
                for m in re.finditer(r'Solving for (\w+).*?Initial residual = [Nn]a[Nn]', tail):
                    nan_fields.add(m.group(1))
                if nan_fields:
                    return f"Divergence detected (NaN in: {', '.join(nan_fields)})"
                return "Divergence detected (NaN in solution)"

            if "Floating point exception" in tail:
                return "Floating point exception (likely divergence)"

            # Check for very high Courant numbers (sign of instability)
            co_values = re.findall(r'Courant Number mean:\s*([\d.e+-]+)\s*max:\s*([\d.e+-]+)', tail)
            if co_values:
                last_co_max = float(co_values[-1][1])
                if last_co_max > 100:
                    return f"Extreme Courant number ({last_co_max:.0f}) - likely unstable"

            # Check if simulation actually progressed
            time_matches = re.findall(r'^Time = ([\d.e+-]+)', tail, re.MULTILINE)
            if time_matches:
                end_time_cfg = self.config.get("simulation_control", {}).get("controlDict", {}).get("endTime", 0)
                last_time = float(time_matches[-1])
                if end_time_cfg and last_time < float(end_time_cfg) * 0.1:
                    return f"Solver stopped early at t={last_time}s (target: {end_time_cfg}s)"

        except Exception as e:
            logger.debug(f"Could not analyze solver log: {e}")

        return ""

    def _preflight_check(self, case_dir: str):
        """
        Quick sanity checks before launching the solver.

        Catches common misconfigurations that would cause divergence,
        giving the user an actionable warning instead of a cryptic OpenFOAM crash.
        """
        import re

        # Check controlDict endTime > 0
        control_dict = os.path.join(case_dir, "system", "controlDict")
        if os.path.exists(control_dict):
            try:
                content = open(control_dict).read()
                m = re.search(r'endTime\s+([\d.e+-]+)', content)
                if m and float(m.group(1)) <= 0:
                    logger.warning("endTime is 0 or negative -- solver will exit immediately")
            except Exception:
                pass

        # Check 0/U exists (boundary conditions written)
        u_file = os.path.join(case_dir, "0", "U")
        if not os.path.exists(u_file):
            logger.warning("0/U not found -- boundary conditions may not be set up")
            logger.warning("Run --steps boundary first, or check setup:bc output")

        # Check mesh exists
        poly_mesh = os.path.join(case_dir, "constant", "polyMesh", "points")
        if not os.path.exists(poly_mesh):
            logger.warning("constant/polyMesh/points not found -- mesh may not exist")
            logger.warning("Run --steps mesh first")

    def _cleanup_processor_directories(self, case_dir: str):
        """
        Remove processor* directories after reconstruction to save disk space.

        After reconstructPar, the fields are consolidated in time directories
        and the processor directories are no longer needed.
        """
        import glob

        processor_dirs = glob.glob(os.path.join(case_dir, "processor*"))

        if not processor_dirs:
            return

        # Calculate total size before deletion
        total_size = 0
        for proc_dir in processor_dirs:
            for dirpath, dirnames, filenames in os.walk(proc_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        pass

        # Remove directories
        removed_count = 0
        for proc_dir in processor_dirs:
            try:
                shutil.rmtree(proc_dir)
                removed_count += 1
            except OSError as e:
                logger.warning(f"Could not remove {proc_dir}: {e}")

        # Format size for display
        if total_size > 1024 * 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024 * 1024):.1f} GB"
        elif total_size > 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{total_size / 1024:.1f} KB"

        logger.info(f"🧹 Cleaned up {removed_count} processor directories (freed {size_str})")


class ExecuteReconstructionTask(Task):
    """Reconstructs parallel case from processor directories."""

    def execute(self, context: dict) -> bool:
        """Reconstruct decomposed OpenFOAM case."""
        logger.info("Reconstructing case from processor directories...")
        case_dir = context["case_directory"]
        run_settings = self.config.get("run_settings", {})

        # Check if case is actually decomposed
        import glob
        processor_dirs = glob.glob(os.path.join(case_dir, "processor*"))
        if not processor_dirs:
            logger.warning("No processor directories found - case may already be reconstructed")
            return True

        try:
            # Run reconstructPar for all times
            run_command(self.config, ["reconstructPar"], case_dir, "log.reconstructPar")
            logger.info("✅ Case reconstructed successfully")
            context["case_decomposed"] = False
            return True

        except CommandExecutionError as e:
            logger.error(f"Reconstruction failed: {e}")
            return False


class ExecutePostProcessingTask(Task):
    """Runs the pvbatch post-processing script."""

    def execute(self, context: dict) -> bool:
        """This task contains the execution logic from your original run_postprocessing method."""
        logger.info("Executing post-processing script...")
        case_dir = context["case_directory"]
        pp_config = self.config.get("post_processing", {})

        # Setup environment variables for the script
        os.environ["CASE_PATH"] = case_dir

        # Try to find pvbatch executable
        pvbatch_exe = pp_config.get("pvbatch_exe")
        if not pvbatch_exe:
            # Try to find pvbatch in PATH
            import shutil as sh
            pvbatch_exe = sh.which("pvbatch")
            if not pvbatch_exe:
                logger.error("pvbatch executable not found in PATH")
                logger.error("Install ParaView: sudo apt-get install paraview")
                logger.error("Or set 'pvbatch_exe' in config.json post_processing section")
                return False
            logger.info(f"Found pvbatch: {pvbatch_exe}")

        if not os.path.exists(pvbatch_exe):
            logger.error(f"pvbatch executable not found at path: {pvbatch_exe}")
            return False

        # Find the post_processor.py script
        # Look in src/aortacfd_lib/ relative to current directory
        script_path = os.path.join(os.getcwd(), "src", "aortacfd_lib", "post_processor.py")
        if not os.path.exists(script_path):
            # Try alternative path
            script_path = os.path.join("aortacfd_lib", "post_processor.py")

        if not os.path.exists(script_path):
            logger.error(f"post_processor.py not found at: {script_path}")
            return False

        logger.info(f"Using post-processor script: {script_path}")
        logger.info(f"Case directory: {case_dir}")

        try:
            # Run pvbatch with the case directory as argument
            cmd = [pvbatch_exe, script_path, case_dir]
            logger.info(f"Running: {' '.join(cmd)}")

            run_command(self.config, cmd, ".", "log.postProcessing")
        except CommandExecutionError as e:
            logger.error(f"Post-processing failed: {e}")
            logger.warning("You can run post-processing manually:")
            logger.warning(f"  cd {case_dir}")
            logger.warning(f"  pvbatch {script_path}")
            return False

        logger.info("Post-processing completed successfully.")
        logger.info(f"Check results in: {case_dir}/Images/")
        return True


class ExecuteHemodynamicsTask(Task):
    """
    Compute hemodynamic metrics: WSS, TAWSS, OSI, RRT, pressure drop.

    This task can be run:
    1. After simulation completes (uses runtime function object data)
    2. As standalone post-processing (runs postProcess -func wallShearStress if needed)

    For pulsatile flow: Computes TAWSS, OSI, RRT from fieldAverage data
    For steady flow: Computes steady WSS and pressure drop only
    """

    def execute(self, context: dict) -> bool:
        """Execute hemodynamics post-processing."""
        logger.info("=" * 60)
        logger.info("HEMODYNAMICS ANALYSIS")
        logger.info("=" * 60)

        case_dir = context["case_directory"]

        # Determine output directory (reports folder)
        run_dir = os.path.dirname(case_dir)  # Parent of openfoam/
        reports_dir = os.path.join(run_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        try:
            from aortacfd_lib.hemodynamics_postprocessor import (
                HemodynamicsPostProcessor,
                run_hemodynamics_analysis
            )

            # Run complete analysis
            results = run_hemodynamics_analysis(case_dir, self.config, reports_dir)

            # Log summary
            logger.info("-" * 60)
            logger.info("HEMODYNAMICS SUMMARY")
            logger.info("-" * 60)
            logger.info(f"  Inlet type: {results.inlet_type}")

            if results.wss_mean > 0:
                logger.info(f"  WSS max/mean: {results.wss_max:.4f} / {results.wss_mean:.4f} Pa")

            if results.is_pulsatile and results.tawss_mean > 0:
                logger.info(f"  TAWSS max/mean: {results.tawss_max:.4f} / {results.tawss_mean:.4f} Pa")
                logger.info(f"  OSI max/mean: {results.osi_max:.4f} / {results.osi_mean:.4f}")
                logger.info(f"  RRT max/mean: {results.rrt_max:.4f} / {results.rrt_mean:.4f} Pa⁻¹")

            if results.pressure_drop_mmhg:
                logger.info("  Pressure drops:")
                for outlet, dp in results.pressure_drop_mmhg.items():
                    logger.info(f"    → {outlet}: {dp:.2f} mmHg")

            logger.info("-" * 60)
            logger.info(f"Full report: {reports_dir}/hemodynamics_report.txt")

            # Clean console summary
            if results.is_pulsatile and results.tawss_mean > 0:
                Logger.console(f"     TAWSS: {results.tawss_mean:.2f} Pa (mean), OSI: {results.osi_mean:.3f}")
            elif results.wss_mean > 0:
                Logger.console(f"     WSS: {results.wss_mean:.2f} Pa (mean)")
            return True

        except ImportError as e:
            logger.error(f"Failed to import hemodynamics module: {e}")
            logger.warning("Hemodynamics analysis skipped.")
            return False
        except Exception as e:
            logger.error(f"Hemodynamics analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return False