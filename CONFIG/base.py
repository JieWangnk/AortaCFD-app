# CONFIG/base.py
"""
Base configuration for the AortaCFD application.

This file contains universal parameters that serve as the default baseline for all
simulations. These values are loaded first by the ConfigBuilder.
"""

CONFIG = {
    # The OpenFOAM version is a global, application-wide setting.
    "openfoam_version": "8",

    # Foundational physical properties of the fluid (blood).
    # These are constant across all simulations.
    "physics": {
        "nu": 3.3e-06,      # Kinematic viscosity (m^2/s)
        "rho": 1060,        # Density (kg/m^3)
    },

    # Definitions for mesh refinement levels. This provides a consistent
    # meaning to "coarse", "medium", and "fine" across the project.
    "mesh": {
        "refinement_levels": {
            "coarse": 2.0,
            "medium": 1.5,
            "fine": 1.0
        }
    },

    # Path to external applications used in the workflow.
    # This is specific to the machine, not the simulation.
    "post_processing": {
        "pvbatch_exe": "/home/jie/ParaView-5.11.2-MPI-Linux-Python3.9-x86_64/bin/pvbatch",
    }
}