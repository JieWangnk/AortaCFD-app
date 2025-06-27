# System Requirements

- **OpenFOAM 8** (must be installed and sourced)
- **ParaView** (for post-processing, including `pvbatch`)
- **pimpleFOAM_WK** solver for 3-element Windkessel boundary conditions ([see Windkessel code repo](https://github.com/EManchester/OpenFOAM-v8-Windkessel-code))
- **Python 3.7+** and the dependencies in `requirement.txt`

## Installing OpenFOAM 8 (Ubuntu Example)
```bash
sudo sh -c "wget -O - https://dl.openfoam.org/gpg.key | apt-key add -"
sudo add-apt-repository http://dl.openfoam.org/ubuntu
sudo apt-get update
sudo apt-get install openfoam8
source /opt/openfoam8/etc/bashrc
```

## Installing ParaView (pvbatch)
Install from your package manager or the [official ParaView website](https://www.paraview.org/download/). Ensure `pvbatch` is in your PATH.

## Compiling the Windkessel Solver (pimpleFOAM_WK)
```bash
git clone https://github.com/EManchester/OpenFOAM-v8-Windkessel-code.git
cd OpenFOAM-v8-Windkessel-code
wmake
```
This will create the `pimpleFOAM_WK` solver in your `$FOAM_USER_APPBIN` directory. 