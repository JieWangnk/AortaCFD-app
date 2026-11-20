#!/usr/bin/env python3
"""Build the configs for the OpenCardioFlow gallery runs.

Every gallery config is derived from a shipped config so the derivation is
on record:

* mesh, numerics and run settings come from the U-bend production run
  (``cases_input/ubend/config_adaptive_span.json``: adaptive-span strategy,
  17 cells across the lumen, 3 boundary layers, 4 subdomains);
* physics and geometry for the synthetic arches come from ``cases_input/G3``;
* the inflow waveform for every arch is ``G3_flowrate.csv`` (HR 70, mean
  5.0 L/min, peak 25.8 L/min).

Runs (one question each, see research_notes/vascular_cfd_website_plan_2026-11-19.md
section 11):

  ubend    gallery_coarse_span11       mesh level (11 cells across)
  G3       gallery_wk_pulsatile        outlet model, arm B (3-element Windkessel)
  G3       gallery_zerograd_pulsatile  outlet model, arm A (zero gradient, p = 0 at the descending outlet)
  G3       gallery_wk_constant         steady vs pulsatile (constant inflow at the waveform mean)
  sev_001  gallery_wk_pulsatile        severity 0 %
  sev_002  gallery_wk_pulsatile        severity 35 %
  sev_003  gallery_wk_pulsatile        severity 70 %
  ubend    gallery_fine_span26         mesh level (26 cells across)

Usage: python scripts/gallery/make_gallery_configs.py   (from the repo root)
"""

import copy
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "cases_input"

UBEND_PROD = json.loads((CASES / "ubend" / "config_adaptive_span.json").read_text())
G3 = json.loads((CASES / "G3" / "config.json").read_text())

PERIOD = 0.857  # s, HR 70
WRITES_PER_CYCLE = 50

WK_OUTLETS = {
    "type": "3EWINDKESSEL",
    "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80,
        "venous_pressure": 0,
        "methodology": "murray_law_automatic",
        "tau": 1.0,
        "initial_pressure_method": "map",
        "enable_stabilization": True,
    },
}
ZG_OUTLETS = {
    "type": "zeroGradient",
    "per_outlet": {"outlet1": {"type": "fixedValue", "pressure_mmHg": 0}},
}
PULSATILE_INLET = {
    "type": "TIMEVARYING",
    "csv_file": "G3_flowrate.csv",
    "data_type": "flowrate",
    "profile": "parabolic",
}
CONSTANT_INLET = {"type": "CONSTANT", "cardiac_output": 5.0, "profile": "parabolic"}


def arch_config(description, inlet, outlets, cycles=2):
    mesh = copy.deepcopy(UBEND_PROD["mesh"])
    mesh.pop("_doc", None)
    return {
        "case_info": {
            "patient_id": "synthetic",
            "description": description,
            "source": "OpenCardioFlow gallery; mesh and numerics from cases_input/ubend/config_adaptive_span.json",
        },
        "physics": copy.deepcopy(G3["physics"]),
        "numerics": {"profile": "standard"},
        "mesh": mesh,
        "geometry": copy.deepcopy(G3["geometry"]),
        "boundary_conditions": {"inlet": inlet, "outlets": outlets, "walls": {"type": "no_slip"}},
        "simulation_control": {
            "cardiac_cycle_period": PERIOD,
            "number_of_cycles": cycles,
            "writeInterval": round(PERIOD / WRITES_PER_CYCLE, 5),
            "keep_last_cycles": 1,
        },
        "run_settings": {"solution_type": "parallel", "subdomains": 4, "decomposition_method": "scotch"},
    }


def ubend_config(span, description):
    c = copy.deepcopy(UBEND_PROD)
    c["mesh"].pop("_doc", None)
    c["mesh"]["SNAPPY_SETTINGS"]["cells_across_span"] = span
    c["case_info"] = {
        "patient_id": "ubend",
        "description": description,
        "source": "OpenCardioFlow gallery; config_adaptive_span.json with cells_across_span changed",
    }
    return c


def main():
    runs = []

    def add(case, run, cfg):
        path = CASES / case / f"config_{run}.json"
        path.write_text(json.dumps(cfg, indent=2) + "\n")
        runs.append((case, run, str(path.relative_to(ROOT))))

    add("ubend", "gallery_coarse_span11", ubend_config(11, "U-bend, pulsatile, 11 cells across the lumen (mesh-level study, coarse)"))
    add(
        "G3",
        "gallery_wk_pulsatile",
        arch_config("Branched arch, 65 % coarctation, pulsatile, 3-element Windkessel outlets", PULSATILE_INLET, WK_OUTLETS),
    )
    add(
        "G3",
        "gallery_zerograd_pulsatile",
        arch_config("Branched arch, 65 % coarctation, pulsatile, zero-gradient outlets", PULSATILE_INLET, ZG_OUTLETS),
    )
    add(
        "G3",
        "gallery_wk_constant",
        arch_config(
            "Branched arch, 65 % coarctation, constant inflow 5.0 L/min (waveform mean), Windkessel outlets",
            CONSTANT_INLET,
            WK_OUTLETS,
        ),
    )
    for case, sev in (("sev_001", 0), ("sev_002", 35), ("sev_003", 70)):
        shutil.copy(CASES / "G3" / "G3_flowrate.csv", CASES / case / "G3_flowrate.csv")
        add(
            case,
            "gallery_wk_pulsatile",
            arch_config(f"Branched arch, {sev} % coarctation area reduction, pulsatile, Windkessel outlets", PULSATILE_INLET, WK_OUTLETS),
        )
    add("ubend", "gallery_fine_span26", ubend_config(26, "U-bend, pulsatile, 26 cells across the lumen (mesh-level study, fine)"))

    (ROOT / "scripts" / "gallery" / "runs.txt").write_text("".join(f"{c} {r} {p}\n" for c, r, p in runs))
    for c, r, p in runs:
        print(f"{c:8s} {r:28s} {p}")


if __name__ == "__main__":
    main()
