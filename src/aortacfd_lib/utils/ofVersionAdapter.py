import os

class OFVersionAdapter:
    def __init__(self, version):
        self.version = version

    def get_foam_file_header(self, object_class, object_name):
        """
        Generate the FoamFile header dynamically based on the OpenFOAM version.
        """
        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  {self.version}
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