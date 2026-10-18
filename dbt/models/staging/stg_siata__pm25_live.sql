-- Live hourly PM2.5, one row per station and hour (the load step already deduplicated).
select
    station_code,
    timestamp_hour,
    case
        when pm25 between {{ var('pm25_min_plausible') }} and {{ var('pm25_max_plausible') }}
            then pm25
    end as pm25,
    pm25 as pm25_reported,
    landed_on
from {{ source('siata', 'siata_pm25_hourly') }}
