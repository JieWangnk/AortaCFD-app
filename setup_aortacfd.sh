#!/bin/bash
# AortaCFD Complete Environment Setup Script
# This script sets up Python virtual environment and compiles Windkessel BC libraries

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"
WK_LIB_DIR="$HOME/OpenFOAM/libraries"
WK_REPO="https://github.com/JieWangnk/OpenFOAM-WK.git"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================================================"
echo "AortaCFD Environment Setup"
echo "================================================================================"
echo ""

# ============================================================================
# Part 1: Python Virtual Environment
# ============================================================================

echo -e "${YELLOW}Part 1: Setting up Python Virtual Environment${NC}"
echo "--------------------------------------------------------------------------------"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python3 not found. Please install Python 3.8+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓ Python version: $PYTHON_VERSION${NC}"

# Create virtual environment
if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠ Virtual environment already exists at $VENV_DIR${NC}"
    read -p "Remove and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
        echo -e "${GREEN}✓ Removed existing virtual environment${NC}"
    else
        echo -e "${YELLOW}Using existing virtual environment${NC}"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
echo -e "${GREEN}✓ pip upgraded${NC}"

# Install requirements
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install -r "$SCRIPT_DIR/requirements.txt" > /dev/null 2>&1
    echo -e "${GREEN}✓ Python dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠ requirements.txt not found, skipping Python package installation${NC}"
fi

# Test Python imports
echo "Testing Python imports..."
python3 -c "import numpy; import vtk; import stl; import jinja2" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All required Python packages imported successfully${NC}"
else
    echo -e "${RED}✗ Some Python packages failed to import${NC}"
fi

echo ""

# ============================================================================
# Part 2: OpenFOAM Windkessel BC Libraries
# ============================================================================

echo -e "${YELLOW}Part 2: Compiling OpenFOAM Windkessel BC Libraries${NC}"
echo "--------------------------------------------------------------------------------"

# Check OpenFOAM installation
if [ -z "$WM_PROJECT_DIR" ]; then
    echo -e "${YELLOW}⚠ OpenFOAM environment not loaded${NC}"
    echo "Looking for OpenFOAM installation..."

    if [ -f "/opt/openfoam12/etc/bashrc" ]; then
        echo "Found OpenFOAM 12 at /opt/openfoam12"
        source /opt/openfoam12/etc/bashrc
        echo -e "${GREEN}✓ OpenFOAM 12 environment loaded${NC}"
    elif [ -f "/usr/lib/openfoam/openfoam2312/etc/bashrc" ]; then
        echo "Found OpenFOAM at /usr/lib/openfoam/openfoam2312"
        source /usr/lib/openfoam/openfoam2312/etc/bashrc
        echo -e "${GREEN}✓ OpenFOAM environment loaded${NC}"
    else
        echo -e "${RED}✗ OpenFOAM not found. Please install OpenFOAM 12${NC}"
        echo ""
        echo "Install OpenFOAM 12 with:"
        echo "  sudo sh -c \"wget -O - https://dl.openfoam.org/gpg.key | apt-key add -\""
        echo "  sudo add-apt-repository http://dl.openfoam.org/ubuntu"
        echo "  sudo apt-get update"
        echo "  sudo apt-get install openfoam12"
        echo ""
        exit 1
    fi
else
    echo -e "${GREEN}✓ OpenFOAM environment already loaded${NC}"
    echo "  OpenFOAM version: $(foamVersion)"
    echo "  WM_PROJECT_DIR: $WM_PROJECT_DIR"
fi

# Check wmake
if ! command -v wmake &> /dev/null; then
    echo -e "${RED}✗ wmake not found. OpenFOAM environment not properly loaded${NC}"
    exit 1
fi
echo -e "${GREEN}✓ wmake found${NC}"

# Check if Windkessel repo exists
mkdir -p "$WK_LIB_DIR"
WK_REPO_DIR="$WK_LIB_DIR/OpenFOAM-WK"

if [ -d "$WK_REPO_DIR" ]; then
    echo -e "${YELLOW}⚠ Windkessel repository already exists at $WK_REPO_DIR${NC}"
    read -p "Remove and re-clone? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$WK_REPO_DIR"
        echo -e "${GREEN}✓ Removed existing repository${NC}"
    else
        echo -e "${YELLOW}Using existing repository${NC}"
    fi
fi

if [ ! -d "$WK_REPO_DIR" ]; then
    echo "Cloning Windkessel repository..."
    git clone "$WK_REPO" "$WK_REPO_DIR"
    echo -e "${GREEN}✓ Repository cloned${NC}"
fi

# Compile modularWKPressure
echo ""
echo "Compiling modularWKPressure..."
cd "$WK_REPO_DIR/modularWKPressure"
wclean > /dev/null 2>&1
wmake libso
if [ -f "$FOAM_USER_LIBBIN/libmodularWKPressure.so" ]; then
    echo -e "${GREEN}✓ libmodularWKPressure.so compiled successfully${NC}"
    ls -lh "$FOAM_USER_LIBBIN/libmodularWKPressure.so" | awk '{print "  Size: " $5 " | " $9}'
else
    echo -e "${RED}✗ Failed to compile libmodularWKPressure.so${NC}"
    exit 1
fi

# Compile stabilizedWindkesselVelocity
echo ""
echo "Compiling stabilizedWindkesselVelocity..."
cd "$WK_REPO_DIR/stabilizedWindkesselVelocity"
wclean > /dev/null 2>&1
wmake libso
if [ -f "$FOAM_USER_LIBBIN/libstabilizedWindkesselVelocity.so" ]; then
    echo -e "${GREEN}✓ libstabilizedWindkesselVelocity.so compiled successfully${NC}"
    ls -lh "$FOAM_USER_LIBBIN/libstabilizedWindkesselVelocity.so" | awk '{print "  Size: " $5 " | " $9}'
else
    echo -e "${RED}✗ Failed to compile libstabilizedWindkesselVelocity.so${NC}"
    exit 1
fi

echo ""

# ============================================================================
# Part 3: Final Verification
# ============================================================================

echo -e "${YELLOW}Part 3: Final Verification${NC}"
echo "--------------------------------------------------------------------------------"

# Check Python environment
source "$VENV_DIR/bin/activate"
PYTHON_PATH=$(which python)
if [[ "$PYTHON_PATH" == *"venv"* ]]; then
    echo -e "${GREEN}✓ Python virtual environment: $PYTHON_PATH${NC}"
else
    echo -e "${RED}✗ Python virtual environment not activated${NC}"
fi

# Check OpenFOAM
WMAKE_PATH=$(which wmake)
if [ -n "$WMAKE_PATH" ]; then
    echo -e "${GREEN}✓ OpenFOAM wmake: $WMAKE_PATH${NC}"
else
    echo -e "${RED}✗ OpenFOAM wmake not found${NC}"
fi

# Check Windkessel libraries
if [ -f "$FOAM_USER_LIBBIN/libmodularWKPressure.so" ] && [ -f "$FOAM_USER_LIBBIN/libstabilizedWindkesselVelocity.so" ]; then
    echo -e "${GREEN}✓ Windkessel libraries compiled${NC}"
    echo "  Location: $FOAM_USER_LIBBIN"
else
    echo -e "${RED}✗ Windkessel libraries not found${NC}"
fi

# Test Python imports
python3 -c "import numpy, vtk, stl, jinja2" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All Python packages working${NC}"
else
    echo -e "${RED}✗ Some Python packages not working${NC}"
fi

echo ""
echo "================================================================================"
echo -e "${GREEN}Setup Complete!${NC}"
echo "================================================================================"
echo ""
echo "To activate the environment in future sessions:"
echo ""
echo "  # Load OpenFOAM environment"
echo "  source /opt/openfoam12/etc/bashrc"
echo ""
echo "  # Activate Python virtual environment"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "Or add this alias to your ~/.bashrc:"
echo ""
echo "  alias aortacfd='source /opt/openfoam12/etc/bashrc && source $VENV_DIR/bin/activate && cd $SCRIPT_DIR'"
echo ""
echo "Then run: aortacfd"
echo ""
echo "To test the setup:"
echo "  python run_patient.py patient1 --config cases_input/patient1/config_3ewk_40percent.json --step case --step boundary"
echo ""
