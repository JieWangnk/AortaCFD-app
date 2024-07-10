import os 

class SolnType:
    def __init__(self,DIRECTORY ,SOLN_TYPE, SUBDOMAINS, DECOMPOSITION_METHOD):
        self.DIRECTORY = DIRECTORY
        self.SOLN_TYPE = SOLN_TYPE
        self.SUBDOMAINS = SUBDOMAINS
        self.DECOMPOSITION_METHOD = DECOMPOSITION_METHOD


    def write_decomposeParDict(self):
        content = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  11                                     |
|   \\\\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       dictionary;
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
}}

hierarchicalCoeffs
{{
    n               (4 2 1); // total must match numberOfSubdomains
    order           xyz;
}}


// ************************************************************************* //""".format(no_subdomains=self.SUBDOMAINS, deco_method=self.DECOMPOSITION_METHOD)

        with open(os.path.join(self.DIRECTORY,"system","decomposeParDict"), "w") as f:
            f.write(content)
        print("decomposeParDict file has been written.")
        
