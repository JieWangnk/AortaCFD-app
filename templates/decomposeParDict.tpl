{{ header }}

numberOfSubdomains  {{ run_settings.subdomains }};

method              {{ run_settings.decomposition_method }};

simpleCoeffs
{
    n               (1 1 {{ run_settings.subdomains }}); // Simple 1D decomposition
    
    {# This logic handles the version-specific delta keyword #}
    {% if version == '8' %}
    delta           0.001;
    {% endif %}
}

hierarchicalCoeffs
{
    n               (1 1 {{ run_settings.subdomains }});
    order           xyz;
}

// ************************************************************************* //