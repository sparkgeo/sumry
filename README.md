# sumry

A CLI utility tool for summarizing various data sources.

## Features

- **Multi-format support**: CSV, Excel (.xlsx, .xls, .xlsm), Parquet, GeoJSON, GeoPackage, Shapefiles, FlatGeobuf, GeoTIFF/COG, JPEG2000, LAS/LAZ/COPC, and PMTiles
- **Beautiful output**: Rich-formatted tables and panels for clear, readable summaries
- **JSON output**: Export summaries as JSON for programmatic use with `--json` flag
- **Verbose mode**: Additional statistics and sample data with `-v` flag
- **Sample records**: Display sample data rows with `--count` option
- **Sheet/layer selection**: Choose specific Excel sheets or GeoPackage layers with `--select`
- **Fast and lightweight**: Built with performance in mind
- **Clean output**: No unnecessary warnings or library messages in standard mode

## Installation

This project uses UV as the package manager. To install dependencies:

```bash
# Clone the repository
git clone <repository-url>
cd sumry

# Install dependencies with UV
uv sync
```

## Usage

### Basic usage

```bash
# Summarize a CSV file
uv run sumry data.csv

# Override the CSV/TSV text encoding when needed
uv run sumry data.csv --encoding latin-1

# Summarize a GeoJSON file
uv run sumry locations.geojson

# Summarize an Excel file
uv run sumry spreadsheet.xlsx

# Summarize a Parquet file (also supports --verbose, --count, and --json)
uv run sumry data.parquet

# Summarize the first GeoPackage layer and list available layers
uv run sumry data.gpkg

# Select GeoPackage layers by name or zero-based index
uv run sumry data.gpkg --select "roads,buildings" -v -n 5
uv run sumry data.gpkg --select 0 --json

# Summarize a Shapefile
uv run sumry boundaries.shp
```

### Command-line Options

```bash
# List supported file formats
uv run sumry --formats
uv run sumry -f

# Verbose mode - show additional statistics and sample values
uv run sumry data.csv --verbose
uv run sumry data.csv -v

# Display sample records (default: 5 rows)
uv run sumry data.csv --count 10
uv run sumry data.csv -n 10

# Select specific Excel sheets
uv run sumry spreadsheet.xlsx --select "Sheet1,Sheet3"
uv run sumry spreadsheet.xlsx -s "Sheet1"

# Output as JSON
uv run sumry data.csv --json
uv run sumry data.csv -j

# Combine options
uv run sumry data.csv -v -n 5 --json
```

## Output Examples

CSV/TSV files are read as UTF-8 (with or without a BOM), with a Windows-1252
fallback when UTF-8 decoding fails. The summary reports the encoding used.
This fallback is a guess; use `--encoding` if the text looks incorrect or the
file uses another encoding. Explicit encodings are used strictly without fallback.
TSV files use a tab separator.

### Standard Output (CSV)
```
mn
 CSV File Summary 
po
  File            sample.csv  
  Rows            10          
  Columns         4           
  Memory Usage    1.44 KB     

Columns/Fields:
 Name    Type   
 name    object 
 age     int64  
 city    object 
 salary  int64
```

### Verbose Output (CSV)
Includes sample values and statistics for each column:
- Numeric columns: min, max, mean, unique count
- Text columns: unique count, most common value
- Sample values: first 3 non-null values

### JSON Output
Export summaries in JSON format for integration with other tools:

```bash
# Output JSON to file
uv run sumry data.csv --json > summary.json

# Pipe to jq for processing
uv run sumry data.csv --json | jq '.columns[] | .name'

# Get just the basic info
uv run sumry data.csv --json | jq '.basic_info'
```

JSON output includes:
- Basic file information (rows, columns, memory usage)
- Column names and types
- Statistics (when using verbose mode)
- Sample data (when using count option)

### GeoJSON/GeoPackage/Shapefile Output
Includes additional geometry information:
- Geometry types and counts
- Bounding box coordinates
- Total area (for polygons)
- Total length (for lines)
- Coordinate Reference System (CRS)

GeoPackage support covers vector layers and nonspatial attribute tables. By default,
the first layer is summarized. Use `--select` for one or more comma-separated layer
names or zero-based indices. Multiple selected layers appear under `layers` in JSON
output. Raster tiles are not summarized.

### Rasters, point clouds, and tile archives

```bash
uv run sumry elevation.tif
uv run sumry imagery.cog.tif -v -n 5 --json
uv run sumry imagery.jp2 -v
uv run sumry scan.tiff                 # companion worldfile is read automatically
uv run sumry survey.las -v -n 5
uv run sumry survey.copc.laz --json
uv run sumry basemap.pmtiles -v -n 5
uv run sumry buildings.fgb -v -n 5
```

- **GeoTIFF, COG, TIFF + worldfile, JPEG2000:** dimensions, bands, data types,
  CRS, bounds, resolution, transform, compression, NoData, scale/offset, and
  overviews. COG layout is identified from GDAL metadata rather than the filename;
  this is not a full COG conformance validation. GDAL reads companion worldfiles
  such as `.tfw`, `.tifw`, and `.wld`. Worldfiles do not define a CRS: a companion
  `.prj` is used when the raster has none, otherwise CRS remains unknown.
- **LAS, LAZ, COPC:** header point counts, LAS version, point format, CRS,
  bounds, scales/offsets, and dimensions. COPC is identified by its information
  VLR. Coordinates in samples and statistics use scaled x/y/z values.
- **PMTiles v3:** tile type/compression, zoom range, geographic bounds, tile
  counts, clustering, and vector layer names when supplied in metadata. `-v`
  includes archive metadata; `-n` lists tile addresses and stored byte sizes,
  without decoding feature or image payloads. Internal NONE/GZIP compression is
  supported; other internal compression methods produce an explicit error.
- **FlatGeobuf:** the same field, geometry, statistics, and sample summaries as
  the other vector formats.

Raster and point-cloud default summaries read metadata without loading pixel or
point arrays. Raster verbose statistics use at most 100,000 pixels per band,
with a nearest-neighbour grid for larger rasters. Invalid/masked values are
excluded, and statistics are labelled exact or approximate. Values are stored
band values (scale/offset are reported but not applied); complex statistics use
magnitude. Point-cloud verbose statistics use at most the first 100,000 points,
which are not necessarily spatially representative. `-n` returns evenly spaced
raster pixel indices with pixel-centre coordinates, or the first N point records.
PMTiles samples follow archive tile-ID order. Requests larger than the dataset
return the available samples.

JSON keeps `basic_info`, `statistics`, and `sample_data`, adding `spatial_info`,
`bands`, `sampling_info`, and `metadata` where applicable. Raster and point-cloud
invalid scalar values are represented as `null`. These readers accept local files;
remote URL streaming and COPC spatial queries are not exposed by the CLI.
JPEG2000 requires a supporting GDAL driver, included in standard Rasterio wheels.

## CLI Options Reference

| Option | Short | Description | Example |
|--------|-------|-------------|---------|
| `--formats` | `-f` | Show supported file formats and exit | `sumry --formats` |
| `--verbose` | `-v` | Show detailed statistics and sample values | `sumry data.csv -v` |
| `--count N` | `-n N` | Display N sample records in table format | `sumry data.csv -n 10` |
| `--select` | `-s` | Select Excel sheets or GeoPackage layers (comma-separated names or indices) | `sumry data.gpkg -s "roads,buildings"` |
| `--json` | `-j` | Output results in JSON format | `sumry data.csv -j` |
| `--encoding` | | Override CSV/TSV text encoding | `sumry data.csv --encoding latin-1` |
| `--help` | | Show help message and exit | `sumry --help` |

## Supported Formats

| Format | Extensions | Description |
|--------|------------|-------------|
| CSV | .csv, .tsv | Comma and tab-separated values |
| Excel | .xlsx, .xls, .xlsm | Microsoft Excel spreadsheets |
| Parquet | .parquet | Apache Parquet columnar data |
| GeoJSON | .geojson, .json | Geographic JSON format |
| GeoPackage | .gpkg | GeoPackage vector layers and attribute tables |
| Shapefile | .shp | ESRI Shapefile format |
| FlatGeobuf | .fgb | FlatGeobuf vector features |
| GeoTIFF / COG / TIFF | .tif, .tiff | Georeferenced rasters, including companion worldfiles |
| JPEG2000 | .jp2, .j2k, .jpx | JPEG2000 rasters |
| LAS / LAZ / COPC | .las, .laz, .copc | Point clouds, including .copc.laz |
| PMTiles | .pmtiles | Version 3 tile archives |

## Dependencies

- **typer**: CLI framework
- **rich**: Terminal formatting and styling
- **pandas**: Data processing for CSV, Excel, and Parquet files
- **pyarrow**: Parquet file support
- **geopandas**: Geospatial data processing
- **pyogrio**: GeoPackage layer discovery and reading
- **openpyxl**: Excel file support
- **shapely**: Geometric operations
- **pyproj**: Coordinate system transformations
- **rasterio**: Raster metadata and pixel access through GDAL
- **laspy[lazrs]**: LAS, LAZ, and COPC point clouds
- **pmtiles**: PMTiles archive metadata and directories
- **numpy**: Raster and point-cloud statistics

## Development

```bash
# Install in development mode
uv sync

# Run tests (if available)
uv run python -m unittest discover -s tests -v

# Build the package
uv build
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Sparkgeo

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
