# Flow Split Validation - Quick Reference

## ⚡ Quick Commands

```bash
# Run demo (recommended first step)
python validation/test_flow_split_demo.py

# Analyze specific case
python validation/analyzers/flow_split_analyzer.py \
    cases/patient1 --config cases_input/patient1/config.json

# Integrated BC validation (includes flow split analysis)
./validation/run_bc_validation.py patient1 \
    --profile sim_laminar_medium --time 0.1
```

## 📝 Custom Flow Split Config

```json
{
  "boundary_conditions": {
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "methodology": "custom_flow_split",
        "flow_split": {
          "outlet1": 0.10,   // 10%
          "outlet2": 0.10,   // 10%
          "outlet3": 0.10,   // 10%
          "outlet4": 0.70    // 70%
        }
      }
    }
  }
}
```

## 📊 Interpretation Guide

### Deviation Levels:
- **< 10%**: ✅ Good match with Murray's Law
- **10-50%**: ⚠️ Moderate deviation (check if intentional)
- **> 50%**: ❌ Poor match (likely incorrect)

### Common Patterns:
- **Equal split (25% each)**: Usually BAD (ignores geometry)
- **Murray auto**: Perfect match by definition (0% deviation)
- **Custom split**: Validate against Murray to check realism

## 🔬 Murray's Law Exponents

| Vessel Type | Diameter Range | Exponent (n) |
|-------------|---------------|--------------|
| Large aortic | > 25mm | 2.0 |
| Thoracic/abdominal | 15-25mm | 2.2 |
| Major branches | 8-15mm | 2.39 |
| Coronary/peripheral | 4-8mm | 2.5 |
| Small arteries | < 4mm | 2.7-3.0 |

**Default**: 2.39 (2024 meta-analysis)

## 📈 Patient1 Results Summary

```
Geometry:  outlet1=7.3mm, outlet2=4.6mm, outlet3=3.6mm, outlet4=8.7mm
Murray:    33.0%         10.8%          6.3%          50.0%

Custom (30/70):  Deviation 44% (fails)
Equal (25%):     Deviation 126% (very poor)
Murray auto:     Deviation 0% (perfect)
```

## 🎯 What Does This Validate?

**WITHOUT flow rate extraction**:
- ✅ Custom ratios sum to 1.0
- ✅ Geometry-based Murray's Law prediction
- ✅ Deviation analysis (custom vs Murray)
- ✅ Configuration validation

**Next step** (with flow extraction):
- ⏭️ Compare actual flow rates vs custom/Murray

## 📂 Key Files

```
validation/
├── analyzers/flow_split_analyzer.py     # Main module
├── test_flow_split_demo.py              # Demo script
├── FLOW_SPLIT_VALIDATION_SUMMARY.md     # Full docs
└── FLOW_SPLIT_QUICK_REFERENCE.md        # This file

cases_input/patient1/
└── config_custom_flow_split.json        # Example config
```

## 🔧 Python API

```python
from validation.analyzers.flow_split_analyzer import FlowSplitAnalyzer

analyzer = FlowSplitAnalyzer(case_dir)
metrics = analyzer.analyze_flow_split(config)

print(f"Custom: {metrics.custom_split}")
print(f"Murray: {metrics.murray_split}")
print(f"Deviation: {metrics.mean_deviation_percent:.1f}%")
print(f"Match: {metrics.ratios_match}")
```

## ✅ Validation Checklist

- [ ] Custom flow_split defined in config
- [ ] Ratios sum to 1.0 (±1%)
- [ ] Deviation from Murray < 10% (or justified)
- [ ] Geometry STL files available
- [ ] Murray exponent appropriate for vessel size
- [ ] Flow split matches physiological expectations

---

**Full Documentation**: [FLOW_SPLIT_VALIDATION_SUMMARY.md](FLOW_SPLIT_VALIDATION_SUMMARY.md)
