# Mesh Resolution Architecture

Technical documentation of the mesh resolution system design in AortaCFD.

---

## Design Pattern: Strategy Pattern with Priority Cascade

The mesh resolution system uses a **Strategy Pattern** to make the parameter hierarchy explicit and maintainable.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│         _calculate_blockmesh_cells(bounds)                  │
│         (Main entry point)                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         _resolve_cell_size(mesh_resolution)                 │
│         (Resolution engine)                                 │
│                                                             │
│   1. Get strategies from _get_cell_size_strategies()       │
│   2. Try each strategy in priority order                   │
│   3. Return first successful result                        │
│   4. Return (cell_size, source, priority)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│      _get_cell_size_strategies(mesh_resolution)             │
│      (Strategy registry - SINGLE SOURCE OF TRUTH)           │
│                                                             │
│   Returns: [(priority, name, function), ...]               │
│                                                             │
│   [                                                         │
│     (1, "resolution_level", λ: method_1()),               │
│     (2, "target_cell_size_mm", λ: method_2()),            │
│     (3, "blockmesh_resolution", λ: method_3()),           │
│     (4, "cells_per_diameter", λ: method_4()),             │
│     (5, "refinement_levels", λ: method_5()),              │
│     (6, "default_fallback", λ: (1.0, "default"))          │
│   ]                                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ (Each strategy calls its helper method)
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌───────────────────┐     ┌───────────────────┐
│ _cell_size_from_  │     │ _cell_size_from_  │     ...
│ target_mm()       │     │ blockmesh_res()   │
│                   │     │                   │
│ Returns:          │     │ Returns:          │
│ (float, str)      │     │ (float, str)      │
│ or (None, None)   │     │ or (None, None)   │
└───────────────────┘     └───────────────────┘
```

---

## Component Responsibilities

### 1. `_get_cell_size_strategies()` - Strategy Registry

**Purpose:** Define all available strategies in priority order

**Returns:** `List[(int, str, Callable)]`
- `int`: Priority (1 = highest, 5 = fallback)
- `str`: Strategy name (for logging/debugging)
- `Callable`: Lambda function that calls the strategy method

**Key Feature:** **Single source of truth** for priority order

```python
def _get_cell_size_strategies(self, mesh_resolution: dict):
    return [
        (1, "resolution_level", lambda: self._cell_size_from_resolution_level(mesh_resolution)),
        (2, "target_cell_size_mm", lambda: self._cell_size_from_target_mm(mesh_resolution)),
        (3, "blockmesh_resolution", lambda: self._cell_size_from_blockmesh_resolution(mesh_resolution)),
        (4, "cells_per_diameter", lambda: self._cell_size_from_cells_per_diameter(mesh_resolution)),
        (5, "refinement_levels", lambda: self._cell_size_from_refinement_level()),
        (6, "default_fallback", lambda: (1.0, "default fallback (1.0mm, matches 'medium' profile)"))
    ]
```

**To modify priority order:** Just reorder this list.

**To add new strategy:** Append `(priority, name, lambda: new_method())` to list.

---

### 2. `_resolve_cell_size()` - Resolution Engine

**Purpose:** Execute strategies in order until one succeeds

**Algorithm:**
```
FOR each (priority, name, function) in strategies:
    result, source = function()
    IF result is not None:
        RETURN (result, source, priority)
    ENDIF
ENDFOR
RAISE RuntimeError (should never happen - priority 5 always returns value)
```

**Returns:** `(cell_size_mm: float, source: str, priority: int)`

**Features:**
- Zero nested if/else chains
- Early exit on first success
- Defensive: raises error if all strategies somehow fail
- Logs warning for default fallback (priority 5)

---

### 3. `_calculate_blockmesh_cells()` - Main Entry Point

**Purpose:** Orchestrate cell size resolution and grid calculation

**Algorithm:**
```
1. Get mesh_resolution dict from config
2. Call _resolve_cell_size() → (cell_size, source, priority)
3. Validate cell_size > 0
4. Log resolved parameters
5. Compute grid: num_cells = domain_size / cell_size
6. Return {x: nx, y: ny, z: nz}
```

**Simplicity:** This method is now <30 lines with no complex logic.

---

### 4. Strategy Helper Methods

Each strategy is implemented as a separate method:

| Method | Priority | Formula | Requires Geometry |
|--------|----------|---------|-------------------|
| `_cell_size_from_resolution_level()` | 1 | `preset lookup` | No |
| `_cell_size_from_target_mm()` | 2 | `size = value` | No |
| `_cell_size_from_blockmesh_resolution()` | 3 | `size = 2R/N` | Yes |
| `_cell_size_from_cells_per_diameter()` | 4 | `size = 2R/cells` | Yes |
| `_cell_size_from_refinement_level()` | 5 | `size = lookup[level]` | No |
| Default (inline lambda) | 6 | `size = 1.0mm` | No |

**Contract:** All methods return `(cell_size: float | None, source: str)`

---

## Example Execution Flow

### Scenario: User sets `cells_per_diameter = 15`

```
User Config:
{
  "mesh": {
    "mesh_resolution": {
      "cells_per_diameter": 15
    }
  },
  "geometry": {
    "reference_radius_strategy": "min"
  }
}

Execution Trace:
─────────────────────────────────────────────────────────────
1. _calculate_blockmesh_cells(bounds) called

2. _resolve_cell_size(mesh_resolution) called

3. Get strategies:
   [(1, "target_cell_size_mm", λ...),
    (2, "blockmesh_resolution", λ...),
    (3, "cells_per_diameter", λ...),
    (4, "refinement_levels", λ...),
    (5, "default_fallback", λ...)]

4. Try strategy 1:
   → _cell_size_from_target_mm() returns (None, None)
   → Continue to next strategy

5. Try strategy 2:
   → _cell_size_from_blockmesh_resolution() returns (None, None)
   → Continue to next strategy

6. Try strategy 3:
   → _cell_size_from_cells_per_diameter() called
   → Finds cells_per_diameter = 15
   → reference_radius_mm = 10.234 (from geometry analysis)
   → Computes: cell_size = 2 * 10.234 / 15 = 1.364mm
   → Returns (1.364, "2*R/15.0 cells (ref_radius=10.23mm)")
   → SUCCESS! Exit loop

7. _resolve_cell_size() returns:
   (1.364, "2*R/15.0 cells (ref_radius=10.23mm)", 3)

8. _calculate_blockmesh_cells() validates:
   → 1.364 > 0 ✓

9. Log output:
   [INFO] ✓ Target cell size: 1.364 mm
   [INFO]   Source: 2*R/15.0 cells (ref_radius=10.23mm) (priority 3/5)
   [INFO]   Reference radius: 10.234 mm (strategy: min)

10. Compute grid:
    → Domain: 100mm × 80mm × 60mm
    → Cells: 73 × 59 × 44
    → Return {"x": 73, "y": 59, "z": 44}
```

---

## Advantages of This Design

### 1. Maintainability

**Before (nested if/else):**
```python
if target_mm is not None:
    cell_size = target_mm
else:
    if block_res is not None:
        if reference_radius:
            cell_size = 2*R / block_res
        else:
            # skip...
    else:
        if cells_per_diam:
            if reference_radius:
                # ...
            else:
                # ...
        else:
            # ... (deeply nested)
```

**After (strategy pattern):**
```python
for priority, name, func in strategies:
    result, source = func()
    if result is not None:
        return result, source, priority
```

### 2. Extensibility

**To add new parameter (e.g., `target_cell_count_total`):**

Step 1: Write helper method:
```python
def _cell_size_from_total_count(self, mesh_resolution: dict) -> tuple:
    total_count = mesh_resolution.get('target_cell_count_total')
    if total_count:
        domain_volume = calculate_volume(self.bounds)
        cell_size = (domain_volume / total_count) ** (1/3)
        return cell_size, f"total_count={total_count}"
    return None, None
```

Step 2: Add to strategy list (choose priority):
```python
def _get_cell_size_strategies(self, mesh_resolution: dict):
    return [
        (1, "target_cell_size_mm", ...),
        (2, "total_cell_count", lambda: self._cell_size_from_total_count(mesh_resolution)),  # NEW
        (3, "blockmesh_resolution", ...),
        # ... rest unchanged
    ]
```

**That's it!** No modifications to `_resolve_cell_size()` or `_calculate_blockmesh_cells()`.

### 3. Testability

Each component can be tested independently:

```python
def test_target_mm_strategy():
    config = {"mesh": {"mesh_resolution": {"target_cell_size_mm": 1.5}}}
    analyzer = GeometryAnalyzer(config, ...)
    cell_size, source = analyzer._cell_size_from_target_mm(config["mesh"]["mesh_resolution"])
    assert cell_size == 1.5
    assert "target_cell_size_mm" in source

def test_priority_cascade():
    # Test that priority 1 wins even if others are set
    config = {
        "mesh": {
            "mesh_resolution": {
                "target_cell_size_mm": 1.0,     # Priority 1
                "cells_per_diameter": 15        # Priority 3 (should be ignored)
            }
        }
    }
    analyzer = GeometryAnalyzer(config, ...)
    cell_size, source, priority = analyzer._resolve_cell_size(config["mesh"]["mesh_resolution"])
    assert cell_size == 1.0
    assert priority == 1
```

### 4. Debuggability

**Clear log output with priority:**
```
[INFO] ✓ Target cell size: 1.000 mm
[INFO]   Source: mesh.mesh_resolution.target_cell_size_mm (explicit) (priority 1/5)
```

**Priority number tells you immediately:**
- Priority 1 → User set explicit value (best)
- Priority 3 → Computed from geometry (good)
- Priority 5 → Default fallback (warning issued)

---

## Design Principles Applied

### SOLID Principles

✅ **Single Responsibility:**
- `_get_cell_size_strategies()` - defines strategies
- `_resolve_cell_size()` - executes strategies
- Each helper method - computes one type of cell size

✅ **Open/Closed:**
- Open for extension (add new strategies to list)
- Closed for modification (no changes to resolution engine)

✅ **Liskov Substitution:**
- All strategies return same type: `(float | None, str)`
- Any strategy can be swapped without breaking system

✅ **Interface Segregation:**
- Strategies don't depend on each other
- Each has minimal interface

✅ **Dependency Inversion:**
- `_resolve_cell_size()` depends on strategy interface (function returning tuple)
- Not on concrete strategy implementations

---

## Performance Considerations

**Complexity:** O(n) where n = number of strategies (currently 5)
- Best case: O(1) if priority 1 strategy succeeds
- Worst case: O(5) if reaches default fallback
- Average case: O(2-3) for typical configs

**Memory:** Negligible
- Strategy list is ~5 small tuples
- Lambda functions are lightweight closures

**Optimization:** None needed - this is not a performance bottleneck

---

## Future Enhancements

### Potential New Strategies

1. **Total Cell Count:**
   ```python
   (2, "target_cell_count_total", lambda: self._cell_size_from_total_count(...))
   ```

2. **Y+ Target:**
   ```python
   (3, "target_yplus", lambda: self._cell_size_from_yplus(...))
   ```

3. **Profile-Based (coarse/medium/fine):**
   ```python
   (1, "mesh_quality_profile", lambda: self._cell_size_from_profile(...))
   ```

### Configuration Validation

Add method to check for conflicting parameters:

```python
def _validate_mesh_config(self, mesh_resolution: dict):
    """Warn if multiple high-priority parameters are set."""
    set_params = []
    if mesh_resolution.get('target_cell_size_mm'):
        set_params.append('target_cell_size_mm')
    if mesh_resolution.get('blockmesh_resolution'):
        set_params.append('blockmesh_resolution')
    # ...

    if len(set_params) > 1:
        self.log.warning(
            f"Multiple mesh resolution parameters set: {set_params}. "
            f"Only highest priority will be used. "
            f"Recommendation: set only ONE parameter."
        )
```

---

## References

- **Implementation:** `src/aortacfd_lib/mesh_setup.py` (lines 337-450)
- **User Guide:** `MESH_RESOLUTION_GUIDE.md`
- **Examples:** `examples/mesh_configs/*.json`
- **Helper Script:** `examples/mesh_configs/compute_cell_size.py`

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-14 | 2.0 | Strategy pattern refactoring |
| 2025-10-14 | 1.5 | Helper function decomposition |
| 2025-10-13 | 1.0 | Original nested if/else implementation |

---

**Document maintained by:** AortaCFD Development Team
**Last updated:** 2025-10-14
