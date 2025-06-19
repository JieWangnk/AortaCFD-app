# CONFIG/profiles/laminar_medium.py
"""
This is a Simulation Profile. It defines all the settings needed for a
medium-fidelity laminar simulation.
"""

CONFIG = {
    # Mesh settings for a medium-fidelity run.
    "mesh": {
        "SNAPPY_SETTINGS": {
            "parallel": False, #
            "nProcessors": 3, #
            "expansionFactor": 0.02, #
            "regionRefinementLevel": 2, #
            "nCellsBetweenLevels": 3, #
            "featureLevel": 2, #
            "surfaceRefinementLevels": [1, 1], #
            "resolveFeatureAngle": 30, #
            "nSmoothPatch": 3, #
            "addLayer": 5 #
        }
    },
    # Run settings for this profile.
    "run_settings": {
        "solution_type": "parallel", #
        "subdomains": 3, #
        "decomposition_method": "scotch" #
    },
    # Physics and solver settings.
    "physics": {
        "simulation_type": "laminar", #
        "outter_correction_loop": 100 #
    },
    # Simulation run-time controls.
    "simulation_control": {
        "controlDict": {
            "deltaT": 1e-6, #
            "writeControl": "timeStep", #
            "writeInterval": 1, #
            "runTimeModifiable": "true", #
            "functions": ["wallShearStress"] #
        }
    }
}