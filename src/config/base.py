# config/base.py
"""
This file holds the universal settings for the entire application.
These are parameters that rarely, if ever, change.
"""

config = {
    # OpenFOAM version configuration - supports multiple versions
    "openfoam": {
        "default_version": "8",
        "supported_versions": ["8", "12"],
        "version_configs": {
            "8": {
                "env_path": "/opt/openfoam8/etc/bashrc",
                "major_version": 8,
                "foundation": True,
                "solver_names": {
                    "incompressible": "pimpleFoam",
                    "windkessel": "pimpleFOAM_WK"
                },
                "windkessel": {
                    "repository": "https://github.com/EManchester/OpenFOAM-v8-Windkessel-code",
                    "boundary_condition": "windkesselPressure",
                    "solver_name": "pimpleFOAM_WK",
                    "supported": True,
                    "compilation_required": True
                }
            },
            "12": {
                "env_path": "/opt/openfoam12/etc/bashrc", 
                "major_version": 12,
                "foundation": True,
                "solver_names": {
                    "incompressible": "foamRun",
                    "windkessel": "foamRun"
                },
                "solver_modules": {
                    "incompressible": "incompressibleFluid",
                    "windkessel": "incompressibleFluid"
                },
                "windkessel": {
                    "repository": "https://github.com/JieWangnk/OpenFOAM-WK",
                    "boundary_condition": "modularWKPressure",
                    "library_name": "libmodularWKPressure.so",
                    "source_path": "src/modularWKPressure",
                    "supported": True,
                    "compilation_required": True
                }
            }
        }
    },
    
    # Legacy support - will be overridden by version-specific config
    "openfoam_version": "8",
    "openfoam_env_path": "/opt/openfoam8/etc/bashrc",
    
    # Foundational physical properties of the fluid (blood).
    "physics": {
        "nu": 3.3e-06,      #
        "rho": 1060,        #
    },

    # Definitions for what "coarse", "medium", and "fine" mean.
    "mesh": {
        "refinement_levels": {
            "coarse": 2.0,  #
            "medium": 1.5,  #
            "fine": 1.0     #
        }
    },

    # Path to external applications used in the workflow.
    "post_processing": {
        "pvbatch_exe": "/home/jie/ParaView-5.11.2-MPI-Linux-Python3.9-x86_64/bin/pvbatch", #
    }
}