-- Hourly PM2.5 by station. Local use only: hourly series are never published (docs/data.md).
select station_code, timestamp_hour, date_local, hour_local, pm25, source
from {{ ref('int_pm25_hourly') }}
