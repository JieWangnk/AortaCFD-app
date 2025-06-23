# config/base.py
"""
This file holds the universal settings for the entire application.
These are parameters that rarely, if ever, change.
"""

config = {
    # The OpenFOAM version is a global setting.
    "openfoam_version": "8", #
    "openfoam_env_path": "/home/jie/OpenFOAM/OpenFOAM-8/etc/bashrc", # Path to the OpenFOAM environment script
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