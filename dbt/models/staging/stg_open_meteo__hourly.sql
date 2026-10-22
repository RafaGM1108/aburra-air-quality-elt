-- Hourly weather at the Open-Meteo grid point on the Aburrá Valley floor.
select
    timestamp_hour,
    timezone('America/Bogota', timestamp_hour)::date as date_local,
    hour(timezone('America/Bogota', timestamp_hour)) as hour_local,
    temperature_2m,
    relative_humidity_2m,
    precipitation,
    wind_speed_10m,
    wind_direction_10m,
    boundary_layer_height,
    source,
    landed_on
from {{ source('siata', 'open_meteo_hourly') }}
