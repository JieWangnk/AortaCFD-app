"""Export a finished AortaCFD run as a small bundle for the web 3D viewer.

The bundle is one folder with three files:

* ``meta.json``  captions, numbers, patch list and byte offsets into ``flow.bin``
* ``scene.glb``  the surface of every patch (wall decimated), positions in mm,
                 with ``_P`` (mmHg) and ``_WSS`` (Pa) at the reference frame
* ``flow.bin``   wall fields per exported frame (uint8) and flow paths per
                 keyframe (int16 xyz, uint16 speed)

Everything is read from the OpenFOAM case with pyvista, so the exporter works
for any run the pipeline produced (aorta, U-bend, coarctation, coronary) as
long as the patch names contain ``inlet``, ``outlet`` and ``wall``.

Usage::

    python -m aortacfd_lib.web_export output/ubend/1cycle_wk_laptop_A \\
        -o ../AortaCFD-web/docs/assets/cases/ubend --title "U-bend, pulsatile"
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import struct
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

PA_PER_MMHG = 133.322
M3S_TO_LMIN = 60_000.0
BUNDLE_FORMAT = "aortacfd-web-bundle/1"
GLB_MAGIC = 0x46546C67
GLB_JSON = 0x4E4F534A
GLB_BIN = 0x004E4942
PULSATILE_TYPES = {"TIMEVARYING", "WOMERSLEY", "MAPPED_PROFILE", "MRI"}


# ----------------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------------
def _load_json(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def _density(config: dict) -> float:
    """Blood density from the merged config (kg/m^3), default 1060."""
    phys = config.get("physics", {}) if isinstance(config, dict) else {}
    for key in ("blood_density", "density", "rho"):
        val = phys.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return float(val)
    return 1060.0


def _inlet_type(config: dict) -> str:
    bc = config.get("boundary_conditions", {}) if isinstance(config, dict) else {}
    inlet = bc.get("inlet_settings") or bc.get("inlet") or {}
    return str(inlet.get("type", "")).upper()


def classify_patches(names: Sequence[str]) -> Dict[str, object]:
    """Pick wall, inlet and outlet patches by name."""
    wall = [n for n in names if "wall" in n.lower()]
    inlet = [n for n in names if "inlet" in n.lower()]
    outlets = sorted(n for n in names if "outlet" in n.lower())
    if not wall or not inlet:
        raise ValueError(f"Need a wall and an inlet patch; found {list(names)}")
    return {"wall": wall[0], "inlet": inlet[0], "outlets": outlets}


def pick_frames(n_times: int, n_frames: Optional[int]) -> List[int]:
    """Evenly spaced frame indices; always ends with the last time."""
    if n_times <= 0:
        return []
    if n_frames is None or n_frames >= n_times:
        return list(range(n_times))
    if n_frames <= 1:
        return [n_times - 1]
    idx = np.round(np.linspace(0, n_times - 1, n_frames)).astype(int)
    return sorted(set(int(i) for i in idx))


def quantise_u8(values: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Map values in [lo, hi] to uint8 0..255 (clipped)."""
    span = hi - lo if hi > lo else 1.0
    return np.clip(np.round((np.asarray(values, float) - lo) / span * 255.0), 0, 255).astype(np.uint8)


def resample_polyline(
    xyz: np.ndarray, speed: np.ndarray, spacing: float, max_points: int
) -> Tuple[np.ndarray, np.ndarray]:
    """Resample a polyline to equal arc-length spacing, keeping at most ``max_points``."""
    xyz = np.asarray(xyz, float)
    speed = np.asarray(speed, float)
    if len(xyz) < 2:
        return xyz, speed
    seg = np.linalg.norm(np.diff(xyz, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = s[-1]
    if total <= 0:
        return xyz[:1], speed[:1]
    n = int(min(max_points, max(2, np.floor(total / spacing) + 1)))
    si = np.linspace(0.0, min(total, spacing * (n - 1)), n)
    out = np.column_stack([np.interp(si, s, xyz[:, k]) for k in range(3)])
    return out, np.interp(si, s, speed)


def despike(values: np.ndarray) -> np.ndarray:
    """3-point median filter along a path; removes single-point interpolation spikes."""
    v = np.asarray(values, float)
    if len(v) < 3:
        return v
    stacked = np.vstack([np.r_[v[0], v[:-1]], v, np.r_[v[1:], v[-1]]])
    return np.median(stacked, axis=0)


def monitor_flux(run_dir, patch: str, t0: float, t1: float):
    """Time-mean volume flux (m^3/s, signed) of a patch between t0 and t1 from the
    solver's own sum(phi) monitor (postProcessing/<patch>Flow), or None when the
    run has no such monitor.

    The saved boundary velocity of a mixed outlet condition (the stabilised
    Windkessel velocity) is not the face flux the pressure equation conserved,
    so flow shares taken from the saved fields can be off by more than 10 % on
    a pulsatile run. The monitor is exact to solver tolerance.
    """
    files = sorted(Path(run_dir, "openfoam", "postProcessing", f"{patch}Flow").glob("*/surfaceFieldValue.dat"))
    if not files:
        return None
    rows = {}
    for f in files:  # a restart writes a second folder; later folders win on a repeated time
        for row in np.loadtxt(f, comments="#", ndmin=2):
            rows[float(row[0])] = float(row[1])
    if not rows:
        return None
    t = np.array(sorted(rows))
    q = np.array([rows[x] for x in t])
    m = (t >= t0 - 1e-9) & (t <= t1 + 1e-9)
    if m.sum() < 2:
        return float(q[int(np.argmin(np.abs(t - t1)))])
    return float(np.trapezoid(q[m], t[m]) / (t[m][-1] - t[m][0]))


def patch_flux(surface) -> float:
    """Signed volume flux through a patch surface from its face velocities (m^3/s).

    Positive means along the face normals, which follow the OpenFOAM face
    orientation (outward from the fluid) when the surface comes straight from
    the OpenFOAM reader.
    """
    if "U" not in surface.cell_data:
        return float("nan")
    s = surface.compute_normals(
        cell_normals=True, point_normals=False, auto_orient_normals=False, consistent_normals=False
    )
    areas = s.compute_cell_sizes(length=False, volume=False)["Area"]
    u = np.asarray(s.cell_data["U"], float)
    n = np.asarray(s.cell_data["Normals"], float)
    return float(np.sum(np.einsum("ij,ij->i", u, n) * areas))


def _patch_mean(surface, name: str) -> float:
    """Area-weighted mean of a scalar cell field on a patch (0 when the field is missing)."""
    if name not in surface.cell_data:
        return 0.0
    areas = np.asarray(surface.compute_cell_sizes(length=False, volume=False)["Area"], float)
    vals = np.asarray(surface.cell_data[name], float)
    return float(np.sum(vals * areas) / (areas.sum() or 1.0))


def cap_geometry(surface) -> dict:
    """Centre (m), equivalent radius (m) and mean outward normal of a cap patch."""
    s = surface.compute_normals(
        cell_normals=True, point_normals=False, auto_orient_normals=False, consistent_normals=False
    )
    areas = np.asarray(s.compute_cell_sizes(length=False, volume=False)["Area"], float)
    normals = np.asarray(s.cell_data["Normals"], float)
    centres = np.asarray(s.cell_centers().points, float)
    area = float(areas.sum())
    w = areas / area if area > 0 else np.full(len(areas), 1.0 / max(1, len(areas)))
    n = (normals * w[:, None]).sum(0)
    n = n / (np.linalg.norm(n) or 1.0)
    return {"centre": (centres * w[:, None]).sum(0), "radius": float(np.sqrt(area / np.pi)), "normal": n, "area": area}


def write_glb(path: Path, nodes: Sequence[dict]) -> int:
    """Write a minimal binary glTF 2.0 file.

    Each node is ``{"name", "positions" (n,3) float32, "indices" (m,3), "attributes": {name: (n,) float32}}``.
    Custom attribute names must start with an underscore (glTF rule).
    """
    buf = bytearray()
    views: List[dict] = []
    accessors: List[dict] = []
    meshes: List[dict] = []
    gnodes: List[dict] = []

    def add_view(arr: np.ndarray, target: int) -> int:
        a = np.ascontiguousarray(arr)
        off = len(buf)
        buf.extend(a.tobytes())
        while len(buf) % 4:
            buf.append(0)
        views.append({"buffer": 0, "byteOffset": off, "byteLength": int(a.nbytes), "target": target})
        return len(views) - 1

    for nd in nodes:
        pos = np.asarray(nd["positions"], np.float32)
        idx = np.asarray(nd["indices"]).ravel()
        idx = idx.astype(np.uint16 if len(pos) < 65536 else np.uint32)
        v = add_view(pos, 34962)
        accessors.append(
            {
                "bufferView": v,
                "componentType": 5126,
                "count": int(len(pos)),
                "type": "VEC3",
                "min": pos.min(0).tolist(),
                "max": pos.max(0).tolist(),
            }
        )
        attrs = {"POSITION": len(accessors) - 1}
        for name, arr in (nd.get("attributes") or {}).items():
            a = np.asarray(arr, np.float32)
            v = add_view(a, 34962)
            accessors.append({"bufferView": v, "componentType": 5126, "count": int(len(a)), "type": "SCALAR"})
            attrs[name] = len(accessors) - 1
        v = add_view(idx, 34963)
        accessors.append(
            {
                "bufferView": v,
                "componentType": 5123 if idx.dtype == np.uint16 else 5125,
                "count": int(len(idx)),
                "type": "SCALAR",
            }
        )
        meshes.append(
            {"name": nd["name"], "primitives": [{"attributes": attrs, "indices": len(accessors) - 1, "mode": 4}]}
        )
        gnodes.append({"name": nd["name"], "mesh": len(meshes) - 1})

    gltf = {
        "asset": {"version": "2.0", "generator": "AortaCFD web_export"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(gnodes)))}],
        "nodes": gnodes,
        "meshes": meshes,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(buf)}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    while len(js) % 4:
        js += b" "
    total = 12 + 8 + len(js) + 8 + len(buf)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", GLB_MAGIC, 2, total))
        f.write(struct.pack("<II", len(js), GLB_JSON))
        f.write(js)
        f.write(struct.pack("<II", len(buf), GLB_BIN))
        f.write(buf)
    return total


class _Blob:
    """Append-only byte buffer; returns 4-byte-aligned offsets."""

    def __init__(self):
        self.buf = bytearray()

    def put(self, arr: np.ndarray) -> int:
        a = np.ascontiguousarray(arr)
        while len(self.buf) % 4:
            self.buf.append(0)
        off = len(self.buf)
        self.buf.extend(a.tobytes())
        return off


# ----------------------------------------------------------------------------
# OpenFOAM reading
# ----------------------------------------------------------------------------
class _Case:
    """Thin wrapper around pyvista's OpenFOAM reader."""

    def __init__(self, case_dir: Path):
        import pyvista as pv

        case_dir = Path(case_dir)
        foam = case_dir / "openfoam.foam"
        if not foam.exists():
            foam.touch()
        self.reader = pv.OpenFOAMReader(str(foam))
        self.reader.cell_to_point_creation = True
        self.reader.enable_all_patch_arrays()
        self.times = [float(t) for t in self.reader.time_values]
        names = [n.split("/", 1)[1] for n in self.reader.patch_array_names if n.startswith("patch/")]
        self.patches = classify_patches(names)

    def frame(self, t: float):
        """Return (internal mesh, {patch: surface}) at time t."""
        self.reader.set_active_time_value(t)
        mb = self.reader.read()
        boundary = mb["boundary"]
        surfaces = {k: boundary[k].extract_surface() for k in boundary.keys()}
        return mb["internalMesh"], surfaces


def _wall_surface(surface, max_faces: int):
    """Triangulated, cleaned wall; decimated when it has more than max_faces triangles."""
    tri = surface.triangulate().clean()
    if max_faces and tri.n_cells > max_faces:
        tri = tri.decimate(1.0 - max_faces / tri.n_cells, attribute_error=False).clean()
    return tri


def tawss_from_frames(w_frames) -> Optional[np.ndarray]:
    """Time-averaged wall shear stress: the mean over the exported frames of |wss| per wall point.

    This is the mean of magnitudes. The magnitude of the solver's mean vector
    (wallShearStressMean) is smaller wherever the shear changes direction and
    was used here before 21 Nov 2026. One frame (a steady run) gives no TAWSS.
    """
    if len(w_frames) < 2:
        return None
    return np.mean(np.stack([np.asarray(w, float) for w in w_frames]), axis=0)


def _point_field(poly, name: str, index: np.ndarray, ncomp: int) -> np.ndarray:
    """Point array ``name`` at the given point indices; zeros (with a warning) when the array is missing."""
    if name in poly.point_data:
        return np.asarray(poly.point_data[name], float)[index]
    logger.warning("web_export: field %s missing at this time, using zeros", name)
    shape = (len(index),) if ncomp == 1 else (len(index), ncomp)
    return np.zeros(shape)


def _faces_of(poly) -> np.ndarray:
    faces = np.asarray(poly.faces).reshape(-1, 4)
    assert (faces[:, 0] == 3).all(), "surface must be triangles"
    return faces[:, 1:]


def _streamlines(internal, inlet_surface, n_seeds: int, max_length: float, rng: np.random.Generator):
    """Forward streamlines seeded on the inlet; returns list of (xyz, |U|) in SI."""
    import pyvista as pv

    centres = np.asarray(inlet_surface.cell_centers().points, float)
    u = np.asarray(inlet_surface.cell_data["U"], float) if "U" in inlet_surface.cell_data else None
    if u is not None:
        mag = np.linalg.norm(u, axis=1)
        keep = mag > 0.05 * (mag.max() or 1.0)
        centres = centres[keep] if keep.any() else centres
    if len(centres) > n_seeds:
        centres = centres[rng.choice(len(centres), n_seeds, replace=False)]
    seeds = pv.PolyData(centres)
    sl = internal.streamlines_from_source(
        seeds,
        vectors="U",
        integration_direction="forward",
        max_time=max_length,
        initial_step_length=0.2,
        max_step_length=0.5,
        terminal_speed=1e-5,
        compute_vorticity=False,
    )
    if sl.n_points == 0:
        return []
    pts = np.asarray(sl.points, float)
    speed = np.linalg.norm(np.asarray(sl["U"], float), axis=1)
    # the streamer sometimes interpolates one wild value at a cell edge; cap at the field's own maximum
    if "U" in internal.point_data:
        speed = np.minimum(speed, float(np.linalg.norm(np.asarray(internal.point_data["U"], float), axis=1).max()))
    cells = np.asarray(sl.lines)
    out = []
    i = 0
    while i < len(cells):
        n = int(cells[i])
        ids = cells[i + 1 : i + 1 + n]
        if n >= 4:
            out.append((pts[ids], despike(speed[ids])))
        i += n + 1
    return out


# ----------------------------------------------------------------------------
# main export
# ----------------------------------------------------------------------------
def _run_numbers(run_dir: Path) -> dict:
    """Numbers the pipeline already wrote: QoIs, mesh size, provenance."""
    out: dict = {"qoi": {}, "mesh": {}, "provenance": {}}
    for rel in ("reports/results/qoi_summary.json", "results/qoi_summary.json"):
        q = _load_json(run_dir / rel)
        if q:
            out["qoi"] = q.get("qoi", {})
            out["per_outlet_pressure_drop_mmhg"] = q.get("per_outlet_pressure_drop_mmhg", {})
            break
    mq = _load_json(run_dir / "reports" / "mesh_quality_summary.json")
    if mq:
        out["mesh"] = {k: mq.get(k) for k in ("n_cells", "cells", "max_non_orthogonality", "max_skewness") if k in mq}
    if not out["mesh"].get("n_cells") and not out["mesh"].get("cells"):
        try:
            import re

            txt = (run_dir / "openfoam" / "logs" / "log.checkMesh").read_text(errors="ignore")
            m = re.search(r"^\s*cells:\s+(\d+)", txt, re.M)
            if m:
                out["mesh"]["n_cells"] = int(m.group(1))
        except OSError:
            pass
    rc = _load_json(run_dir / "reports" / "ro-crate-metadata.json")
    for ent in rc.get("@graph", []):
        if ent.get("@id") == "#aortacfd":
            out["provenance"]["aortacfd_version"] = ent.get("version")
            out["provenance"]["git_commit"] = ent.get("gitCommit")
        if ent.get("@id") == "#openfoam":
            out["provenance"]["openfoam"] = ent.get("version")
    return out


def export_run(
    run_dir: Path,
    out_dir: Path,
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    source: Optional[str] = None,
    licence: Optional[str] = None,
    max_faces: int = 24000,
    n_paths: int = 300,
    path_points: int = 160,
    keyframes: int = 4,
    frames: Optional[int] = None,
    seed: int = 0,
    poster: Optional[Path] = None,
) -> dict:
    """Export one run folder (``output/<case>/<run>``) to ``out_dir``; returns the meta dict."""
    run_dir = Path(run_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    config = _load_json(run_dir / "reports" / "merged_config.json")
    rho = _density(config)
    pulsatile = _inlet_type(config) in PULSATILE_TYPES
    case = _Case(run_dir / "openfoam")
    if not case.times:
        raise ValueError(f"No time directories under {run_dir / 'openfoam'}")
    # the initial time holds no solved fields (no wallShearStress), so skip it when other times exist
    usable = case.times[1:] if len(case.times) > 1 else case.times
    frame_idx = pick_frames(len(usable), frames if pulsatile else 1)
    frame_times = [usable[i] for i in frame_idx]
    rng = np.random.default_rng(seed)
    blob = _Blob()
    P = case.patches
    logger.info("web_export: %s, %d frames, patches %s", run_dir, len(frame_idx), P)

    # --- geometry from the last frame (same mesh at every time) ---
    internal, surf = case.frame(frame_times[-1])
    wall_full = surf[P["wall"]].triangulate().clean()
    wall = _wall_surface(surf[P["wall"]], max_faces)
    from scipy.spatial import cKDTree

    nearest = cKDTree(np.asarray(wall_full.points)).query(np.asarray(wall.points))[1]
    bounds = np.asarray(internal.bounds, float).reshape(3, 2)
    origin = bounds.mean(1)
    diag = float(np.linalg.norm(bounds[:, 1] - bounds[:, 0]))
    to_mm = lambda x: (np.asarray(x, float) - origin) * 1000.0  # noqa: E731
    caps = {}
    for name in [P["inlet"]] + list(P["outlets"]):
        g = cap_geometry(surf[name])
        caps[name] = {
            "centre": np.round(to_mm(g["centre"]), 3).tolist(),
            "radius_mm": round(g["radius"] * 1000.0, 3),
            "normal": np.round(g["normal"], 4).tolist(),
        }

    # --- per-frame wall fields and fluxes ---
    p_frames, w_frames, p_inlet = [], [], []
    q_in, q_out = [], {o: [] for o in P["outlets"]}
    path_sets = {}
    key_idx = set(pick_frames(len(frame_idx), keyframes if pulsatile else 1))
    for k, t in enumerate(frame_times):
        internal, surf = case.frame(t)
        wf = surf[P["wall"]].triangulate().clean()
        p_frames.append(_point_field(wf, "p", nearest, 1) * rho / PA_PER_MMHG)
        w_frames.append(np.linalg.norm(_point_field(wf, "wallShearStress", nearest, 3), axis=1) * rho)
        q_in.append(abs(patch_flux(surf[P["inlet"]])))
        p_inlet.append(_patch_mean(surf[P["inlet"]], "p") * rho / PA_PER_MMHG)
        for o in P["outlets"]:
            q_out[o].append(abs(patch_flux(surf[o])))
        if k in key_idx:
            lines = _streamlines(internal, surf[P["inlet"]], n_paths, 3.0 * diag, rng)
            path_sets[k] = lines
    tawss = tawss_from_frames(w_frames)

    # --- quantised fields into the blob ---
    p_all = np.concatenate(p_frames)
    w_all = np.concatenate(w_frames)
    p_lo, p_hi = (float(x) for x in np.percentile(p_all, [0.5, 99.5]))
    dp_frames = [pin - f for pin, f in zip(p_inlet, p_frames)]  # pressure drop from the inlet, positive downstream
    dp_all = np.concatenate(dp_frames)
    dp_lo, dp_hi = (float(x) for x in np.percentile(dp_all, [0.5, 99.5]))
    w_lo, w_hi = 0.0, float(np.percentile(w_all, 99.5))
    fields = {
        "p": {
            "lo": p_lo,
            "hi": p_hi,
            "unit": "mmHg",
            "clip": "0.5th to 99.5th percentile",
            "frames": [blob.put(quantise_u8(f, p_lo, p_hi)) for f in p_frames],
        },
        "dp": {
            "lo": dp_lo,
            "hi": dp_hi,
            "unit": "mmHg",
            "label": "pressure drop from the inlet",
            "clip": "0.5th to 99.5th percentile",
            "frames": [blob.put(quantise_u8(f, dp_lo, dp_hi)) for f in dp_frames],
        },
        "wss": {
            "lo": w_lo,
            "hi": w_hi,
            "unit": "Pa",
            "clip": "99.5th percentile",
            "frames": [blob.put(quantise_u8(f, w_lo, w_hi)) for f in w_frames],
        },
    }
    if tawss is not None:
        t_hi = float(np.percentile(tawss, 99.5))
        fields["tawss"] = {
            "lo": 0.0,
            "hi": t_hi,
            "unit": "Pa",
            "clip": "99.5th percentile",
            "off": blob.put(quantise_u8(tawss, 0.0, t_hi)),
        }

    # --- flow paths into the blob ---
    max_abs_mm = float(np.abs(to_mm(bounds.T)).max()) or 1.0
    pos_scale = int(max(1, min(100, np.floor(32000.0 / max_abs_mm))))
    all_speed = np.concatenate([s for lines in path_sets.values() for _, s in lines]) if path_sets else np.ones(1)
    speed_max = float(np.percentile(all_speed, 99.5)) or 1.0
    paths = []
    for k in sorted(path_sets):
        lines = path_sets[k]
        if not lines:
            continue
        lengths = [float(np.linalg.norm(np.diff(x, axis=0), axis=1).sum()) for x, _ in lines]
        spacing = max(diag / 220.0, float(np.percentile(lengths, 95)) / path_points)
        res = [resample_polyline(x, s, spacing, path_points) for x, s in lines]
        res = [(x, s) for x, s in res if len(x) >= 4]
        lens = np.array([len(x) for x, _ in res], np.uint16)
        xyz = np.vstack([to_mm(x) for x, _ in res])
        sp = np.concatenate([s for _, s in res])
        paths.append(
            {
                "frame": k,
                "spacing_mm": round(spacing * 1000.0, 4),
                "n": int(len(res)),
                "np": int(len(xyz)),
                "lens": blob.put(lens),
                "xyz": blob.put(np.round(xyz * pos_scale).astype(np.int16)),
                "sp": blob.put(np.clip(sp / speed_max * 65535.0, 0, 65535).astype(np.uint16)),
            }
        )

    # --- surface file ---
    ref = int(np.argmax(q_in)) if pulsatile else len(frame_idx) - 1
    nodes = [
        {
            "name": P["wall"],
            "positions": to_mm(wall.points),
            "indices": _faces_of(wall),
            "attributes": {"_P": p_frames[ref], "_WSS": w_frames[ref]},
        }
    ]
    for name in [P["inlet"]] + list(P["outlets"]):
        cap = surf[name].triangulate().clean()
        nodes.append({"name": name, "positions": to_mm(cap.points), "indices": _faces_of(cap)})
    glb_bytes = write_glb(out_dir / "scene.glb", nodes)
    (out_dir / "flow.bin").write_bytes(bytes(blob.buf))

    # --- numbers ---
    q_in_arr = np.asarray(q_in)
    q_out_sum = np.sum([np.asarray(v) for v in q_out.values()], axis=0) if q_out else np.zeros_like(q_in_arr)
    share = {o: float(np.mean(v) / (np.mean(q_out_sum) or 1.0)) for o, v in q_out.items()}
    balance = float((np.mean(q_out_sum) - np.mean(q_in_arr)) / (np.mean(q_in_arr) or 1.0))
    flow_method = (
        "face velocity dot face normal times face area, per patch, from the saved fields; "
        "shares are time means over the exported frames"
    )
    period = (config.get("simulation_control", {}) if isinstance(config, dict) else {}).get("cardiac_cycle_period")
    t1 = float(frame_times[-1])
    t0 = max(float(frame_times[0]), t1 - float(period)) if (pulsatile and period) else float(frame_times[0])
    mon_in = monitor_flux(run_dir, P["inlet"], t0, t1)
    mon_out = {o: monitor_flux(run_dir, o, t0, t1) for o in P["outlets"]}
    if mon_in is not None and mon_out and all(v is not None for v in mon_out.values()):
        q_in_mon = abs(mon_in)
        q_out_mon = float(sum(mon_out.values()))  # signed: reversed flow counts against its patch
        share = {o: float(v / (q_out_mon or 1.0)) for o, v in mon_out.items()}
        balance = float((q_out_mon - q_in_mon) / (q_in_mon or 1.0))
        flow_method = (
            f"solver sum(phi) monitors (postProcessing/<patch>Flow), time mean over t = {t0:g} to {t1:g} s"
            + (" (the last cycle)" if pulsatile and period else "")
            + "; the per-frame series above come from the saved fields"
        )
    case_info = config.get("case_info", {}) if isinstance(config, dict) else {}
    sim = config.get("simulation_control", {}) if isinstance(config, dict) else {}
    meta = {
        "format": BUNDLE_FORMAT,
        "title": title or case_info.get("name") or run_dir.parent.name,
        "description": description or case_info.get("description") or "",
        "source": source or "",
        "licence": licence or "",
        "case": run_dir.parent.name,
        "run": run_dir.name,
        "generated": _dt.date.today().isoformat(),
        "units": {"position": "mm", "p": "mmHg", "wss": "Pa", "flow": "L/min", "speed": "m/s"},
        "origin_m": np.round(origin, 6).tolist(),
        "extent_mm": np.round((bounds[:, 1] - bounds[:, 0]) * 1000.0, 2).tolist(),
        "density_kg_m3": rho,
        "patches": P,
        "caps": caps,
        "n_wall_points": int(wall.n_points),
        "n_wall_faces": int(wall.n_cells),
        "n_wall_faces_full": int(wall_full.n_cells),
        "pulsatile": bool(pulsatile),
        "inlet_type": _inlet_type(config),
        "cycle_period_s": sim.get("cardiac_cycle_period"),
        "times": [round(t, 6) for t in case.times],
        "frame_times": [round(t, 6) for t in frame_times],
        "reference_frame": ref,
        "flow": {
            "inlet_L_min": np.round(q_in_arr * M3S_TO_LMIN, 4).tolist(),
            "inlet_pressure_mmHg": np.round(p_inlet, 3).tolist(),
            "outlets_L_min": {o: np.round(np.asarray(v) * M3S_TO_LMIN, 4).tolist() for o, v in q_out.items()},
            "share_mean": {o: round(s, 4) for o, s in share.items()},
            "balance_error": round(balance, 5),
            "method": flow_method,
        },
        "fields": fields,
        "paths": paths,
        "pos_scale": pos_scale,
        "speed_max": speed_max,
        "bin_bytes": len(blob.buf),
        "glb_bytes": glb_bytes,
        "export": {
            "max_faces": max_faces,
            "n_paths": n_paths,
            "path_points": path_points,
            "keyframes": sorted(path_sets),
            "seed": seed,
        },
    }
    if poster is not None and Path(poster).is_file():
        import shutil

        target = out_dir / ("poster" + Path(poster).suffix.lower())
        shutil.copyfile(poster, target)
        meta["poster"] = target.name
    meta.update(_run_numbers(run_dir))
    summary = {
        "inlet_flow_mean_L_min": round(float(np.mean(q_in_arr)) * M3S_TO_LMIN, 3),
        "inlet_flow_peak_L_min": round(float(np.max(q_in_arr)) * M3S_TO_LMIN, 3),
        "wss_p99_Pa_at_reference_frame": round(float(np.percentile(w_frames[ref], 99)), 3),
        "wall_pressure_range_mmHg_at_reference_frame": [
            round(float(p_frames[ref].min()), 2),
            round(float(p_frames[ref].max()), 2),
        ],
    }
    if tawss is not None:
        summary["tawss_mean_Pa"] = round(float(tawss.mean()), 3)
        summary["tawss_p95_Pa"] = round(float(np.percentile(tawss, 95)), 3)
    meta["summary"] = summary
    (out_dir / "meta.json").write_text(json.dumps(meta, separators=(",", ":")))
    logger.info("web_export: wrote %s (glb %d B, bin %d B)", out_dir, glb_bytes, len(blob.buf))
    return meta


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Export an AortaCFD run for the web 3D viewer")
    ap.add_argument("run_dir", help="run folder, e.g. output/ubend/1cycle_wk_laptop_A")
    ap.add_argument("-o", "--out", required=True, help="bundle folder to write (meta.json, scene.glb, flow.bin)")
    ap.add_argument("--title")
    ap.add_argument("--description")
    ap.add_argument("--source", help="where the geometry and data come from (shown on the page)")
    ap.add_argument("--licence", help="licence of the published data")
    ap.add_argument("--max-faces", type=int, default=24000)
    ap.add_argument("--paths", type=int, default=300, help="flow paths per keyframe")
    ap.add_argument("--path-points", type=int, default=160, help="max points per flow path")
    ap.add_argument("--keyframes", type=int, default=4, help="frames at which flow paths are computed (pulsatile runs)")
    ap.add_argument("--frames", type=int, default=None, help="number of wall-field frames to export (default: all)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--poster", help="still image copied into the bundle and shown until the 3D view is ready")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    meta = export_run(
        a.run_dir,
        a.out,
        title=a.title,
        description=a.description,
        source=a.source,
        licence=a.licence,
        max_faces=a.max_faces,
        n_paths=a.paths,
        path_points=a.path_points,
        keyframes=a.keyframes,
        frames=a.frames,
        seed=a.seed,
        poster=a.poster,
    )
    print(
        f"wrote {a.out}: wall {meta['n_wall_faces']} faces ({meta['n_wall_faces_full']} full), "
        f"{len(meta['frame_times'])} frames, {len(meta['paths'])} path sets, "
        f"glb {meta['glb_bytes'] / 1e6:.2f} MB, bin {meta['bin_bytes'] / 1e6:.2f} MB"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
