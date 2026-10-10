"""Streamlit app. Run with ``make app``."""

import streamlit as st

from aburra_air.utils.config import get_config

config = get_config()

st.set_page_config(page_title=config.project.name)
st.title(config.project.name)
st.write("TODO: build the app.")
