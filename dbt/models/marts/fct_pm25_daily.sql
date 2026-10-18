-- Daily PM2.5 by station with the 24 h exceedance flag and the ICA (Res. 2254 de 2017).
select
    d.station_code,
    d.date_local,
    d.valid_hours,
    d.is_valid_day,
    d.pm25_mean,
    d.pm25_max,
    d.pm25_mean > {{ var('pm25_24h_limit') }} as exceeds_24h_limit,
    -- Breakpoints are integers with gaps (12 -> 13): truncate before the lookup (docs/data.md).
    round(
        (b.ica_high - b.ica_low) / (b.pm25_high - b.pm25_low) * (trunc(d.pm25_mean) - b.pm25_low)
        + b.ica_low
    )::integer as ica,
    b.category as ica_category,
    b.color as ica_color
from {{ ref('int_pm25_daily') }} as d
left join {{ ref('ica_pm25_breakpoints') }} as b
    on trunc(d.pm25_mean) between b.pm25_low and b.pm25_high
