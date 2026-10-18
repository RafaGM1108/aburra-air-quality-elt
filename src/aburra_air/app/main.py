"""Streamlit dashboard on the published aggregates. Run with ``make app``."""

from datetime import date
from pathlib import Path

import httpx
import plotly.express as px
import streamlit as st

from aburra_air.data import marts
from aburra_air.utils.config import get_config

# ICA colors of Res. 2254 de 2017, Table 6.
ICA_COLORS = {
    "Buena": "#00e400",
    "Aceptable": "#ffff00",
    "Dañina a la salud de grupos sensibles": "#ff7e00",
    "Dañina a la salud": "#ff0000",
    "Muy dañina a la salud": "#8f3f97",
    "Peligrosa": "#7e0023",
    "Sin datos": "#9ca3af",
}
LIMIT_24H = 37
# The frozen historical year and the live data are two years apart: show one at a time.
PERIODS = {
    "Historical (2023-08 to 2024-07)": (date(2023, 8, 1), date(2024, 7, 31)),
    "Live (since 2026-10)": (date(2026, 10, 1), date(2100, 1, 1)),
    "All": marts.ALL_TIME,
}
LABELS = {"ica_category": "ICA", "day_type": "", "date_local": "", "pm25_mean": "µg/m³"}
REPO = "https://github.com/RafaGM1108/aburra-air-quality-elt"

config = get_config()
st.set_page_config(page_title="Aburrá Valley PM2.5", layout="wide")


@st.cache_resource(ttl=3600)
def marts_folder() -> str:
    """Local marts folder, filled from the data release when a mart is missing or > 1 day old."""
    with httpx.Client(follow_redirects=True, timeout=60) as client:
        return str(marts.ensure_marts(config.paths.model_input, client, max_age_hours=24))


folder = Path(marts_folder())

st.title("PM2.5 in the Aburrá Valley")
st.caption(
    "Daily and monthly aggregates of SIATA's official PM2.5 network, with the Colombian ICA "
    "(Resolución 2254 de 2017). Hourly series are not published."
)

latest = marts.latest_ica(folder)
st.subheader("Latest valid day by station")
if latest.empty:
    st.info("No station has a location yet.")
else:
    figure = px.scatter_map(
        latest,
        lat="latitude",
        lon="longitude",
        color="ica_category",
        color_discrete_map=ICA_COLORS,
        hover_name="station_name",
        labels=LABELS,
        hover_data={
            "date_local": True,
            "pm25_mean": True,
            "ica": True,
            "latitude": False,
            "longitude": False,
        },
        zoom=9.5,
        height=480,
    )
    figure.update_traces(marker={"size": 14})
    figure.update_layout(map_style="open-street-map", margin={"l": 0, "r": 0, "t": 0, "b": 0})
    st.plotly_chart(figure)

options = marts.station_options(folder)
if options.empty:
    st.warning("No daily data yet. Run the pipeline (`make elt`) or wait for the Daily ELT.")
    st.stop()

left, right = st.columns([2, 1])
label = left.selectbox("Station", options["label"].tolist())
code = int(options.loc[options["label"] == label, "station_code"].iloc[0])
period = PERIODS[right.radio("Period", list(PERIODS), horizontal=True)]

daily = marts.daily_series(folder, code, period)
st.subheader("Daily mean PM2.5")
if daily.empty:
    st.info("No valid day in this period (a day needs at least 18 valid hours).")
else:
    figure = px.scatter(
        daily,
        x="date_local",
        y="pm25_mean",
        color="ica_category",
        color_discrete_map=ICA_COLORS,
        labels=LABELS,
    )
    figure.add_hline(y=LIMIT_24H, line_dash="dash", annotation_text="24 h limit (37 µg/m³)")
    st.plotly_chart(figure)

left, right = st.columns(2)
with left:
    monthly = marts.monthly_exceedances(folder, code, period)
    st.subheader("Exceedance days by month")
    if monthly.empty:
        st.info("No monthly data in this period.")
    else:
        st.plotly_chart(
            px.bar(
                monthly,
                x="month",
                y="exceedance_days",
                hover_data=["valid_days", "pm25_mean"],
                labels={"month": "", "exceedance_days": "days > 37 µg/m³"},
            ),
        )
with right:
    profile = marts.hour_profile(folder, code)
    st.subheader("Mean by hour of day (all periods)")
    if profile.empty:
        st.info("No hourly profile for this station.")
    else:
        st.plotly_chart(
            px.line(
                profile,
                x="hour_of_day",
                y="pm25_mean",
                color="day_type",
                markers=True,
                labels={**LABELS, "hour_of_day": "hour (America/Bogota)"},
            ),
        )

st.caption(
    "Source: SIATA (Sistema de Alerta Temprana de Medellín y el Valle de Aburrá), Área "
    "Metropolitana del Valle de Aburrá. Data: "
    f"[data-latest release]({REPO}/releases/tag/data-latest). "
    f"Code: [aburra-air-quality-elt]({REPO})."
)
