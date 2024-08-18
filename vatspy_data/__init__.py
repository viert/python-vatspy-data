import json
import requests
import time
from collections import defaultdict
from logging import getLogger
from shapely import centroid
from shapely.geometry import shape
from collections import deque
from typing import Dict, DefaultDict, Any, List, Optional
from .types import (
    Country,
    Airport,
    FIR,
    UIR,
    GeoItem,
    GeoItemProperties,
    Boundaries,
    BoundingBox,
    Point,
    ParserState
)

DEFAULT_DATA_PATH = "https://raw.githubusercontent.com/vatsimnetwork/vatspy-data-project/master/VATSpy.dat"
DEFAULT_GEOJSON_PATH = "https://raw.githubusercontent.com/vatsimnetwork/vatspy-data-project/master/Boundaries.geojson"


log = getLogger(__name__)


class VatspyData:
    _data_path: str
    _geojson_path: str

    _countries: List[Country]
    _airports: List[Airport]
    _firs: List[FIR]
    _uirs: List[UIR]

    _country_idx: Dict[str, int]
    _airport_icao_idx: DefaultDict[str, List[int]]
    _airport_iata_idx: DefaultDict[str, List[int]]
    _fir_icao_idx: DefaultDict[str, List[int]]
    _fir_prefix_idx: Dict[str, int]
    _uir_icao_idx: Dict[str, int]
    _uir_fir_idx: Dict[str, int]

    def __init__(self,
                 data_path: str = DEFAULT_DATA_PATH,
                 geojson_path: str = DEFAULT_GEOJSON_PATH):
        self._reset()
        self._data_path = data_path
        self._geojson_path = geojson_path
        self._load()
        self._build_indexes()

    def _load(self):
        geo = self._load_geo()
        raw_data = self._load_data()

        geo_map = {}
        for item in geo["features"]:
            item_id = item["properties"]["id"]
            geom = shape(item["geometry"])
            center = centroid(geom)
            geo_map[item_id] = GeoItem(
                properties=GeoItemProperties(**item["properties"]),
                boundaries=Boundaries(
                    geometry=item["geometry"],
                    bbox=BoundingBox(
                        min=Point(lng=geom.bounds[0], lat=geom.bounds[1]),
                        max=Point(lng=geom.bounds[2], lat=geom.bounds[3]),
                    ),
                    center=Point(lng=center.x, lat=center.y)
                )
            )
        self._parse(raw_data, geo_map)

    def _build_indexes(self):
        log.debug("building vatspy data indexes")
        t1 = time.time()

        self._country_idx = {}
        for i, c in enumerate(self._countries):
            for code in c.codes:
                self._country_idx[code] = i

        self._airport_icao_idx = defaultdict(list)
        self._airport_iata_idx = defaultdict(list)

        for i, a in enumerate(self._airports):
            self._airport_icao_idx[a.icao].append(i)
            if a.iata is not None:
                self._airport_iata_idx[a.iata].append(i)

        self._fir_icao_idx = defaultdict(list)
        self._fir_prefix_idx = {}

        for i, f in enumerate(self._firs):
            self._fir_icao_idx[f.icao].append(i)
            self._fir_prefix_idx[f.callsign_prefix] = i

        self._uir_icao_idx = {}
        self._uir_fir_idx = {}

        for i, u in enumerate(self._uirs):
            self._uir_icao_idx[u.icao] = i
            for fir_id in u.fir_ids:
                self._uir_fir_idx[fir_id] = i

        t2 = time.time()
        log.debug("vatspy data indexes built in %.3fs", t2 - t1)

    def _parse(self, raw_data: str, geo_map: Dict[str, GeoItem]):
        state = ParserState.STARTED
        lines = deque(raw_data.split("\n"))

        def category_to_state(category: str) -> Optional[ParserState]:
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
                    log.error("unknown category %s", category)
                    return None

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
                        log.error("invalid country line '%s'", line)
                        continue
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
                        log.error("invalid FIR line '%s'", line)
                        continue

                    icao, name, callsign_prefix, geom_id = tokens
                    geom = geo_map.get(geom_id)
                    if geom is None:
                        log.error("no geometry for '%s'", line)
                        continue

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
                        log.error("invalid UIR line '%s'", line)
                        continue

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
                        log.error("invalid airport line '%s'", line)
                        continue
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
        self._countries = list(country_map.values())
        self._airports = list(airports.values())
        self._firs = list(firs.values())
        self._uirs = list(uirs.values())

    def _reset(self):
        self._countries = []
        self._airports = []
        self._firs = []
        self._uirs = []
        self._country_idx = {}
        self._airport_icao_idx = defaultdict(list)
        self._airport_iata_idx = defaultdict(list)
        self._fir_icao_idx = defaultdict(list)
        self._fir_prefix_idx = {}
        self._uir_icao_idx = {}
        self._uir_fir_idx = {}

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

    def find_country_by_icao(self, icao: str) -> Optional[Country]:
        idx = self._country_idx.get(icao[:2])
        if idx is not None:
            return self._countries[idx]
        return None

    def find_country_by_code(self, code: str) -> Optional[Country]:
        idx = self._country_idx.get(code)
        if idx is not None:
            return self._countries[idx]
        return None

    def find_fir_by_callsign(self, callsign: str) -> Optional[FIR]:
        code = callsign.split("_")[0]
        idxs = self._fir_icao_idx.get(code)
        if idxs:
            return self._firs[idxs[0]]

        for i in range(len(callsign), 4, -1):
            code = callsign[:i]
            idx = self._fir_prefix_idx.get(code)
            if idx is not None:
                return self._firs[idx]

    def find_airport_by_callsign(self, callsign: str) -> Optional[Airport]:
        code = callsign.split("_")[0]
        return self.find_airport_by_code(code)

    def find_airport_by_code(self, code: str) -> Optional[Airport]:
        if len(code) < 4:
            idxs = self._airport_iata_idx.get(code)
            if not idxs:
                return None
            return self._airports[idxs[0]]
        idxs = self._airport_icao_idx.get(code, self._airport_iata_idx.get(code))
        if not idxs:
            return None
        return self._airports[idxs[0]]

    def find_fir_by_code(self, code: str) -> Optional[FIR]:
        idxs = self._fir_icao_idx.get(code)
        if idxs:
            return self._firs[idxs[0]]

    def find_uir_by_code(self, code: str) -> Optional[FIR]:
        idx = self._uir_icao_idx.get(code)
        if idx is not None:
            return self._firs[idx]
