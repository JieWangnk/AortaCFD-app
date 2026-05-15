"""Case packager (Block B of the parametric-study workflow).

Takes a directory of case folders that already contain split STL patches
(typically produced by the Blender geometry generator under
``~/GitHub/blender/``, but any source works as long as the folder
contains ``inlet.stl``, ``outlet*.stl``, and ``wall_aorta.stl``) and
stamps each one with a ``config.json`` so it is ready for
``run_patient.py``.

This is a pure "fold a config onto a folder of STLs" operation. It
does not generate geometry, does not run CFD, does not aggregate.

Usage::

    python -m scripts.package_cases /tmp/gen_sobol \\
        --config-template examples/templates/config_workshop_quick.json \\
        --output cases_input/sobol_demo \\
        --inflow-csv path/to/inflow.csv     # optional, copied into each case
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


STL_PATCH_NAMES = ("inlet.stl", "wall_aorta.stl")


def _list_case_dirs(src: Path) -> list[Path]:
    if not src.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {src}")
    out: list[Path] = []
    for d in sorted(src.iterdir()):
        if not d.is_dir():
            continue
        if any((d / name).exists() for name in STL_PATCH_NAMES):
            out.append(d)
    return out


def _outlet_names(case_dir: Path) -> list[str]:
    names: list[str] = []
    for p in sorted(case_dir.glob("outlet*.stl")):
        names.append(p.stem)
    return names


def _apply_geometry_keywords(config: dict[str, Any], outlet_names: list[str]) -> dict[str, Any]:
    """Make sure config.geometry's keyword lists match the patches we actually have."""
    geo = config.setdefault("geometry", {})
    geo.setdefault("inlet_keywords_ordered", "inlet")
    geo.setdefault("wall_keywords_ordered", "wall_aorta")
    geo.setdefault("scale_factor", 0.001)
    if outlet_names:
        geo["outlet_keywords_ordered"] = outlet_names
    elif "outlet_keywords_ordered" not in geo:
        logger.warning("No outlet*.stl files found and config has no outlet_keywords_ordered; "
                       "the case will not be runnable until you add outlets.")
    return config


def _write_case_meta(case_dir: Path, geometry_meta: dict[str, Any], template_name: str) -> None:
    meta = {
        "schema_version": "1.0",
        "case_id": case_dir.name,
        "source": "synthetic" if geometry_meta else "clinical",
        "geometry_meta": geometry_meta if geometry_meta else None,
        "config_template": template_name,
    }
    # Surface the most useful fields at the top level for easy joins.
    if geometry_meta:
        if "sample_index" in geometry_meta:
            meta["sample_index"] = geometry_meta["sample_index"]
        if "seed" in geometry_meta:
            meta["seed"] = geometry_meta["seed"]
        if "params" in geometry_meta:
            meta["params"] = geometry_meta["params"]
        if "generator" in geometry_meta:
            meta["source_generator"] = geometry_meta["generator"]
    (case_dir / "case.meta.json").write_text(json.dumps(meta, indent=2) + "\n")


def package_case(
    case_dir: Path,
    config_template: dict[str, Any],
    config_template_name: str,
    inflow_csv: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Stamp a single case directory with a config and metadata.

    Returns the destination case directory (the original ``case_dir`` if
    ``output_dir`` is None, otherwise ``output_dir / case_dir.name``).
    """
    dest = case_dir if output_dir is None else (output_dir / case_dir.name)
    if dest != case_dir:
        if dest.exists():
            logger.info("Replacing existing case directory: %s", dest)
            shutil.rmtree(dest)
        shutil.copytree(case_dir, dest)

    geometry_meta = {}
    geom_meta_path = case_dir / "geometry.meta.json"
    if geom_meta_path.exists():
        try:
            geometry_meta = json.loads(geom_meta_path.read_text())
        except Exception as e:
            logger.warning("Could not parse %s: %s", geom_meta_path, e)

    # Fresh copy of the template — never mutate the caller's dict
    config = json.loads(json.dumps(config_template))
    outlet_names = _outlet_names(dest)
    config = _apply_geometry_keywords(config, outlet_names)

    # Optional CSV stamp
    if inflow_csv is not None:
        target_csv = dest / inflow_csv.name
        if inflow_csv.resolve() != target_csv.resolve():
            shutil.copy2(inflow_csv, target_csv)
        bcs = config.setdefault("boundary_conditions", {}).setdefault("inlet", {})
        if bcs.get("type") == "TIMEVARYING":
            bcs.setdefault("csv_file", inflow_csv.name)
            bcs["csv_file"] = inflow_csv.name

    (dest / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    _write_case_meta(dest, geometry_meta, config_template_name)
    return dest


def package_directory(
    src: Path,
    config_template: Path,
    inflow_csv: Path | None = None,
    output_dir: Path | None = None,
) -> list[Path]:
    template_payload = json.loads(config_template.read_text())
    template_name = config_template.name

    case_dirs = _list_case_dirs(src)
    if not case_dirs:
        raise RuntimeError(f"No case directories found under {src} (looked for at least inlet.stl or wall_aorta.stl).")

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

    out: list[Path] = []
    for case_dir in case_dirs:
        dest = package_case(
            case_dir=case_dir,
            config_template=template_payload,
            config_template_name=template_name,
            inflow_csv=inflow_csv,
            output_dir=output_dir,
        )
        out.append(dest)
        logger.info("Packaged %s -> %s", case_dir.name, dest)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="package_cases",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("src", type=Path, help="Source directory containing one folder per case (with split STL patches).")
    p.add_argument("--config-template", type=Path, required=True, help="Path to a config.json template (see examples/templates/).")
    p.add_argument("--inflow-csv", type=Path, default=None, help="Optional inlet flowrate CSV to copy into each case (required when template is TIMEVARYING).")
    p.add_argument("--output", "--output-dir", dest="output_dir", type=Path, default=None, help="Where to write packaged cases (default: in-place).")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if not args.config_template.exists():
        p.error(f"Config template not found: {args.config_template}")
    if args.inflow_csv is not None and not args.inflow_csv.exists():
        p.error(f"Inflow CSV not found: {args.inflow_csv}")

    packaged = package_directory(
        src=args.src,
        config_template=args.config_template,
        inflow_csv=args.inflow_csv,
        output_dir=args.output_dir,
    )
    print(f"Packaged {len(packaged)} cases")
    for d in packaged:
        print(f"  {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
