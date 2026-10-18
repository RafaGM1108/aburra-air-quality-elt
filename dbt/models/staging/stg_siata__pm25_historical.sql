-- Historical hourly PM2.5 (2023-07 → 2024-07); -9999 is already NULL from the load step.
select
    station_code,
    timestamp_hour,
    case
        when pm25 between {{ var('pm25_min_plausible') }} and {{ var('pm25_max_plausible') }}
            then pm25
    end as pm25,
    pm25 as pm25_reported,
    quality
from {{ source('siata', 'siata_pm25_historical') }}
