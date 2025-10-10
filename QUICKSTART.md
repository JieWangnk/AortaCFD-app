# AortaCFD Quick Start

## One-Command Setup

```bash
# Run automated setup script
./setup_aortacfd.sh
```

This will:
1. ✅ Create Python virtual environment
2. ✅ Install all Python dependencies
3. ✅ Clone Windkessel BC repository
4. ✅ Compile both Windkessel libraries
5. ✅ Verify everything works

---

## Manual Setup (if needed)

### 1. Python Virtual Environment

```bash
# Create and activate venv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. OpenFOAM Windkessel BC

```bash
# Load OpenFOAM
source /opt/openfoam12/etc/bashrc

# Clone repository
mkdir -p ~/OpenFOAM/libraries
cd ~/OpenFOAM/libraries
git clone https://github.com/JieWangnk/OpenFOAM-WK.git
cd OpenFOAM-WK

# Compile libraries
cd modularWKPressure && wmake libso

# Verify
ls $FOAM_USER_LIBBIN | grep -i WK
```

---

## Daily Usage

### Start Session

```bash
# Load environments
source /opt/openfoam12/etc/bashrc
source venv/bin/activate

# Or use alias (add to ~/.bashrc)
alias aortacfd='source /opt/openfoam12/etc/bashrc && source ~/AortaCFD-app/venv/bin/activate && cd ~/AortaCFD-app'
```

### Run Test

```bash
# Quick test (Windkessel calculation only)
python run_patient.py patient1 \
  --config cases_input/patient1/config_3ewk_40percent.json \
  --step case --step boundary

# Full simulation
python run_patient.py patient1 \
  --config cases_input/patient1/config_3ewk_40percent.json
```

---

## Verification Commands

```bash
# Check Python environment
which python  # Should be in venv/
pip list | grep numpy

# Check OpenFOAM
which wmake
foamVersion

# Check Windkessel libraries
ls $FOAM_USER_LIBBIN | grep -i windkessel
# Should show:
#   libmodularWKPressure.so
#   libstabilizedWindkesselVelocity.so
```

---

## Troubleshooting

### Python issues
```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### OpenFOAM issues
```bash
source /opt/openfoam12/etc/bashrc
which wmake  # Should return a path
```

### Windkessel compilation issues
```bash
source /opt/openfoam12/etc/bashrc
cd ~/OpenFOAM/libraries/OpenFOAM-WK/modularWKPressure
wclean
wmake libso
```

---

## Documentation

- **[SETUP_ENVIRONMENT.md](SETUP_ENVIRONMENT.md)** - Complete setup guide
- **[TEST_3EWK_40PCT.md](TEST_3EWK_40PCT.md)** - Test configuration guide
- **[WINDKESSEL_BC_REFERENCE.md](WINDKESSEL_BC_REFERENCE.md)** - Windkessel BC reference

---

## Quick Reference

| Task | Command |
|------|---------|
| Setup | `./setup_aortacfd.sh` |
| Activate | `source /opt/openfoam12/etc/bashrc && source venv/bin/activate` |
| Test WK | `python run_patient.py patient1 --config config_3ewk_40percent.json --step boundary` |
| Full run | `python run_patient.py patient1 --config config_3ewk_40percent.json` |
| Check libs | `ls $FOAM_USER_LIBBIN \| grep -i windkessel` |
