-- SIATA pads some names with spaces (e.g. "Medellín "), which would split groupings.
select
    station_code,
    trim(station_id) as station_id,
    trim(station_name) as station_name,
    trim(municipality) as municipality,
    longitude,
    latitude,
    landed_on
from {{ source('siata', 'siata_stations') }}
