#!/bin/bash
#===============================================================================
# AortaCFD Environment Check Script
#
# Verifies that all dependencies are correctly installed.
# Run this AFTER setting up your venv:
#
#   python3 -m venv venv
#   source venv/bin/activate
#   pip install -r requirements.txt
#   ./scripts/setup_environment.sh
#
# Author: Jie Wang
# Date: November 2025
#===============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}⚠${NC} $1"; ((WARNINGS++)); }
print_fail() { echo -e "  ${RED}✗${NC} $1"; ((ERRORS++)); }
print_info() { echo -e "  ${BLUE}ℹ${NC} $1"; }

#===============================================================================
# 1. Python & Virtual Environment
#===============================================================================
print_header "1. Python Environment"

# Check venv
if [ -n "$VIRTUAL_ENV" ]; then
    print_ok "Virtual environment active: $VIRTUAL_ENV"
    PYTHON_CMD="python"
    PIP_CMD="pip"
else
    print_warn "Virtual environment NOT active"
    print_info "Activate with: source venv/bin/activate"
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
fi

# Check Python version
if command -v $PYTHON_CMD &> /dev/null; then
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    print_ok "Python $PYTHON_VERSION"
else
    print_fail "Python not found"
fi

#===============================================================================
# 2. OpenFOAM
#===============================================================================
print_header "2. OpenFOAM"

if [ -n "$WM_PROJECT_VERSION" ]; then
    print_ok "OpenFOAM $WM_PROJECT_VERSION loaded"
else
    # Try to find and source OpenFOAM
    if [ -f "/opt/openfoam12/etc/bashrc" ]; then
        source /opt/openfoam12/etc/bashrc 2>/dev/null
        print_ok "OpenFOAM 12 found at /opt/openfoam12"
    else
        print_warn "OpenFOAM not loaded. Source it with:"
        print_info "source /opt/openfoam12/etc/bashrc"
    fi
fi

# Check key commands
for cmd in blockMesh snappyHexMesh pimpleFoam; do
    if command -v $cmd &> /dev/null; then
        print_ok "$cmd available"
    else
        print_fail "$cmd not found"
    fi
done

#===============================================================================
# 3. modularWKPressure Library
#===============================================================================
print_header "3. Windkessel BC Library"

WK_DIR="$HOME/OpenFOAM/${USER}-12/src/modularWKPressure"
if [ -d "$WK_DIR" ]; then
    print_ok "Source: $WK_DIR"

    if [ -n "$FOAM_USER_LIBBIN" ] && [ -f "$FOAM_USER_LIBBIN/libmodularWKPressure.so" ]; then
        print_ok "Library compiled"
    else
        print_warn "Library not compiled. Run: cd $WK_DIR && wmake"
    fi
else
    print_warn "modularWKPressure not found"
    print_info "Install with: ./scripts/install_windkessel_of12.sh"
fi

#===============================================================================
# 4. Python Packages
#===============================================================================
print_header "4. Python Packages"

PACKAGES=("numpy" "scipy" "trimesh" "jinja2" "matplotlib" "pandas" "vtk" "pyvista")

for pkg in "${PACKAGES[@]}"; do
    if $PYTHON_CMD -c "import $pkg" 2>/dev/null; then
        print_ok "$pkg"
    else
        print_fail "$pkg not installed"
    fi
done

#===============================================================================
# Summary
#===============================================================================
print_header "Summary"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "  ${GREEN}All checks passed! Ready to run simulations.${NC}"
elif [ $ERRORS -eq 0 ]; then
    echo -e "  ${YELLOW}$WARNINGS warning(s) - environment mostly ready${NC}"
else
    echo -e "  ${RED}$ERRORS error(s), $WARNINGS warning(s) - fix issues above${NC}"
fi

echo ""
echo "  Quick start:"
echo "    python run_patient.py patient1 --quick"
echo ""

exit $ERRORS
