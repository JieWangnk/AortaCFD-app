"""Every inlet type must reach the right OpenFOAM boundary condition in 0/U.

Regression test for the MAPPED_PROFILE bug: the config docs told users to
write ``inlet.type = "MAPPED_PROFILE"`` (``MRI`` is the deprecated alias),
but U.tpl, the config accessor, the validator and the physics advisor only
recognised ``MRI``. A MAPPED_PROFILE config fell through to a constant
inlet. These tests pin the dispatch for all inlet types in all four places.
"""

import re
from pathlib import Path

import jinja2
import pytest

TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "templates"

PULSATILE_MAPPED = ["TIMEVARYING", "WOMERSLEY", "MRI", "MAPPED_PROFILE"]
UNIFORM = ["CONSTANT", "PARABOLIC"]


def _render_u(inlet_type: str) -> str:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES)), undefined=jinja2.ChainableUndefined)
    return env.get_template("U.tpl").render(
        inlet_patch="inlet",
        inlet_settings={"type": inlet_type},
        inlet_velocity_vector="(0 0 0.1)",
        inlet_profile="plug",
        outlet_patches=[],
        outlet_settings={},
        wall_patch="wall_aorta",
        world_patch_mode=False,
        openfoam_version="12",
    )


def _inlet_bc_type(rendered: str) -> str:
    start = rendered.find("The inlet velocity")
    block = rendered[start:]
    m = re.search(r"type\s+(\w+);", block)
    assert m, "no inlet BC type found in rendered U"
    return m.group(1)


@pytest.mark.parametrize("inlet_type", PULSATILE_MAPPED)
def test_mapped_inlets_write_timeVaryingMappedFixedValue(inlet_type):
    assert _inlet_bc_type(_render_u(inlet_type)) == "timeVaryingMappedFixedValue"


@pytest.mark.parametrize("inlet_type", UNIFORM)
def test_uniform_inlets_write_fixedValue(inlet_type):
    assert _inlet_bc_type(_render_u(inlet_type)) == "fixedValue"


def test_accessor_is_pulsatile_for_mapped_profile():
    from config.accessor import Config

    for t in PULSATILE_MAPPED:
        assert Config({"boundary_conditions": {"inlet": {"type": t}}}).is_pulsatile, t
    for t in UNIFORM:
        assert not Config({"boundary_conditions": {"inlet": {"type": t}}}).is_pulsatile, t


def test_validator_accepts_mapped_profile():
    from aortacfd_lib.utils.validation import BoundaryConditionValidator

    assert "MAPPED_PROFILE" in BoundaryConditionValidator.VALID_INLET_TYPES
    assert "MRI" in BoundaryConditionValidator.VALID_INLET_TYPES


def test_physics_advisor_treats_mapped_profile_as_pulsatile():
    from aortacfd_lib import physics_advisor as pa

    src = Path(pa.__file__).read_text()
    m = re.search(r"inlet_type in \[([^\]]*)\]", src)
    assert m and "MAPPED_PROFILE" in m.group(1) and "MRI" in m.group(1)


def test_hemodynamics_postprocessor_marks_mapped_profile_pulsatile(tmp_path):
    from aortacfd_lib.hemodynamics_postprocessor import HemodynamicsPostProcessor

    for t in PULSATILE_MAPPED:
        proc = HemodynamicsPostProcessor(str(tmp_path), {"inlet": {"type": t}, "geometry": {}})
        assert proc.is_pulsatile, t
    proc = HemodynamicsPostProcessor(str(tmp_path), {"inlet": {"type": "CONSTANT"}, "geometry": {}})
    assert not proc.is_pulsatile
