import os

class FvSchemesWriter():
    def __init__(self, DIRECTORY, SIMULATIONTYPE,SIMULATIONPERFORMANCE):
        self.DIRECTORY = DIRECTORY
        self.SIMULATIONTYPE = SIMULATIONTYPE
        self.SIMULATIONPERFORMANCE = SIMULATIONPERFORMANCE

    def write_fvSchemes_file(self):
        filepath = os.path.join(self.DIRECTORY,"system","fvSchemes")

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
            if self.SIMULATIONTYPE == 'LES':
                if self.SIMULATIONPERFORMANCE == "high":
                    f.write(self._get_LES_high_fvSchemes())
                elif self.SIMULATIONPERFORMANCE == "medium":
                    f.write(self._get_LES_medium_fvSchemes())
                elif self.SIMULATIONPERFORMANCE == "low":
                    f.write(self._get_LES_low_fvSchemes())
                else:
                    print("Invalid simulation performance.")
                
    def _get_laminar_high_fvSchemes(self):
        laminar_fvSchemes = """/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  10
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSchemes;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddtSchemes
{
    default         backward;
}

gradSchemes
{
    default         cellLimited Gauss linear 1;
    grad(p)         cellLimited Gauss linear 0.5;
}

divSchemes
{
    default         none;

    div(phi,U)      Gauss linearUpwind default;
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
}

laplacianSchemes
{
    default         Gauss linear limited 0.5;
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         corrected;
}


// ************************************************************************* //
"""
        return laminar_fvSchemes

    def _get_laminar_medium_fvSchemes(self):
        laminar_fvSchemes = """/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  10
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSchemes;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddtSchemes
{
    default         backward;
}

gradSchemes
{
    default     cellLimited Gauss linear 0.5;
}

divSchemes
{
    default         none;

    div(phi,U)      Gauss linear;
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
}

laplacianSchemes
{
    default         Gauss linear limited 0.5;
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         corrected;
}


// ************************************************************************* //
"""
        return laminar_fvSchemes

    def _get_laminar_low_fvSchemes(self):
        laminar_fvSchemes = """/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  10
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSchemes;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddtSchemes
{
    default         Euler;
}

gradSchemes
{
    default         cellLimited Gauss linear 0.5;
}

divSchemes
{
    default         none;

    div(phi,U)      Gauss upwind;
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
}

laplacianSchemes
{
    default         Gauss linear limited 0.5;
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         corrected;
}


// ************************************************************************* //
"""
        return laminar_fvSchemes

    def _get_LES_high_fvSchemes(self):
        LES_fvSchemes = """/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  8
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSchemes;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddtSchemes
{
    default         backward;
}

gradSchemes
{
    default         cellMDLimited Gauss linear 0.5;
}

divSchemes
{
    default         none;
    div(phi,U)      Gauss linear;
    div(phi,k)      Gauss linear;
    div(phi,epsilon)      Gauss linear;
    div(phi,R)      Gauss linear;
    div(R)          Gauss linear;
    div(phi,nuTilda)    Gauss linear;
    div((nuEff*dev2(T(grad(U))))) Gauss linear; 
}

laplacianSchemes
{
    default         Gauss linear corrected;
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         corrected;
}

wallDist
{
    method meshWave;
}
// ************************************************************************* //
"""
        return LES_fvSchemes
        
    def _get_LES_medium_fvSchemes(self):
        LES_fvSchemes = """/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  8
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSchemes;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddtSchemes
{
    default         backward;
}

gradSchemes
{
    default     cellLimited Gauss linear 1;
    grad(p)     cellLimited Gauss linear 0.5;
}

divSchemes
{
    default         none;
    div(phi,U)      Gauss linear;
    div(phi,k)      Gauss limitedLinear 1;
    div(phi,epsilon)      Gauss limitedLinear 1;
    div(phi,R)      Gauss limitedLinear 1;
    div(R)          Gauss linear;
    div(phi,nuTilda) Gauss limitedLinear 1;
    div((nuEff*dev2(T(grad(U))))) Gauss linear; 
}

laplacianSchemes
{
    default         Gauss linear corrected;
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         corrected;
}

wallDist
{
    method meshWave;
}
// ************************************************************************* //
"""
        return LES_fvSchemes

    def _get_LES_low_fvSchemes(self):
        LES_fvSchemes = """/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  8
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSchemes;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddtSchemes
{
    default         Euler;
}

gradSchemes
{
    default         cellLimited Gauss linear 1;
}

divSchemes
{
    default         none;
    div(phi,U)      Gauss upwind;
    div(phi,k)      Gauss upwind;
    div(phi,epsilon)    Gauss upwind;
    div(phi,R)      Gauss upwind;
    div(R)          Gauss upwind;
    div(phi,nuTilda)    Gauss upwind;
    div((nuEff*dev2(T(grad(U)))))   Gauss linear;
}

laplacianSchemes
{
    default         Gauss linear corrected;
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         corrected;
}

wallDist
{
    method meshWave;
}
// ************************************************************************* //
"""
        return LES_fvSchemes
    
