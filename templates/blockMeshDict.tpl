/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  {{ config.openfoam_version }}
     \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      blockMeshDict;
}
// ************************************************************************* //

vertices
(
    {# This is the corrected syntax for number formatting #}
    ({{ '%.6g' % bounds.min[0] }} {{ '%.6g' % bounds.min[1] }} {{ '%.6g' % bounds.min[2] }})
    ({{ '%.6g' % bounds.max[0] }} {{ '%.6g' % bounds.min[1] }} {{ '%.6g' % bounds.min[2] }})
    ({{ '%.6g' % bounds.max[0] }} {{ '%.6g' % bounds.max[1] }} {{ '%.6g' % bounds.min[2] }})
    ({{ '%.6g' % bounds.min[0] }} {{ '%.6g' % bounds.max[1] }} {{ '%.6g' % bounds.min[2] }})
    ({{ '%.6g' % bounds.min[0] }} {{ '%.6g' % bounds.min[1] }} {{ '%.6g' % bounds.max[2] }})
    ({{ '%.6g' % bounds.max[0] }} {{ '%.6g' % bounds.min[1] }} {{ '%.6g' % bounds.max[2] }})
    ({{ '%.6g' % bounds.max[0] }} {{ '%.6g' % bounds.max[1] }} {{ '%.6g' % bounds.max[2] }})
    ({{ '%.6g' % bounds.min[0] }} {{ '%.6g' % bounds.max[1] }} {{ '%.6g' % bounds.max[2] }})
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({{ cells.x }} {{ cells.y }} {{ cells.z }}) simpleGrading (1 1 1)
);

edges
(
);

boundary
(
    world
    {
        type patch;
        faces
        (
            (0 3 2 1)
            (4 5 6 7)
            (0 1 5 4)
            (3 7 6 2)
            (0 4 7 3)
            (1 2 6 5)
        );
    }
);
// ************************************************************************* //