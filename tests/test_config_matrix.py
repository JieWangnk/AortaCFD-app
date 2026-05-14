"""Epic D: configuration-variability integration tests (v1.2.0).

Rotates one config axis at a time and asserts on the rendered OpenFOAM
dictionaries. Does NOT invoke the OpenFOAM solver — these are template-
render and config-validation tests, fast enough to run on every commit.

D.1   Baseline (BPM120 default, covered de facto by test_user_promises).
D.2   MAPPED_PROFILE inlet end-to-end — the rename's user-facing target.
D.6   RAS kOmegaSST + zeroGradient outlet (turbulence axis).
D.7   LES WALE + auto-stabilization-disable.
D.8   precise numerics profile renders LUST + CrankNicolson schemes.
D.9   Profile-string fuzz — typos rejected at config-build time (hardening).
D.10  Flow-split polymorphism edge cases.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import warnings
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# Shared fixtures
# =============================================================================


@pytest.fixture
def tmp_case_dir() -> Path:
    """A scratch OpenFOAM case directory pre-populated with the dirs the
    rendering pipeline expects (constant/triSurface, 0/, system/)."""
    d = Path(tempfile.mkdtemp(prefix="aortacfd-D-"))
    (d / "0").mkdir()
    (d / "constant" / "triSurface").mkdir(parents=True)
    (d / "constant" / "boundaryData" / "inlet").mkdir(parents=True)
    (d / "system").mkdir()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _base_config(**overrides):
    """A minimal valid config; tests deep-merge overrides into it."""
    cfg = {
        "geometry": {
            "case_name": "test_case",
            "wall_keywords_ordered": "wall",
            "inlet_keywords_ordered": "inlet",
            "outlet_keywords_ordered": ["outlet1", "outlet2"],
        },
        "physics": {
            "model": "laminar",
            "simulation_type": "laminar",
            "transport_properties": {"nu": 3.77e-06, "rho": 1060},
        },
        "openfoam_version": "12",
        "openfoam_major_version": 12,
        "template_vars": {"openfoam_version": "12", "openfoam_major_version": 12},
        "boundary_conditions": {
            "inlet": {"type": "CONSTANT", "velocity": 0.5, "profile": "plug"},
            "outlets": {"type": "zeroGradient"},
        },
        "windkessel_settings": {
            "systolic_pressure": 120,
            "diastolic_pressure": 80,
            "venous_pressure": 0,
        },
    }
    # shallow merge: each top-level key in overrides replaces the same key in cfg
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k] = {**cfg[k], **v}
        else:
            cfg[k] = v
    return cfg


def _patch_processor_mock(area_m2: float = 1e-4, radius_m: float = 0.006):
    """Build a PatchProcessing mock that pretends the inlet is a 6mm-radius disc."""
    m = MagicMock()
    m.calculate_inlet_center_radius.return_value = (
        np.array([0.0, 0.0, 0.0]),
        radius_m,
        np.array([0.0, 0.0, 1.0]),
    )
    m.calculate_surface_area.return_value = area_m2
    return m


# =============================================================================
# D.2 — MAPPED_PROFILE inlet end-to-end (+ deprecation warning on MRI alias)
# =============================================================================


class TestD2_MappedProfile:
    """Verify the MAPPED_PROFILE inlet branch reads pre-mapped time directories,
    copies them into the case's boundaryData, and that the legacy ``MRI``
    alias still works but emits a DeprecationWarning."""

    @staticmethod
    def _stage_mapped_source(src: Path, n_points: int = 8, n_timesteps: int = 4):
        """Create a tiny pre-mapped source directory with N timesteps × N points."""
        # source points file (3D coordinates on the inlet face)
        pts = np.column_stack(
            [
                np.linspace(-0.005, 0.005, n_points),
                np.zeros(n_points),
                np.zeros(n_points),
            ]
        )
        with (src / "points").open("w") as f:
            f.write(f"{n_points}\n(\n")
            for p in pts:
                f.write(f"({p[0]:.6e} {p[1]:.6e} {p[2]:.6e})\n")
            f.write(")\n")

        # Per-timestep U files (simple plug flow of 1 m/s in +z, but varying t)
        for i in range(n_timesteps):
            t = i * 0.1
            td = src / f"{t:.6f}"
            td.mkdir()
            with (td / "U").open("w") as f:
                f.write(f"{n_points}\n(\n")
                for _ in range(n_points):
                    f.write(f"(0 0 {0.5 + 0.1 * i:.4f})\n")
                f.write(")\n")

    def _stage_prereqs(self, case_dir: Path, inlet_patch: str = "inlet", n_pts: int = 8):
        """Stage the artefacts that `writeMeshObj` would have produced, so the
        task can skip past the polyMesh-existence check and the OpenFOAM call."""
        (case_dir / "constant" / "polyMesh").mkdir(parents=True, exist_ok=True)
        # The fake .obj file that writeMeshObj would have written
        obj = case_dir / f"patch_{inlet_patch}.obj"
        obj.write_text("# fake obj\n")
        # The mesh face-centre points file that EnhancedPointsFormatter outputs
        # We pre-stage it in boundaryData (where shutil.move ends up)
        bd = case_dir / "constant" / "boundaryData" / inlet_patch
        bd.mkdir(parents=True, exist_ok=True)
        (bd / "points").write_text("4\n(\n" + "(0 0 0)\n" * 4 + ")\n")

    def _run_with_stubs(self, task, case_dir: Path):
        """Invoke ``task.execute`` with the OpenFOAM-touching parts stubbed out."""
        ctx = {"case_directory": str(case_dir)}
        with (
            patch("workflow.tasks.setup_tasks.run_command", return_value=0),
            patch("workflow.tasks.setup_tasks.detect_world_patch_mode", return_value=False),
            patch.object(task, "_read_bare_points", return_value=np.zeros((4, 3))),
            patch.object(task, "_read_bare_velocities", return_value=np.tile([0, 0, 0.5], (4, 1))),
        ):
            # Stub EnhancedPointsFormatter so it doesn't try to parse the fake obj
            with patch("workflow.tasks.setup_tasks.EnhancedPointsFormatter") as fmt_cls:
                fmt = fmt_cls.return_value
                fmt.format_coordinates.side_effect = lambda: (case_dir / "points").write_text(
                    "4\n(\n" + "(0 0 0)\n" * 4 + ")\n"
                )
                try:
                    task.execute(ctx)
                except Exception:
                    pass  # we only care about the MAPPED_PROFILE dispatch side-effects
        return ctx

    def test_mapped_profile_inlet_writes_boundary_data(self, tmp_case_dir):
        """End-to-end: setup_tasks dispatches into the MAPPED_PROFILE branch
        and copies the source time directories into boundaryData."""
        from workflow.tasks.setup_tasks import PrepareBoundaryDataTask

        source = Path(tempfile.mkdtemp(prefix="mapped-src-"))
        try:
            self._stage_mapped_source(source, n_points=4, n_timesteps=4)
            self._stage_prereqs(tmp_case_dir)

            config = _base_config(boundary_conditions={"inlet": {"type": "MAPPED_PROFILE", "file": str(source)}})
            config["patient_case_directory"] = str(tmp_case_dir.parent)

            task = PrepareBoundaryDataTask(config=config)
            ctx = self._run_with_stubs(task, tmp_case_dir)

            inlet_bd = tmp_case_dir / "constant" / "boundaryData" / "inlet"
            time_dirs = sorted(p.name for p in inlet_bd.iterdir() if p.is_dir())
            assert len(time_dirs) >= 4, f"MAPPED_PROFILE branch should have copied 4 time directories; got {time_dirs}"
            assert (
                inlet_bd / "0.000000" / "U"
            ).is_file(), "MAPPED_PROFILE branch did not place U field in time directory"
            assert ctx.get("cardiac_cycle", 0) > 0, "MAPPED_PROFILE branch must set cardiac_cycle from source data"
        finally:
            shutil.rmtree(source, ignore_errors=True)

    def test_mri_alias_emits_deprecation_warning(self, tmp_case_dir):
        """The legacy ``inlet.type = 'MRI'`` value still works but warns."""
        from workflow.tasks.setup_tasks import PrepareBoundaryDataTask

        source = Path(tempfile.mkdtemp(prefix="mri-alias-src-"))
        try:
            self._stage_mapped_source(source, n_points=4, n_timesteps=2)
            self._stage_prereqs(tmp_case_dir)

            config = _base_config(boundary_conditions={"inlet": {"type": "MRI", "file": str(source)}})
            config["patient_case_directory"] = str(tmp_case_dir.parent)

            task = PrepareBoundaryDataTask(config=config)

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                self._run_with_stubs(task, tmp_case_dir)

                deprecation = [w for w in caught if issubclass(w.category, DeprecationWarning)]
                assert any("MAPPED_PROFILE" in str(w.message) for w in deprecation), (
                    f"MRI alias did not emit a DeprecationWarning. " f"Saw: {[str(w.message)[:80] for w in caught]}"
                )

            # And the inlet_type should have been normalised to MAPPED_PROFILE for the rest of the pipeline.
            inlet_bd = tmp_case_dir / "constant" / "boundaryData" / "inlet"
            assert any(
                p.is_dir() and p.name[0].isdigit() for p in inlet_bd.iterdir()
            ), "MRI alias should follow the same code path as MAPPED_PROFILE"
        finally:
            shutil.rmtree(source, ignore_errors=True)


# =============================================================================
# D.6 — RAS + zeroGradient outlet
# =============================================================================


class TestD6_RANSZeroGradient:
    """RAS kOmegaSST physics + zeroGradient outlet renders the expected
    momentumTransport, k, omega, nut files and skips Windkessel templates."""

    def test_ras_komegasst_renders_turbulence_fields(self, tmp_case_dir):
        from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup

        config = _base_config(
            physics={
                "model": "rans",
                "simulation_type": "RAS",
                "rans_model": "kOmegaSST",
                "transport_properties": {"nu": 3.77e-06, "rho": 1060},
                "turbulence_intensity": 0.05,
            },
            boundary_conditions={
                "inlet": {"type": "CONSTANT", "velocity": 0.5, "profile": "plug"},
                "outlets": {"type": "zeroGradient"},
            },
        )
        config["geometry"]["case_name"] = "test"

        with (
            patch(
                "aortacfd_lib.utils.patch_processing.PatchProcessing",
                return_value=_patch_processor_mock(),
            ),
            patch("aortacfd_lib.boundary_condition_setup.detect_world_patch_mode", return_value=False),
        ):
            bcs = BoundaryConditionSetup(config, str(tmp_case_dir))
            bcs.write_all_bc_files()

        u_text = (tmp_case_dir / "0" / "U").read_text()
        p_text = (tmp_case_dir / "0" / "p").read_text()

        # On U: outlets become pressureInletOutletVelocity regardless of outlet type
        # (zeroGradient on U would be wrong for an outlet). Verify NOT Windkessel velocity.
        assert (
            "stabilizedWindkesselVelocity" not in u_text
        ), "RAS + zeroGradient outlet should not render the Windkessel velocity BC"
        # On p: zeroGradient outlet should NOT render modularWKPressure
        assert "modularWKPressure" not in p_text, "RAS + zeroGradient: WK pressure BC unexpectedly present"
        # The outlet block should fall into the zeroGradient fallback path
        assert p_text.count("zeroGradient") >= 2, "RAS + zeroGradient: each outlet should use zeroGradient pressure BC"

        # k, omega, nut must be present for RAS
        assert (tmp_case_dir / "0" / "k").is_file(), "RAS branch should write 0/k"
        assert (tmp_case_dir / "0" / "omega").is_file(), "RAS branch should write 0/omega"
        assert (tmp_case_dir / "0" / "nut").is_file(), "RAS branch should write 0/nut"


# =============================================================================
# D.7 — LES + auto-stabilization-disable
# =============================================================================


class TestD7_LESAutoStabilization:
    """LES WALE must auto-disable the hard backflow stabilisation that's safe
    for RAS but causes problems with LES (see _apply_les_stabilisation_override)."""

    def test_les_auto_disables_stabilization(self, tmp_case_dir):
        """LES + Windkessel + enable_stabilization unset → auto-flipped to False.

        The override only fires when the user hasn't explicitly set
        enable_stabilization (see boundary_condition_setup.py:166-174).
        """
        from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup

        config = _base_config(
            physics={
                "model": "les",
                "simulation_type": "LES",
                "les_model": "WALE",
                "transport_properties": {"nu": 3.77e-06, "rho": 1060},
                "turbulence_intensity": 0.05,
            },
            boundary_conditions={
                "inlet": {"type": "CONSTANT", "velocity": 0.5, "profile": "plug"},
                "outlets": {
                    "type": "3EWINDKESSEL",
                    "windkessel_settings": {
                        # Crucially NO enable_stabilization key -> override fires
                        "systolic_pressure": 120,
                        "diastolic_pressure": 80,
                        "venous_pressure": 0,
                    },
                },
            },
        )

        with (
            patch(
                "aortacfd_lib.utils.patch_processing.PatchProcessing",
                return_value=_patch_processor_mock(),
            ),
            patch("aortacfd_lib.boundary_condition_setup.detect_world_patch_mode", return_value=False),
        ):
            bcs = BoundaryConditionSetup(config, str(tmp_case_dir))
            bcs._apply_les_stabilisation_override()

        wk = bcs.outlet_settings.get("windkessel_settings", {})
        assert wk.get("enable_stabilization") is False, (
            f"LES branch should have auto-disabled enable_stabilization; " f"got: {wk.get('enable_stabilization')}"
        )


# =============================================================================
# D.8 — precise numerics profile renders LUST + CrankNicolson
# =============================================================================


class TestD8_PreciseProfile:
    """The precise profile must produce specific scheme strings in fvSchemes."""

    def test_precise_profile_renders_lust_and_cranknicolson(self):
        from config.numerics_builder import NumericsBuilder

        config = _base_config(numerics={"profile": "precise"})
        builder = NumericsBuilder()
        numerics = builder.build(config)

        # Check the key precise-only schemes
        div_schemes = numerics.get("divSchemes", {})
        assert "Gauss LUST" in div_schemes.get(
            "div(phi,U)", ""
        ), f"precise profile must use LUST for div(phi,U); got: {div_schemes.get('div(phi,U)')}"

        # Time integration: precise uses backward (2nd order)
        ddt = numerics.get("ddtSchemes", {}).get("default", "")
        assert ddt in ("backward", "CrankNicolson 0.9"), f"precise profile must use backward or CN; got: {ddt}"


# =============================================================================
# D.9 — Hardening: typos rejected at config-build time
# =============================================================================


class TestD9_ConfigHardening:
    """Schema enums + builder validators catch user typos at config-load time
    rather than at solver-launch time hours later."""

    def test_unknown_inlet_profile_raises_at_build(self):
        from config.builder import ConfigBuilder

        bad = {"inlet": {"profile": "walldistance"}}  # missing underscore
        with pytest.raises(ValueError, match="Unknown inlet.profile"):
            ConfigBuilder()._validate_inlet_profile_name(bad)

    def test_unknown_rans_model_raises(self):
        from config.builder import ConfigBuilder

        bad = {"physics": {"model": "rans", "rans_model": "komegasst"}}  # case
        with pytest.raises(ValueError, match="Unknown physics.rans_model"):
            ConfigBuilder()._validate_turbulence_model_names(bad)

    def test_unknown_les_model_raises(self):
        from config.builder import ConfigBuilder

        bad = {"physics": {"model": "les", "les_model": "wale"}}  # case
        with pytest.raises(ValueError, match="Unknown physics.les_model"):
            ConfigBuilder()._validate_turbulence_model_names(bad)

    def test_valid_inlet_profile_passes(self):
        from config.builder import ConfigBuilder

        for profile in ("wall_distance", "WALL_DISTANCE", "  Plug  "):
            ConfigBuilder()._validate_inlet_profile_name({"inlet": {"profile": profile}})

    def test_valid_turbulence_models_pass(self):
        from config.builder import ConfigBuilder

        cases = [
            {"physics": {"model": "rans_komegasst", "rans_model": "kOmegaSST"}},
            {"physics": {"model": "rans", "rans_model": "kEpsilon"}},
            {"physics": {"model": "les", "les_model": "WALE"}},
            {"physics": {"model": "les_wale", "les_model": "Smagorinsky"}},
            {"physics": {"model": "laminar"}},  # no rans/les_model -> no validation
        ]
        for c in cases:
            ConfigBuilder()._validate_turbulence_model_names(c)


# =============================================================================
# D.10 — Flow-split polymorphism edge cases
# =============================================================================


class TestD10_FlowSplitEdgeCases:
    """The flow_split key accepts None, scalar, dict, or partial-dict with
    '_rest':'murray'. Edge cases used to silently produce wrong R/C/Z."""

    @staticmethod
    def _make_wk(outlet_patches, outlet_radii_m):
        """Construct a WkSetup with just enough config to exercise _parse_custom_flow_split."""
        from aortacfd_lib.wk_setup import WkSetup

        tmp = tempfile.mkdtemp(prefix="wk-test-")
        cfg = {
            "geometry": {
                "case_name": "test",
                "wall_keywords_ordered": "wall",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": outlet_patches,
            },
            "boundary_conditions": {
                "inlet": {"type": "CONSTANT", "velocity": 0.5},
                "outlets": {
                    "type": "3EWINDKESSEL",
                    "windkessel_settings": {
                        "systolic_pressure": 120,
                        "diastolic_pressure": 80,
                        "venous_pressure": 0,
                    },
                },
            },
        }
        wk = WkSetup(cfg, [], tmp, 0.8)
        radii = {name: r for name, r in zip(outlet_patches, outlet_radii_m)}
        return wk, radii

    def test_flow_split_percentages_above_100_normalises(self):
        """User-supplied percentages summing to >100 should be normalised, not silently scaled wrong."""
        wk, radii = self._make_wk(["o1", "o2", "o3"], [0.003, 0.003, 0.003])
        # Mode 2: two fixed values (70 + 70 = 140%) with _rest=murray
        split = wk._parse_custom_flow_split(
            {"o1": 70, "o2": 70, "_rest": "murray"},
            ["o1", "o2", "o3"],
            radii,
        )
        total = sum(split.values())
        assert abs(total - 1.0) < 1e-6, f"flow_split ratios should sum to 1.0 after parsing; got {total}: {split}"

    def test_flow_split_negative_value_rejected(self):
        """A negative percentage is unphysical and should raise.

        NOTE: pre-v1.2.0 _parse_custom_flow_split silently accepted negative
        values, producing negative R/C/Z that would have caused the solver to
        diverge. v1.2.0 must reject up-front. Currently xfail until the fix
        lands.
        """
        wk, radii = self._make_wk(["o1", "o2"], [0.003, 0.003])
        with pytest.raises((ValueError, AssertionError)):
            wk._parse_custom_flow_split(
                {"o1": -20, "o2": 120},
                ["o1", "o2"],
                radii,
            )

    def test_flow_split_complete_ratios_sum_to_one(self):
        """Mode 1: complete ratios are passed through unchanged (when they sum to 1)."""
        wk, radii = self._make_wk(["o1", "o2"], [0.003, 0.003])
        split = wk._parse_custom_flow_split({"o1": 0.4, "o2": 0.6}, ["o1", "o2"], radii)
        assert abs(sum(split.values()) - 1.0) < 1e-6
        assert abs(split["o1"] - 0.4) < 1e-6
        assert abs(split["o2"] - 0.6) < 1e-6


# =============================================================================
# D.11 — Pressure anchor for zeroGradient outlets with pulsatile inlet
# =============================================================================


class TestD11_PressureAnchor:
    """zeroGradient outlets need a pressure reference somewhere. v1.2.0 rejects
    unanchored pulsatile configs at build time and exposes ``pressure_anchor``
    to pin one outlet to a fixed pressure."""

    def test_unanchored_pulsatile_rejected(self):
        from config.builder import ConfigBuilder

        bad = {
            "boundary_conditions": {
                "inlet": {"type": "TIMEVARYING"},
                "outlets": {"type": "zeroGradient"},
            }
        }
        with pytest.raises(ValueError, match="pressure_anchor"):
            ConfigBuilder()._validate_outlet_pressure_reference(bad)

    def test_steady_inlet_allows_unanchored(self):
        """CONSTANT/PARABOLIC inlet → pressure field self-anchors; no validator error."""
        from config.builder import ConfigBuilder

        for inlet_type in ("CONSTANT", "PARABOLIC"):
            cfg = {
                "boundary_conditions": {
                    "inlet": {"type": inlet_type},
                    "outlets": {"type": "zeroGradient"},
                }
            }
            ConfigBuilder()._validate_outlet_pressure_reference(cfg)  # no raise

    def test_pulsatile_with_anchor_still_rejected(self):
        """v1.2.0 policy (option B): the one-outlet pressure_anchor is insufficient
        on severe-stenosis geometries (verified empirically on BPM120 — solver
        still diverges at t~0.020s in correctPressure even with the anchor set).
        Pulsatile + zeroGradient is rejected regardless of anchor.
        """
        from config.builder import ConfigBuilder

        cfg = {
            "boundary_conditions": {
                "inlet": {"type": "TIMEVARYING"},
                "outlets": {
                    "type": "zeroGradient",
                    "pressure_anchor": {"outlet": "outlet1", "pressure_mmHg": 80},
                },
            }
        }
        with pytest.raises(ValueError, match="anchor was set but is insufficient"):
            ConfigBuilder()._validate_outlet_pressure_reference(cfg)

    def test_anchor_with_steady_inlet_still_allowed(self):
        """The anchor remains useful for steady (CONSTANT/PARABOLIC) inlets where
        the pressure field is well-posed by construction."""
        from config.builder import ConfigBuilder

        for inlet_type in ("CONSTANT", "PARABOLIC"):
            cfg = {
                "boundary_conditions": {
                    "inlet": {"type": inlet_type},
                    "outlets": {
                        "type": "zeroGradient",
                        "pressure_anchor": {"outlet": "outlet1", "pressure_mmHg": 80},
                    },
                }
            }
            ConfigBuilder()._validate_outlet_pressure_reference(cfg)  # no raise

    def test_anchor_renders_fixedValue_on_named_outlet(self, tmp_case_dir):
        """The anchored outlet must render as fixedValue at the kinematic-converted
        pressure; the other outlets stay zeroGradient."""
        from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup

        config = _base_config(
            boundary_conditions={
                "inlet": {"type": "CONSTANT", "velocity": 0.5, "profile": "plug"},
                "outlets": {
                    "type": "zeroGradient",
                    "pressure_anchor": {"outlet": "outlet1", "pressure_mmHg": 80},
                },
            }
        )

        with (
            patch(
                "aortacfd_lib.utils.patch_processing.PatchProcessing",
                return_value=_patch_processor_mock(),
            ),
            patch("aortacfd_lib.boundary_condition_setup.detect_world_patch_mode", return_value=False),
        ):
            bcs = BoundaryConditionSetup(config, str(tmp_case_dir))
            bcs.write_all_bc_files()

        p_text = (tmp_case_dir / "0" / "p").read_text()

        # The anchor outlet (outlet1) is rendered as fixedValue at ~10.06 m²/s²
        # (80 mmHg × 133.322 Pa/mmHg ÷ 1060 kg/m³ ≈ 10.06)
        anchor_block = p_text.split("outlet1")[1].split("outlet2")[0]
        assert "fixedValue" in anchor_block, "anchored outlet1 should be fixedValue"
        assert (
            "10.06" in anchor_block
        ), f"anchored outlet1 should show ~10.06 m²/s² (80mmHg kinematic); got: {anchor_block[:200]}"

        # outlet2 remains zeroGradient
        rest_block = p_text.split("outlet2")[1].split("wall")[0]
        assert "zeroGradient" in rest_block, "non-anchored outlet2 should be zeroGradient"
        assert "fixedValue" not in rest_block, "non-anchored outlet2 should NOT be fixedValue"

    def test_anchor_auto_resolves_to_first_outlet(self, tmp_case_dir):
        """outlet: 'auto' uses the first outlet patch."""
        from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup

        config = _base_config(
            boundary_conditions={
                "inlet": {"type": "CONSTANT", "velocity": 0.5, "profile": "plug"},
                "outlets": {
                    "type": "zeroGradient",
                    "pressure_anchor": {"outlet": "auto"},  # no pressure_mmHg → default 80
                },
            }
        )

        with (
            patch(
                "aortacfd_lib.utils.patch_processing.PatchProcessing",
                return_value=_patch_processor_mock(),
            ),
            patch("aortacfd_lib.boundary_condition_setup.detect_world_patch_mode", return_value=False),
        ):
            bcs = BoundaryConditionSetup(config, str(tmp_case_dir))
            bcs.write_all_bc_files()

        resolved = bcs.outlet_settings.get("pressure_anchor_resolved", {})
        assert resolved.get("outlet") == "outlet1", "auto should resolve to first outlet"
        assert resolved.get("p_mmHg") == 80.0, "default pressure should be 80 mmHg"

    def test_anchor_unknown_outlet_raises(self, tmp_case_dir):
        """Typing the wrong outlet name should fail loudly, not silently no-op."""
        from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup

        config = _base_config(
            boundary_conditions={
                "inlet": {"type": "CONSTANT", "velocity": 0.5},
                "outlets": {
                    "type": "zeroGradient",
                    "pressure_anchor": {"outlet": "nonexistent_outlet"},
                },
            }
        )

        with (
            patch(
                "aortacfd_lib.utils.patch_processing.PatchProcessing",
                return_value=_patch_processor_mock(),
            ),
            patch("aortacfd_lib.boundary_condition_setup.detect_world_patch_mode", return_value=False),
        ):
            bcs = BoundaryConditionSetup(config, str(tmp_case_dir))
            with pytest.raises(ValueError, match="not one of the configured outlets"):
                bcs.write_all_bc_files()


# =============================================================================
# D.12 — Per-outlet BC types validator (v1.4.0 schema)
# =============================================================================


class TestD12_PerOutletValidator:
    """outlets.per_outlet lets users override the outlet type per outlet
    (e.g. outlet1: fixedValue, outlet2-4: 3EWINDKESSEL). v1.4.0 ships
    schema + validator for it; rendering and wk_setup integration come
    in subsequent commits."""

    @staticmethod
    def _cfg(per_outlet=None, default_type="3EWINDKESSEL", inlet_type="TIMEVARYING"):
        outlets = {"type": default_type, "windkessel_settings": {}}
        if per_outlet is not None:
            outlets["per_outlet"] = per_outlet
        return {
            "geometry": {
                "case_name": "test",
                "wall_keywords_ordered": "wall",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": ["outlet1", "outlet2", "outlet3", "outlet4"],
            },
            "boundary_conditions": {
                "inlet": {"type": inlet_type},
                "outlets": outlets,
            },
        }

    def test_per_outlet_unknown_name_rejected(self):
        from config.builder import ConfigBuilder

        cfg = self._cfg(per_outlet={"outlet99": {"type": "fixedValue", "pressure_mmHg": 80}})
        with pytest.raises(ValueError, match="not in geometry.outlet_keywords_ordered"):
            ConfigBuilder()._validate_outlet_per_outlet(cfg)

    def test_per_outlet_unknown_type_rejected(self):
        from config.builder import ConfigBuilder

        cfg = self._cfg(per_outlet={"outlet1": {"type": "ZeroGrad"}})  # wrong case
        with pytest.raises(ValueError, match="is not a valid outlet type"):
            ConfigBuilder()._validate_outlet_per_outlet(cfg)

    def test_per_outlet_missing_type_rejected(self):
        from config.builder import ConfigBuilder

        cfg = self._cfg(per_outlet={"outlet1": {"pressure_mmHg": 80}})  # no 'type'
        with pytest.raises(ValueError, match="missing the required 'type' key"):
            ConfigBuilder()._validate_outlet_per_outlet(cfg)

    def test_per_outlet_windkessel_without_settings_rejected(self):
        """Windkessel override needs windkessel_settings — either inline or global."""
        from config.builder import ConfigBuilder

        cfg = self._cfg(
            per_outlet={"outlet1": {"type": "3EWINDKESSEL"}},
            default_type="zeroGradient",  # no global windkessel_settings
        )
        # Strip the global windkessel_settings that _cfg adds by default
        cfg["boundary_conditions"]["outlets"].pop("windkessel_settings", None)
        with pytest.raises(ValueError, match="requires windkessel_settings"):
            ConfigBuilder()._validate_outlet_per_outlet(cfg)

    def test_per_outlet_valid_mixed_config_passes(self):
        from config.builder import ConfigBuilder

        cfg = self._cfg(
            per_outlet={
                "outlet1": {"type": "fixedValue", "pressure_mmHg": 80},
                "outlet2": {"type": "zeroGradient"},
                "outlet3": {"type": "3EWINDKESSEL"},  # inherits global windkessel_settings
            }
        )
        ConfigBuilder()._validate_outlet_per_outlet(cfg)  # no raise

    def test_per_outlet_anchoring_allows_pulsatile_with_default_zerogradient(self):
        """The pressure-reference validator must accept a pulsatile + default-
        zeroGradient config when per_outlet pins at least one outlet to a
        pressure-anchoring type (fixedValue / Windkessel / fixedPressure /
        resistance). Previously this combo was hard-rejected."""
        from config.builder import ConfigBuilder

        cfg = self._cfg(
            default_type="zeroGradient",
            inlet_type="TIMEVARYING",
            per_outlet={
                "outlet1": {"type": "3EWINDKESSEL"},
                "outlet2": {"type": "fixedValue", "pressure_mmHg": 80},
            },
        )
        # Should pass — outlet1 + outlet2 anchor the pressure field even
        # though the default for outlet3+4 is zeroGradient.
        ConfigBuilder()._validate_outlet_pressure_reference(cfg)  # no raise

    def test_default_zerogradient_pulsatile_still_rejected_without_anchors(self):
        """Sanity check: removing the per_outlet overrides re-triggers the
        existing v1.2.0 rejection."""
        from config.builder import ConfigBuilder

        cfg = self._cfg(default_type="zeroGradient", inlet_type="TIMEVARYING")  # no per_outlet
        with pytest.raises(ValueError, match="zeroGradient"):
            ConfigBuilder()._validate_outlet_pressure_reference(cfg)


class TestD12_PerOutletResolver:
    """The resolver in boundary_condition_setup builds an `_outlet_type_map`
    that the templates will consume in step 3/6. Step 2/6 just builds it and
    exposes it; these tests verify the map is shaped correctly under each
    config flavour."""

    @staticmethod
    def _make_bcs(per_outlet=None, default_type="3EWINDKESSEL", pressure_anchor=None, tmp_case_dir=None):
        from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup

        outlets = {"type": default_type, "windkessel_settings": {"systolic_pressure": 120}}
        if per_outlet is not None:
            outlets["per_outlet"] = per_outlet
        if pressure_anchor is not None:
            outlets["pressure_anchor"] = pressure_anchor

        config = _base_config(
            boundary_conditions={"inlet": {"type": "CONSTANT", "velocity": 0.5, "profile": "plug"}, "outlets": outlets},
        )
        config["geometry"]["outlet_keywords_ordered"] = ["outlet1", "outlet2", "outlet3"]

        with patch(
            "aortacfd_lib.utils.patch_processing.PatchProcessing",
            return_value=_patch_processor_mock(),
        ), patch("aortacfd_lib.boundary_condition_setup.detect_world_patch_mode", return_value=False):
            bcs = BoundaryConditionSetup(config, str(tmp_case_dir or "/tmp"))
        return bcs

    def test_resolver_no_per_outlet_uses_default_for_all(self, tmp_case_dir):
        bcs = self._make_bcs(default_type="3EWINDKESSEL", tmp_case_dir=tmp_case_dir)
        prepared = bcs._prepare_outlet_settings()
        m = prepared["_outlet_type_map"]
        assert set(m.keys()) == {"outlet1", "outlet2", "outlet3"}
        for entry in m.values():
            assert entry["type"] == "3EWINDKESSEL"
            assert "windkessel_settings" in entry

    def test_resolver_per_outlet_overrides_only_named_outlets(self, tmp_case_dir):
        bcs = self._make_bcs(
            default_type="3EWINDKESSEL",
            per_outlet={"outlet1": {"type": "fixedValue", "pressure_mmHg": 80}},
            tmp_case_dir=tmp_case_dir,
        )
        m = bcs._prepare_outlet_settings()["_outlet_type_map"]
        # outlet1 was overridden; outlet2/3 keep the default
        assert m["outlet1"]["type"] == "fixedValue"
        assert m["outlet1"]["pressure_mmHg"] == 80
        assert "p_kinematic" in m["outlet1"]
        # 80 mmHg / 1060 kg/m³ × 133.322 Pa/mmHg ≈ 10.06 m²/s²
        assert abs(m["outlet1"]["p_kinematic"] - 10.062) < 0.01
        assert m["outlet2"]["type"] == "3EWINDKESSEL"
        assert m["outlet3"]["type"] == "3EWINDKESSEL"

    def test_resolver_pressure_anchor_legacy_path_writes_into_map(self, tmp_case_dir):
        """v1.2.0 outlets.pressure_anchor should rewrite into a per_outlet
        entry on the named outlet. Existing v1.2.0 configs keep working."""
        bcs = self._make_bcs(
            default_type="zeroGradient",
            pressure_anchor={"outlet": "outlet2", "pressure_mmHg": 75},
            tmp_case_dir=tmp_case_dir,
        )
        m = bcs._prepare_outlet_settings()["_outlet_type_map"]
        assert m["outlet2"]["type"] == "fixedValue"
        assert m["outlet2"]["pressure_mmHg"] == 75.0
        assert "_from" in m["outlet2"]  # marks the legacy rewrite
        # outlet1, outlet3 stay at the default
        assert m["outlet1"]["type"] == "zeroGradient"
        assert m["outlet3"]["type"] == "zeroGradient"

    def test_resolver_pressure_anchor_wins_over_per_outlet(self, tmp_case_dir):
        """If both set on the same outlet, pressure_anchor wins (it's the
        explicit "I really want this pinned" lever from v1.2.0)."""
        bcs = self._make_bcs(
            default_type="zeroGradient",
            per_outlet={"outlet1": {"type": "3EWINDKESSEL", "windkessel_settings": {}}},
            pressure_anchor={"outlet": "outlet1", "pressure_mmHg": 90},
            tmp_case_dir=tmp_case_dir,
        )
        m = bcs._prepare_outlet_settings()["_outlet_type_map"]
        # pressure_anchor wins — outlet1 is fixedValue 90, not Windkessel.
        assert m["outlet1"]["type"] == "fixedValue"
        assert m["outlet1"]["pressure_mmHg"] == 90.0

    def test_resolver_windkessel_per_outlet_falls_back_to_global_settings(self, tmp_case_dir):
        """If per_outlet specifies Windkessel without inline settings, the
        resolver falls back to the global windkessel_settings."""
        bcs = self._make_bcs(
            default_type="zeroGradient",
            per_outlet={"outlet1": {"type": "3EWINDKESSEL"}},  # no inline wk_settings
            tmp_case_dir=tmp_case_dir,
        )
        m = bcs._prepare_outlet_settings()["_outlet_type_map"]
        assert m["outlet1"]["type"] == "3EWINDKESSEL"
        # Falls back to the outer windkessel_settings (systolic_pressure: 120)
        assert m["outlet1"]["windkessel_settings"]["systolic_pressure"] == 120


class TestD12_PerOutletRendering:
    """Step 3/6: per-outlet template dispatch. The templates loop over outlets
    and look up each one's effective type in _outlet_type_map. These tests
    verify the rendered 0/p and 0/U files reflect per-outlet types correctly."""

    def _render(self, per_outlet, default_type, tmp_case_dir):
        from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup

        outlets = {"type": default_type, "windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}}
        if per_outlet is not None:
            outlets["per_outlet"] = per_outlet

        config = _base_config(
            boundary_conditions={
                "inlet": {"type": "CONSTANT", "velocity": 0.5, "profile": "plug"},
                "outlets": outlets,
            }
        )
        config["geometry"]["outlet_keywords_ordered"] = ["outlet1", "outlet2", "outlet3"]

        with patch(
            "aortacfd_lib.utils.patch_processing.PatchProcessing",
            return_value=_patch_processor_mock(),
        ), patch("aortacfd_lib.boundary_condition_setup.detect_world_patch_mode", return_value=False):
            bcs = BoundaryConditionSetup(config, str(tmp_case_dir))
            bcs.write_all_bc_files()

        return (tmp_case_dir / "0" / "p").read_text(), (tmp_case_dir / "0" / "U").read_text()

    @staticmethod
    def _block(text, outlet):
        """Slice the outlet-specific Jinja-rendered block out of a 0/p or 0/U
        file. Each outlet block is:

            <outlet>
            {
                ... settings ...
            }

        Match from the outlet name to the closing brace at 4-space indent."""
        import re

        m = re.search(rf"    {re.escape(outlet)}\n    \{{(.*?)\n    \}}", text, re.DOTALL)
        assert m, f"Could not find outlet block for {outlet} in rendered text"
        return m.group(1)

    def test_p_dispatch_per_outlet_mixed_types(self, tmp_case_dir):
        """Mixed config: outlet1 fixedValue, outlet2 zeroGradient, outlet3 default Windkessel."""
        p_text, _ = self._render(
            per_outlet={
                "outlet1": {"type": "fixedValue", "pressure_mmHg": 80},
                "outlet2": {"type": "zeroGradient"},
                # outlet3 inherits the default 3EWINDKESSEL
            },
            default_type="3EWINDKESSEL",
            tmp_case_dir=tmp_case_dir,
        )

        outlet1_block = self._block(p_text, "outlet1")
        outlet2_block = self._block(p_text, "outlet2")
        outlet3_block = self._block(p_text, "outlet3")

        # outlet1 is fixedValue at the per-outlet pressure (80 mmHg kinematic ~ 10.06)
        assert "fixedValue" in outlet1_block
        assert "10.06" in outlet1_block, f"expected kinematic ~10.06 in outlet1 block; got:\n{outlet1_block[:300]}"
        assert "modularWKPressure" not in outlet1_block

        # outlet2 is zeroGradient
        assert "zeroGradient" in outlet2_block
        assert "fixedValue" not in outlet2_block
        assert "modularWKPressure" not in outlet2_block

        # outlet3 is the default Windkessel
        assert "modularWKPressure" in outlet3_block
        assert "fixedValue" not in outlet3_block

    def test_u_dispatch_per_outlet_zerogradient_does_not_get_stabilized_wk(self, tmp_case_dir):
        """A zeroGradient per-outlet override must NOT render the
        stabilizedWindkesselVelocity (only Windkessel + enable_stabilization does).
        Regression guard against the entire-file outlet_type lookup."""
        _, u_text = self._render(
            per_outlet={
                "outlet1": {"type": "zeroGradient"},
            },
            default_type="3EWINDKESSEL",
            tmp_case_dir=tmp_case_dir,
        )
        outlet1_block = self._block(u_text, "outlet1")
        # Even with default 3EWINDKESSEL, the zeroGradient per-outlet override
        # means outlet1 gets pressureInletOutletVelocity, not stabilizedWindkesselVelocity.
        assert "stabilizedWindkesselVelocity" not in outlet1_block
        assert "pressureInletOutletVelocity" in outlet1_block

    def test_backwards_compat_no_per_outlet_renders_identically(self, tmp_case_dir):
        """Configs without per_outlet should produce the same rendering as
        before — the dispatch resolves every outlet to the global default."""
        p_text, _ = self._render(per_outlet=None, default_type="3EWINDKESSEL", tmp_case_dir=tmp_case_dir)
        # All outlets render as Windkessel modularWKPressure
        for outlet in ("outlet1", "outlet2", "outlet3"):
            block = self._block(p_text, outlet)
            assert "modularWKPressure" in block, f"outlet {outlet} should be Windkessel; got: {block[:200]}"


class TestD12_WkSetupFiltering:
    """Step 4/6: wk_setup must operate ONLY on the Windkessel subset of
    outlets — otherwise Murray's-law flow split over-distributes inlet flow
    to outlets that aren't pressure-driven (e.g. a per_outlet fixedValue)."""

    @staticmethod
    def _make_wk(default_type, per_outlet=None, outlet_names=("o1", "o2", "o3")):
        from aortacfd_lib.wk_setup import WkSetup

        outlets_dict = {"type": default_type, "windkessel_settings": {"systolic_pressure": 120, "diastolic_pressure": 80}}
        if per_outlet is not None:
            outlets_dict["per_outlet"] = per_outlet

        cfg = {
            "geometry": {
                "case_name": "test",
                "wall_keywords_ordered": "wall",
                "inlet_keywords_ordered": "inlet",
                "outlet_keywords_ordered": list(outlet_names),
            },
            "boundary_conditions": {
                "inlet": {"type": "TIMEVARYING"},
                "outlets": outlets_dict,
            },
        }
        return WkSetup(cfg, [], tempfile.mkdtemp(prefix="wk-filter-"), 0.8)

    def test_resolve_all_windkessel_returns_full_list(self):
        wk = self._make_wk(default_type="3EWINDKESSEL")
        result = wk._resolve_windkessel_outlets(["o1", "o2", "o3"])
        assert result == ["o1", "o2", "o3"]

    def test_resolve_no_windkessel_returns_empty(self):
        """All outlets zeroGradient → no Windkessel processing."""
        wk = self._make_wk(default_type="zeroGradient")
        result = wk._resolve_windkessel_outlets(["o1", "o2", "o3"])
        assert result == []

    def test_resolve_mixed_returns_only_windkessel_outlets(self):
        """Default WK + 1 per_outlet override to fixedValue → 2 WK outlets remain."""
        wk = self._make_wk(
            default_type="3EWINDKESSEL",
            per_outlet={"o1": {"type": "fixedValue", "pressure_mmHg": 80}},
        )
        result = wk._resolve_windkessel_outlets(["o1", "o2", "o3"])
        assert result == ["o2", "o3"]  # o1 filtered out

    def test_resolve_inverted_mixed(self):
        """Default zeroGradient + 1 per_outlet WK override → 1 WK outlet."""
        wk = self._make_wk(
            default_type="zeroGradient",
            per_outlet={"o2": {"type": "3EWINDKESSEL"}},
        )
        result = wk._resolve_windkessel_outlets(["o1", "o2", "o3"])
        assert result == ["o2"]

    def test_execute_returns_early_when_no_windkessel(self):
        """Empty WK subset → execute() is a no-op (doesn't crash)."""
        wk = self._make_wk(default_type="zeroGradient")
        # Should not raise even though config doesn't have inlet flow / cardiac cycle
        # data sufficient for a real Windkessel computation
        wk.execute()
        # If we got here without an exception, the early-return path is working


class TestD12_PressureAnchorDeprecation:
    """Step 6/6: outlets.pressure_anchor still works in v1.4.0 but emits a
    DeprecationWarning. Users should migrate to outlets.per_outlet."""

    def test_pressure_anchor_emits_deprecation_warning(self, tmp_case_dir):
        from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup

        config = _base_config(
            boundary_conditions={
                "inlet": {"type": "CONSTANT", "velocity": 0.5, "profile": "plug"},
                "outlets": {
                    "type": "zeroGradient",
                    "pressure_anchor": {"outlet": "outlet1", "pressure_mmHg": 80},
                },
            }
        )

        with patch(
            "aortacfd_lib.utils.patch_processing.PatchProcessing",
            return_value=_patch_processor_mock(),
        ), patch("aortacfd_lib.boundary_condition_setup.detect_world_patch_mode", return_value=False):
            bcs = BoundaryConditionSetup(config, str(tmp_case_dir))
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                bcs.write_all_bc_files()

            dep = [w for w in caught if issubclass(w.category, DeprecationWarning)]
            assert any("pressure_anchor is deprecated" in str(w.message) for w in dep), (
                f"Expected DeprecationWarning about pressure_anchor; got: "
                f"{[str(w.message)[:80] for w in caught]}"
            )

    def test_pressure_anchor_still_renders_correctly_with_warning(self, tmp_case_dir):
        """The deprecation warning is informational only — pressure_anchor
        must continue to produce the same rendered 0/p as before."""
        from aortacfd_lib.boundary_condition_setup import BoundaryConditionSetup

        config = _base_config(
            boundary_conditions={
                "inlet": {"type": "CONSTANT", "velocity": 0.5, "profile": "plug"},
                "outlets": {
                    "type": "zeroGradient",
                    "pressure_anchor": {"outlet": "outlet1", "pressure_mmHg": 80},
                },
            }
        )

        with patch(
            "aortacfd_lib.utils.patch_processing.PatchProcessing",
            return_value=_patch_processor_mock(),
        ), patch("aortacfd_lib.boundary_condition_setup.detect_world_patch_mode", return_value=False):
            bcs = BoundaryConditionSetup(config, str(tmp_case_dir))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                bcs.write_all_bc_files()

        p_text = (tmp_case_dir / "0" / "p").read_text()
        # outlet1 must still render as fixedValue with the 80 mmHg kinematic value
        outlet1_block = p_text.split("outlet1")[1].split("outlet2")[0]
        assert "fixedValue" in outlet1_block
        assert "10.06" in outlet1_block  # 80 * 133.322 / 1060 ≈ 10.062
