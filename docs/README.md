# AortaCFD Documentation for Publication

This directory contains publication-ready materials and technical notes for AortaCFD.

---

## Quick Start for Paper Writing

### 1. Main Methods Section
Use **`METHODS_CMAME_CONCISE.tex`** - this is the most current, complete methodology:
- Computational framework architecture
- Governing equations (Navier-Stokes, turbulence models)
- Three-profile numerical system (robust/standard/precise)
- Automated mesh generation
- Boundary conditions (Windkessel, inlet profiles)
- Verification approach

```latex
\input{METHODS_CMAME_CONCISE}
```

### 2. Results Tables
Use **`RESULTS_TABLES_CMAME.tex`** for:
- Profile specifications table (matches code exactly)
- Mesh resolution guidelines
- Physics model comparison
- Parallel scalability data
- Demonstration cases

### 3. Architecture Diagram
Use **`architecture_diagram_improved.tex`** (compile separately):
```bash
pdflatex architecture_diagram_improved.tex
# Output: architecture_diagram_improved.pdf
```

---

## File Organization

### Core LaTeX Files (Use These)

| File | Purpose | Status |
|------|---------|--------|
| `METHODS_CMAME_CONCISE.tex` | Main methods section | **Current** |
| `RESULTS_TABLES_CMAME.tex` | Results tables | **Updated** |
| `VERIFICATION_VALIDATION_CMAME.tex` | V&V section | Current |
| `architecture_diagram_improved.tex` | TikZ diagram | Current |

### Supporting Files

| File | Purpose | Notes |
|------|---------|-------|
| `BACKGROUND_CMAME.tex` | Literature/background | Optional |
| `LITERATURE_REVIEW.tex` | Extended review | For thesis, not paper |
| `APPENDIX_IMPLEMENTATION_CMAME.tex` | Implementation details | Supplementary |
| `APPENDIX_CUSTOMIZATION_CMAE.tex` | Customization guide | Supplementary |

### Markdown Documentation (User Guides)

| File | Purpose |
|------|---------|
| `MESH_PARAMETER_STUDY.md` | **DOE study results and preset design rationale** |
| `MESH_SPECIFICATION_GUIDE.md` | Mesh resolution guidance |
| `MESH_ADAPTIVE_SOLVER_SYSTEM.md` | Automatic solver adjustment |
| `MESH_QUALITY_WARNINGS.md` | Quality thresholds |
| `REGENERATE_NUMERICS_USAGE.md` | Regenerating numerics after meshing |

---

## Mesh Quality Presets (DOE Validated)

The code implements three mesh quality presets, validated by a 22-test DOE study:

| Preset | Time | nSmoothThickness | maxFaceThickRatio | Use Case |
|--------|------|------------------|-------------------|----------|
| `draft` | 1x | 10 | 0.5 | Quick geometry checks |
| `standard` | 2-3x | 10 | 0.5 | **Production (default)** |
| `high_quality` | 5-10x | 10 | 0.5 | Publications, complex cases |

**Key DOE Findings:**
- `nSmoothThickness`: LOWER is better (+0.367 effect on skewness)
- `maxFaceThicknessRatio`: LOWER is better (+0.286 effect)
- `span_refinement_level`: Use 1 or 2 (level 3 causes mesh failure with high cell counts)

**Span Refinement Guidelines (Follow-up Study):**
- Safe: `span_refinement_level` ≤ 2 with `cells_across_span` = 10-20
- Unsafe: `span_refinement_level` = 3 with `cells_across_span` > 10

**Source**: `src/config/mesh_quality_presets.py`
**Study Details**: `docs/_internal/MESH_PARAMETER_STUDY.md`

---

## Three-Profile System Reference

The code implements exactly three numerical profiles:

| Profile | Time | Convection | Outer Corr. | Tolerance | Use Case |
|---------|------|------------|-------------|-----------|----------|
| `robust` | Euler | upwind | 5 | 1e-4 | Debugging, poor meshes |
| `standard` | backward | bounded 2nd-order | 2 | 1e-6 | **Production (default)** |
| `precise` | CN 0.9 | LUST | 3 | 1e-8 | Convergence, LES |

**Source**: `src/config/profiles/numerics/*.py`

---

## Demonstration Cases

Three patient cases are available:

| Case ID | Description | Source |
|---------|-------------|--------|
| `0014_H_AO_COA` | Pediatric coarctation | SimVascular VMR |
| `BPM120` | Pediatric coarctation | Published (Wang et al.) |
| `PAT002` | Adult aorta | Cape Town collaboration |

### Running Demo Simulations

```bash
# List cases
python run_patient.py --list

# Run with standard settings
python run_patient.py BPM120

# Mesh-only for quick geometry check
python run_patient.py BPM120 --steps case,mesh
```

---

## Paper Structure Recommendation

### CMAME Software Paper Structure

```
1. Introduction
   - Motivation (cardiovascular CFD complexity)
   - Current limitations (manual workflow, reproducibility)
   - Contribution (automated pipeline)

2. Methods (METHODS_CMAME_CONCISE.tex)
   2.1 Computational Framework Architecture
   2.2 Automated Workflow Pipeline
   2.3 Governing Equations
   2.4 Numerical Discretization
   2.5 Three-Profile Numerical System
   2.6 Automated Mesh Generation
   2.7 Boundary Conditions

3. Verification & Validation (VERIFICATION_VALIDATION_CMAME.tex)
   3.1 Code Verification (unit tests, MMS)
   3.2 Solution Verification (mesh convergence, GCI)
   3.3 Validation (comparison to published data)

4. Results (RESULTS_TABLES_CMAME.tex)
   4.1 Profile Performance Comparison
   4.2 Demonstration Cases
   4.3 Computational Efficiency

5. Discussion
   - Limitations
   - Future work

6. Conclusions

Appendix A: Implementation Details
Appendix B: Complete Profile Specifications
```

---

## Key Figures to Generate

### Required Figures

1. **Architecture Diagram** - `architecture_diagram_improved.pdf`
2. **Mesh Convergence** - GCI analysis for BPM120 case
3. **Velocity Contours** - Peak systole comparison
4. **WSS Distribution** - Time-averaged and instantaneous
5. **Profile Comparison** - robust vs standard vs precise

### Generating Figures

```bash
# Run simulation
python run_patient.py BPM120

# Results in:
# output/BPM120/run_*/openfoam/
# output/BPM120/run_*/reports/
# output/BPM120/run_*/results/

# View in ParaView
paraview output/BPM120/run_*/openfoam/openfoam.foam
```

---

## Compiling LaTeX

### Prerequisites

```bash
# Ubuntu/Debian
sudo apt-get install texlive-latex-extra texlive-pictures

# Required packages in documents:
# booktabs, xcolor, colortbl, array, siunitx, hyperref
# tikz (for diagrams)
```

### Compile Methods Section

```bash
cd docs/
pdflatex METHODS_CMAME_CONCISE.tex
# May need bibtex for references
```

### Compile Architecture Diagram

```bash
pdflatex architecture_diagram_improved.tex
# Convert to PNG if needed:
pdftoppm -png -r 300 architecture_diagram_improved.pdf diagram
```

---

## What NOT to Claim

**Avoid overselling. The framework:**

- Does NOT guarantee solution accuracy (requires mesh convergence study)
- Does NOT replace understanding of CFD fundamentals
- Does NOT validate automatically (user must verify results)
- Is NOT a "clinical tool" (research/educational only)

**Honest claims:**

- Automates OpenFOAM dictionary generation
- Reduces setup time and human error
- Provides consistent, reproducible configurations
- Enables systematic parameter studies
- Includes 188 unit tests for code correctness

---

## Validation Requirements for Publication

Before claiming validated results:

1. **Mesh Independence** (mandatory)
   - 3+ mesh levels (refinement ratio √2)
   - Calculate GCI per Roache (1998)
   - Report observed order of accuracy
   - Target: GCI < 3%

2. **Comparison to Reference Data**
   - Published experimental/clinical data
   - Or comparison to established codes
   - Report relative errors with uncertainty

3. **Physical Sanity Checks**
   - Mass conservation < 0.1%
   - Residuals converged to tolerance
   - Velocities in physiological range
   - Pressure drops reasonable

---

## Contact

For documentation questions:
- Repository: https://github.com/JieWangnk/AortaCFD-app
- Email: jie.wang-2@manchester.ac.uk

---

**Last Updated:** 2025-12-22
