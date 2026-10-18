select
    station_code,
    station_id,
    station_name,
    municipality,
    longitude,
    latitude,
    landed_on
from {{ source('siata', 'siata_stations') }}
