-- Daily PM2.5 by station (calendar day, America/Bogota), with 24 h exceedance and ICA.
-- A day counts only with at least var('min_valid_hours') valid hours.
with daily as (
    select
        station_code,
        date_local,
        count(pm25) as valid_hours,
        avg(pm25) as pm25_mean_all_hours,
        max(pm25) as pm25_max
    from {{ ref('int_pm25_hourly') }}
    group by station_code, date_local
),

valid as (
    select
        *,
        valid_hours >= {{ var('min_valid_hours') }} as is_valid_day,
        case when valid_hours >= {{ var('min_valid_hours') }} then pm25_mean_all_hours end
            as pm25_mean
    from daily
)

select
    v.station_code,
    v.date_local,
    v.valid_hours,
    v.is_valid_day,
    v.pm25_mean,
    v.pm25_max,
    v.pm25_mean > {{ var('pm25_24h_limit') }} as exceeds_24h_limit,
    -- Breakpoints are integers with gaps (12 -> 13): truncate before the lookup (docs/data.md).
    round(
        (b.ica_high - b.ica_low) / (b.pm25_high - b.pm25_low) * (trunc(v.pm25_mean) - b.pm25_low)
        + b.ica_low
    )::integer as ica,
    b.category as ica_category,
    b.color as ica_color
from valid as v
left join {{ ref('ica_pm25_breakpoints') }} as b
    on trunc(v.pm25_mean) between b.pm25_low and b.pm25_high
