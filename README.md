## python-vatspy-data

This module loads and parses data from https://github.com/vatsimnetwork/vatspy-data-project

The results are available as an easy-to-use `VatspyData` object containing
the countries, the airports, and the FIRs along with geodata available as a
`shapely` Geometry.


### Installation

```commandline
pip install vatspy-data
```

### Usage

```python
from vatspy_data import VatspyData

vd = VatspyData() # the data is loaded and parsed in the constructor

print(vd.countries.get("LI"))
# Country(name='Italy', codes=['LI'], radar_name='Radar')

print(vd.firs.get("EGGX"))
# FIR(icao='EGGX', name='Shanwick Oceanic', callsign_prefix='EGGX', geom=GeoItem(properties=GeoItemProperties(id='EGGX', oceanic=False, label_lon=-22.5, label_lat=53.0, region='EMEA', division='VATUK'), geom=<MULTIPOLYGON (((-30 61, -10 61, -10 57, -15 57, -15 49, -8 48.494, -8 45, -...>))
```
