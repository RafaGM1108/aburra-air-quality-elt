-- Stations from the live list, plus codes seen only in the historical data.
with readings as (
    select distinct station_code from {{ ref('int_pm25_hourly') }}
)

select
    coalesce(s.station_code, r.station_code) as station_code,
    s.station_id,
    s.station_name,
    s.municipality,
    s.longitude,
    s.latitude,
    s.station_code is not null as in_live_network
from {{ ref('stg_siata__stations') }} as s
full outer join readings as r on s.station_code = r.station_code
