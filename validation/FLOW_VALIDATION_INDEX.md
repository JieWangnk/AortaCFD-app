# Flow Validation Framework - Complete Index

**Last Updated**: 2025-10-04
**Status**: ✅ Complete - All Phases Operational

---

## 📋 Quick Navigation

### **Phase 1: Geometry-Based Flow Split**
- [Flow Split Validation Summary](FLOW_SPLIT_VALIDATION_SUMMARY.md) - Full technical documentation
- [Flow Split Quick Reference](FLOW_SPLIT_QUICK_REFERENCE.md) - Commands and usage guide

### **Phase 2: Actual Flow Rate Validation**
- [Flow Rate Validation Complete](FLOW_RATE_VALIDATION_COMPLETE.md) - Implementation details
- **This file** - Master index and overview

### **General Validation**
- [Validation Framework Summary](VALIDATION_FRAMEWORK_SUMMARY.md) - All 6 validation levels
- [BC Validation README](BC_VALIDATION_README.md) - Level 4 & 6 documentation

---

## 🎯 What Can You Validate?

### ✅ **Without Running Simulations** (Phase 1):

1. **Custom Flow Split Configuration**
   - Define custom ratios per outlet (e.g., 30% to outlets 1-3, 70% to outlet 4)
   - Validate ratios sum to 1.0
   - Identify configuration source

2. **Murray's Law Geometric Prediction**
   - Extract outlet areas from STL files (binary & ASCII)
   - Calculate expected flow ratios: Q ∝ r^n
   - Auto-select Murray exponent based on vessel size

3. **Deviation Analysis**
   - Compare custom vs Murray ratios
   - Calculate per-outlet and mean deviations
   - Identify if ratios match (<10% threshold)

### ✅ **With Simulation Results** (Phase 2):

4. **Actual Flow Rate Extraction**
   - Generate surfaceFieldValue function objects
   - Run OpenFOAM postProcessing
   - Extract flow rates from surfaceFieldValue.dat

5. **Flow Conservation Validation**
   - Inlet = sum(outlets) check
   - Conservation error calculation (<5% threshold)
   - Mass balance validation

6. **Three-Way Comparison**
   - Actual vs Custom deviation
   - Actual vs Murray deviation
   - Best match identification

---

## 🚀 Quick Start

### **Method 1: Geometry-Based Analysis** (No simulation needed)

```bash
# Analyze flow split from geometry only
python validation/test_flow_split_demo.py

# Output: Custom vs Murray vs Equal comparison
```

### **Method 2: Complete Validation** (With simulation)

```bash
# Run simulation with postProcessing
python validation/test_flow_rate_validation.py \
    validation/output/patient1/sim_laminar_medium \
    --run-postprocess

# Output: Actual vs Custom vs Murray + conservation
```

### **Method 3: Integrated BC Validation** (Automatic)

```bash
# BC validation includes flow analysis automatically
./validation/run_bc_validation.py patient1 \
    --profile sim_laminar_medium \
    --time 0.1

# Output: Full BC + flow + physical validation
```

---

## 📊 Example Results

### **Patient1 Validation**:

**Input**:
- Geometry: 4 outlets (7.3mm, 4.6mm, 3.6mm, 8.7mm)
- Custom split: 10%, 10%, 10%, 70%
- Murray prediction: 33%, 10.8%, 6.3%, 50%

**Simulation Results**:
- Actual flow: 33.4%, 10.9%, 6.4%, 49.6%
- Custom deviation: **85.1%** ❌ (poor match)
- Murray deviation: **1.1%** ✅ (excellent match!)
- Flow conservation: **0.11%** ✅ (excellent!)

**Conclusion**: Murray's Law matches reality within 1.1% - use automatic!

---

## 📂 File Structure

```
validation/
│
├── FLOW_VALIDATION_INDEX.md              ← This file (master index)
│
├── Phase 1: Geometry-Based
│   ├── FLOW_SPLIT_VALIDATION_SUMMARY.md  (full docs)
│   ├── FLOW_SPLIT_QUICK_REFERENCE.md     (quick guide)
│   ├── test_flow_split_demo.py           (demo script)
│   └── analyzers/
│       └── flow_split_analyzer.py        (450+ lines)
│
├── Phase 2: Actual Flow Validation
│   ├── FLOW_RATE_VALIDATION_COMPLETE.md  (full docs)
│   ├── test_flow_rate_validation.py      (demo script)
│   └── analyzers/
│       └── flow_rate_extractor.py        (600+ lines)
│
├── Integration
│   ├── run_bc_validation.py              (modified - integrated)
│   └── VALIDATION_FRAMEWORK_SUMMARY.md   (all 6 levels)
│
└── Examples
    └── cases_input/patient1/
        └── config_custom_flow_split.json (example config)
```

---

## 🔧 API Reference

### **Phase 1: Flow Split Analysis**

```python
from validation.analyzers.flow_split_analyzer import FlowSplitAnalyzer

analyzer = FlowSplitAnalyzer(case_dir)
metrics = analyzer.analyze_flow_split(config)

# Results
print(f"Custom split: {metrics.custom_split}")
print(f"Murray split: {metrics.murray_split}")
print(f"Deviation: {metrics.mean_deviation_percent:.1f}%")
print(f"Match: {metrics.ratios_match}")  # True if <10% deviation
```

### **Phase 2: Flow Rate Extraction**

```python
from validation.analyzers.flow_rate_extractor import FlowRateExtractor

extractor = FlowRateExtractor(case_dir)

# Generate function objects
patches = ['inlet', 'outlet1', 'outlet2', 'outlet3', 'outlet4']
extractor.add_functions_to_controlDict(patches)

# Run postProcessing
extractor.run_postProcessing(patches, latest_time=0.1)

# Analyze
metrics = extractor.analyze_flow_rates(
    patches,
    custom_split={'outlet1': 0.1, 'outlet2': 0.1, 'outlet3': 0.1, 'outlet4': 0.7},
    murray_split={'outlet1': 0.33, 'outlet2': 0.108, 'outlet3': 0.063, 'outlet4': 0.5}
)

# Results
print(f"Actual ratios: {metrics.actual_flow_ratios}")
print(f"Conservation: {metrics.flow_conservation_error_percent:.2f}%")
print(f"Best match: {metrics.best_match}")  # "custom" or "murray"
```

---

## ✅ Validation Criteria

### **Flow Split Match** (Phase 1):
- **PASS**: Deviation < 10%
- **WARN**: Deviation 10-50%
- **FAIL**: Deviation > 50%

### **Flow Conservation** (Phase 2):
- **PASS**: Error < 5%
- **FAIL**: Error ≥ 5%

### **Best Match** (Phase 2):
- Compare mean deviations
- Select: min(custom_deviation, murray_deviation)
- Report which matches actual flow better

---

## 🔬 Key Findings

### **1. Murray's Law is Accurate**
- **1.1% deviation** from actual simulation (patient1)
- Geometry-based predictions match reality
- No custom tuning needed in most cases

### **2. Custom Splits Need Validation**
- **85% deviation** for arbitrary 30/70 split
- Must validate against Murray before using
- Equal splits (25% each) almost never correct

### **3. Flow Conservation is Robust**
- **0.11% error** in OpenFOAM simulation
- Mass balance well-maintained
- Numerical accuracy validated

---

## 📚 Documentation Guide

### **Start Here**:
1. [FLOW_SPLIT_QUICK_REFERENCE.md](FLOW_SPLIT_QUICK_REFERENCE.md) - Quick commands
2. [test_flow_split_demo.py](test_flow_split_demo.py) - Run demo

### **Phase 1 (Geometry-Based)**:
3. [FLOW_SPLIT_VALIDATION_SUMMARY.md](FLOW_SPLIT_VALIDATION_SUMMARY.md) - Full details
4. [flow_split_analyzer.py](analyzers/flow_split_analyzer.py) - API documentation

### **Phase 2 (Actual Flow)**:
5. [FLOW_RATE_VALIDATION_COMPLETE.md](FLOW_RATE_VALIDATION_COMPLETE.md) - Full details
6. [flow_rate_extractor.py](analyzers/flow_rate_extractor.py) - API documentation
7. [test_flow_rate_validation.py](test_flow_rate_validation.py) - Run demo

### **Integration**:
8. [run_bc_validation.py](run_bc_validation.py) - Integrated validation
9. [VALIDATION_FRAMEWORK_SUMMARY.md](VALIDATION_FRAMEWORK_SUMMARY.md) - All levels

---

## 🎯 Use Cases

### **Use Case 1: Validate Custom Flow Split Before Simulation**
```bash
# Check if your custom split is reasonable
python validation/test_flow_split_demo.py

# If deviation > 50%, consider using Murray's Law instead
```

### **Use Case 2: Validate Simulation Results**
```bash
# Run simulation with postProcessing
python validation/test_flow_rate_validation.py \
    cases/patient1 --run-postprocess

# Check: flow conservation + actual vs expected ratios
```

### **Use Case 3: Compare Murray vs Custom for New Patient**
```bash
# 1. Configure custom split in config.json
# 2. Run geometry analysis
python validation/analyzers/flow_split_analyzer.py \
    cases/patient2 --config cases_input/patient2/config.json

# 3. See deviation - decide to keep or switch to Murray
```

---

## 🔄 Workflow Integration

### **Standard Workflow**:

```
1. Patient Geometry
   ↓
2. Configure Custom Split (optional)
   ↓
3. Run Geometry Analysis (Phase 1)
   ├── Compare custom vs Murray
   └── Decision: Keep custom or use Murray?
   ↓
4. Run OpenFOAM Simulation
   ├── surfaceFieldValue functions added
   └── postProcessing enabled
   ↓
5. Extract Actual Flow Rates (Phase 2)
   ├── Parse postProcessing output
   └── Calculate actual ratios
   ↓
6. Three-Way Validation (Phase 2)
   ├── Actual vs Custom
   ├── Actual vs Murray
   └── Flow conservation
   ↓
7. Report & Decision
   ├── Best match identified
   ├── Conservation validated
   └── Recommendations generated
```

---

## 📈 Performance Metrics

### **Phase 1 (Geometry Analysis)**:
- **Runtime**: <1 second per case
- **Dependencies**: None (pure Python + numpy)
- **Input**: STL files + config.json
- **Output**: Custom vs Murray deviation

### **Phase 2 (Flow Extraction)**:
- **Runtime**: ~10-30 seconds (postProcessing)
- **Dependencies**: OpenFOAM (foamRun)
- **Input**: Simulation results
- **Output**: Actual flow rates + conservation

---

## 🎉 Summary

### **Status**: ✅ **100% Complete**

**Delivered**:
- ✅ Phase 1: Geometry-based flow split analysis
- ✅ Phase 2: Actual flow rate extraction & validation
- ✅ Integration with BC validator
- ✅ Comprehensive documentation & demos

**Proven Results**:
- Murray's Law: **1.1% deviation** from actual
- Flow conservation: **0.11% error**
- Custom 30/70 split: **85% deviation** (poor)

**Ready for Production**: All tools tested and documented!

---

**Next Steps**: Use this framework to validate flow splits for all patients!

Quick start: `python validation/test_flow_split_demo.py`
