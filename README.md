# DF Aggregator

## Dependencies:
- [numpy](https://numpy.org/install/)
- [scikit-learn](https://scikit-learn.org/stable/install.html)
- [python-geojson](https://python-geojson.readthedocs.io/en/latest/)

## Usage: df-aggregator.py [options]

### Required inputs:
-  -g FILE, --geofile=FILE
  - GeoJSON Output File
  - Conventional file extension: .geojson

-  -r FILE, --receivers=FILE
  - List of receiver URLs
  - Do not include quotes. Each receiver should be on a new line.

-  -d FILE, --database=FILE
  - Name of new or existing database to store intersect information.
  - If a database doesn't exist one is created.
  - Post processing math is done against the entire database.

### Optional Inputs:
-  -e Number, --epsilon=Number
  - Max Clustering Distance, Default 0.2.
  - 0 to disable clustering.
  - Point spread across a larger geographoical area should require a smaller value.
  - Clustering should be disabled for moving targets.

-  -c Number, --confidence=Number
  - Minimum confidence value, default 10
  - Do not computer intersects for LOBs less than this value.

-  -p Number, --power=Number
  - Minimum power value, default 10
  - Do not computer intersects for LOBs less than this value.

-  -m Number, --min-samples=Number
  - Minimum samples per cluster. Default 20
  - A higher value can yeild more accurate results, but requires more data.

-  --dist-from-reference=Number
  - The default is 500 km.
  - When there are more than two receivers, the intersect with the strongest average signal
  is marked as a reference point.
  - Any intersections that exceed the specified distance from the reference are thrown out.