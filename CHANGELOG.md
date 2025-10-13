# Changelog

All notable changes to the AortaCFD project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2024-12-01

### Added

#### Boundary Conditions
- **CONSTANT inlet with cardiac output** - Specify inlet flow as L/min instead of velocity
  - Automatic velocity calculation from cardiac output and inlet area
  - Clinically intuitive specification (e.g., 5 L/min resting, 10-15 L/min exercise)
- **Enhanced flow split methods** for Windkessel outlets
  - Murray's Law (r³) - physiologically based
  - Area-based distribution
  - Equal distribution
  - Custom per-outlet ratios
- **Percentage-based flow split** - First N-1 outlets share X%, last gets remainder

#### Testing Infrastructure
- **362 total tests** with 100% pass rate
  - 302 unit tests
  - 42 integration tests
  - 18 end-to-end tests
- **Test coverage: 29%** (key modules: inlet_mapping 92%, mesh_setup 79%)
- **CI/CD with GitHub Actions**
  - Matrix testing (Python 3.10, 3.11, 3.12)
  - Automated coverage reports
  - Code quality checks (Black, isort, Flake8)
  - Security scanning
- **CFD validation framework**
  - Mesh quality validation (no solver required)
  - Simulation validation with OpenFOAM execution
  - Multi-config comparison tools

#### Mesh Generation
- **Automated mesh generation** with snappyHexMesh
  - blockMesh for background mesh
  - snappyHexMesh for patient geometry refinement
- **Boundary layer generation** with configurable settings
  - Number of layers, expansion ratio, thickness
- **Profile-based mesh sizing** (coarse/medium/fine)
- **Quality validation** with checkMesh

#### Configuration System
- **Profile-based configuration** - Pre-defined solver/resolution combinations
  - Laminar: coarse/medium/fine
  - RANS: coarse/medium/fine
  - LES: medium/fine
- **3-layer merge system** - Base + Profile + Case configs
- **Intelligent config builder** - Automatic parameter inference

#### Documentation
- **USER_GUIDE.md** - Comprehensive user documentation
- **CLAUDE.md** - Developer/AI assistant implementation guide
- **Mesh quality guides** - Validated settings and results

### Fixed
- **Inlet velocity direction** - Correct handling for vertical aorta geometry
- **Configuration compatibility** - Support for both nested and flat config structures
- **OpenFOAM 12 compatibility** - Updated solver commands and templates
- **Flow conservation** - Windkessel flow split validation to machine precision
- **Simulation time parsing** - Handle 's' suffix and avoid ExecutionTime conflicts

### Changed
- **OpenFOAM 12 as primary solver** - Uses `foamRun -solver incompressibleFluid`
- **Windkessel BC library** - Switched to `modularWKPressure` for OF12
- **Project restructure** - Moved to `src/` directory structure
- **Simplified documentation** - Consolidated multiple guides into USER_GUIDE.md

---

## [1.0.0] - 2024-06-01

### Added
- Initial public release of AortaCFD
- Complete CFD simulation pipeline for patient-specific aortic blood flow
- OpenFOAM integration (v8 and v12)
- Murray's Law automatic flow distribution
- Three-element Windkessel (3EWK) boundary conditions
- Patient runner CLI interface
- Profile-based configuration system

### Features
- **Inlet boundary conditions**
  - Time-varying from CSV (realistic cardiac waveforms)
  - Constant velocity (steady-state testing)
  - Parabolic profile (laminar validation)
  - Womersley profile (pulsatile analytical)
- **Outlet boundary conditions**
  - 3-element Windkessel (physiological)
  - Zero gradient (simple testing)
  - Fixed pressure
- **Turbulence models**
  - Laminar flow
  - RANS (k-ω SST)
  - LES (WALE/Smagorinsky)
- **Automated mesh generation**
  - blockMesh for background mesh
  - snappyHexMesh for patient geometry
  - Boundary layer generation
- **Post-processing tools**
  - Hemodynamic analysis
  - Wall shear stress calculation
  - Flow visualization
  - Publication-ready reporting

---

## Version Summary

| Version | Date | Key Features |
|---------|------|--------------|
| 1.2.0 | 2024-12-01 | OpenFOAM 12, testing framework, automated mesh generation, cardiac output inlet |
| 1.0.0 | 2024-06-01 | Initial release, basic pipeline, Murray's Law, 3EWK |

---

## Future Roadmap

### High Priority
- [ ] Performance benchmarking suite
- [ ] Additional patient validation cases
- [ ] Docker containerization
- [ ] Enhanced error diagnostics

### Medium Priority
- [ ] Multi-patient batch processing optimization
- [ ] Advanced mesh quality metrics
- [ ] Interactive visualization dashboard
- [ ] Cloud deployment support

### Low Priority
- [ ] Video tutorials
- [ ] Extended API documentation
- [ ] Performance optimization guide
- [ ] DICOM integration for medical imaging

---

## Contributors

**Development:**
- Jie Wang (University of Manchester) - Lead developer
- Project contributors - Code review, validation, testing

---

## Notes

### Breaking Changes
- v1.2.0: Configuration structure changed from flat to nested (backward compatible with automatic conversion)
- v1.2.0: OpenFOAM 12 recommended (v8 still supported)

### Security
- All user inputs validated through `validation.py`
- Path traversal protection in file operations
- No known security vulnerabilities

---

*For detailed commit history, see `git log` or [GitHub commit history](https://github.com/JieWangnk/AortaCFD-app/commits).*
