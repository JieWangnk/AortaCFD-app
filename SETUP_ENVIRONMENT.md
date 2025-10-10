# AortaCFD Environment Setup Guide

Complete guide for setting up Python virtual environment and OpenFOAM Windkessel boundary conditions.

---

## Part 1: Python Virtual Environment Setup

### Step 1: Create Virtual Environment

```bash
# Navigate to project directory
cd /home/jie/AortaCFD-app

# Create virtual environment (Python 3.12)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Verify activation (should show venv path)
which python
```

**Expected output:**
```
/home/jie/AortaCFD-app/venv/bin/python
```

### Step 2: Upgrade pip

```bash
pip install --upgrade pip setuptools wheel
```

### Step 3: Install Python Dependencies

```bash
# Install all requirements
pip install -r requirements.txt

# Verify installation
pip list
```

**Key packages installed:**
- numpy, pandas, scipy (numerical computing)
- matplotlib, pyvista, vtk (visualization)
- jinja2 (templating)
- numpy-stl (STL file processing)

### Step 4: Test Python Setup

```bash
# Quick test
python -c "import numpy; import vtk; import stl; print('✓ All imports successful')"
```

### Step 5: Deactivate (when done)

```bash
deactivate
```

---

## Part 2: OpenFOAM Windkessel BC Compilation

### Prerequisites

**Required:**
- OpenFOAM 12 (Foundation version)
- g++ compiler
- git

**Check OpenFOAM installation:**
```bash
# Load OpenFOAM environment
source /opt/openfoam12/etc/bashrc

# Verify
which wmake
foamVersion
```

**Expected output:**
```
OpenFOAM-12
```

---

### Step 1: Clone Windkessel Repository

```bash
# Create a directory for the Windkessel code
mkdir -p ~/OpenFOAM/libraries
cd ~/OpenFOAM/libraries

# Clone the repository
git clone https://github.com/JieWangnk/OpenFOAM-WK.git
cd OpenFOAM-WK
```

**Repository structure:**
```
OpenFOAM-WK/
├── modularWKPressure/           # Pressure BC library
├── stabilizedWindkesselVelocity/  # Velocity BC library
├── tutorials/                    # Example cases
└── README.md
```

---

### Step 2: Compile modularWKPressure Library

```bash
cd ~/OpenFOAM/libraries/OpenFOAM-WK/modularWKPressure

# Clean any previous builds
wclean

# Compile the library
wmake libso

# Verify compilation
ls -lh $FOAM_USER_LIBBIN/libmodularWKPressure.so
```

**Expected output:**
```
-rwxr-xr-x 1 jie jie 245K Oct  9 15:30 /home/jie/OpenFOAM/jie-12/platforms/linux64GccDPInt32Opt/lib/libmodularWKPressure.so
```

---

### Step 3: Compile stabilizedWindkesselVelocity Library

```bash
cd ~/OpenFOAM/libraries/OpenFOAM-WK/stabilizedWindkesselVelocity

# Clean any previous builds
wclean

# Compile the library
wmake libso

# Verify compilation
ls -lh $FOAM_USER_LIBBIN/libstabilizedWindkesselVelocity.so
```

**Expected output:**
```
-rwxr-xr-x 1 jie jie 189K Oct  9 15:31 /home/jie/OpenFOAM/jie-12/platforms/linux64GccDPInt32Opt/lib/libstabilizedWindkesselVelocity.so
```

---

### Step 4: Verify Library Installation

```bash
# Check both libraries exist
ls -lh $FOAM_USER_LIBBIN | grep -i windkessel

# Expected output:
# libmodularWKPressure.so
# libstabilizedWindkesselVelocity.so
```

---

### Step 5: Test with Tutorial Case (Optional)

```bash
# Copy tutorial case
cd ~/OpenFOAM/libraries/OpenFOAM-WK/tutorials
cp -r CoA_test ~/OpenFOAM/test_windkessel
cd ~/OpenFOAM/test_windkessel

# Generate mesh
blockMesh

# Check boundary conditions
cat system/controlDict | grep libs
# Should show:
#   libs ("libmodularWKPressure.so" "libstabilizedWindkesselVelocity.so");

# Run a quick test (1 time step)
foamRun -solver incompressibleFluid -time 0:0.001

# Check for errors
tail -20 log.foamRun
```

---

## Part 3: Integrated Setup for AortaCFD

### Step 1: Update AortaCFD Configuration

The Windkessel libraries are automatically loaded by AortaCFD when using `3EWINDKESSEL` outlet type.

Check [src/config/base.py](src/config/base.py):
```python
"windkessel": {
    "repository": "https://github.com/JieWangnk/OpenFOAM-WK",
    "boundary_condition": "modularWKPressure",
    "solver_name": "foamRun",
    "solver_module": "incompressibleFluid",
    "supported": True,
    "compilation_required": True
}
```

### Step 2: Environment Variables (Add to ~/.bashrc)

```bash
# Add to ~/.bashrc for permanent setup
cat >> ~/.bashrc << 'EOF'

# OpenFOAM 12 Environment
source /opt/openfoam12/etc/bashrc

# AortaCFD Python Virtual Environment
alias aortacfd='source /home/jie/AortaCFD-app/venv/bin/activate && cd /home/jie/AortaCFD-app'
EOF

# Reload bashrc
source ~/.bashrc
```

### Step 3: Quick Start Alias

```bash
# Now you can activate everything with:
aortacfd

# You should see:
# (venv) jie@hostname:~/AortaCFD-app$
```

---

## Part 4: Verification Checklist

### ✓ Python Environment

```bash
source venv/bin/activate
python -c "
import numpy
import vtk
import stl
import jinja2
print('✓ All Python packages installed')
"
```

### ✓ OpenFOAM Environment

```bash
source /opt/openfoam12/etc/bashrc
which wmake && echo "✓ OpenFOAM 12 loaded"
foamVersion | grep "OpenFOAM-12" && echo "✓ Correct version"
```

### ✓ Windkessel Libraries

```bash
[ -f "$FOAM_USER_LIBBIN/libmodularWKPressure.so" ] && echo "✓ modularWKPressure.so compiled"
[ -f "$FOAM_USER_LIBBIN/libstabilizedWindkesselVelocity.so" ] && echo "✓ stabilizedWindkesselVelocity.so compiled"
```

### ✓ Full Integration Test

```bash
# Activate environment
source /opt/openfoam12/etc/bashrc
source venv/bin/activate

# Test Windkessel calculation only
python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json --step case --step boundary

# Look for:
# ================================================================================
# Calculating 3-Element Windkessel Coefficients (Clinical Method)
# ================================================================================
```

---

## Troubleshooting

### Python Virtual Environment Issues

**Problem: `venv/bin/activate` not found**
```bash
# Recreate virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Problem: Import errors (e.g., `ImportError: No module named numpy`)**
```bash
# Ensure venv is activated
source venv/bin/activate
which python  # Should show venv path

# Reinstall requirements
pip install --upgrade -r requirements.txt
```

---

### OpenFOAM Issues

**Problem: `wmake: command not found`**
```bash
# Load OpenFOAM environment
source /opt/openfoam12/etc/bashrc

# Or check installation path:
ls /opt/openfoam*/etc/bashrc
```

**Problem: `Could not find OpenFOAM installation`**

Check if OpenFOAM 12 is installed:
```bash
ls /opt/ | grep openfoam
```

If not installed, install OpenFOAM 12:
```bash
# Ubuntu/Debian
sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key | apt-key add -"
sudo add-apt-repository http://dl.openfoam.org/ubuntu
sudo apt-get update
sudo apt-get install openfoam12
```

---

### Windkessel Compilation Issues

**Problem: Compilation errors**

Check compiler and OpenFOAM environment:
```bash
# Verify g++ is installed
g++ --version

# Verify OpenFOAM environment variables
echo $WM_PROJECT_DIR
echo $FOAM_USER_LIBBIN

# Clean and retry
wclean
wmake libso
```

**Problem: Libraries not found at runtime**

Check library path:
```bash
# List user libraries
ls -lh $FOAM_USER_LIBBIN

# If empty, recompile with OpenFOAM environment loaded
source /opt/openfoam12/etc/bashrc
cd ~/OpenFOAM/libraries/OpenFOAM-WK/modularWKPressure
wmake libso
```

**Problem: `error while loading shared libraries`**

Add user lib path to LD_LIBRARY_PATH:
```bash
export LD_LIBRARY_PATH=$FOAM_USER_LIBBIN:$LD_LIBRARY_PATH
```

---

## Quick Reference Commands

### Start Working Session

```bash
# Load everything
source /opt/openfoam12/etc/bashrc
source /home/jie/AortaCFD-app/venv/bin/activate
cd /home/jie/AortaCFD-app

# Or use alias (if set up)
aortacfd
```

### Run Test

```bash
# Quick WK test
python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json --step case --step boundary

# Full simulation
python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json
```

### Check Status

```bash
# Python environment
which python  # Should be in venv/
pip list | head -10

# OpenFOAM
which wmake
ls $FOAM_USER_LIBBIN | grep -i windkessel
```

---

## Summary

✅ **Python venv:** `/home/jie/AortaCFD-app/venv/`
✅ **WK Libraries:** `$FOAM_USER_LIBBIN/lib*Windkessel*.so`
✅ **Activate:** `source venv/bin/activate && source /opt/openfoam12/etc/bashrc`
✅ **Test:** `python run_patient.py patient1 --config config_3ewk_40percent.json --step boundary`

For detailed API reference, see [WINDKESSEL_BC_REFERENCE.md](WINDKESSEL_BC_REFERENCE.md)
