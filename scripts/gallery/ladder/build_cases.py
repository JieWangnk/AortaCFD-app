"""Build the AortaCFD-app case folders of the complexity ladder from the engine's geometries.

Ladder (each level adds one thing to the planar bend, every level gets the 12/18/26 mesh ladder):
  L0  planar bend from the engine (the U-bend's calibre, lengths and arch radius; 12 mm curvature ramps at the
      arch ends, so it is 6 mm taller than the Blender U-bend of the published mesh page and is rebuilt here)
  L1  + torsion along the bend            twist 108 deg (torsion/curvature 0.6)
  L2  + 50 % area coarctation             isthmus, throat 15 mm past the bend end, 30 mm long
  L3  + a reversing inflow                 reverse lobe in early diastole, same parabolic profile, 3 cycles
      (the app's womersley profile blew up on this waveform, -18 m/s at the systolic peak, 23 Nov 2026: bug filed in the notes)

Usage: python3 build_cases.py GEOM_DIR APP_ROOT [L0,L1,...]
GEOM_DIR holds <src>.stl + <src>.json written by `scenarios.py aorta --name <src>`; APP_ROOT is AortaCFD-app.
Writes cases_input/ladder_L*/{wall_aorta,inlet,outlet1}.stl, geometry.meta.json, three configs each, the
inflow files, and scripts/gallery/runs_ladder.txt (every level listed, in ladder order).
"""
import hashlib
import json
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from split_stl import split  # noqa: E402

geom = pathlib.Path(sys.argv[1]); app = pathlib.Path(sys.argv[2])
only = sys.argv[3].split(",") if len(sys.argv) > 3 else None
here = pathlib.Path(__file__).resolve().parent
ubend = app / "cases_input/ubend"

LEVELS = {
    "L0": dict(src="L0", twist=0.0, coa=0.0, cycles=1, profile="parabolic", csv="ubend_inflow.csv",
               what="planar 180-degree bend from the geometry engine (U-bend calibre 27.4/26.0/24.4 mm, ascending 50 mm, arch radius 40.4 mm, descending 200 mm)"),
    "L1": dict(src="L1b", twist=108.0, coa=0.0, cycles=1, profile="parabolic", csv="ubend_inflow.csv",
               what="the L0 bend with 108 degrees of Frenet torsion along the arch (torsion/curvature 0.6)"),
    "L2": dict(src="L2", twist=108.0, coa=0.5, cycles=1, profile="parabolic", csv="ubend_inflow.csv",
               what="the L1 twisted bend with a 50 % area coarctation at the isthmus (throat 15 mm past the bend end, 30 mm long)"),
    "L3": dict(src="L2", twist=108.0, coa=0.5, cycles=3, profile="parabolic", csv="reversing_inflow.csv",
               what="the L2 geometry with a reversing inflow (half-sine systole, reverse lobe 0.40-0.52 s, parabolic profile scaled to the flow rate), three cycles"),
}
GRID_RES = 1.0  # engine marching-cubes voxel (mm); the template default. 0.5 mm took 12 min (planar) to >1 h (twisted)
MESHES = [("coarse_span12", 12), ("mid_span18", 18), ("fine_span26", 26)]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


runs = []
for name, L in LEVELS.items():
    case = f"ladder_{name}"
    for tag, _ in MESHES:
        runs.append(f"{case} gallery_{tag} cases_input/{case}/config_gallery_{tag}.json")
    if only and name not in only:
        continue
    d = app / "cases_input" / case
    d.mkdir(exist_ok=True)
    src_stl = geom / f"{L['src']}.stl"
    written, rotation = split(src_stl, d, align=L['twist'] != 0)  # twisted levels: outlet cap made axis-aligned (see split_stl.py)
    files = {f: dict(**v, sha256_16=sha(d / f)) for f, v in written.items()}
    shutil.copy(ubend / "ubend_inflow.csv", d / "ubend_inflow.csv")
    if L["csv"] != "ubend_inflow.csv":
        shutil.copy(here / L["csv"], d / L["csv"])
    engine_meta = json.loads((geom / f"{L['src']}.json").read_text())
    (d / "geometry.meta.json").write_text(json.dumps(dict(
        schema_version="2.0", case_id=case, generator="geometry-generation-trial scenarios.py aorta (engine source STL split by patch name)",
        command=f"python scenarios.py aorta --branches '' --twist {L['twist']:g}" + (f" --coarctation {L['coa']:g}" if L["coa"] else "") + f" --grid-res {GRID_RES:g} --name {L['src']}",
        description=L["what"],
        derived_from="cases_input/ubend parameters (the engine's aorta defaults are the U-bend values); not the Blender surface",
        params=dict(d_ascending=27.4, d_arch=26.0, d_descending=24.4, ascending_length=50.0, arch_R_c=40.4, arch_angle_deg=180.0, arch_blend_mm=12.0,
                    arch_twist_deg=L["twist"], coarctation_area_reduction=L["coa"], coarctation_length_mm=30.0, coarctation_offset_mm=15.0,
                    descending_length=200.0, grid_res=GRID_RES),
        engine_record=engine_meta.get("diagnostics", {}), rotation=rotation, files=files), indent=1))
    for tag, n in MESHES:
        cfg = json.loads((ubend / f"config_gallery_{tag}.json").read_text())
        cfg["_doc"] = f"Complexity ladder {name} ({L['what']}); the U-bend gallery mesh configuration with {n} cells across the span. Invoke with: python run_patient.py {case} --config cases_input/{case}/config_gallery_{tag}.json"
        cfg["case_info"] = dict(patient_id=case, description=f"Ladder {name}: {L['what']}; {n} cells across the inlet span",
                                source="OpenCardioFlow complexity ladder, 23 Nov 2026; cases_input/ubend/config_gallery_*.json with the geometry and inflow changed")
        assert cfg["mesh"]["SNAPPY_SETTINGS"]["cells_across_span"] == n
        cfg["boundary_conditions"]["inlet"]["csv_file"] = L["csv"]
        cfg["boundary_conditions"]["inlet"]["profile"] = L["profile"]
        cfg["simulation_control"]["number_of_cycles"] = L["cycles"]
        cfg["simulation_control"]["_keep_last_cycles"] = 1
        (d / f"config_gallery_{tag}.json").write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"{case}: {len(MESHES)} configs, inflow {L['csv']} ({L['profile']}), {L['cycles']} cycle(s)")
(app / "scripts/gallery/runs_ladder.txt").write_text("\n".join(runs) + "\n")
print(f"wrote scripts/gallery/runs_ladder.txt with {len(runs)} runs")
