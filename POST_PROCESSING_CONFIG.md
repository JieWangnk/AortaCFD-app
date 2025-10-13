# Post-Processing Configuration Guide

## Overview

The `post_processor.py` script can process both **Reconstructed** and **Decomposed** OpenFOAM cases.

---

## Configuration in config.json

Add this section to your `config.json`:

```json
{
  "post_processing": {
    "enabled": true,
    "case_type": "Reconstructed",
    "fields": ["U", "p"],
    "time_steps": "last",
    "create_animations": false,
    "resolution": [1920, 1080]
  }
}
```

### Parameters:

#### `case_type`
- **`"Reconstructed"`** - Use after running `reconstructPar` (default)
  - Reads from time directories: `0/`, `0.1/`, `0.2/`, etc.
  - Best for post-processing after parallel solver

- **`"Decomposed"`** - Read directly from processor directories
  - Reads from: `processor0/`, `processor1/`, `processor2/`, etc.
  - **Advantage:** No need to run `reconstructPar` (saves disk space & time)
  - **Use when:** Large parallel cases where reconstruction is slow

#### `fields`
List of fields to visualize:
- `"U"` - Velocity magnitude
- `"p"` - Pressure
- `"wallShearStress"` - Wall shear stress (requires: `foamCalc wallShearStress`)
- `"vorticity"` - Vorticity magnitude (requires: `foamCalc vorticity`)

#### `time_steps`
Which time steps to process:
- `"last"` - Only the last time step (fastest, default)
- `"all"` - All available time steps
- `"peak"` - Peak systole (maximum velocity time)
- `[0.5, 1.0, 1.5]` - Specific time values (array of numbers)

#### `create_animations`
- `true` - Create .avi animations (requires ffmpeg)
- `false` - Only create screenshots (default)

#### `resolution`
Screenshot resolution `[width, height]`:
- `[1920, 1080]` - Full HD
- `[3840, 2160]` - 4K
- `[1280, 720]` - HD

---

## Usage Examples

### Example 1: Reconstructed Case (After reconstructPar)

**Workflow:**
```bash
# 1. Run parallel simulation
python run_patient.py patient1

# 2. Case is automatically reconstructed by workflow
# 3. Run post-processing
cd output/patient1/run_*/openfoam
pvbatch ../../../../src/aortacfd_lib/post_processor.py
```

**config.json:**
```json
{
  "post_processing": {
    "case_type": "Reconstructed",
    "fields": ["U", "p"],
    "time_steps": "last"
  },
  "run_settings": {
    "solution_type": "parallel",
    "subdomains": 8
  }
}
```

### Example 2: Decomposed Case (Skip reconstructPar)

For large cases where reconstruction takes too long:

**Workflow:**
```bash
# 1. Run parallel simulation
python run_patient.py patient1

# 2. Skip reconstructPar step
# 3. Post-process directly from processor directories
cd output/patient1/run_*/openfoam
pvbatch ../../../../src/aortacfd_lib/post_processor.py
```

**config.json:**
```json
{
  "post_processing": {
    "case_type": "Decomposed",
    "fields": ["U", "p"],
    "time_steps": "last"
  },
  "run_settings": {
    "solution_type": "parallel",
    "subdomains": 8
  }
}
```

**Note:** ParaView can read decomposed cases directly without reconstruction!

### Example 3: All Time Steps with Animations

```json
{
  "post_processing": {
    "case_type": "Reconstructed",
    "fields": ["U", "p", "wallShearStress"],
    "time_steps": "all",
    "create_animations": true,
    "resolution": [1920, 1080]
  }
}
```

**Before running:** Calculate WSS if needed:
```bash
cd output/patient1/run_*/openfoam
foamCalc wallShearStress
pvbatch ../../../../src/aortacfd_lib/post_processor.py
```

### Example 4: Specific Time Steps

```json
{
  "post_processing": {
    "case_type": "Reconstructed",
    "fields": ["U", "p"],
    "time_steps": [0.0, 0.4, 0.8, 1.2, 1.6]
  }
}
```

---

## Command Line Usage

### Basic (uses current directory):
```bash
cd output/patient1/run_YYYYMMDD_HHMMSS/openfoam
pvbatch ../../../../src/aortacfd_lib/post_processor.py
```

### With explicit path:
```bash
pvbatch post_processor.py /path/to/case
```

### With environment variable:
```bash
export CASE_PATH=/path/to/case
pvbatch post_processor.py
```

---

## Output

Post-processing creates:

```
output/patient1/run_YYYYMMDD_HHMMSS/openfoam/Images/
├── postProcessing.log           # Processing log
├── Velocity_1.6.png             # Velocity screenshot
├── Pressure_1.6.png             # Pressure screenshot
├── WSS_1.6.png                  # WSS screenshot (if calculated)
├── Velocity.avi                 # Velocity animation (if enabled)
└── Pressure.avi                 # Pressure animation (if enabled)
```

---

## Troubleshooting

### Case Type Detection

The script automatically detects the case type:
- If `processor*/` directories exist and no time directories → uses `Decomposed`
- If time directories exist → uses `Reconstructed`
- Manual override via config.json `case_type` setting

### Missing Fields

If you get errors about missing fields:

```bash
# Calculate WSS first
cd output/patient1/run_*/openfoam
foamCalc wallShearStress

# Calculate vorticity
foamCalc vorticity

# Then run post-processor
pvbatch ../../../../src/aortacfd_lib/post_processor.py
```

### Parallel Case Not Reconstructed

If you ran in parallel but didn't reconstruct:

**Option 1:** Reconstruct first
```bash
cd output/patient1/run_*/openfoam
reconstructPar
pvbatch ../../../../src/aortacfd_lib/post_processor.py
```

**Option 2:** Post-process decomposed case
```json
{
  "post_processing": {
    "case_type": "Decomposed"
  }
}
```

### Animations Not Created

Animations require ffmpeg:
```bash
# Install ffmpeg
sudo snap install ffmpeg

# Or enable universe repo
sudo add-apt-repository universe
sudo apt-get update
sudo apt-get install ffmpeg
```

---

## Performance Tips

### For Large Cases:

1. **Use `case_type: "Decomposed"`** - Skip reconstruction (saves time & disk)
2. **Use `time_steps: "last"`** - Only process final time step
3. **Limit fields** - Only visualize what you need
4. **Lower resolution** - Use `[1280, 720]` for faster processing

### For Publications:

1. **Use `case_type: "Reconstructed"`** - Better quality
2. **Use `time_steps: "peak"`** - Peak systole for clearest flow features
3. **High resolution** - Use `[3840, 2160]` for 4K images
4. **Include WSS** - Add `"wallShearStress"` to fields

---

## Integration with Workflow

The post-processor is automatically called at the end of `runAll` workflow if enabled in config.

To disable automatic post-processing:
```json
{
  "post_processing": {
    "enabled": false
  }
}
```

Then run manually when needed.

---

## Summary

| Scenario | case_type | Pros | Cons |
|----------|-----------|------|------|
| **Small serial runs** | `Reconstructed` | Simple, standard | N/A |
| **Small parallel runs** | `Reconstructed` | High quality | Needs reconstructPar |
| **Large parallel runs** | `Decomposed` | Fast, saves disk | Slightly different rendering |
| **Publication figures** | `Reconstructed` | Best quality | Slower |
| **Quick checks** | `Decomposed` | Very fast | Lower quality |

**Recommendation:** Use `Decomposed` for quick checks during development, `Reconstructed` for final publication figures.
