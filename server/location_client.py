"""Amazon Location Service v2 client — ap-south-1, API-key auth.

Covers the four v2 surfaces the /v2 API needs (docs/plan/04 §2-3):

  geo-places  POST /v2/suggest          (T2 search — HERE data)
              GET  /v2/place/{PlaceId}  (resolve a suggestion)
              POST /v2/reverse-geocode  (address for a point)
  geo-routes  POST /v2/routes           (Car/Scooter, traffic, alternatives)

Auth: API key from env ALIVE_LOCATION_KEY, passed as the documented
`?key=` query parameter — never logged, never hardcoded. Region from
ALIVE_LOCATION_REGION, default ap-south-1.

Degradation contract: with no key the client reports enabled=False and
every method raises LocationDisabled immediately (no request attempted);
callers in server/v2 catch this and degrade honestly (T2 skipped, 503 on
Amazon-backed endpoints, OSRM routing). With a key, network/API failures
return None — the caller decides whether an empty result is acceptable.
"""
import os
from typing import Optional

import httpx

PLACES_URL = "https://geo-places.{region}.amazonaws.com"
ROUTES_URL = "https://geo-routes.{region}.amazonaws.com"
DEFAULT_REGION = "ap-south-1"

_TIMEOUT = httpx.Timeout(8.0, connect=4.0)


class LocationDisabled(RuntimeError):
    """Raised by every method when no ALIVE_LOCATION_KEY is configured."""


class LocationClient:
    """Thin async wrapper over the geo-places / geo-routes v2 REST APIs."""

    def __init__(self, api_key: Optional[str] = None,
                 region: Optional[str] = None,
                 http: Optional[httpx.AsyncClient] = None):
        # None = read env (normal path); "" forces disabled (tests).
        self._key = os.environ.get("ALIVE_LOCATION_KEY", "") \
            if api_key is None else api_key
        self._region = region or os.environ.get("ALIVE_LOCATION_REGION",
                                                DEFAULT_REGION)
        self._http = http
        self._owns_http = http is None

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=_TIMEOUT,
                headers={"User-Agent": "alive108-v2/0.1",
                         "Content-Type": "application/json"})
        return self._http

    def _need_key(self) -> str:
        if not self._key:
            raise LocationDisabled(
                "ALIVE_LOCATION_KEY not configured — Amazon Location "
                "features disabled")
        return self._key

    async def close(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    # --- geo-places --------------------------------------------------------
    async def suggest(self, q: str, lat: float, lon: float,
                      limit: int = 8) -> Optional[list]:
        """geo-places Suggest, biased to the user, India-only.

        Returns normalized rows: {id, name, subtitle, lat, lon, place_id,
        kind, distance_m, source:"amazon"} — None on any upstream failure.
        """
        key = self._need_key()
        body = {
            "QueryText": q,
            "MaxResults": max(1, min(int(limit), 25)),
            "BiasPosition": [float(lon), float(lat)],
            "Filter": {"IncludeCountries": ["IND"]},
            "Language": "en",
            "PoliticalView": "IND",
            "AdditionalFeatures": ["Core"],
        }
        try:
            r = await self._client().post(
                f"{PLACES_URL.format(region=self._region)}/v2/suggest",
                params={"key": key}, json=body)
            r.raise_for_status()
            items = r.json().get("ResultItems") or []
        except (httpx.HTTPError, ValueError):
            return None
        out = []
        for it in items:
            if it.get("SuggestResultItemType") != "Place":
                continue
            place = it.get("Place") or {}
            pos = place.get("Position") or []
            if len(pos) < 2:
                continue
            addr = place.get("Address") or {}
            label = addr.get("Label") or ""
            title = it.get("Title") or label.split(",")[0].strip()
            # subtitle: full address minus the leading name, when present
            sub = label
            if title and label.startswith(title):
                sub = label[len(title):].lstrip(", ").strip()
            out.append({
                "id": f"amz:{place.get('PlaceId')}" if place.get("PlaceId")
                    else None,
                "place_id": place.get("PlaceId"),
                "name": title,
                "subtitle": sub,
                "lat": float(pos[1]), "lon": float(pos[0]),
                "kind": place.get("PlaceType") or "place",
                "distance_m": place.get("Distance") or it.get("Distance"),
                "source": "amazon",
            })
        return out

    async def get_place(self, place_id: str) -> Optional[dict]:
        """geo-places GetPlace → normalized {name, subtitle, lat, lon,...}."""
        key = self._need_key()
        if not place_id:
            return None
        try:
            r = await self._client().get(
                f"{PLACES_URL.format(region=self._region)}/v2/place/"
                f"{place_id}",
                params={"key": key, "Language": "en",
                        "PoliticalView": "IND",
                        "AdditionalFeatures": "Core"})
            r.raise_for_status()
            p = r.json()
        except (httpx.HTTPError, ValueError):
            return None
        pos = p.get("Position") or []
        addr = p.get("Address") or {}
        label = addr.get("Label") or ""
        return {
            "id": f"amz:{p.get('PlaceId') or place_id}",
            "place_id": p.get("PlaceId") or place_id,
            "name": (p.get("Name") or label.split(",")[0].strip()
                     or "Unnamed place"),
            "subtitle": label,
            "lat": float(pos[1]) if len(pos) >= 2 else None,
            "lon": float(pos[0]) if len(pos) >= 2 else None,
            "kind": p.get("PlaceType") or "place",
            "address": {k: addr.get(k) for k in
                        ("Locality", "District", "SubDistrict", "Region",
                         "SubRegion", "PostalCode", "Street",
                         "AddressNumber") if addr.get(k)},
            "source": "amazon",
        }

    async def reverse_geocode(self, lat: float, lon: float,
                              limit: int = 10) -> Optional[list]:
        """geo-places ReverseGeocode → normalized candidates near a point."""
        key = self._need_key()
        body = {
            "QueryPosition": [float(lon), float(lat)],
            "MaxResults": max(1, min(int(limit), 25)),
            "Language": "en",
            "PoliticalView": "IND",
            "AdditionalFeatures": ["Core"],
        }
        try:
            r = await self._client().post(
                f"{PLACES_URL.format(region=self._region)}"
                "/v2/reverse-geocode",
                params={"key": key}, json=body)
            r.raise_for_status()
            items = r.json().get("ResultItems") or []
        except (httpx.HTTPError, ValueError):
            return None
        out = []
        for it in items:
            pos = it.get("Position") or []
            addr = it.get("Address") or {}
            out.append({
                "place_id": it.get("PlaceId"),
                "title": it.get("Title") or "",
                "label": addr.get("Label") or "",
                "street": addr.get("Street"),
                "locality": addr.get("Locality")
                            or addr.get("SubDistrict") or addr.get("District"),
                "region": addr.get("Region"),
                "lat": float(pos[1]) if len(pos) >= 2 else None,
                "lon": float(pos[0]) if len(pos) >= 2 else None,
                "distance_m": it.get("Distance"),
                "kind": it.get("PlaceType") or "place",
                "source": "amazon",
            })
        return out

    # --- geo-routes ---------------------------------------------------------
    async def calculate_routes(self, from_lat: float, from_lon: float,
                               to_lat: float, to_lon: float,
                               travel_mode: str = "Car",
                               alternatives: int = 2,
                               depart_at: Optional[str] = None
                               ) -> Optional[list]:
        """geo-routes CalculateRoutes → [{distance_m, duration_s,
        freeflow_s|None, geometry(LineString), notices}].

        Traffic: `DepartNow`/`DepartureTime` + Traffic.Usage=UseTraffic so
        duration_s reflects current conditions; TypicalDuration spans are
        summed into freeflow_s when the API returns them (else None — no
        invented free-flow number).
        """
        key = self._need_key()
        if travel_mode not in ("Car", "Pedestrian", "Scooter", "Truck",
                               "Intermodal", "Transit"):
            travel_mode = "Car"
        body = {
            "Origin": [float(from_lon), float(from_lat)],
            "Destination": [float(to_lon), float(to_lat)],
            "TravelMode": travel_mode,
            "MaxAlternatives": max(0, min(int(alternatives), 5)),
            "OptimizeRoutingFor": "FastestRoute",
            "LegGeometryFormat": "Simple",
            "InstructionsMeasurementSystem": "Metric",
            "Traffic": {"Usage": "UseTraffic"},
            "LegAdditionalFeatures": ["Summary", "TypicalDuration"],
        }
        if depart_at:
            body["DepartureTime"] = depart_at
        else:
            body["DepartNow"] = True
        try:
            r = await self._client().post(
                f"{ROUTES_URL.format(region=self._region)}/v2/routes",
                params={"key": key}, json=body)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            return None

        out = []
        for rt in data.get("Routes") or []:
            summ = rt.get("Summary") or {}
            coords: list = []
            typical_s = 0.0
            saw_typical = False
            for leg in rt.get("Legs") or []:
                geom = leg.get("Geometry") or {}
                for c in geom.get("LineString") or []:
                    if isinstance(c, (list, tuple)) and len(c) >= 2:
                        c = [float(c[0]), float(c[1])]
                        if not coords or c != coords[-1]:
                            coords.append(c)
                # typical (free-flow-ish) durations ride on spans when
                # requested via LegAdditionalFeatures
                for span in leg.get("Spans") or []:
                    td = (span or {}).get("TypicalDuration")
                    if isinstance(td, (int, float)) and td > 0:
                        typical_s += float(td)
                        saw_typical = True
            if len(coords) < 2:
                continue
            notices = [n.get("Code") for n in rt.get("Notices") or []
                       if isinstance(n, dict) and n.get("Code")]
            out.append({
                "distance_m": float(summ.get("Distance") or 0.0),
                "duration_s": float(summ.get("Duration") or 0.0),
                "freeflow_s": typical_s if saw_typical else None,
                "geometry": {"type": "LineString", "coordinates": coords},
                "notices": notices,
                "source": "amazon-location-routes",
            })
        return out
