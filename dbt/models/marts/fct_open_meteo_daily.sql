{{ config(location=env_var('ABURRA_AIR_MODEL_INPUT', '../data/05_model_input') ~ '/fct_open_meteo_daily.parquet') }}

-- One weather record per Aburrá Valley calendar day. Data by Open-Meteo.com, CC BY 4.0.
select *
from {{ ref('int_open_meteo_daily') }}
