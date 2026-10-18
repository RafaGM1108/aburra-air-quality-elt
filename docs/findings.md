# Findings

Every number on this page comes from a file in
[`data/08_reporting/`](https://github.com/RafaGM1108/aburra-air-quality-elt/tree/main/data/08_reporting).
Those files are the outputs of the Daily ELT run uploaded on 2026-10-18T19:22:50Z, fetched
with `make fetch-reporting`. `provenance.json` lists each file's upload time and SHA-256.
To refresh them, run `make fetch-reporting` after a Daily ELT run.

**Window:** 2023-08-01 to 2024-07-31, the 12 full months of SIATA's frozen historical
file, and the only complete year available (`conf/base.yaml`, `analysis:`). Live data
collected since 2026-10 is not included yet. **Source:** SIATA, Área Metropolitana del
Valle de Aburrá. Rules and thresholds are in [Methodology](methodology.md).

## Worst stations (`station_ranking.csv`, `station_ranking.png`)

- **16 stations** have at least 75% valid days in the window and are ranked. Five codes
  are listed unranked: four have no valid day, and code 44 has 65.3% coverage.
- **Estación Tráfico Centro (CEN-TRAF, Medellín)** is clearly the worst station. It has
  87 days above the 37 µg/m³ 24 h limit (24.3% of its 358 valid days) and a mean of
  34.9 µg/m³.
- Next come the southern stations: Casa de Justicia, Itagüí (44 days, 12.1%), Hospital,
  La Estrella (42 days, 11.6%) and I.E. Concejo Municipal de Itagüí (33 days, 9.2%).
- The best-ranked station is Parque Biblioteca Fernando Botero, Medellín, with 2
  exceedance days (0.6%). The lowest mean among ranked stations is Torre Social,
  Barbosa, at 14.2 µg/m³.
- Every ranked station's annual mean of daily means is between 14.2 and 34.9 µg/m³.
  Res. 2254 sets the annual PM2.5 limit at 25 µg/m³, so these means are context only:
  they are not a formal annual-limit check.

## Seasonal pattern (`monthly_profile.csv`, `monthly_profile.png`)

- **March 2024 is the worst month.** All stations together have a mean of 32.4 µg/m³
  and 106 station-days above the limit. April 2024 follows (24.7 µg/m³, 62 days), then
  February 2024 (23.0 µg/m³, 31 days).
- From May to July 2024 the monthly means are the lowest of the window, 14.9 to
  16.3 µg/m³. The other months have between 11 and 16 exceedance station-days.
- Coverage is 71.4% to 80.2% of station-days. This counts stations with no valid data in
  the window, so it understates the coverage of the 16 ranked stations.

## Day of week (`weekday_profile.csv`, `weekday_profile.png`)

- **Sunday is the cleanest day:** 16.6 µg/m³. Thursday and Friday are the worst at
  22.0 µg/m³, and Saturday (19.0) is close to Monday (19.1). Coverage is 75.7% to 78.0%
  of station-days.

## Diurnal cycle (`diurnal_profile.csv`, `diurnal_profile.png`)

- On weekdays, PM2.5 peaks at **10:00** (31.3 µg/m³) and is lowest at **18:00**
  (14.9 µg/m³).
- On weekends, the peak is earlier and lower: **09:00** (24.9 µg/m³), with the minimum
  also at 18:00 (12.2 µg/m³).
- Coverage is 94.7% of possible station-hours on weekdays (101,186 of 106,896) and 94.8%
  on weekends (40,226 of 42,432). The reference is the 17 stations with any valid hour in
  the window (4,454 weekday and 1,768 weekend station-days).

## Critical episodes (`episodes.csv`)

Episodes follow the Art. 11/13 rule on 24 h moving averages, per station.

- The window has **41 episodes**: 32 at prevención and 9 at alerta, at 15 stations.
  There is no emergencia episode.
- CEN-TRAF accounts for 10 of them, including 7 of the 9 alertas. Its longest episode
  is a prevención one of 652 hours, from 2024-02-26 to 2024-03-25.
- **A valley-wide event:** 13 stations started a prevención episode on 2024-03-04 or
  2024-03-05. This matches the March peak in the seasonal profile.
- During CEN-TRAF's alerta episode of 2024-02-18 to 2024-02-21, its 24 h moving average
  peaked at 625.5 µg/m³, the highest peak in the file. The next highest is 278.2 µg/m³
  (also CEN-TRAF), and no other station's episode peaks above 108.1 µg/m³. Check this
  value against SIATA's own reports before quoting it.

## Limits

- One year, PM2.5 only. PM10, O3 and NO2 after 2024 are not available (see
  [Data](data.md)).
- The meaning of SIATA's `calidad` flag is undocumented. All values in 0–1000 µg/m³ are
  kept, whatever their flag.
- Pooled pattern means mix stations with different coverage. Exceedances and episodes
  are per station, as Res. 2254 requires.
- Episodes are per station. The municipal declaration (Art. 12) is not computed.
