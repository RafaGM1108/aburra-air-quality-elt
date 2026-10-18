-- Monthly summary by station: valid days, mean of daily means and exceedance days.
select
    station_code,
    date_trunc('month', date_local)::date as month,
    count(*) filter (where is_valid_day) as valid_days,
    avg(pm25_mean) as pm25_mean,
    count(*) filter (where exceeds_24h_limit) as exceedance_days
from {{ ref('fct_pm25_daily') }}
group by station_code, month
