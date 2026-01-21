from pathlib import Path
import pandas as pd
import geopandas as gpd
import pyarrow.parquet as pq
import rasterio
import json
import warnings
import os
from typing import Dict, Any, Optional, List


def detect_file_type(file_path: Path) -> Optional[str]:
    """Detect the type of file based on its extension."""
    suffix = file_path.suffix.lower()

    if suffix in ['.csv', '.tsv']:
        return "CSV"
    elif suffix in ['.xlsx', '.xls', '.xlsm']:
        return "Excel"
    elif suffix in ['.geojson', '.json']:
        if suffix == '.json':
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data.get('type') in ['Feature', 'FeatureCollection']:
                        return "GeoJSON"
            except:
                pass
        else:
            return "GeoJSON"
    elif suffix in ['.shp']:
        return "Shapefile"
    elif suffix in ['.parquet', '.pq']:
        # Check if it's a GeoParquet file by looking for geometry column metadata
        try:
            parquet_file = pq.ParquetFile(file_path)
            schema = parquet_file.schema_arrow
            # Check for geo metadata in the schema
            if schema.metadata and b'geo' in schema.metadata:
                return "GeoParquet"
            # Also check for geometry column
            for field in schema:
                if field.name == 'geometry':
                    return "GeoParquet"
        except:
            pass
        return "Parquet"
    elif suffix in ['.tif', '.tiff', '.img', '.nc', '.hdf', '.vrt', '.asc', '.dem']:
        # Known raster extensions - verify with rasterio
        try:
            with rasterio.open(file_path) as src:
                return "Raster"
        except:
            pass

    # Try rasterio for unknown extensions that might be GDAL-supported rasters
    try:
        with rasterio.open(file_path) as src:
            return "Raster"
    except:
        pass

    return None


def read_csv(file_path: Path, verbose: bool = False) -> Dict[str, Any]:
    """Read and summarize a CSV file."""
    df = pd.read_csv(file_path)
    
    summary = {
        "basic_info": {
            "File": file_path.name,
            "Rows": len(df),
            "Columns": len(df.columns),
            "Memory Usage": f"{df.memory_usage(deep=True).sum() / 1024:.2f} KB"
        },
        "columns": []
    }
    
    for col in df.columns:
        col_info = {
            "name": col,
            "type": str(df[col].dtype)
        }
        summary["columns"].append(col_info)
    
    if verbose:
        summary["sample_values"] = {}
        summary["statistics"] = {}
        
        for col in df.columns:
            summary["sample_values"][col] = df[col].dropna().head(5).tolist()
            
            if pd.api.types.is_numeric_dtype(df[col]):
                summary["statistics"][col] = {
                    "min": float(df[col].min()) if not pd.isna(df[col].min()) else None,
                    "max": float(df[col].max()) if not pd.isna(df[col].max()) else None,
                    "mean": float(df[col].mean()) if not pd.isna(df[col].mean()) else None,
                    "unique": df[col].nunique()
                }
            else:
                summary["statistics"][col] = {
                    "unique": df[col].nunique(),
                    "most_common": df[col].value_counts().head(1).index[0] if not df[col].empty else None
                }
    
    return summary


def read_excel(file_path: Path, verbose: bool = False) -> Dict[str, Any]:
    """Read and summarize an Excel file."""
    xl_file = pd.ExcelFile(file_path)
    
    summary = {
        "basic_info": {
            "File": file_path.name,
            "Sheets": len(xl_file.sheet_names),
            "Sheet Names": ", ".join(xl_file.sheet_names)
        }
    }
    
    if xl_file.sheet_names:
        df = pd.read_excel(file_path, sheet_name=xl_file.sheet_names[0])
        
        summary["basic_info"]["Active Sheet"] = xl_file.sheet_names[0]
        summary["basic_info"]["Rows"] = len(df)
        summary["basic_info"]["Columns"] = len(df.columns)
        summary["basic_info"]["Memory Usage"] = f"{df.memory_usage(deep=True).sum() / 1024:.2f} KB"
        
        summary["columns"] = []
        for col in df.columns:
            col_info = {
                "name": col,
                "type": str(df[col].dtype)
            }
            summary["columns"].append(col_info)
        
        if verbose:
            summary["sample_values"] = {}
            summary["statistics"] = {}
            
            for col in df.columns:
                summary["sample_values"][col] = df[col].dropna().head(5).tolist()
                
                if pd.api.types.is_numeric_dtype(df[col]):
                    summary["statistics"][col] = {
                        "min": float(df[col].min()) if not pd.isna(df[col].min()) else None,
                        "max": float(df[col].max()) if not pd.isna(df[col].max()) else None,
                        "mean": float(df[col].mean()) if not pd.isna(df[col].mean()) else None,
                        "unique": df[col].nunique()
                    }
                else:
                    summary["statistics"][col] = {
                        "unique": df[col].nunique(),
                        "most_common": df[col].value_counts().head(1).index[0] if not df[col].empty else None
                    }
    
    return summary


def read_geojson(file_path: Path, verbose: bool = False) -> Dict[str, Any]:
    """Read and summarize a GeoJSON file."""
    if not verbose:
        warnings.filterwarnings('ignore')
    
    gdf = gpd.read_file(file_path)
    
    summary = {
        "basic_info": {
            "File": file_path.name,
            "Features": len(gdf),
            "CRS": str(gdf.crs) if gdf.crs else "None",
            "Memory Usage": f"{gdf.memory_usage(deep=True).sum() / 1024:.2f} KB"
        },
        "columns": [],
        "geometry_info": {}
    }
    
    for col in gdf.columns:
        if col != 'geometry':
            col_info = {
                "name": col,
                "type": str(gdf[col].dtype)
            }
            summary["columns"].append(col_info)
    
    if 'geometry' in gdf.columns:
        geom_types = gdf.geometry.geom_type.value_counts()
        bounds = gdf.total_bounds
        
        # Calculate area and length with warning suppression
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            area_sum = gdf.geometry.area.sum() if gdf.geometry.geom_type.iloc[0] in ['Polygon', 'MultiPolygon'] else None
            length_sum = gdf.geometry.length.sum() if gdf.geometry.geom_type.iloc[0] in ['LineString', 'MultiLineString'] else None
        
        summary["geometry_info"] = {
            "Geometry Types": ", ".join(f"{t}: {c}" for t, c in geom_types.items()),
            "Bounds (minx, miny, maxx, maxy)": f"[{bounds[0]:.6f}, {bounds[1]:.6f}, {bounds[2]:.6f}, {bounds[3]:.6f}]",
            "Total Area": f"{area_sum:.6f}" if area_sum is not None else "N/A",
            "Total Length": f"{length_sum:.6f}" if length_sum is not None else "N/A"
        }
    
    if verbose:
        summary["sample_values"] = {}
        summary["statistics"] = {}
        
        for col in gdf.columns:
            if col != 'geometry':
                summary["sample_values"][col] = gdf[col].dropna().head(5).tolist()
                
                if pd.api.types.is_numeric_dtype(gdf[col]):
                    summary["statistics"][col] = {
                        "min": float(gdf[col].min()) if not pd.isna(gdf[col].min()) else None,
                        "max": float(gdf[col].max()) if not pd.isna(gdf[col].max()) else None,
                        "mean": float(gdf[col].mean()) if not pd.isna(gdf[col].mean()) else None,
                        "unique": gdf[col].nunique()
                    }
                else:
                    summary["statistics"][col] = {
                        "unique": gdf[col].nunique()
                    }

    return summary


def read_parquet(file_path: Path, verbose: bool = False) -> Dict[str, Any]:
    """Read and summarize a Parquet file."""
    df = pd.read_parquet(file_path)

    summary = {
        "basic_info": {
            "File": file_path.name,
            "Rows": len(df),
            "Columns": len(df.columns),
            "Memory Usage": f"{df.memory_usage(deep=True).sum() / 1024:.2f} KB"
        },
        "columns": []
    }

    for col in df.columns:
        col_info = {
            "name": col,
            "type": str(df[col].dtype)
        }
        summary["columns"].append(col_info)

    if verbose:
        summary["sample_values"] = {}
        summary["statistics"] = {}

        for col in df.columns:
            summary["sample_values"][col] = df[col].dropna().head(5).tolist()

            if pd.api.types.is_numeric_dtype(df[col]):
                summary["statistics"][col] = {
                    "min": float(df[col].min()) if not pd.isna(df[col].min()) else None,
                    "max": float(df[col].max()) if not pd.isna(df[col].max()) else None,
                    "mean": float(df[col].mean()) if not pd.isna(df[col].mean()) else None,
                    "unique": df[col].nunique()
                }
            else:
                summary["statistics"][col] = {
                    "unique": df[col].nunique(),
                    "most_common": df[col].value_counts().head(1).index[0] if not df[col].empty else None
                }

    return summary


def read_geoparquet(file_path: Path, verbose: bool = False) -> Dict[str, Any]:
    """Read and summarize a GeoParquet file."""
    if not verbose:
        warnings.filterwarnings('ignore')

    gdf = gpd.read_parquet(file_path)

    summary = {
        "basic_info": {
            "File": file_path.name,
            "Features": len(gdf),
            "CRS": str(gdf.crs) if gdf.crs else "None",
            "Memory Usage": f"{gdf.memory_usage(deep=True).sum() / 1024:.2f} KB"
        },
        "columns": [],
        "geometry_info": {}
    }

    for col in gdf.columns:
        if col != 'geometry':
            col_info = {
                "name": col,
                "type": str(gdf[col].dtype)
            }
            summary["columns"].append(col_info)

    if 'geometry' in gdf.columns:
        geom_types = gdf.geometry.geom_type.value_counts()
        bounds = gdf.total_bounds

        # Calculate area and length with warning suppression
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            area_sum = gdf.geometry.area.sum() if gdf.geometry.geom_type.iloc[0] in ['Polygon', 'MultiPolygon'] else None
            length_sum = gdf.geometry.length.sum() if gdf.geometry.geom_type.iloc[0] in ['LineString', 'MultiLineString'] else None

        summary["geometry_info"] = {
            "Geometry Types": ", ".join(f"{t}: {c}" for t, c in geom_types.items()),
            "Bounds (minx, miny, maxx, maxy)": f"[{bounds[0]:.6f}, {bounds[1]:.6f}, {bounds[2]:.6f}, {bounds[3]:.6f}]",
            "Total Area": f"{area_sum:.6f}" if area_sum is not None else "N/A",
            "Total Length": f"{length_sum:.6f}" if length_sum is not None else "N/A"
        }

    if verbose:
        summary["sample_values"] = {}
        summary["statistics"] = {}

        for col in gdf.columns:
            if col != 'geometry':
                summary["sample_values"][col] = gdf[col].dropna().head(5).tolist()

                if pd.api.types.is_numeric_dtype(gdf[col]):
                    summary["statistics"][col] = {
                        "min": float(gdf[col].min()) if not pd.isna(gdf[col].min()) else None,
                        "max": float(gdf[col].max()) if not pd.isna(gdf[col].max()) else None,
                        "mean": float(gdf[col].mean()) if not pd.isna(gdf[col].mean()) else None,
                        "unique": gdf[col].nunique()
                    }
                else:
                    summary["statistics"][col] = {
                        "unique": gdf[col].nunique()
                    }

    return summary


def read_shapefile(file_path: Path, verbose: bool = False) -> Dict[str, Any]:
    """Read and summarize a Shapefile."""
    if not verbose:
        warnings.filterwarnings('ignore')

    gdf = gpd.read_file(file_path)

    summary = {
        "basic_info": {
            "File": file_path.name,
            "Features": len(gdf),
            "CRS": str(gdf.crs) if gdf.crs else "None",
            "Memory Usage": f"{gdf.memory_usage(deep=True).sum() / 1024:.2f} KB"
        },
        "columns": [],
        "geometry_info": {}
    }

    for col in gdf.columns:
        if col != 'geometry':
            col_info = {
                "name": col,
                "type": str(gdf[col].dtype)
            }
            summary["columns"].append(col_info)

    if 'geometry' in gdf.columns:
        geom_types = gdf.geometry.geom_type.value_counts()
        bounds = gdf.total_bounds

        # Calculate area and length with warning suppression
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            area_sum = gdf.geometry.area.sum() if gdf.geometry.geom_type.iloc[0] in ['Polygon', 'MultiPolygon'] else None
            length_sum = gdf.geometry.length.sum() if gdf.geometry.geom_type.iloc[0] in ['LineString', 'MultiLineString'] else None

        summary["geometry_info"] = {
            "Geometry Types": ", ".join(f"{t}: {c}" for t, c in geom_types.items()),
            "Bounds (minx, miny, maxx, maxy)": f"[{bounds[0]:.6f}, {bounds[1]:.6f}, {bounds[2]:.6f}, {bounds[3]:.6f}]",
            "Total Area": f"{area_sum:.6f}" if area_sum is not None else "N/A",
            "Total Length": f"{length_sum:.6f}" if length_sum is not None else "N/A"
        }

    if verbose:
        summary["sample_values"] = {}
        summary["statistics"] = {}

        for col in gdf.columns:
            if col != 'geometry':
                summary["sample_values"][col] = gdf[col].dropna().head(5).tolist()

                if pd.api.types.is_numeric_dtype(gdf[col]):
                    summary["statistics"][col] = {
                        "min": float(gdf[col].min()) if not pd.isna(gdf[col].min()) else None,
                        "max": float(gdf[col].max()) if not pd.isna(gdf[col].max()) else None,
                        "mean": float(gdf[col].mean()) if not pd.isna(gdf[col].mean()) else None,
                        "unique": gdf[col].nunique()
                    }
                else:
                    summary["statistics"][col] = {
                        "unique": gdf[col].nunique()
                    }

    return summary


def read_raster(file_path: Path, verbose: bool = False) -> Dict[str, Any]:
    """Read and summarize a raster file (GeoTIFF, NetCDF, etc.) using rasterio.

    Extracts gdalinfo-like metadata including driver, dimensions, CRS, bounds,
    pixel size, and per-band information. For files with subdatasets (like NetCDF),
    includes subdataset information.
    """
    with rasterio.open(file_path) as src:
        # Get file size
        file_size_bytes = os.path.getsize(file_path)
        if file_size_bytes >= 1024 * 1024 * 1024:
            file_size_str = f"{file_size_bytes / (1024 * 1024 * 1024):.2f} GB"
        elif file_size_bytes >= 1024 * 1024:
            file_size_str = f"{file_size_bytes / (1024 * 1024):.2f} MB"
        else:
            file_size_str = f"{file_size_bytes / 1024:.2f} KB"

        # Get bounds
        bounds = src.bounds

        summary = {
            "basic_info": {
                "File": file_path.name,
                "Driver": f"{src.driver}",
                "Size": f"{src.width} x {src.height} pixels",
                "Bands": src.count,
                "CRS": str(src.crs) if src.crs else "None",
                "Bounds": f"[{bounds.left:.6f}, {bounds.bottom:.6f}, {bounds.right:.6f}, {bounds.top:.6f}]",
                "Pixel Size": f"({src.res[0]:.6f}, {src.res[1]:.6f})",
                "File Size": file_size_str
            },
            "bands": [],
            "raster_info": {
                "Transform": str(src.transform),
                "Interleave": src.interleaving.value if src.interleaving else "N/A"
            }
        }

        # Check for subdatasets (common in NetCDF, HDF files)
        subdatasets = src.subdatasets
        if subdatasets:
            summary["subdatasets"] = []
            for subdataset in subdatasets:
                # Extract variable name from subdataset path (e.g., "netcdf:file.nc:var_name")
                var_name = subdataset.split(":")[-1] if ":" in subdataset else subdataset
                subdataset_info = {
                    "name": var_name,
                    "path": subdataset
                }
                # Get more details by opening the subdataset
                try:
                    with rasterio.open(subdataset) as sub_src:
                        subdataset_info["size"] = f"{sub_src.width} x {sub_src.height}"
                        subdataset_info["bands"] = sub_src.count
                        subdataset_info["dtype"] = str(sub_src.dtypes[0]) if sub_src.count > 0 else "N/A"
                        subdataset_info["crs"] = str(sub_src.crs) if sub_src.crs else "None"
                except Exception:
                    subdataset_info["size"] = "N/A"
                    subdataset_info["bands"] = "N/A"
                    subdataset_info["dtype"] = "N/A"
                    subdataset_info["crs"] = "N/A"
                summary["subdatasets"].append(subdataset_info)

        # Collect band information
        for band_idx in range(1, src.count + 1):
            band_info = {
                "number": band_idx,
                "dtype": str(src.dtypes[band_idx - 1]),
                "nodata": src.nodatavals[band_idx - 1] if src.nodatavals[band_idx - 1] is not None else "None",
                "color": src.colorinterp[band_idx - 1].name if src.colorinterp else "undefined"
            }
            summary["bands"].append(band_info)

        # Verbose mode: compute band statistics
        if verbose:
            summary["band_statistics"] = []
            for band_idx in range(1, src.count + 1):
                band_data = src.read(band_idx, masked=True)

                # Compute statistics on valid data
                if band_data.count() > 0:
                    stats = {
                        "band": band_idx,
                        "min": float(band_data.min()),
                        "max": float(band_data.max()),
                        "mean": float(band_data.mean()),
                        "std": float(band_data.std())
                    }
                else:
                    stats = {
                        "band": band_idx,
                        "min": "N/A",
                        "max": "N/A",
                        "mean": "N/A",
                        "std": "N/A"
                    }
                summary["band_statistics"].append(stats)

            # Add metadata tags
            if src.tags():
                summary["metadata"] = dict(src.tags())

    return summary