"""PyVista-based post-processor for AortaCFD OpenFOAM runs.

A pure-Python replacement for the ParaView/pvbatch post-processor in
`post_processor.py`. Reads the case `.foam` file via PyVista's native
`POpenFOAMReader` (handles decomposed `processor*/` cases) and renders
the workshop / tutorial figure set headlessly.

The output directory layout matches the existing post-processor:
    <run_dir>/Images/
        velocity_peak_systole.png
        wall_shear_stress.png
        pressure_clip.png
        velocity_t<sim_time>.png   (one per time step in the time series)
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


RHO_BLOOD = 1060.0       # kg/m^3 — converts OpenFOAM kinematic to dynamic
MMHG_PER_PA = 1.0 / 133.322


def _load_case(case_openfoam_dir: Path, time: Optional[float]):
    """Open the .foam file, pick a time step, and return (multiblock, t).

    Centralises the read so each renderer doesn't re-open the case.
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
    return reader.read(), t


def _ensure_umag(internal: "pv.DataSet") -> str:
    """Compute |U| on `internal` if not already there. Returns scalar name."""
    if "U_magnitude" in internal.point_data or "U_magnitude" in internal.cell_data:
        return "U_magnitude"
    if "U" in internal.point_data:
        u = np.asarray(internal.point_data["U"])
        internal.point_data["U_magnitude"] = np.linalg.norm(u, axis=1)
    elif "U" in internal.cell_data:
        u = np.asarray(internal.cell_data["U"])
        internal.cell_data["U_magnitude"] = np.linalg.norm(u, axis=1)
    else:
        raise RuntimeError("No 'U' field on the mesh")
    return "U_magnitude"


def _build_isosurfaces(
    internal: "pv.DataSet",
    scalar: str,
    *,
    n_levels: int = 6,
    low_frac: float = 0.10,
    high_percentile: float = 98.0,
) -> "pv.PolyData":
    """Return iso-surfaces of `scalar` on `internal`, evenly spaced
    between `low_frac * max` and the `high_percentile` of the field.

    Bypasses the no-slip-layer occlusion problem: the 0-velocity skin
    is skipped (since low_frac > 0) and we render purely the interior
    shells where the actual flow lives. This is the unstructured-mesh
    analogue of volume rendering in ParaView — same look, same
    physically-meaningful "see the jet through the wall" effect.
    """
    if scalar in internal.point_data:
        arr = np.asarray(internal.point_data[scalar])
    else:
        arr = np.asarray(internal.cell_data[scalar])

    hi = float(np.percentile(arr, high_percentile))
    lo = max(low_frac * hi, 1e-6)
    if hi <= lo:
        hi = lo * 1.1
    levels = np.linspace(lo, hi, n_levels)
    return internal.contour(isosurfaces=list(levels), scalars=scalar)


def render_velocity_magnitude(
    case_openfoam_dir: Path,
    out_png: Path,
    *,
    time: Optional[float] = None,
    window_size: tuple[int, int] = (1280, 720),
    cmap: str = "viridis",
    wall_patch: str = "wall_aorta",
    wall_opacity: float = 0.10,
    iso_levels: int = 6,
    iso_opacity: float = 0.55,
) -> Path:
    """Render velocity magnitude on the internal flow using nested
    iso-surfaces at multiple |U| levels, with a translucent wall shell
    behind for anatomical context.

    The no-slip layer at the wall (|U|≈0) is excluded by starting the
    iso-surface stack at 10 % of the |U| 98th-percentile — so the
    interior jet through the coarctation actually shows up instead of
    being occluded by the slow-flow skin. This is the unstructured-mesh
    equivalent of ParaView's volume rendering.

    Args:
        iso_levels:   number of |U| iso-surfaces stacked from low to high.
        iso_opacity:  alpha applied uniformly to every iso-surface.
        wall_opacity: alpha of the wall_aorta shell (0 to omit entirely).
    """
    import pyvista as pv

    multiblock, t = _load_case(case_openfoam_dir, time)
    if "internalMesh" not in multiblock.keys():
        raise RuntimeError(
            f"PyVista returned a MultiBlock with no 'internalMesh' block: {list(multiblock.keys())}"
        )

    internal = multiblock["internalMesh"]
    umag_name = _ensure_umag(internal)

    # Iso-surface stack — skips the no-slip layer, shows actual flow regions
    iso = _build_isosurfaces(internal, umag_name, n_levels=iso_levels)
    # Colourmap range matches what the iso-surfaces actually span (5th–98th pct)
    umag_arr = (
        np.asarray(internal.point_data[umag_name])
        if umag_name in internal.point_data
        else np.asarray(internal.cell_data[umag_name])
    )
    clim = (0.0, float(np.percentile(umag_arr, 98)))

    out_png.parent.mkdir(parents=True, exist_ok=True)

    plotter = pv.Plotter(off_screen=True, window_size=list(window_size))
    plotter.set_background("white")

    # 1) Wall shell — translucent grey for anatomy
    boundary = multiblock.get("boundary") if hasattr(multiblock, "get") else None
    wall = boundary[wall_patch] if (boundary is not None and wall_patch in boundary.keys()) else None
    if wall is not None and wall_opacity > 0.0:
        plotter.add_mesh(
            wall, color="lightgray", opacity=wall_opacity,
            specular=0.1, show_scalar_bar=False,
        )

    # 2) Nested iso-surfaces of |U|
    plotter.add_mesh(
        iso,
        scalars=umag_name,
        cmap=cmap,
        clim=clim,
        opacity=iso_opacity,
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

    plotter.camera_position = _camera_pose_max_silhouette(internal)
    plotter.screenshot(str(out_png))
    plotter.close()

    logger.info(
        "PyVista wrote %s (t=%.3fs, %d iso-surfaces from %s, clim 0-%.2f m/s, wall=%s @ %.0f%%)",
        out_png, t, iso_levels, umag_name, clim[1],
        wall_patch if wall is not None else "none", wall_opacity * 100,
    )
    return out_png


def render_wall_shear_stress(
    case_openfoam_dir: Path,
    out_png: Path,
    *,
    time: Optional[float] = None,
    wall_patch: str = "wall_aorta",
    window_size: tuple[int, int] = (1280, 720),
    cmap: str = "viridis",
    clip_percentile: tuple[float, float] = (2, 98),
) -> Path:
    """Render |WSS| (Pa) on the wall patch at one time step.

    The 2nd-to-98th-percentile clip stops the colormap being washed out
    by the handful of cells at sharp geometric features (the
    coarctation throat) that hold the global max.
    """
    import pyvista as pv

    multiblock, t = _load_case(case_openfoam_dir, time)
    if "boundary" not in multiblock.keys():
        raise RuntimeError(
            f"No 'boundary' block at top level; got: {list(multiblock.keys())}"
        )
    boundary = multiblock["boundary"]
    if wall_patch not in boundary.keys():
        raise RuntimeError(
            f"Wall patch '{wall_patch}' not found. Available patches: "
            f"{list(boundary.keys())}"
        )
    wall = boundary[wall_patch]

    if "wallShearStress" not in wall.point_data and "wallShearStress" not in wall.cell_data:
        raise RuntimeError(
            f"No 'wallShearStress' on {wall_patch} at t={t}. Has the wallShearStress "
            "function object run? See hemodynamics_postprocessor.py."
        )

    # Convert kinematic (m^2/s^2) to dynamic (Pa) via density
    if "wallShearStress" in wall.point_data:
        wss = np.asarray(wall.point_data["wallShearStress"])
        wss_mag_pa = np.linalg.norm(wss, axis=1) * RHO_BLOOD
        scalar_name = "WSS_magnitude_Pa"
        wall.point_data[scalar_name] = wss_mag_pa
    else:
        wss = np.asarray(wall.cell_data["wallShearStress"])
        wss_mag_pa = np.linalg.norm(wss, axis=1) * RHO_BLOOD
        scalar_name = "WSS_magnitude_Pa"
        wall.cell_data[scalar_name] = wss_mag_pa

    lo, hi = np.percentile(wss_mag_pa, clip_percentile)
    if hi <= lo:
        hi = lo + 1e-9  # degenerate field; avoid zero-range crash

    out_png.parent.mkdir(parents=True, exist_ok=True)

    plotter = pv.Plotter(off_screen=True, window_size=list(window_size))
    plotter.set_background("white")
    plotter.add_mesh(
        wall,
        scalars=scalar_name,
        cmap=cmap,
        clim=(float(lo), float(hi)),
        scalar_bar_args=dict(
            title=f"|WSS| (Pa) — t={t:.3f}s",
            n_labels=5,
            fmt="%.2f",
            vertical=True,
            position_x=0.88,
            position_y=0.12,
            width=0.06,
            height=0.76,
        ),
    )
    plotter.camera_position = _camera_pose_max_silhouette(wall)
    plotter.screenshot(str(out_png))
    plotter.close()

    logger.info(
        "PyVista wrote %s (t=%.3fs, |WSS| Pa range %.2f–%.2f at %s%%)",
        out_png, t, lo, hi, clip_percentile,
    )
    return out_png


def render_pressure_clip(
    case_openfoam_dir: Path,
    out_png: Path,
    *,
    time: Optional[float] = None,
    window_size: tuple[int, int] = (1280, 720),
    cmap: str = "coolwarm",
    wall_opacity: float = 0.15,
    units: str = "mmHg",  # "mmHg" | "Pa"
) -> Path:
    """Slice the internal mesh by a plane through its PCA centre normal
    to PC3 (the arch plane), colour by pressure, and overlay the wall
    as a translucent shell so the slice has anatomical context.
    """
    import pyvista as pv

    multiblock, t = _load_case(case_openfoam_dir, time)
    internal = multiblock["internalMesh"]
    if "p" not in internal.point_data and "p" not in internal.cell_data:
        raise RuntimeError(f"No 'p' field on internalMesh at t={t}")

    # Promote pressure to point data (clip needs it on points) and convert units
    if "p" in internal.point_data:
        p_kin = np.asarray(internal.point_data["p"])
    else:
        # cell → point interpolation
        internal = internal.cell_data_to_point_data()
        p_kin = np.asarray(internal.point_data["p"])

    p_pa = p_kin * RHO_BLOOD
    if units == "mmHg":
        p_disp = p_pa * MMHG_PER_PA
        unit_label = "mmHg"
        fmt = "%.1f"
    else:
        p_disp = p_pa
        unit_label = "Pa"
        fmt = "%.1f"
    scalar_name = f"p_{unit_label}"
    internal.point_data[scalar_name] = p_disp

    centre, axes = _principal_axes(np.asarray(internal.points))
    pc3 = axes[2]
    clip = internal.clip(normal=tuple(pc3), origin=tuple(centre), invert=False)
    if clip.n_points == 0:
        # Some meshes produce a degenerate clip on one side; flip orientation
        clip = internal.clip(normal=tuple(-pc3), origin=tuple(centre), invert=False)

    # Pressure range from the *clip* itself (visible content), 5–95th percentile
    p_clip = np.asarray(clip.point_data[scalar_name])
    lo, hi = np.percentile(p_clip, [5, 95])
    if hi <= lo:
        hi = lo + 1e-9

    wall = multiblock["boundary"]["wall_aorta"] if "wall_aorta" in multiblock["boundary"].keys() else None

    out_png.parent.mkdir(parents=True, exist_ok=True)

    plotter = pv.Plotter(off_screen=True, window_size=list(window_size))
    plotter.set_background("white")

    if wall is not None:
        plotter.add_mesh(wall, color="lightgray", opacity=wall_opacity, show_scalar_bar=False)

    plotter.add_mesh(
        clip,
        scalars=scalar_name,
        cmap=cmap,
        clim=(float(lo), float(hi)),
        scalar_bar_args=dict(
            title=f"p ({unit_label}) — t={t:.3f}s",
            n_labels=5,
            fmt=fmt,
            vertical=True,
            position_x=0.88,
            position_y=0.12,
            width=0.06,
            height=0.76,
        ),
    )
    plotter.camera_position = _camera_pose_max_silhouette(internal)
    plotter.screenshot(str(out_png))
    plotter.close()

    logger.info(
        "PyVista wrote %s (t=%.3fs, p %s range %.2f–%.2f)",
        out_png, t, unit_label, lo, hi,
    )
    return out_png


def render_velocity_time_series(
    case_openfoam_dir: Path,
    out_dir: Path,
    *,
    times: Optional[list[float]] = None,
    window_size: tuple[int, int] = (1280, 720),
    cmap: str = "viridis",
    wall_patch: str = "wall_aorta",
    wall_opacity: float = 0.10,
    iso_levels: int = 6,
    iso_opacity: float = 0.55,
) -> list[Path]:
    """Render |U| at every requested time step (or every available step).

    Uses the same iso-surface stack and translucent wall shell as
    `render_velocity_magnitude`, with the colourmap clim FROZEN across
    the series at the global 98th percentile so the same colour means
    the same |U| in every frame, and the camera locked to the first
    frame's PCA pose.
    """
    import pyvista as pv

    foam = _find_foam_file(case_openfoam_dir)
    if foam is None:
        raise FileNotFoundError(f"No .foam under {case_openfoam_dir}")
    reader = pv.POpenFOAMReader(str(foam))
    all_times = list(reader.time_values or [])
    if not all_times:
        raise RuntimeError(f"No time values in {foam}")
    if times is None:
        times = all_times

    # First pass: find the global |U| range across the whole series so the
    # colourmap is comparable frame-to-frame.
    global_max = 0.0
    for t in times:
        reader.set_active_time_value(_resolve_render_time(all_times, t))
        internal = reader.read()["internalMesh"]
        if "U" in internal.point_data:
            u = np.asarray(internal.point_data["U"])
        else:
            u = np.asarray(internal.cell_data["U"])
        umag = np.linalg.norm(u, axis=1)
        global_max = max(global_max, float(np.percentile(umag, 98)))

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # Cache the camera from the first frame so it stays still across the series
    camera_pose = None

    for t in times:
        t_eff = _resolve_render_time(all_times, t)
        reader.set_active_time_value(t_eff)
        multiblock = reader.read()
        internal = multiblock["internalMesh"]
        _ensure_umag(internal)

        out_png = out_dir / f"velocity_t{t_eff:.3f}s.png"
        plotter = pv.Plotter(off_screen=True, window_size=list(window_size))
        plotter.set_background("white")

        boundary = multiblock.get("boundary") if hasattr(multiblock, "get") else None
        wall = boundary[wall_patch] if boundary is not None and wall_patch in boundary.keys() else None
        if wall is not None and wall_opacity > 0.0:
            plotter.add_mesh(
                wall, color="lightgray", opacity=wall_opacity,
                specular=0.1, show_scalar_bar=False,
            )

        iso = _build_isosurfaces(internal, "U_magnitude", n_levels=iso_levels)
        plotter.add_mesh(
            iso,
            scalars="U_magnitude",
            cmap=cmap,
            clim=(0.0, global_max),
            opacity=iso_opacity,
            scalar_bar_args=dict(
                title=f"|U| (m/s) — t={t_eff:.3f}s",
                n_labels=5,
                fmt="%.2f",
                vertical=True,
                position_x=0.88,
                position_y=0.12,
                width=0.06,
                height=0.76,
            ),
        )
        if camera_pose is None:
            camera_pose = _camera_pose_max_silhouette(internal)
        plotter.camera_position = camera_pose
        plotter.screenshot(str(out_png))
        plotter.close()
        written.append(out_png)

    logger.info(
        "PyVista wrote %d time-series frames to %s (|U| clim 0–%.3f m/s, %d iso @ %.0f%% opacity)",
        len(written), out_dir, global_max, iso_levels, iso_opacity * 100,
    )
    return written


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
    time_series: bool = True,
) -> list[Path]:
    """Run the PyVista post-processor on an AortaCFD run.

    `case_dir` is the top-level run directory (the one that contains
    `openfoam/`, `reports/`, `results/`). Writes PNGs under
    `case_dir/<out_subdir>/` and returns the list of paths written.

    Each renderer is wrapped in try/except — a missing field on one
    output should not block the others.
    """
    case_dir = Path(case_dir)
    openfoam_dir = case_dir / "openfoam"
    if not openfoam_dir.is_dir():
        raise FileNotFoundError(
            f"Expected `{openfoam_dir}` (with snappy mesh + solver output); not found."
        )

    images_dir = case_dir / out_subdir
    written: list[Path] = []

    # Static single-time renders
    for label, fn, name in [
        ("velocity",        render_velocity_magnitude, "velocity_peak_systole.png"),
        ("wallShearStress", render_wall_shear_stress,  "wall_shear_stress.png"),
        ("pressure_clip",   render_pressure_clip,      "pressure_clip.png"),
    ]:
        try:
            written.append(fn(openfoam_dir, images_dir / name))
        except Exception as exc:    # noqa: BLE001
            logger.warning("PyVista %s render failed: %s", label, exc)

    # Multi-time velocity series, locked colourmap so frames are comparable
    if time_series:
        try:
            written.extend(
                render_velocity_time_series(openfoam_dir, images_dir / "velocity_series")
            )
        except Exception as exc:    # noqa: BLE001
            logger.warning("PyVista velocity time-series render failed: %s", exc)

    return written
