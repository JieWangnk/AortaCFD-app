{{ header }}

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform 0;

boundaryField
{
    // The inlet pressure is standardized here
    {{ inlet_patch }}
    {
        type            zeroGradient;
    }

    // The outlets are created dynamically based on the JSON settings
    {% for outlet in outlet_patches %}
    {{ outlet }}
    {
        {% if outlet_settings.type == "3EWINDKESSEL" %}
        type            WKBC;
        index           {{ loop.index0 }};
        value           uniform 0;
        {% else %}
        type            zeroGradient;
        {% endif %}
    }
    {% endfor %}

    // The wall condition is standardized here
    {{ wall_patch }}
    {
        type            zeroGradient;
    }
}
// ************************************************************************* //