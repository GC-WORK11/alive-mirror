"""Upstream base URLs — one place to change an external endpoint.

Modules import the constant from here instead of carrying their own
literal, so an upstream URL change (regional mirror, host retirement)
lands in exactly one file. Names are preserved per call site via
`from upstreams import X as Y` — existing module attrs keep working
(`airindex.OPENAQ_V3`, `airfield.OPEN_METEO`, ...).
"""

OPEN_METEO_MET = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AQ = "https://air-quality-api.open-meteo.com/v1/air-quality"
OSRM_PUBLIC = "https://router.project-osrm.org"
OPENAQ_V3 = "https://api.openaq.org/v3"
PHOTON_API = "https://photon.komoot.io/api/"
PHOTON_REVERSE = "https://photon.komoot.io/reverse"
