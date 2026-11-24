"""Split the engine's multi-solid ASCII STL (named solids: wall_AAo, wall_ARCH, wall_DAo, inlet, outlet_DAo)
into the three binary patch files AortaCFD-app reads: wall_aorta.stl (all wall solids), inlet.stl, outlet1.stl.
Usage: python3 split_stl.py IN.stl OUT_DIR [--align-outlet]   (prints the solids found and the patch statistics)

--align-outlet rotates the whole geometry (about the origin) so the outlet cap's outward normal is exactly -z and the
inlet normal lies in the x-z half-plane x > 0. Why: snappyHexMesh cuts a cap plane that is diagonal to its background
grid into stair-step rim cells, some with two faces on the pressure outlet and volumes under a tenth of the median; on
the 108-degree twisted arch (outlet normal 40 degrees from every axis) one such cell grew a reverse jet from 0.5 to
2.5 m/s in early diastole and the time step collapsed at 0.474 s (23 Nov 2026). An axis-aligned outlet plane has no
such cells (the planar bend: none). The velocity inlet tolerates stair-step cells; the pressure outlet does not."""
import pathlib
import sys

import numpy as np
import pyvista as pv


def read_solids(path):
    solids, name, tri, cur = {}, None, [], []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith("solid"):
                name, tri = s[5:].strip() or f"solid{len(solids)}", []
            elif s.startswith("vertex"):
                cur.append([float(v) for v in s.split()[1:4]])
                if len(cur) == 3:
                    tri.append(cur); cur = []
            elif s.startswith("endsolid"):
                solids[name] = np.array(tri, dtype=float)
    return solids


def polydata(tris):
    n = len(tris)
    pts = tris.reshape(-1, 3)
    faces = np.hstack([np.full((n, 1), 3), np.arange(3 * n).reshape(n, 3)]).ravel()
    return pv.PolyData(pts, faces).clean()


def _cap_normal(tris, body_centre):
    """Unit outward normal of a cap (area-weighted mean of the triangle normals, signed away from the body)."""
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]).sum(axis=0)
    n /= np.linalg.norm(n)
    if n @ (tris.reshape(-1, 3).mean(axis=0) - body_centre) < 0:
        n = -n
    return n


def _rotation_to(a, b):
    """Rotation matrix taking unit vector a onto unit vector b (Rodrigues; 180 degrees handled)."""
    a = np.asarray(a, float) / np.linalg.norm(a); b = np.asarray(b, float) / np.linalg.norm(b)
    v = np.cross(a, b); c = float(a @ b)
    if np.linalg.norm(v) < 1e-12:
        if c > 0:
            return np.eye(3)
        axis = np.cross(a, [1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.cross(a, [0.0, 1.0, 0.0])
        axis /= np.linalg.norm(axis)
        return 2.0 * np.outer(axis, axis) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]], float)
    return np.eye(3) + vx + vx @ vx / (1.0 + c)


def align_outlet(solids):
    """Rotate every solid so the outlet cap normal is -z and the inlet normal lies in the x-z half-plane x > 0.
    Returns (rotated solids, record dict)."""
    walls = np.concatenate([v for k, v in solids.items() if k.startswith("wall")])
    inlet = [v for k, v in solids.items() if k.startswith("inlet")][0]
    outlet = [v for k, v in solids.items() if k.startswith("outlet")][0]
    body = walls.reshape(-1, 3).mean(axis=0)
    n_out, n_in = _cap_normal(outlet, body), _cap_normal(inlet, body)
    r1 = _rotation_to(n_out, [0.0, 0.0, -1.0])
    nin = r1 @ n_in
    ang = np.arctan2(nin[1], nin[0])
    ca, sa = np.cos(-ang), np.sin(-ang)
    r2 = np.array([[ca, -sa, 0.0], [sa, ca, 0.0], [0.0, 0.0, 1.0]])
    rot = r2 @ r1
    rotated = {k: v @ rot.T for k, v in solids.items()}
    rec = dict(applied=True, matrix=np.round(rot, 9).tolist(), outlet_normal_before=np.round(n_out, 4).tolist(),
               inlet_normal_before=np.round(n_in, 4).tolist(), outlet_normal_after=np.round(rot @ n_out, 4).tolist(),
               inlet_normal_after=np.round(rot @ n_in, 4).tolist(),
               why="outlet cap plane made axis-aligned so snappyHexMesh cuts no stair-step sliver cells on the pressure outlet (dt collapse on the tilted outlet, 23 Nov 2026)")
    print(f"  rotated: outlet normal {rec['outlet_normal_before']} -> {rec['outlet_normal_after']}, inlet normal {rec['inlet_normal_before']} -> {rec['inlet_normal_after']}")
    return rotated, rec


def split(path, out_dir, outlet_name="outlet1", align=False):
    out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    solids = read_solids(path)
    print("solids:", {k: len(v) for k, v in solids.items()})
    rotation = dict(applied=False)
    if align:
        solids, rotation = align_outlet(solids)
    walls = [v for k, v in solids.items() if k.startswith("wall")]
    inlets = [v for k, v in solids.items() if k.startswith("inlet")]
    outlets = [v for k, v in solids.items() if k.startswith("outlet")]
    assert walls and len(inlets) == 1 and len(outlets) == 1, "expected wall solids, one inlet and one outlet"
    written = {}
    for fname, tris in (("wall_aorta.stl", np.concatenate(walls)), ("inlet.stl", inlets[0]), (f"{outlet_name}.stl", outlets[0])):
        pd = polydata(tris)
        pd.save(out_dir / fname, binary=True)
        c = np.array(pd.center)
        area = pd.area
        written[fname] = dict(faces=int(pd.n_cells), centre_mm=[round(float(x), 2) for x in c], area_mm2=round(float(area), 1))
        print(f"  {fname}: {pd.n_cells} faces, centre {np.round(c, 1)}, area {area:.0f} mm2" + (f", equivalent diameter {2 * np.sqrt(area / np.pi):.2f} mm" if "wall" not in fname else f", bounds {np.round(pd.bounds, 1)}"))
    return written, rotation


if __name__ == "__main__":
    split(sys.argv[1], sys.argv[2], align="--align-outlet" in sys.argv[3:])
