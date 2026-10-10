# aburra-air-quality-elt

Daily ELT pipeline for air quality in the Aburrá Valley (Medellín, Colombia): Python
extractors land SIATA station data, DuckDB stores it, dbt models it into hourly and daily
marts with Colombian ICA categories (Resolución 2254 de 2017), and a Streamlit dashboard
serves it. See the [README](https://github.com/RafaGM1108/aburra-air-quality-elt#readme)
for the quickstart and [Data](data.md) for sources and thresholds.
