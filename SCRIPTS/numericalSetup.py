import os

class FvSchemesWriter():
    def __init__(self, DIRECTORY, SIMULATIONTYPE, SIMULATIONPERFORMANCE, OPENFOAM_VERSION):
        self.DIRECTORY = DIRECTORY
        self.SIMULATIONTYPE = SIMULATIONTYPE
        self.SIMULATIONPERFORMANCE = SIMULATIONPERFORMANCE
        self.openfoam_version = OPENFOAM_VERSION  # Store the OpenFOAM version

    def write_fvSchemes_file(self):
        filepath = os.path.join(self.DIRECTORY, "system", "fvSchemes")

        with open(filepath, 'w') as f:
            if self.SIMULATIONTYPE == 'laminar':
                if self.SIMULATIONPERFORMANCE == "high":
                    f.write(self._get_laminar_high_fvSchemes())
                elif self.SIMULATIONPERFORMANCE == "medium":
                    f.write(self._get_laminar_medium_fvSchemes())
                elif self.SIMULATIONPERFORMANCE == "low":
                    f.write(self._get_laminar_low_fvSchemes())
                else:
                    print("Invalid simulation performance.")
            elif self.SIMULATIONTYPE == 'LES':
                if self.SIMULATIONPERFORMANCE == "high":
                    f.write(self._get_LES_high_fvSchemes())
                elif self.SIMULATIONPERFORMANCE == "medium":
                    f.write(self._get_LES_medium_fvSchemes())
                elif self.SIMULATIONPERFORMANCE == "low":
                    f.write(self._get_LES_low_fvSchemes())
                else:
                    print("Invalid simulation performance.")

    def _get_foam_file_header(self):
        """
        Generate the FoamFile header dynamically based on the OpenFOAM version.
        """
        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  {self.openfoam_version}
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSchemes;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
"""

    def _get_laminar_high_fvSchemes(self):
        laminar_fvSchemes = f"""{self._get_foam_file_header()}

ddtSchemes
{{
    default         backward;
}}

gradSchemes
{{
    default         cellLimited Gauss linear 1;
    grad(p)         cellLimited Gauss linear 0.5;
}}

divSchemes
{{
    default         none;

    div(phi,U)      Gauss linearUpwind default;
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear limited 0.5;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

// ************************************************************************* //
"""
        return laminar_fvSchemes

    def _get_laminar_medium_fvSchemes(self):
        laminar_fvSchemes = f"""{self._get_foam_file_header()}

ddtSchemes
{{
    default         backward;
}}

gradSchemes
{{
    default         cellLimited Gauss linear 0.5;
}}

divSchemes
{{
    default         none;

    div(phi,U)      Gauss linear;
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear limited 0.5;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

// ************************************************************************* //
"""
        return laminar_fvSchemes

    def _get_laminar_low_fvSchemes(self):
        laminar_fvSchemes = f"""{self._get_foam_file_header()}

ddtSchemes
{{
    default         Euler;
}}

gradSchemes
{{
    default         cellLimited Gauss linear 0.5;
}}

divSchemes
{{
    default         none;

    div(phi,U)      Gauss upwind;
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear limited 0.5;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

// ************************************************************************* //
"""
        return laminar_fvSchemes

    def _get_LES_high_fvSchemes(self):
        LES_fvSchemes = f"""{self._get_foam_file_header()}

ddtSchemes
{{
    default         backward;
}}

gradSchemes
{{
    default         cellMDLimited Gauss linear 0.5;
}}

divSchemes
{{
    default         none;
    div(phi,U)      Gauss linear;
    div(phi,k)      Gauss linear;
    div(phi,epsilon)      Gauss linear;
    div(phi,R)      Gauss linear;
    div(R)          Gauss linear;
    div(phi,nuTilda)    Gauss linear;
    div((nuEff*dev2(T(grad(U))))) Gauss linear; 
}}

laplacianSchemes
{{
    default         Gauss linear corrected;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

wallDist
{{
    method meshWave;
}}

// ************************************************************************* //
"""
        return LES_fvSchemes

    def _get_LES_medium_fvSchemes(self):
        LES_fvSchemes = f"""{self._get_foam_file_header()}

ddtSchemes
{{
    default         backward;
}}

gradSchemes
{{
    default         cellLimited Gauss linear 1;
    grad(p)         cellLimited Gauss linear 0.5;
}}

divSchemes
{{
    default         none;
    div(phi,U)      Gauss linear;
    div(phi,k)      Gauss limitedLinear 1;
    div(phi,epsilon)      Gauss limitedLinear 1;
    div(phi,R)      Gauss limitedLinear 1;
    div(R)          Gauss linear;
    div(phi,nuTilda) Gauss limitedLinear 1;
    div((nuEff*dev2(T(grad(U))))) Gauss linear; 
}}

laplacianSchemes
{{
    default         Gauss linear corrected;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

wallDist
{{
    method meshWave;
}}

// ************************************************************************* //
"""
        return LES_fvSchemes

    def _get_LES_low_fvSchemes(self):
        LES_fvSchemes = f"""{self._get_foam_file_header()}

ddtSchemes
{{
    default         Euler;
}}

gradSchemes
{{
    default         cellLimited Gauss linear 1;
}}

divSchemes
{{
    default         none;
    div(phi,U)      Gauss upwind;
    div(phi,k)      Gauss upwind;
    div(phi,epsilon)    Gauss upwind;
    div(phi,R)      Gauss upwind;
    div(R)          Gauss upwind;
    div(phi,nuTilda)    Gauss upwind;
    div((nuEff*dev2(T(grad(U)))))   Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear corrected;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

wallDist
{{
    method meshWave;
}}

// ************************************************************************* //
"""
        return LES_fvSchemes

