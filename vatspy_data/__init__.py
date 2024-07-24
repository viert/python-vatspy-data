import json
import requests
from shapely.geometry import shape
from collections import deque
from typing import Dict, Any
from .types import Country, Airport, FIR, UIR, GeoItem, ParserState

DEFAULT_DATA_PATH = "https://raw.githubusercontent.com/vatsimnetwork/vatspy-data-project/master/VATSpy.dat"
DEFAULT_GEOJSON_PATH = "https://raw.githubusercontent.com/vatsimnetwork/vatspy-data-project/master/Boundaries.geojson"


class VatspyData:
    _data_path: str
    _geojson_path: str

    countries: Dict[str, Country]
    airports: Dict[str, Airport]
    firs: Dict[str, FIR]
    uirs: Dict[str, UIR]

    def __init__(self,
                 data_path: str = DEFAULT_DATA_PATH,
                 geojson_path: str = DEFAULT_GEOJSON_PATH):
        self._reset()
        self._data_path = data_path
        self._geojson_path = geojson_path
        self._load()

    def _load(self):
        geo = self._load_geo()
        raw_data = self._load_data()

        geo_map = {}
        for item in geo["features"]:
            item_id = item["properties"]["id"]
            geo_map[item_id] = GeoItem(
                properties=item["properties"],
                geom=shape(item["geometry"])
            )
        self._parse(raw_data, geo_map)

    def _parse(self, raw_data: str, geo_map: Dict[str, GeoItem]):
        state = ParserState.STARTED
        lines = deque(raw_data.split("\n"))

        def category_to_state(category: str):
            match category.lower():
                case "countries":
                    return ParserState.READ_COUNTRY
                case "airports":
                    return ParserState.READ_AIRPORT
                case "firs":
                    return ParserState.READ_FIR
                case "uirs":
                    return ParserState.READ_UIR
                case "idl":
                    return ParserState.FINISHED
                case _:
                    raise ValueError(f"unknown category {category}")

        country_map = {}
        airports = {}
        firs = {}
        uirs = {}

        while lines and state != ParserState.FINISHED:
            line = lines.popleft().strip()
            if not line or line.startswith(";"):
                continue

            if line.startswith("["):
                category = line[1:-1].lower()
                state = category_to_state(category)
                continue

            match state:
                case ParserState.READ_COUNTRY:
                    tokens = line.split("|")
                    if len(tokens) != 3:
                        raise ValueError(f"invalid country line {line}")
                    name, code, custom_radar = tokens
                    custom_radar = custom_radar or None
                    if name not in country_map:
                        kwargs = dict(name=name, codes=[code])
                        if custom_radar:
                            kwargs["radar_name"] = custom_radar
                        country_map[name] = Country(**kwargs)
                    else:
                        country_map[name].codes.append(code)
                case ParserState.READ_FIR:
                    tokens = line.split("|")
                    if len(tokens) != 4:
                        raise ValueError(f"invalid FIR line {line}")

                    icao, name, callsign_prefix, geom_id = tokens
                    geom = geo_map.get(geom_id)
                    if geom is None:
                        raise ValueError(f"no geometry for {line}")

                    fir = FIR(
                        icao=icao,
                        name=name,
                        callsign_prefix=callsign_prefix,
                        geom=geom,
                    )
                    firs[icao] = fir
                case ParserState.READ_UIR:
                    tokens = line.split("|")
                    if len(tokens) != 3:
                        raise ValueError(f"invalid UIR line {line}")

                    icao, name, firs_list = tokens
                    fir_ids = firs_list.split(",")

                    uir = UIR(
                        icao=icao,
                        name=name,
                        fir_ids=fir_ids
                    )
                    uirs[icao] = uir

                case ParserState.READ_AIRPORT:
                    tokens = line.split("|")
                    if len(tokens) != 7:
                        raise ValueError(f"invalid airport line {line}")
                    icao, name, lat, lng, iata, fir_id, is_pseudo = tokens
                    iata = iata or None
                    airport = Airport(
                        icao=icao,
                        name=name,
                        lat=lat,
                        lng=lng,
                        iata=iata,
                        fir_id=fir_id,
                        pseudo=is_pseudo
                    )
                    airports[icao] = airport

        self._reset()
        for country in country_map.values():
            for code in country.codes:
                self.countries[code] = country
        self.airports = airports
        self.firs = firs
        self.uirs = uirs

    def _reset(self):
        self.countries = {}
        self.airports = {}
        self.firs = {}
        self.uirs = {}

    def _load_geo(self) -> Dict[str, Any]:
        use_http = self._geojson_path.startswith("http://") or self._geojson_path.startswith("https://")
        if use_http:
            resp = requests.get(self._geojson_path)
            return resp.json()
        else:
            with open(self._geojson_path) as f:
                return json.load(f)

    def _load_data(self):
        use_http = self._data_path.startswith("http://") or self._data_path.startswith("https://")
        if use_http:
            resp = requests.get(self._data_path)
            return resp.text
        else:
            with open(self._data_path) as f:
                return f.read()
