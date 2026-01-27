# velocityFieldAverage Feature Tests

## Test Scripts

### test_fieldaverage_template.py
**Purpose**: Verify that the fieldAverageU function is correctly rendered in the controlDict template.

**What it tests**:
- Template renders with velocityFieldAverage: true
- All required components present (UMean, UPrime2Mean, pMean)
- Correct configuration (timeStart, periodicRestart, etc.)

**Usage**:
```bash
python3 tests/test_fieldaverage_template.py
```

**Expected output**: ✅ All checks passed!

---

### test_backward_compatibility.py
**Purpose**: Ensure existing configurations without velocityFieldAverage continue to work correctly.

**What it tests**:
1. **Old config** without velocityFieldAverage option
   - Expected: fieldAverageU NOT generated
   - Result: ✅ Works correctly

2. **Explicitly disabled** (velocityFieldAverage: false)
   - Expected: fieldAverageU NOT generated
   - Result: ✅ Works correctly

3. **Explicitly enabled** (velocityFieldAverage: true)
   - Expected: fieldAverageU generated with all components
   - Result: ✅ Works correctly

4. **Non-pulsatile flow** (steady inlet)
   - Expected: fieldAverageU NOT generated even if requested
   - Result: ✅ Works correctly

**Usage**:
```bash
python3 tests/test_backward_compatibility.py
```

**Expected output**: ✅ All 4 tests pass

---

## Test Results Summary

All tests passed successfully:

```
================================================================================
Test 1: Old config WITHOUT velocityFieldAverage (backward compatibility)
================================================================================
✅ PASS: Old config works correctly
  - fieldAverageWSS: Present (as expected)
  - fieldAverageU: NOT present (correct, option was not set)

================================================================================
Test 2: Config with velocityFieldAverage = false (explicitly disabled)
================================================================================
✅ PASS: Explicitly disabled works correctly
  - fieldAverageWSS: Present (as expected)
  - fieldAverageU: NOT present (correct, option = false)

================================================================================
Test 3: Config with velocityFieldAverage = true (enabled)
================================================================================
✅ PASS: Enabled config works correctly
  - fieldAverageWSS: Present
  - fieldAverageU: Present
  - UMean computation: Enabled
  - UPrime2Mean computation: Enabled

================================================================================
Test 4: Non-pulsatile flow (fieldAverageU should NOT be enabled)
================================================================================
✅ PASS: fieldAverageU correctly NOT enabled for steady flow
  - fieldAverageU: NOT present (correct, requires pulsatile flow)
```

---

## Implementation Verification

### Files Modified

1. **`src/templates/controlDict.tpl`**
   - Line 72: Added enable_velocity_avg flag
   - Lines 128-156: Added fieldAverageU function block

2. **`examples/config_full.json`**
   - Lines 552-556: Added velocityFieldAverage configuration option

### Configuration Test

Create a test config:
```json
{
  "hemodynamics": {
    "runtime_functions": {
      "velocityFieldAverage": true
    }
  }
}
```

Expected controlDict entry:
```cpp
fieldAverageU
{
    type            fieldAverage;
    libs            ("libfieldFunctionObjects.so");
    writeControl    writeTime;
    timeStart       1.0;
    periodicRestart true;
    restartPeriod   0.5;
    restartOnRestart false;

    fields
    (
        U
        {
            mean        on;
            prime2Mean  on;
            base        time;
        }
        p
        {
            mean        on;
            prime2Mean  off;
            base        time;
        }
    );
}
```

---

## Running All Tests

```bash
# Run individual tests
python3 tests/test_fieldaverage_template.py
python3 tests/test_backward_compatibility.py

# Or run both
for test in tests/test_fieldaverage_template.py tests/test_backward_compatibility.py; do
    echo "Running $test..."
    python3 "$test"
    echo ""
done
```

---

## Test Coverage

✅ **Template rendering** - Jinja2 template correctly generates fieldAverageU
✅ **Configuration parsing** - Correctly reads velocityFieldAverage option
✅ **Conditional logic** - Only enables for pulsatile flow
✅ **Backward compatibility** - Old configs work unchanged
✅ **Default behavior** - Defaults to false (disabled)
✅ **Field components** - UMean, UPrime2Mean, pMean all included
✅ **Timing parameters** - timeStart, periodicRestart configured correctly

---

## Documentation

- **Feature documentation**: `../VELOCITY_FIELD_AVERAGE_FEATURE.md`
- **Implementation summary**: `../IMPLEMENTATION_SUMMARY.md`
- **Usage examples**: See feature documentation

---

**Status**: ✅ All tests passing, feature ready for production use
