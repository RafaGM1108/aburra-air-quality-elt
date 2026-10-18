-- Hour-of-day profile by station, month and weekday/weekend: sums and counts, so any
-- window of months can be recombined into exact means. An aggregate, not a time series.
select
    station_code,
    date_trunc('month', date_local)::date as month,
    hour_local as hour_of_day,
    dayofweek(date_local) in (0, 6) as is_weekend,
    count(pm25) as valid_hours,
    sum(pm25) as pm25_sum,
    avg(pm25) as pm25_mean
from {{ ref('int_pm25_hourly') }}
group by all
