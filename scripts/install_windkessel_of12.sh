#!/bin/bash
# Installation script for OpenFOAM 12 Windkessel model
# This script downloads and compiles the modularWKPressure boundary condition

set -e

echo "=== OpenFOAM 12 Windkessel Model Installation ==="

# Check if OpenFOAM 12 is sourced
if [ -z "$WM_PROJECT_VERSION" ]; then
    echo "Error: OpenFOAM environment not found. Please source OpenFOAM 12:"
    echo "source /opt/openfoam12/etc/bashrc"
    exit 1
fi

if [ "$WM_PROJECT_VERSION" != "12" ]; then
    echo "Warning: Current OpenFOAM version is $WM_PROJECT_VERSION, expected 12"
    echo "Please ensure OpenFOAM 12 is sourced."
fi

# Set installation directory
INSTALL_DIR="${PWD}/windkessel_of12"
REPO_URL="https://github.com/JieWangnk/OpenFOAM-WK.git"

echo "Installing to: $INSTALL_DIR"

# Create installation directory
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Clone the repository if not already present
if [ ! -d "OpenFOAM-WK" ]; then
    echo "Cloning Windkessel repository..."
    git clone "$REPO_URL"
else
    echo "Repository already exists, updating..."
    cd OpenFOAM-WK
    git pull
    cd ..
fi

# Compile the modularWKPressure library
cd OpenFOAM-WK/src/modularWKPressure

echo "Compiling modularWKPressure boundary condition..."
wmake

# Check if compilation was successful
if [ $? -eq 0 ]; then
    echo "✅ Successfully compiled modularWKPressure boundary condition"
    echo "Library location: $FOAM_USER_LIBBIN/libmodularWKPressure.so"
    
    # Verify the library exists
    if [ -f "$FOAM_USER_LIBBIN/libmodularWKPressure.so" ]; then
        echo "✅ Library file confirmed at: $FOAM_USER_LIBBIN/libmodularWKPressure.so"
    else
        echo "❌ Warning: Library file not found at expected location"
    fi
else
    echo "❌ Compilation failed"
    exit 1
fi

echo ""
echo "=== Installation Complete ==="
echo "The modularWKPressure boundary condition is now available for OpenFOAM 12"
echo ""
echo "Usage in boundary conditions:"
echo "  type            modularWKPressure;"
echo "  phi             phi;"
echo "  order           2;"
echo "  R               1000;     // Peripheral resistance"
echo "  C               1e-6;     // Compliance"
echo "  Z               100;      // Characteristic impedance"
echo "  p0              0;        // Initial pressure"
echo "  value           uniform 0;"
echo ""
echo "Remember to add the library to your controlDict:"
echo "  libs (\"libmodularWKPressure.so\");"