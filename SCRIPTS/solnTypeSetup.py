import os 

class SolnType:
    def __init__(self, DIRECTORY, SOLN_TYPE, SUBDOMAINS, DECOMPOSITION_METHOD, OPENFOAM_VERSION):
        self.DIRECTORY = DIRECTORY
        self.SOLN_TYPE = SOLN_TYPE
        self.SUBDOMAINS = SUBDOMAINS
        self.DECOMPOSITION_METHOD = DECOMPOSITION_METHOD
        self.openfoam_version = OPENFOAM_VERSION  # Store the OpenFOAM version

    def write_decomposeParDict(self):
        """
        Write the decomposeParDict file dynamically based on OpenFOAM version.
        """
        content = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  {openfoam_version}                              |
|   \\\\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      decomposeParDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

numberOfSubdomains  {no_subdomains};

/*
    Main methods are:
    1) Geometric: "simple"; "hierarchical", with ordered sorting, e.g. xyz, yxz
    2) Scotch: "scotch", when running in serial; "ptscotch", running in parallel
*/

method              {deco_method}; //scotch; //ptscotch; //simple; //hierarchical;

simpleCoeffs
{{
    n               (4 2 1); // total must match numberOfSubdomains
    {delta_block}
}}

hierarchicalCoeffs
{{
    n               (4 2 1); // total must match numberOfSubdomains
    order           xyz;
}}


// ************************************************************************* //"""

        # Handle version-specific behavior for `delta` in `simpleCoeffs`
        if int(self.openfoam_version) == 8:
            delta_block = "delta           0.001;"  # Mandatory for OpenFOAM 8 and above
        else:
            delta_block = ""  # Not required for later versions

        # Format the content with the appropriate values
        content = content.format(
            openfoam_version=self.openfoam_version,
            no_subdomains=self.SUBDOMAINS,
            deco_method=self.DECOMPOSITION_METHOD,
            delta_block=delta_block
        )

        # Write the file
        filepath = os.path.join(self.DIRECTORY, "system", "decomposeParDict")
        with open(filepath, "w") as f:
            f.write(content)
        print("decomposeParDict file has been written.")

