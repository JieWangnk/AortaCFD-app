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


def _principal_axes(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute principal axes of a 3-D point cloud via SVD.

    Returns:
        centre: (3,) array — centroid of the points.
        axes:   (3, 3) array — each row is a unit principal axis,
                ordered by descending variance. axes[0] = longest
                (PC1), axes[2] = shortest (PC3).

    The "shortest" axis is the view direction that maximises silhouette
    area: variance perpendicular to it is maximal, so the 2-D projection
    onto its perpendicular plane spreads as wide as possible.
    """
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError(f"Expected (N, 3) point cloud; got shape {points.shape}")
    centre = points.mean(axis=0)
    centered = points - centre
    # SVD gives axes ordered by descending singular value (= sqrt(variance × N))
    _, singular_values, vh = np.linalg.svd(centered, full_matrices=False)
    # vh rows are right-singular vectors = principal axes
    return centre, vh


def _camera_pose_max_silhouette(
    mesh: "pv.DataSet",
    distance_factor: float = 2.5,
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    """Pick a camera pose that looks along the geometry's shortest principal
    axis, so the rendered image shows the maximum-silhouette projection.

    For a tubular structure like an aorta:
      - PC1 = along the vessel length (longest extent)
      - PC2 = across the arch curvature
      - PC3 = perpendicular to the arch plane (shortest)
    Looking along PC3 reproduces the conventional anatomic "anterior" view
    used by radiologists.

    Returns `(position, focal_point, up)` — the tuple `pv.Plotter` expects
    for `plotter.camera_position`.

    `distance_factor` is multiplied by the longest principal-axis extent
    to set how far the camera sits from the centre. 2.5× is comfortable
    for a single object filling ~80 % of the frame.
    """
    points = np.asarray(mesh.points)
    centre, axes = _principal_axes(points)
    pc1, _pc2, pc3 = axes[0], axes[1], axes[2]

    # Camera distance: scale by the size along the longest axis
    extent_pc1 = float(np.ptp(points @ pc1))
    distance = max(extent_pc1, 1e-6) * distance_factor

    position = centre + pc3 * distance
    return (
        tuple(position.astype(float)),
        tuple(centre.astype(float)),
        tuple(pc1.astype(float)),  # up: long axis points up in screen
    )


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
            vertical=True,
            position_x=0.88,
            position_y=0.12,
            width=0.06,
            height=0.76,
        ),
    )
    plotter.set_background("white")
    plotter.camera_position = _camera_pose_max_silhouette(internal)
    plotter.screenshot(str(out_png))
    plotter.close()

    logger.info("PyVista wrote %s (t=%.3fs, |U| from %s)", out_png, t, umag_name)
    return out_png


def open_interactive_viewer(
    case_dir: str | Path,
    *,
    time: Optional[float] = None,
    initial_field: str = "U",
) -> None:
    """Open an interactive PyVista window for an AortaCFD run.

    Lets the user rotate / zoom / pan the geometry and switch between
    the available fields (U, p, wallShearStress) via a side menu.
    Requires an X11 display (i.e. don't try this over SSH without `-X`
    or on a headless server — use the static-PNG `post_process` path
    instead).

    The window blocks until the user closes it. Returns None.
    """
    import pyvista as pv

    case_dir = Path(case_dir)
    openfoam_dir = case_dir / "openfoam"
    foam = _find_foam_file(openfoam_dir)
    if foam is None:
        raise FileNotFoundError(f"No .foam pointer file under {openfoam_dir}")

    reader = pv.POpenFOAMReader(str(foam))
    time_values = list(reader.time_values or [])
    if not time_values:
        raise RuntimeError(f"No time values in {foam}; has the solver written output?")

    t = _resolve_render_time(time_values, time)
    reader.set_active_time_value(t)
    multiblock = reader.read()
    internal = multiblock["internalMesh"]

    # Discover what's available
    point_arrays = list(internal.point_data.keys())
    cell_arrays = list(internal.cell_data.keys())
    available = list(dict.fromkeys(point_arrays + cell_arrays))
    if initial_field not in available:
        raise ValueError(
            f"Field '{initial_field}' not available. Got: {available}"
        )

    # For vector fields, derive a scalar magnitude for visualization
    def _scalar_view(field: str) -> str:
        """Return the array name to display for a given field."""
        if field in internal.point_data:
            arr = np.asarray(internal.point_data[field])
        else:
            arr = np.asarray(internal.cell_data[field])
        if arr.ndim == 2 and arr.shape[1] == 3:
            mag_name = f"{field}_magnitude"
            mag = np.linalg.norm(arr, axis=1)
            if field in internal.point_data:
                internal.point_data[mag_name] = mag
            else:
                internal.cell_data[mag_name] = mag
            return mag_name
        return field

    initial_scalar = _scalar_view(initial_field)
    # Pre-compute scalar views for every field so the picker is instant
    for field in available:
        _scalar_view(field)

    plotter = pv.Plotter(window_size=[1280, 800])
    plotter.set_background("white")
    actor = plotter.add_mesh(
        internal,
        scalars=initial_scalar,
        cmap="viridis",
        scalar_bar_args=dict(
            title=f"{initial_field} — t={t:.3f}s",
            n_labels=5,
            fmt="%.3g",
            vertical=True,
            position_x=0.88,
            position_y=0.12,
            width=0.06,
            height=0.76,
        ),
    )
    plotter.camera_position = _camera_pose_max_silhouette(internal)

    # Field-switcher buttons in a column on the left
    def _make_switcher(field: str):
        def _swap():
            scalar_name = _scalar_view(field)
            actor.mapper.SetScalarModeToUsePointData() \
                if scalar_name in internal.point_data \
                else actor.mapper.SetScalarModeToUseCellData()
            actor.mapper.SelectColorArray(scalar_name)
            actor.mapper.SetScalarRange(internal.get_data_range(scalar_name))
            plotter.scalar_bar.SetTitle(f"{field} — t={t:.3f}s")
            plotter.render()
        return _swap

    for i, field in enumerate(available):
        plotter.add_text(
            field,
            position=(20, 760 - i * 30),
            font_size=10,
            color="black",
            name=f"label_{field}",
        )
        plotter.add_checkbox_button_widget(
            _make_switcher(field),
            value=(field == initial_field),
            position=(5, 750 - i * 30),
            size=20,
            border_size=1,
        )

    plotter.add_text(
        f"AortaCFD interactive | t={t:.3f}s | click checkboxes to switch fields",
        position="upper_edge",
        font_size=10,
        color="black",
    )
    plotter.show()


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
