{{ config(location=env_var('ABURRA_AIR_INTERMEDIATE', '../data/02_intermediate') ~ '/int_open_meteo_daily.parquet') }}

-- Daily weather summaries. Precipitation is accumulated; all other covariates are averaged
-- except boundary-layer height, whose minimum is retained for inversion-sensitive analysis.
select
    date_local,
    count(*) as valid_hours,
    avg(temperature_2m) as temperature_mean,
    avg(relative_humidity_2m) as relative_humidity_mean,
    sum(precipitation) as precipitation_total,
    avg(wind_speed_10m) as wind_speed_mean,
    avg(wind_direction_10m) as wind_direction_mean,
    avg(boundary_layer_height) as boundary_layer_height_mean,
    min(boundary_layer_height) as boundary_layer_height_min
from {{ ref('stg_open_meteo__hourly') }}
group by date_local
