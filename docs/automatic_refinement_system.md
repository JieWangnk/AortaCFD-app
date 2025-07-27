# Automatic Refinement Level Calculation System

## Overview

The AortaCFD automatic refinement system calculates optimal mesh cell sizes based on the minimum patch radius found in the geometry and desired cells per patch diameter. This ensures consistent mesh quality across different geometries without manual tuning.

## Key Features

1. **Geometry-based Calculation**: Uses Murray's law radius calculation to find the minimum patch radius
2. **Configurable Target Resolution**: Set different cell densities for coarse, medium, and fine meshes
3. **Automatic Integration**: Works seamlessly with existing mesh setup process
4. **Fallback Support**: Falls back to manual refinement levels if automatic calculation fails

## How It Works

### 1. Minimum Patch Radius Detection

The system analyzes all outlet patches (and optionally inlet) to find the minimum radius:

```python
# Calculate minimum patch radius from STL geometry
min_radius = murray_calculator.find_minimum_patch_radius(include_inlet=False)
min_diameter = 2 * min_radius
```

### 2. Cell Size Calculation

Cell sizes are calculated based on the desired number of cells across the minimum patch diameter:

```python
cell_size = min_diameter / cells_per_diameter
```

### 3. Refinement Level Generation

The system generates refinement levels for different mesh qualities:

- **Coarse**: 10 cells across minimum patch diameter
- **Medium**: 15 cells across minimum patch diameter  
- **Fine**: 20 cells across minimum patch diameter

## Configuration

### Profile Configuration

Each simulation profile can define its own cell density targets:

```python
"mesh": {
    "cells_per_patch_diameter": {
        "coarse": 10,   # 10 cells across minimum patch diameter
        "medium": 15,   # 15 cells across minimum patch diameter
        "fine": 20      # 20 cells across minimum patch diameter
    },
    "automatic_refinement": {
        "enabled": True,    # Enable automatic refinement
        "methodology": "murray_law_based"
    }
}
```

### Profile-Specific Targets

Different profiles use different cell density targets:

#### Laminar Coarse Profile
- Coarse: 10 cells per diameter
- Medium: 15 cells per diameter
- Fine: 20 cells per diameter

#### Laminar Fine Profile  
- Coarse: 15 cells per diameter
- Medium: 20 cells per diameter
- Fine: 25 cells per diameter

#### RANS Coarse Profile
- Coarse: 12 cells per diameter
- Medium: 18 cells per diameter
- Fine: 24 cells per diameter

## Integration with Mesh Setup

The automatic refinement system is integrated into the `GeometryAnalyzer` class:

```python
from aortacfd_lib.mesh_setup import GeometryAnalyzer

# Automatic refinement enabled by default
analyzer = GeometryAnalyzer(config, case_directory, enable_automatic_refinement=True)

# Manual refinement levels (disable automatic)
analyzer = GeometryAnalyzer(config, case_directory, enable_automatic_refinement=False)
```

## API Reference

### Main Functions

#### `calculate_automatic_mesh_refinement(config, case_directory, cells_per_patch_diameter=None)`

Calculate automatic mesh refinement configuration based on geometry.

**Parameters:**
- `config`: Full configuration dictionary
- `case_directory`: Path to case directory containing STL files
- `cells_per_patch_diameter`: Optional dict mapping refinement levels to cell counts

**Returns:** Dictionary containing mesh configuration with automatic refinement levels

#### `update_config_with_automatic_refinement(config, case_directory, cells_per_patch_diameter=None)`

Update configuration with automatic refinement levels.

**Parameters:**
- `config`: Original configuration dictionary
- `case_directory`: Path to case directory
- `cells_per_patch_diameter`: Optional cell density targets

**Returns:** Updated configuration with automatic refinement levels

### Murray Calculator Methods

#### `find_minimum_patch_radius(include_inlet=True)`

Find the minimum radius among all patches.

**Parameters:**
- `include_inlet`: Whether to include inlet in minimum calculation

**Returns:** Minimum patch radius in meters

#### `calculate_automatic_refinement_levels(cells_per_patch_diameter)`

Calculate refinement levels based on minimum patch radius and desired cells per diameter.

**Parameters:**
- `cells_per_patch_diameter`: Dict mapping level names to desired cells per diameter

**Returns:** Dict of refinement levels with cell sizes in meters

#### `calculate_mesh_refinement_config(cells_per_patch_diameter)`

Calculate complete mesh refinement configuration including suggested snappyHexMesh settings.

**Parameters:**
- `cells_per_patch_diameter`: Dict mapping level names to desired cells per diameter

**Returns:** Complete mesh configuration dictionary

## Example Usage

### Basic Usage

```python
from aortacfd_lib.murray_calculator import calculate_automatic_mesh_refinement

# Calculate automatic refinement with default targets
mesh_config = calculate_automatic_mesh_refinement(config, case_directory)

print(f"Minimum patch radius: {mesh_config['minimum_patch_radius']:.6f} m")
print(f"Coarse cell size: {mesh_config['refinement_levels']['coarse']:.6f} m")
```

### Custom Cell Density Targets

```python
# Custom cell density targets
custom_targets = {
    "coarse": 8,    # 8 cells across minimum diameter
    "medium": 12,   # 12 cells across minimum diameter  
    "fine": 16      # 16 cells across minimum diameter
}

mesh_config = calculate_automatic_mesh_refinement(
    config, case_directory, custom_targets
)
```

### Integration with Configuration

```python
from aortacfd_lib.murray_calculator import update_config_with_automatic_refinement

# Update configuration with automatic refinement
updated_config = update_config_with_automatic_refinement(config, case_directory)

# Access automatic refinement metadata
auto_info = updated_config['mesh']['automatic_refinement']
print(f"Minimum patch radius: {auto_info['minimum_patch_radius']:.6f} m")
```

## Error Handling and Fallbacks

The system includes robust error handling:

1. **Missing STL Files**: Falls back to manual refinement levels if STL files are not found
2. **Calculation Errors**: Logs warnings and uses manual refinement levels
3. **Configuration Errors**: Provides sensible defaults if configuration is incomplete

## Benefits

1. **Consistent Mesh Quality**: Ensures consistent cell density across different geometries
2. **Automated Workflow**: Eliminates manual refinement level tuning
3. **Geometry-Adaptive**: Automatically adapts to different vessel sizes
4. **Scalable**: Works with any geometry size with proper scaling
5. **Backward Compatible**: Falls back to manual refinement levels when needed

## Technical Details

### Minimum Patch Radius Calculation

The system uses the existing Murray's law calculator infrastructure:

1. Extracts outlet areas from STL files using OpenFOAM utilities
2. Calculates equivalent circular radii: `r = sqrt(area / π)`
3. Finds minimum radius among all outlets
4. Optionally includes inlet radius in calculation

### Cell Size Calculation Formula

```
cell_size = (2 * min_radius) / cells_per_diameter
```

Where:
- `min_radius` is the minimum patch radius in meters
- `cells_per_diameter` is the desired number of cells across the diameter

### Suggested SnappyHexMesh Settings

The system also suggests appropriate snappyHexMesh settings:

- **Surface Refinement Levels**: [0, 1, 2] for progressive refinement
- **Feature Level**: 1-2 based on minimum patch size
- **Region Refinement Level**: 1-2 based on minimum patch size
- **Cells Between Levels**: 3 (standard)
- **Resolve Feature Angle**: 30° (standard)

## Troubleshooting

### Common Issues

1. **STL Files Not Found**: Ensure STL files exist in `constant/triSurface/` directory
2. **Calculation Failures**: Check that STL files are valid and contain geometry
3. **Unexpected Cell Sizes**: Verify scale factor is correct (typically 1e-3 for mm to m conversion)

### Debugging

Enable debug logging to see detailed calculation steps:

```python
import logging
logging.basicConfig(level=logging.INFO)

# Run automatic refinement calculation
mesh_config = calculate_automatic_mesh_refinement(config, case_directory)
```

This will show detailed information about:
- Detected patch areas and radii
- Minimum patch radius calculation
- Cell size calculations for each refinement level
- Suggested snappyHexMesh settings

## Future Enhancements

Planned improvements include:

1. **Adaptive Refinement**: Different refinement levels for different patch sizes
2. **Curvature-Based Refinement**: Additional refinement in high-curvature regions
3. **Boundary Layer Calculation**: Automatic boundary layer thickness calculation
4. **Validation Tools**: Tools to validate mesh quality against targets