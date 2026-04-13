/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  12
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

{# Use pre-computed values from template_context.py when available, fallback to inline computation for backward compatibility #}
{%- set _is_steady = is_steady if is_steady is defined else physics.get('steady_state', false) -%}
{%- set _profile = profile if profile is defined else 'standard' -%}
{%- set _ddt_scheme = ddt_scheme if ddt_scheme is defined else ('steadyState' if _is_steady else ('Euler' if _profile == 'robust' else 'backward')) -%}
{%- set _div_scheme_U = div_scheme_U if div_scheme_U is defined else ('Gauss upwind' if _profile == 'robust' else 'Gauss limitedLinearV 1') -%}
{%- set _div_scheme_k = div_scheme_k if div_scheme_k is defined else 'Gauss limitedLinear 1' -%}
{%- set _grad_limiter = grad_limiter if grad_limiter is defined else 0.5 -%}
{%- set _laplacian_scheme = laplacian_scheme if laplacian_scheme is defined else 'Gauss linear limited 0.5' -%}
{%- set _sngrad_scheme = sngrad_scheme if sngrad_scheme is defined else 'limited 0.5' -%}

ddtSchemes
{
    {% if schemes and schemes.ddtSchemes %}
    {%- for key, value in schemes.ddtSchemes.items() %}
    {%- if not key.startswith('_') %}  {# Skip metadata/comments #}
    {{ key }}       {{ value }};
    {%- endif %}
    {%- endfor %}
    {% else %}
    default         {{ _ddt_scheme }};
    {% endif %}
}

gradSchemes
{
    {% if schemes and schemes.gradSchemes %}
    {%- for key, value in schemes.gradSchemes.items() %}
    {%- if not key.startswith('_') %}  {# Skip metadata/comments #}
    {{ key }}       {{ value }};
    {%- endif %}
    {%- endfor %}
    {% else %}
    // Gradient schemes with cellLimited for stability
    default         cellLimited Gauss linear {{ _grad_limiter }};
    grad(p)         cellLimited Gauss linear 0.33;
    grad(U)         cellLimited Gauss linear {{ _grad_limiter }};
    {% endif %}
}

divSchemes
{
    {% if schemes and schemes.divSchemes %}
    {%- for key, value in schemes.divSchemes.items() %}
    {%- if not key.startswith('_') %}  {# Skip metadata/comments #}
    {{ key }}       {{ value }};
    {%- endif %}
    {%- endfor %}
    {% else %}
    default         none;
    div(phi,U)      {{ _div_scheme_U }};
    div(phi,k)      {{ _div_scheme_k }};
    div(phi,epsilon) {{ _div_scheme_k }};
    div(phi,omega)  {{ _div_scheme_k }};
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
    {% endif %}
}

laplacianSchemes
{
    {% if schemes and schemes.laplacianSchemes %}
    {%- for key, value in schemes.laplacianSchemes.items() %}
    {%- if not key.startswith('_') %}  {# Skip metadata/comments #}
    {{ key }}       {{ value }};
    {%- endif %}
    {%- endfor %}
    {% else %}
    default         {{ _laplacian_scheme }};
    {% endif %}
}

interpolationSchemes
{
    {% if schemes and schemes.interpolationSchemes %}
    {%- for key, value in schemes.interpolationSchemes.items() %}
    {%- if not key.startswith('_') %}  {# Skip metadata/comments #}
    {{ key }}       {{ value }};
    {%- endif %}
    {%- endfor %}
    {% else %}
    default         linear;
    {% endif %}
}

snGradSchemes
{
    {% if schemes and schemes.snGradSchemes %}
    {%- for key, value in schemes.snGradSchemes.items() %}
    {%- if not key.startswith('_') %}  {# Skip metadata/comments #}
    {{ key }}       {{ value }};
    {%- endif %}
    {%- endfor %}
    {% else %}
    default         {{ _sngrad_scheme }};
    {% endif %}
}

{% if physics.simulation_type in ['LES', 'RAS', 'RANS'] %}
wallDist
{
    method meshWave;
}
{% endif %}

// ************************************************************************* //