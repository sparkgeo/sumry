# sumry

A fast and user-friendly CLI tool for summarizing various data file formats with rich terminal output.

## Features

- **Multiple Format Support**: CSV, Excel, GeoJSON, and Shapefiles
- **Rich Terminal Output**: Beautiful, colorful summaries using Rich library
- **Quick Insights**: Get file statistics, column types, and sample data
- **Geospatial Support**: Special handling for GeoJSON and Shapefile formats with geometry information

## Installation

```bash
pip install sumry
```

## Usage

### Basic Summary

```bash
sumry path/to/your/file.csv
```

### Show Sample Records

```bash
# Show 5 sample records (default)
sumry path/to/your/file.xlsx --show-sample

# Show specific number of samples
sumry path/to/your/file.geojson --sample 10
```

### Verbose Output

```bash
sumry path/to/your/file.shp --verbose
```

## Supported File Types

- **CSV** (`.csv`)
- **Excel** (`.xlsx`, `.xls`)
- **GeoJSON** (`.geojson`, `.json`)
- **Shapefile** (`.shp`)

## Requirements

- Python >= 3.12
- Dependencies are automatically installed with the package

## Development

```bash
# Clone the repository
git clone https://github.com/yourusername/sumry.git
cd sumry

# Install with development dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
