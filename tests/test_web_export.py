"""Tests for the web viewer exporter (aortacfd_lib.web_export).

The pure helpers are tested directly. The whole export runs on a fake case
built from pyvista primitives (a straight square duct with uniform flow), so
no OpenFOAM run is needed.
"""

import json
import struct

import numpy as np
import pytest

pv = pytest.importorskip("pyvista")

from aortacfd_lib import web_export as we  # noqa: E402


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def test_classify_patches_picks_by_name():
    p = we.classify_patches(["wall_aorta", "inlet", "outlet2", "outlet1"])
    assert p == {"wall": "wall_aorta", "inlet": "inlet", "outlets": ["outlet1", "outlet2"]}
    with pytest.raises(ValueError):
        we.classify_patches(["wall_aorta", "outlet1"])


def test_pick_frames_spacing_and_last():
    assert we.pick_frames(10, None) == list(range(10))
    assert we.pick_frames(10, 1) == [9]
    assert we.pick_frames(10, 4) == [0, 3, 6, 9]
    assert we.pick_frames(0, 3) == []


def test_quantise_u8_clips_and_scales():
    q = we.quantise_u8(np.array([-1.0, 0.0, 0.5, 1.0, 2.0]), 0.0, 1.0)
    assert q.dtype == np.uint8
    assert q.tolist() == [0, 0, 128, 255, 255]
    assert we.quantise_u8(np.array([3.0, 3.0]), 3.0, 3.0).tolist() == [0, 0]  # flat field, no divide by zero


def test_resample_polyline_equal_spacing_and_cap():
    xyz = np.column_stack([np.linspace(0, 10, 101), np.zeros(101), np.zeros(101)])
    speed = np.linspace(1, 2, 101)
    out, sp = we.resample_polyline(xyz, speed, spacing=0.5, max_points=1000)
    assert out.shape == (21, 3)
    assert np.allclose(np.diff(out[:, 0]), 0.5)
    assert np.isclose(sp[0], 1.0) and np.isclose(sp[-1], 2.0)
    out2, _ = we.resample_polyline(xyz, speed, spacing=0.5, max_points=5)
    assert len(out2) == 5 and np.isclose(out2[-1, 0], 2.0)


def test_despike_removes_single_point_spikes():
    s = np.array([0.3, 0.9, 12.85, 0.66, 0.55])
    out = we.despike(s)
    assert out.max() < 1.0
    assert np.allclose(we.despike(np.array([1.0, 2.0])), [1.0, 2.0])


def test_patch_flux_on_a_plane():
    plane = pv.Plane(center=(0, 0, 0), direction=(0, 0, 1), i_size=2.0, j_size=1.0, i_resolution=4, j_resolution=2)
    plane = plane.triangulate()
    plane.cell_data["U"] = np.tile([0.0, 0.0, 3.0], (plane.n_cells, 1))
    assert np.isclose(abs(we.patch_flux(plane)), 3.0 * 2.0 * 1.0)
    g = we.cap_geometry(plane)
    assert np.isclose(g["radius"], np.sqrt(2.0 / np.pi))
    assert np.allclose(np.abs(g["normal"]), [0, 0, 1])


def test_write_glb_is_valid_and_keeps_custom_attributes(tmp_path):
    tri = pv.Sphere(theta_resolution=8, phi_resolution=8).triangulate()
    faces = np.asarray(tri.faces).reshape(-1, 4)[:, 1:]
    out = tmp_path / "scene.glb"
    n = we.write_glb(
        out,
        [{"name": "wall", "positions": tri.points, "indices": faces, "attributes": {"_WSS": np.arange(tri.n_points)}}],
    )
    raw = out.read_bytes()
    assert n == len(raw)
    magic, version, total = struct.unpack_from("<III", raw, 0)
    assert magic == we.GLB_MAGIC and version == 2 and total == len(raw)
    jlen, jtype = struct.unpack_from("<II", raw, 12)
    assert jtype == we.GLB_JSON
    gltf = json.loads(raw[20 : 20 + jlen])
    prim = gltf["meshes"][0]["primitives"][0]
    assert set(prim["attributes"]) == {"POSITION", "_WSS"}
    assert gltf["accessors"][prim["attributes"]["POSITION"]]["count"] == tri.n_points
    assert gltf["accessors"][prim["indices"]]["count"] == 3 * tri.n_cells
    assert gltf["nodes"][0]["name"] == "wall"


# ----------------------------------------------------------------------------
# whole export on a fake case: square duct, uniform flow along +z
# ----------------------------------------------------------------------------
class _FakeCase:
    """Stands in for web_export._Case: a 1 cm square duct, 10 cm long, U = (0, 0, 0.5) m/s."""

    def __init__(self, case_dir):
        self.times = [0.0, 0.1, 0.2]
        self.patches = {"wall": "wall_duct", "inlet": "inlet", "outlets": ["outlet1"]}
        grid = pv.ImageData(dimensions=(6, 6, 41), spacing=(0.002, 0.002, 0.0025), origin=(-0.005, -0.005, 0.0))
        self.grid = grid.cast_to_unstructured_grid()

    def _fields(self, ds, t):
        z = np.asarray(ds.points)[:, 2]
        ds.point_data["U"] = np.column_stack([np.zeros_like(z), np.zeros_like(z), np.full_like(z, 0.5)])
        ds.point_data["p"] = 1.0 - 5.0 * z  # kinematic, falls along the duct
        ds.point_data["wallShearStress"] = np.column_stack(
            [np.zeros_like(z), np.zeros_like(z), np.full_like(z, -0.002 * (1 + t))]
        )
        ds = ds.point_data_to_cell_data(pass_point_data=True)
        return ds

    def frame(self, t):
        internal = self._fields(self.grid.copy(), t)
        surf = self._fields(self.grid.extract_surface(), t)
        n = np.asarray(
            surf.compute_normals(cell_normals=True, point_normals=False, auto_orient_normals=True).cell_data["Normals"]
        )
        inlet = surf.extract_cells(np.where(n[:, 2] < -0.5)[0]).extract_surface()
        outlet = surf.extract_cells(np.where(n[:, 2] > 0.5)[0]).extract_surface()
        wall = surf.extract_cells(np.where(np.abs(n[:, 2]) < 0.5)[0]).extract_surface()
        return internal, {"wall_duct": wall, "inlet": inlet, "outlet1": outlet}


def test_export_run_on_fake_duct(tmp_path, monkeypatch):
    monkeypatch.setattr(we, "_Case", _FakeCase)
    run = tmp_path / "run"
    (run / "reports").mkdir(parents=True)
    (run / "reports" / "merged_config.json").write_text(
        json.dumps(
            {
                "case_info": {"name": "duct", "description": "test duct"},
                "physics": {"blood_density": 1000.0},
                "boundary_conditions": {"inlet_settings": {"type": "TIMEVARYING"}},
                "simulation_control": {"cardiac_cycle_period": 0.2},
            }
        )
    )
    out = tmp_path / "bundle"
    meta = we.export_run(run, out, n_paths=20, keyframes=2, max_faces=0)
    for name in ("meta.json", "scene.glb", "flow.bin"):
        assert (out / name).exists()
    assert meta["format"] == we.BUNDLE_FORMAT
    assert meta["pulsatile"] is True
    assert meta["frame_times"] == [0.1, 0.2]  # t = 0 is skipped
    assert meta["patches"]["outlets"] == ["outlet1"]
    # flux: 0.5 m/s through a 1 cm x 1 cm duct = 5e-5 m3/s = 3 L/min, in and out
    assert np.allclose(meta["flow"]["inlet_L_min"], 3.0, rtol=1e-6)
    assert np.isclose(meta["flow"]["share_mean"]["outlet1"], 1.0)
    assert abs(meta["flow"]["balance_error"]) < 1e-6
    # fields: pressure drop from the inlet grows along the duct; wall shear stress is 0.002 (1 + t) kinematic,
    # so 2.2 Pa at t = 0.1 and 2.4 Pa at t = 0.2 with rho = 1000
    assert meta["fields"]["dp"]["hi"] > meta["fields"]["dp"]["lo"]
    assert meta["fields"]["wss"]["hi"] == pytest.approx(2.4, rel=0.05)
    assert len(meta["fields"]["p"]["frames"]) == 2
    assert len(meta["paths"]) == 2 and all(p["n"] > 0 for p in meta["paths"])
    assert meta["speed_max"] == pytest.approx(0.5, rel=0.05)
    assert meta["bin_bytes"] == (out / "flow.bin").stat().st_size
    assert meta["glb_bytes"] == (out / "scene.glb").stat().st_size
    assert meta["summary"]["inlet_flow_peak_L_min"] == pytest.approx(3.0, rel=1e-4)
    # the uint8 frames cover every wall point
    raw = (out / "flow.bin").read_bytes()
    off = meta["fields"]["wss"]["frames"][1]
    frame = np.frombuffer(raw[off : off + meta["n_wall_points"]], np.uint8)
    assert frame.max() >= 250  # the last frame carries the maximum WSS


def test_export_run_steady_single_frame(tmp_path, monkeypatch):
    monkeypatch.setattr(we, "_Case", _FakeCase)
    run = tmp_path / "run"
    (run / "reports").mkdir(parents=True)
    (run / "reports" / "merged_config.json").write_text(
        json.dumps({"boundary_conditions": {"inlet_settings": {"type": "CONSTANT"}}})
    )
    meta = we.export_run(run, tmp_path / "b", n_paths=10, max_faces=0)
    assert meta["pulsatile"] is False
    assert meta["frame_times"] == [0.2]
    assert len(meta["paths"]) == 1
    assert meta["density_kg_m3"] == 1060.0


def test_monitor_flux_reads_solver_monitor_and_prefers_restart_values(tmp_path):
    """Shares must come from the solver's sum(phi) monitor when the run has one."""
    from aortacfd_lib.web_export import monitor_flux

    pp = tmp_path / "openfoam" / "postProcessing" / "outlet1Flow"
    (pp / "0").mkdir(parents=True)
    (pp / "0" / "surfaceFieldValue.dat").write_text("# Time sum(phi)\n0 0\n0.5 1e-4\n1.0 1e-4\n1.5 9e-5\n2.0 1e-4\n")
    (pp / "1.5").mkdir()
    (pp / "1.5" / "surfaceFieldValue.dat").write_text("# restart\n1.5 1e-4\n2.0 1e-4\n")
    # window with several samples: trapezoid mean; the restart folder overrides the 1.5 s sample
    assert monitor_flux(tmp_path, "outlet1", 0.5, 2.0) == pytest.approx(1e-4)
    # window with one sample: the nearest sample to t1
    assert monitor_flux(tmp_path, "outlet1", 2.0, 2.0) == pytest.approx(1e-4)
    # no monitor for this patch
    assert monitor_flux(tmp_path, "outlet2", 0.0, 2.0) is None


def test_tawss_is_the_mean_of_magnitudes_not_the_magnitude_of_the_mean():
    from aortacfd_lib.web_export import tawss_from_frames

    # one wall point whose shear flips sign between the frames: |mean vector| would be 0
    frames = [np.array([2.0, 1.0]), np.array([2.0, 1.0]), np.array([2.0, 1.0]), np.array([0.0, 1.0])]
    tawss = tawss_from_frames(frames)
    assert tawss is not None
    assert np.allclose(tawss, [1.5, 1.0])
    assert tawss_from_frames([np.array([2.0, 1.0])]) is None  # a steady run has no time average
