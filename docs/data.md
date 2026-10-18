# Data

Research done on 2026-10-10. Re-check the endpoints before relying on them: none of the
SIATA endpoints below is a documented, versioned API.

## SIATA air quality (primary source)

[SIATA](https://siata.gov.co/) (Sistema de Alerta Temprana de Medellín y el Valle de
Aburrá) runs the official air quality network of the Aburrá Valley for the Área
Metropolitana del Valle de Aburrá.

### Live feed: geoportal API (PM2.5 only)

The [SIATA geoportal](https://geoportal.siata.gov.co/) frontend calls an undocumented
FastAPI backend. These endpoints answered without authentication on 2026-10-10:

| Endpoint | Returns |
|----------|---------|
| `GET https://geoportal.siata.gov.co/fastgeoapi/geodata/geodataJson/1/pm25_minio` | GeoJSON, one feature per official PM2.5 station (23 on 2026-10-10): `codigo`, `estacion`, `nombreEstacion`, `Municipio`, coordinates, `PM25_24H_prom`, `ICA_24H_prom`, `fechaInicio`, `fechaFin`. |
| `GET https://geoportal.siata.gov.co/fastgeoapi/geodata/geographJson/1/pm25/{codigo}` | Last 72 hourly PM2.5 values (µg/m³) for one station: `Hora_fin`, `Horas`, `PM25_72H` (`null` = missing). |
| `GET https://geoportal.siata.gov.co/fastgeoapi/geodata/geographJson/1/pm25_30d/{codigo}` | Last 30 daily values for one station (`Dias`, …). |
| `GET https://geoportal.siata.gov.co/fastgeoapi/geodata/geodataJson/1/pm25No_Poeca` | Stations that are not part of the official POECA network. |

Implications for the extractor (Phase 1):

- A daily run that reads the 72 h window overlaps the previous run by 48 h, so one missed
  day loses nothing. The load step must deduplicate on `(station_code, timestamp_hour)`.
- Times are local (America/Bogota, UTC-5, no DST). Only the end hour is given; the hour
  of each value is reconstructed from `Hora_fin` and the position in the array.
- PM10, O3 and NO2 are **not** exposed by the geoportal. The spec's "PM2.5, PM10, O3,
  etc." becomes "PM2.5 live, other pollutants historical only" unless SIATA grants access
  (see below).
- `codigo` matches `codigoSerial` in the historical files, so it is the station key.
- The 72 h series lags the 24 h mean: on 2026-10-10 at ~14:50 the series ended at 07:00
  while `fechaFin` was 14:00. Schedule the daily run with that lag in mind (Phase 4).
- The weekly `SIATA contract` workflow (`make contract`) checks these fields still exist.

### Historical feed: `EntregaData1` JSON files (frozen)

`https://siata.gov.co/EntregaData1/Datos_SIATA_Aire_{pollutant}.json` for `pm25`, `pm10`,
`no2`, `so2` and `co` (`o3` returns 404). Each file is a list of stations with
`codigoSerial`, `nombreCorto`, `nombre`, coordinates and `datos`
(`fecha`, `valor`, `calidad`, `variableConsulta`); `valor = -9999` is missing.

**These files stopped updating.** `Last-Modified` is 2024-08-31 and the data covers
2023-07-31 → 2024-07-31 hourly (one year, 21 PM2.5 stations, 16 with data). The
`*_AQ_*_Last.json` (OpenAQ format) files stopped on 2024-09-05. Use them only for a one-off
backfill (Phase 2), not for the daily job. OpenAQ ingested SIATA through these files, so
it probably stopped at the same date (not checked: the OpenAQ v3 API needs a key).

### Full history and other pollutants

SIATA grants access to its download portal on request by email, stating the purpose; the
portal then asks for a user account and a form per download. That is the only route
found for PM10/O3/NO2 after 2024 and for history before 2023-07.

**Not pursued** (2026-10-18, #4): access will not be granted for this project, so the
scope is fixed to live PM2.5 from the geoportal plus the frozen 2023-07 → 2024-07
`EntregaData1` history. No PM10/O3/NO2 after 2024 and no history before 2023-07.

### Terms of use

No license or terms of use were found on siata.gov.co or the geoportal, and neither host
has a `robots.txt`. The data is public government data and SIATA presents the geoportal
as free for everyone, but redistribution terms are **unconfirmed**, and will stay so:
SIATA will not be asked (#4). These rules are therefore permanent:

- call each endpoint once per station per day, with an identifying `User-Agent`;
- credit SIATA as the source in the README, the release notes and the dashboard;
- commit code and small samples only;
- the pipeline itself is unchanged: raw JSON lands in `01_raw`, is loaded into DuckDB and
  cleaned in dbt staging/intermediate as planned. The restriction is only on what leaves
  the pipeline publicly;
- publish **aggregates only** (Phase 4): daily or coarser marts per station
  (daily means, exceedances, ICA categories) and pattern summaries (e.g. mean by hour of
  day). Never publish the raw JSON, the DuckDB file or any hourly series.

## Open-Meteo (optional weather covariates)

Hourly weather for the valley from the [Open-Meteo](https://open-meteo.com/) forecast and
historical APIs: no key, free for non-commercial use, data under CC BY 4.0 (from
Open-Meteo's published terms; not re-checked for this project).

## Colombian air quality standard: Resolución 2254 de 2017

Source: official PDF from MinAmbiente,
<https://www.minambiente.gov.co/wp-content/uploads/2021/10/Resolucion-2254-de-2017.pdf>
(issued 2017-11-01, in force since 2018-01-01). No later resolution replacing it was
found on 2026-10-10. All values in µg/m³ at reference conditions.

### Maximum permissible levels (Art. 2, Table 1 and Paragraph 1)

| Pollutant | Annual | 24 h | 8 h | 1 h |
|-----------|-------:|-----:|----:|----:|
| PM10 | 50 | **75** | | |
| PM2.5 | 25 | **37** | | |
| SO2 | | 50 | | 100 |
| NO2 | 60 | | | 200 |
| O3 | | | 100 | |
| CO | | | 5,000 | 35,000 |

Table 1 says 100 (PM10) and 50 (PM2.5) for 24 h, but Paragraph 1 lowers them to 75 and
37 from 2018-07-01, so 75 and 37 are the current 24 h limits. Exceedance checks are per
station; averaging several stations is not valid (Paragraph 2).

From **2030-01-01** (Art. 3, Table 2): PM10 annual 30, PM2.5 annual 15, SO2 24 h 20, NO2
annual 40.

### ICA breakpoints (Art. 20, Table 6)

| ICA | Category | Color | PM10 24 h | PM2.5 24 h | O3 8 h | O3 1 h | NO2 1 h | SO2 1 h | CO 8 h |
|-----|----------|-------|-----------|------------|--------|--------|---------|---------|--------|
| 0–50 | Buena | Verde | 0–54 | 0–12 | 0–106 | — | 0–100 | 0–93 | 0–5094 |
| 51–100 | Aceptable | Amarillo | 55–154 | 13–37 | 107–138 | — | 101–189 | 94–197 | 5095–10819 |
| 101–150 | Dañina a la salud de grupos sensibles | Naranja | 155–254 | 38–55 | 139–167 | 245–323 | 190–677 | 198–486 | 10820–14254 |
| 151–200 | Dañina a la salud | Rojo | 255–354 | 56–150 | 168–207 | 324–401 | 678–1221 | 487–797 | 14255–17688 |
| 201–300 | Muy dañina a la salud | Púrpura | 355–424 | 151–250 | 208–393 | 402–794 | 1222–2349 | 798–1583 | 17689–34862 |
| 301–500 | Peligrosa | Marrón | 425–604 | 251–500 | 394 ⁽²⁾ | 795–1185 | 2350–3853 | 1584–2629 | 34863–57703 |

(2) The 8 h O3 ICA is not computed above 394 µg/m³; use the 1 h O3 ICA instead.

Formula (Art. 21), per pollutant *p*:

`ICA_p = (I_high − I_low) / (BP_high − BP_low) × (C_p − BP_low) + I_low`

- Stations measuring several pollutants report the ICA of each one, highlighting the
  highest (Art. 21, Paragraph 1).
- Automatic monitors report a daily ICA and a "moving ICA" on the running average of each
  pollutant's exposure time (Paragraphs 2–3).
- Breakpoints are integers with gaps (12 → 13). Phase 5 must pick a rule, e.g. truncate
  concentrations to integers before the lookup as the US EPA AQI does, and test it at the
  edges.

### Prevention, alert and emergency levels (Art. 10, Table 4)

| Pollutant | Exposure | Prevención | Alerta | Emergencia |
|-----------|----------|-----------|--------|-----------|
| PM10 | 24 h | 155–254 | 255–354 | ≥ 355 |
| PM2.5 | 24 h | 38–55 | 56–150 | ≥ 151 |
| O3 | 8 h | 139–167 | 168–207 | ≥ 208 |
| SO2 | 1 h | 198–486 | 487–797 | ≥ 798 |
| NO2 | 1 h | 190–677 | 678–1221 | ≥ 1222 |
| CO | 8 h | 10820–14254 | 14255–17688 | ≥ 17689 |

Declaration rule (Art. 11): with automatic monitors, use 24 h moving averages. If after
the first value in range, more than 75% of the moving averages over the next 48 hours
stay in that range, the level is declared. Art. 13 ends an episode the same way: more than
75% of the next 48 h below the lower limit (4 h for ozone). A declaration for a whole
municipality needs at least 50% of its stations (Art. 12). This is the rule to use for
"critical episodes" in Phase 5.
