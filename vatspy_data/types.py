from enum import Enum, auto
from typing import Optional, List, Annotated
from pydantic import BaseModel
from pydantic.functional_validators import BeforeValidator
from shapely.geometry.base import BaseGeometry


class GeoItemProperties(BaseModel):
    id: str
    oceanic: Annotated[bool, BeforeValidator(lambda x: x == "1")]
    label_lon: Annotated[float, BeforeValidator(lambda x: float(x))]
    label_lat: Annotated[float, BeforeValidator(lambda x: float(x))]
    region: Optional[str]
    division: Optional[str]


class GeoItem(BaseModel):
    properties: GeoItemProperties
    geom: BaseGeometry

    model_config = {"arbitrary_types_allowed": True}


class Country(BaseModel):
    name: str
    codes: List[str]
    radar_name: str = "Center"


class Airport(BaseModel):
    icao: str
    name: str
    lat: Annotated[float, BeforeValidator(lambda x: float(x))]
    lng: Annotated[float, BeforeValidator(lambda x: float(x))]
    iata: Optional[str]
    fir_id: str
    pseudo: Annotated[bool, BeforeValidator(lambda x: x == "1")]


class FIR(BaseModel):
    icao: str
    name: str
    callsign_prefix: Optional[str] = None
    geom: GeoItem

    model_config = {"arbitrary_types_allowed": True}


class UIR(BaseModel):
    icao: str
    name: str
    fir_ids: List[str]


class ParserState(Enum):
    STARTED = auto()
    READ_COUNTRY = auto()
    READ_AIRPORT = auto()
    READ_FIR = auto()
    READ_UIR = auto()
    FINISHED = auto()
