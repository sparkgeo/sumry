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

sumry requires Python 3.11 or newer. The development environment uses Python 3.12.
Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first; uv can
install Python automatically if the requested version is missing. Git is required
for installation from the repository.

### Install as a terminal tool

Run these commands from any directory:

```bash
uv tool install --python 3.12 git+https://github.com/gridcell/sumry.git
uv tool update-shell
```

Restart your terminal after `uv tool update-shell` so the tools directory is on
your `PATH`. You can then use `sumry` from any directory, without activating a
virtual environment or keeping a local checkout:

```bash
sumry --help
sumry --formats
sumry /path/to/data.csv
```

uv installs sumry and its dependencies in an isolated environment for your user;
no `sudo` is needed.

### Install from a local checkout

If you already cloned the repository, run this from its root directory:

```bash
uv tool install --python 3.12 .
uv tool update-shell
```

Restart your terminal if the shell configuration changed. This installs a snapshot
of the checkout. After changing the source, run `uv tool install --force .` again
to replace that installation. For an installation that follows source edits, see
[Development](#development).

### Update or uninstall

For an installation from GitHub:

```bash
uv tool upgrade sumry
```

To remove the installed tool:

```bash
uv tool uninstall sumry
```

If your shell reports `sumry: command not found`, run `uv tool update-shell` and
restart the terminal. `uv tool list` shows installed tools, and `uv tool dir --bin`
shows the directory that needs to be on your `PATH`.

## Usage

The examples below assume you installed the terminal tool. Pass a local file path;
quote paths containing spaces, for example `sumry "My Data/sales.csv"`.

### Basic usage

```bash
# Summarize a CSV file
sumry data.csv

# Override the CSV/TSV text encoding when needed
sumry data.csv --encoding latin-1

# Summarize a GeoJSON file
sumry locations.geojson

# Summarize an Excel file
sumry spreadsheet.xlsx

# Summarize a Parquet file (also supports --verbose, --count, and --json)
sumry data.parquet

# Summarize the first GeoPackage layer and list available layers
sumry data.gpkg

# Select GeoPackage layers by name or zero-based index
sumry data.gpkg --select "roads,buildings" -v -n 5
sumry data.gpkg --select 0 --json

# Summarize a Shapefile
sumry boundaries.shp
```

### Command-line Options

```bash
# List supported file formats
sumry --formats
sumry -f

# Verbose mode - show additional statistics and sample values
sumry data.csv --verbose
sumry data.csv -v

# Display 10 sample records
sumry data.csv --count 10
sumry data.csv -n 10

# Select specific Excel sheets
sumry spreadsheet.xlsx --select "Sheet1,Sheet3"
sumry spreadsheet.xlsx -s "Sheet1"

# Output as JSON
sumry data.csv --json
sumry data.csv -j

# Combine options
sumry data.csv -v -n 5 --json
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
sumry data.csv --json > summary.json

# Pipe to jq for processing
sumry data.csv --json | jq '.columns[] | .name'

# Get just the basic info
sumry data.csv --json | jq '.basic_info'
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
sumry elevation.tif
sumry imagery.cog.tif -v -n 5 --json
sumry imagery.jp2 -v
sumry scan.tiff                 # companion worldfile is read automatically
sumry survey.las -v -n 5
sumry survey.copc.laz --json
sumry basemap.pmtiles -v -n 5
sumry buildings.fgb -v -n 5
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

Install uv and Git, then clone the repository and set up the project environment:

```bash
git clone https://github.com/gridcell/sumry.git
cd sumry
uv sync
```

`uv sync` installs the project in editable mode into `.venv`, using `uv.lock`
and updating it if the project metadata has changed. The `.python-version` file selects Python 3.12. Source edits are
picked up on the next run; no reinstall or environment activation is needed.

### Run locally

From the repository root:

```bash
uv run sumry --help
uv run sumry test_data/sample.csv
uv run sumry test_data/sample.csv -v -n 5 --json
uv run sumry test_data/sample.geojson
```

Use `uv run sumry` when working on the checkout so you run that checkout's code
and dependencies. To also expose the editable checkout as `sumry` in any directory:

```bash
uv tool install --force --editable .
uv tool update-shell
```

Restart your terminal if needed, and keep the checkout in place while using this
editable installation. The tool has its own environment; rerun the installation
command if you change dependencies.

### Run tests

The test suite uses Python's built-in `unittest` runner:

```bash
uv run python -m unittest discover -s tests -v
```

### Build a distribution

```bash
uv build
```

This writes a wheel (`.whl`) and source archive (`.tar.gz`) to `dist/`. To install a
built wheel as a terminal tool, substitute its actual filename below:

```bash
uv tool install --force /path/to/sumry-version-py3-none-any.whl
```

### Publish a release to PyPI

The [publish workflow](.github/workflows/publish.yml) builds and publishes a wheel
and source distribution when a tag matching `vX.X.X` is pushed to GitHub. The tag
must match `project.version` in `pyproject.toml`; mismatches fail before publishing.
Prerelease tags such as `v1.2.3rc1` do not trigger publishing.

One-time setup:

1. Create a GitHub environment named `pypi` in `sparkgeo/sumry` under
   **Settings → Environments**. Leave required reviewers disabled for automatic
   publishing on tag pushes.
2. In the PyPI `sumry` project's **Publishing** settings, add a
   [Trusted Publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
   with owner `sparkgeo`, repository `sumry`, workflow filename `publish.yml`,
   and environment `pypi`. If the project does not exist yet, register a pending
   publisher at <https://pypi.org/manage/account/publishing/> with project name
   `sumry` and the same settings. No PyPI API token or GitHub secret is needed.

For each release, update `project.version` in `pyproject.toml`, run `uv lock`,
and commit the version and lockfile changes along with the release contents.
Push the commit, then create and push the matching tag (replace `0.5.3` with
the version being released):

```bash
git tag v0.5.3
git push origin v0.5.3
```

The tagged commit must contain the workflow. Follow the run in GitHub's
**Actions** tab. Each release needs a new version; PyPI does not allow replacing
previously published distribution files.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Sparkgeo

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
