{# Use the configured schema name as is (e.g. "staging"), not "<target>_staging". #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name or target.schema }}
{%- endmacro %}
