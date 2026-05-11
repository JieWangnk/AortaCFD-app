class OFVersionAdapter:
    """OpenFOAM 12 specific adapter - no version compatibility needed"""

    def __init__(self, version=12):
        self.version = 12  # Fixed to OpenFOAM 12

    def get_foam_file_header(self, object_class, object_name):
        """
        Generate the FoamFile header for OpenFOAM 12.
        """
        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  12
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       {object_class};
    location    "0";
    object      {object_name};  
}}
"""
