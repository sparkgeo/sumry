"""
sumry - A data summarization tool for analyzing and processing various file formats.
"""

__version__ = "0.1.0"

from sumry.readers import (
    read_csv,
    read_excel,
    read_geojson,
    read_shapefile,
    detect_file_type,
)

__all__ = [
    "read_csv",
    "read_excel",
    "read_geojson",
    "read_shapefile",
    "detect_file_type",
    "__version__",
]
