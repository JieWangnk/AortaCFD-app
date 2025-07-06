# Installation

This guide will walk you through installing all dependencies and setting up AortaCFD for the first time. Follow each step carefully to ensure a successful installation.

---

## System Requirements

- **OpenFOAM 8** (must be installed and sourced)
- **ParaView** (for post-processing, including `pvbatch`)
- **Python 3.7+** (recommend Python 3.8 or newer)
- **pimpleFOAM_WK** solver for 3-element Windkessel boundary conditions ([see Windkessel code repo](https://github.com/EManchester/OpenFOAM-v8-Windkessel-code))
- All Python dependencies in `requirement.txt`

---

## 1. Install OpenFOAM 8

**Ubuntu Example:**
```bash
sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key | apt-key add -"
sudo add-apt-repository http://dl.openfoam.org/ubuntu
sudo apt-get update
sudo apt-get install openfoam8
# Add OpenFOAM to your environment (add this to your ~/.bashrc):
echo 'source /opt/openfoam8/etc/bashrc' >> ~/.bashrc
source ~/.bashrc
```
- For other platforms, see the [OpenFOAM download page](https://www.openfoam.com/download/).

---

## 2. Install ParaView (pvbatch)

- Download from your package manager or the [official ParaView website](https://www.paraview.org/download/).
- Ensure the `pvbatch` executable is available in your PATH:
  ```bash
  which pvbatch
  # Should print the path to pvbatch
  ```

---

## 3. Set Up Python Environment

It is recommended to use a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 4. Clone the AortaCFD Repository
```bash
git clone https://github.com/yourusername/AortaCFD-app.git
cd AortaCFD-app
```

---

## 5. Install Python Dependencies
```bash
pip install -r requirement.txt
```

---

## 6. Compile the Windkessel Solver (pimpleFOAM_WK, if using 3EWK)
Only needed for 3-element Windkessel boundary conditions.
```bash
git clone https://github.com/EManchester/OpenFOAM-v8-Windkessel-code.git
cd OpenFOAM-v8-Windkessel-code
wmake
```
- This will create the `pimpleFOAM_WK` solver in your `$FOAM_USER_APPBIN` directory.
- See the [Windkessel code README](https://github.com/EManchester/OpenFOAM-v8-Windkessel-code/blob/main/README.md) for details.

---

## 7. Verify Your Installation

- **Check OpenFOAM:**
  ```bash
  foamVersion
  which blockMesh
  ```
- **Check ParaView:**
  ```bash
  pvbatch --version
  ```
- **Check Python:**
  ```bash
  python --version
  pip list
  ```
- **Check AortaCFD:**
  ```bash
  python app.py --help
  ```

---

## 8. Troubleshooting & Known Issues
- Ensure all required STL and CSV files are present in the case directory.
- For Windkessel models, check that flow split ratios sum to 1.0.
- LES simulations require a fine mesh profile for best results.
- For 3EWK, ensure the custom solver and boundary files are set up as per [OpenFOAM-v8-Windkessel-code](https://github.com/EManchester/OpenFOAM-v8-Windkessel-code).
- See [Known Issues](known_issues.md) for more.

---

## 9. Next Steps
- See [Getting Started](getting_started.md) for running your first simulation.
- Review [Input Data Structure](input_data_structure.md) to prepare your case data.
- See [Command Reference](command_reference.md) for available workflow commands. 