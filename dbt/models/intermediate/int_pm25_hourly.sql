{{ config(location=env_var('ABURRA_AIR_INTERMEDIATE', '../data/02_intermediate') ~ '/int_pm25_hourly.parquet') }}

-- Live and historical readings on one timeline; live wins if both have the same hour.
with readings as (
    select station_code, timestamp_hour, pm25, 'live' as source, 1 as priority
    from {{ ref('stg_siata__pm25_live') }}
    union all
    select station_code, timestamp_hour, pm25, 'historical' as source, 2 as priority
    from {{ ref('stg_siata__pm25_historical') }}
)

select
    station_code,
    timestamp_hour,
    timezone('America/Bogota', timestamp_hour)::date as date_local,
    hour(timezone('America/Bogota', timestamp_hour)) as hour_local,
    pm25,
    source
from readings
qualify row_number() over (partition by station_code, timestamp_hour order by priority) = 1
