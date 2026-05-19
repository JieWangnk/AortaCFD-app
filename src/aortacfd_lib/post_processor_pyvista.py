"""PyVista-based post-processor for AortaCFD OpenFOAM runs.

A pure-Python replacement for the ParaView/pvbatch post-processor in
`post_processor.py`. Reads the case `.foam` file via PyVista's native
`POpenFOAMReader` (handles decomposed `processor*/` cases) and renders
the workshop / tutorial figure set headlessly.

Phase 1 scope: produce a single peak-systole velocity-magnitude PNG so
the backend wiring can be validated end-to-end against an existing
`output/<case>/<run>/` directory. Subsequent phases add WSS, pressure
clip, and multi-time outputs.

The output directory layout matches the existing post-processor:
    <run_dir>/Images/
        velocity_peak_systole.png
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def _find_foam_file(case_openfoam_dir: Path) -> Optional[Path]:
    """Return the .foam pointer file inside an AortaCFD openfoam/ dir.

    AortaCFD writes one of: `openfoam.foam`, `<patient_id>.foam`, or
    just any `.foam` — they're all empty placeholder files that
    PyVista / ParaView use as an entry point to the case.
    """
    candidates = list(case_openfoam_dir.glob("*.foam"))
    if not candidates:
        return None
    # Prefer the canonical "openfoam.foam" if multiple exist.
    for c in candidates:
        if c.name == "openfoam.foam":
            return c
    return candidates[0]


def _resolve_render_time(time_values: list[float], requested: Optional[float]) -> float:
    """Pick the simulated time to render.

    - If `requested` is None, return the *last* available time (a
      reasonable default when the user didn't ask for anything in
      particular — typically the most converged result we have).
    - If `requested` is given, return the nearest available time.
    """
    if not time_values:
        return 0.0
    if requested is None:
        return float(time_values[-1])
    arr = np.asarray(time_values, dtype=float)
    return float(arr[np.argmin(np.abs(arr - requested))])


def render_velocity_magnitude(
    case_openfoam_dir: Path,
    out_png: Path,
    *,
    time: Optional[float] = None,
    window_size: tuple[int, int] = (1280, 720),
    cmap: str = "viridis",
) -> Path:
    """Render velocity magnitude on the internal mesh at one time step.

    Returns the path to the PNG that was written.

    Raises:
        FileNotFoundError: if no .foam file is found in `case_openfoam_dir`.
        RuntimeError: if PyVista can't read the case or the time step
            has no `U` field.
    """
    import pyvista as pv

    foam = _find_foam_file(case_openfoam_dir)
    if foam is None:
        raise FileNotFoundError(
            f"No .foam pointer file found under {case_openfoam_dir} — "
            "is this a real AortaCFD openfoam/ directory?"
        )

    reader = pv.POpenFOAMReader(str(foam))
    time_values = list(reader.time_values or [])
    if not time_values:
        raise RuntimeError(
            f"No time values found in {foam} — has the solver actually written any output yet?"
        )

    t = _resolve_render_time(time_values, time)
    reader.set_active_time_value(t)
    multiblock = reader.read()

    if "internalMesh" not in multiblock.keys():
        raise RuntimeError(
            f"PyVista returned a MultiBlock with no 'internalMesh' block: {list(multiblock.keys())}"
        )

    internal = multiblock["internalMesh"]
    if "U" not in internal.point_data and "U" not in internal.cell_data:
        raise RuntimeError(
            f"No 'U' field on internalMesh at t={t}; available point arrays: "
            f"{list(internal.point_data.keys())}; cell arrays: "
            f"{list(internal.cell_data.keys())}"
        )

    # Compute |U|. Use point data if available; fall back to cell.
    if "U" in internal.point_data:
        velocity = np.asarray(internal.point_data["U"])
        umag_name = "U_magnitude"
        internal.point_data[umag_name] = np.linalg.norm(velocity, axis=1)
    else:
        velocity = np.asarray(internal.cell_data["U"])
        umag_name = "U_magnitude"
        internal.cell_data[umag_name] = np.linalg.norm(velocity, axis=1)

    out_png.parent.mkdir(parents=True, exist_ok=True)

    plotter = pv.Plotter(off_screen=True, window_size=list(window_size))
    plotter.add_mesh(
        internal,
        scalars=umag_name,
        cmap=cmap,
        scalar_bar_args=dict(
            title=f"|U| (m/s) — t={t:.3f}s",
            n_labels=5,
            fmt="%.2f",
        ),
    )
    plotter.view_isometric()
    plotter.screenshot(str(out_png))
    plotter.close()

    logger.info("PyVista wrote %s (t=%.3fs, |U| from %s)", out_png, t, umag_name)
    return out_png


def post_process(
    case_dir: str | Path,
    *,
    out_subdir: str = "Images",
) -> list[Path]:
    """Run the Phase-1 PyVista post-processor on an AortaCFD run.

    `case_dir` is the top-level run directory (the one that contains
    `openfoam/`, `reports/`, `results/`). Writes PNG(s) under
    `case_dir/<out_subdir>/` and returns the list of paths written.
    """
    case_dir = Path(case_dir)
    openfoam_dir = case_dir / "openfoam"
    if not openfoam_dir.is_dir():
        raise FileNotFoundError(
            f"Expected `{openfoam_dir}` (with snappy mesh + solver output); not found."
        )

    images_dir = case_dir / out_subdir
    written: list[Path] = []

    velocity_png = images_dir / "velocity_peak_systole.png"
    render_velocity_magnitude(openfoam_dir, velocity_png)
    written.append(velocity_png)

    return written
