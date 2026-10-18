{{ config(location=env_var('ABURRA_AIR_INTERMEDIATE', '../data/02_intermediate') ~ '/int_pm25_daily.parquet') }}

-- Daily PM2.5 by station (calendar day, America/Bogota).
-- A day counts only with at least var('min_valid_hours') valid hours.
select
    station_code,
    date_local,
    count(pm25) as valid_hours,
    count(pm25) >= {{ var('min_valid_hours') }} as is_valid_day,
    case when count(pm25) >= {{ var('min_valid_hours') }} then avg(pm25) end as pm25_mean,
    max(pm25) as pm25_max
from {{ ref('int_pm25_hourly') }}
group by station_code, date_local
