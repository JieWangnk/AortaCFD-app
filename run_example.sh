#!/bin/bash
###############################################################################
# AortaCFD Quick-Start Example Script
###############################################################################
#
# This script demonstrates a complete end-to-end CFD workflow using patient1
# sample data. Use this to verify installation and understand the pipeline.
#
# Expected Runtime: 5-15 minutes (with --quick flag)
# Expected Output: Complete CFD results in output/patient1/run_*/
#
# PREREQUISITES:
#   1. OpenFOAM 12 sourced: source /opt/openfoam12/etc/bashrc
#   2. Python 3.12+ with venv activated: source venv/bin/activate
#   3. Sample data present: cases_input/patient1/
#
###############################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        AortaCFD Quick-Start Example - Patient1 Workflow           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

###############################################################################
# Step 1: Environment Check
###############################################################################
echo -e "${YELLOW}[1/6] Checking environment...${NC}"

# Check Python
if ! command -v python &> /dev/null; then
    echo -e "${RED}✗ Python not found. Please install Python 3.12+${NC}"
    exit 1
fi
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Python version: $PYTHON_VERSION${NC}"

# Check OpenFOAM
if ! command -v foamRun &> /dev/null; then
    echo -e "${RED}✗ OpenFOAM not found. Please source OpenFOAM 12:${NC}"
    echo -e "${RED}  source /opt/openfoam12/etc/bashrc${NC}"
    exit 1
fi
OF_VERSION=$(foamRun -help 2>&1 | head -n 1 || echo "OpenFOAM")
echo -e "${GREEN}✓ OpenFOAM available: $OF_VERSION${NC}"

# Check virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}! Virtual environment not activated. Attempting to activate...${NC}"
    if [ -d "venv" ]; then
        source venv/bin/activate
        echo -e "${GREEN}✓ Virtual environment activated${NC}"
    else
        echo -e "${RED}✗ Virtual environment not found. Run: python -m venv venv${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Virtual environment: $VIRTUAL_ENV${NC}"
fi

# Check patient1 data
if [ ! -d "cases_input/patient1" ]; then
    echo -e "${RED}✗ Sample data not found: cases_input/patient1/${NC}"
    echo -e "${RED}  Please ensure patient1 case data is present.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Sample data found: cases_input/patient1${NC}"

echo ""

###############################################################################
# Step 2: List Available Patients
###############################################################################
echo -e "${YELLOW}[2/6] Listing available patient cases...${NC}"
python run_patient.py --list
echo ""

###############################################################################
# Step 3: Show Available Profiles
###############################################################################
echo -e "${YELLOW}[3/6] Available simulation profiles:${NC}"
echo -e "  • ${GREEN}sim_laminar_coarse${NC}  - Quick test (5-10 min, coarse mesh)"
echo -e "  • ${GREEN}sim_laminar_medium${NC}  - Clinical quality (30-60 min, balanced)"
echo -e "  • ${GREEN}sim_laminar_fine${NC}    - High resolution (2-4 hours, fine mesh)"
echo -e "  • ${GREEN}sim_rans_medium${NC}     - Turbulence modeling (2-3 hours)"
echo ""
echo -e "Using: ${GREEN}--quick${NC} flag (sim_laminar_coarse profile)"
echo ""

###############################################################################
# Step 4: Run CFD Simulation
###############################################################################
echo -e "${YELLOW}[4/6] Running CFD simulation...${NC}"
echo -e "Command: ${BLUE}python run_patient.py patient1 --quick${NC}"
echo ""

# Run with --quick for fast demonstration
if python run_patient.py patient1 --quick; then
    echo -e "${GREEN}✓ Simulation completed successfully${NC}"
else
    echo -e "${RED}✗ Simulation failed. Check logs for details.${NC}"
    exit 1
fi
echo ""

###############################################################################
# Step 5: Locate Results
###############################################################################
echo -e "${YELLOW}[5/6] Locating results...${NC}"

# Find the most recent output directory
LATEST_RUN=$(find output/patient1 -maxdepth 1 -type d -name "run_*" 2>/dev/null | sort -r | head -n 1)

if [ -z "$LATEST_RUN" ]; then
    echo -e "${RED}✗ No output directory found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Results directory: $LATEST_RUN${NC}"
echo ""
echo "Results structure:"
tree -L 2 "$LATEST_RUN" 2>/dev/null || ls -lh "$LATEST_RUN"
echo ""

###############################################################################
# Step 6: Summary and Next Steps
###############################################################################
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    Quick-Start Complete! ✓                         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Results Location:${NC}"
echo -e "  📁 $LATEST_RUN"
echo ""
echo -e "${GREEN}Key Output Files:${NC}"
echo -e "  • ${BLUE}openfoam/${NC}           - Complete OpenFOAM case"
echo -e "  • ${BLUE}reports/${NC}            - Simulation setup documentation"
echo -e "  • ${BLUE}logs/${NC}               - Execution logs"
echo -e "  • ${BLUE}summary.json${NC}        - Analysis summary"
echo ""
echo -e "${GREEN}View Results:${NC}"
echo -e "  1. Open ParaView:"
echo -e "     ${BLUE}paraview $LATEST_RUN/openfoam/case.foam &${NC}"
echo ""
echo -e "  2. Check mesh quality:"
echo -e "     ${BLUE}cd $LATEST_RUN/openfoam && checkMesh${NC}"
echo ""
echo -e "  3. Inspect simulation report:"
echo -e "     ${BLUE}cat $LATEST_RUN/reports/simulation_setup_report.md${NC}"
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo -e "  • Run full-quality simulation:"
echo -e "    ${BLUE}python run_patient.py patient1 --profile sim_laminar_medium${NC}"
echo ""
echo -e "  • Run specific workflow steps:"
echo -e "    ${BLUE}python run_patient.py patient1 --step mesh${NC}"
echo -e "    ${BLUE}python run_patient.py patient1 --step post${NC}"
echo ""
echo -e "  • Process your own patient data:"
echo -e "    1. Create directory: ${BLUE}cases_input/my_patient/${NC}"
echo -e "    2. Add STL files: inlet.stl, wall_aorta.stl, outlet*.stl"
echo -e "    3. Add config.json (copy from patient1 example)"
echo -e "    4. Run: ${BLUE}python run_patient.py my_patient${NC}"
echo ""
echo -e "${GREEN}Documentation:${NC}"
echo -e "  • User Guide:       ${BLUE}cat USER_GUIDE.md${NC}"
echo -e "  • README:           ${BLUE}cat README.md${NC}"
echo -e "  • Post-Processing:  ${BLUE}cat POST_PROCESSING_CONFIG.md${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
