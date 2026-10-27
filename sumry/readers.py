from pathlib import Path
import pandas as pd
import geopandas as gpd
import pyogrio
import json
import warnings
from typing import Dict, Any, Optional, List


def detect_file_type(file_path: Path) -> Optional[str]:
    """Detect the type of file based on its extension."""
    suffix = file_path.suffix.lower()
    
    if suffix in ['.csv', '.tsv']:
        return "CSV"
    elif suffix in ['.xlsx', '.xls', '.xlsm']:
        return "Excel"
    elif suffix == '.parquet':
        return "Parquet"
    elif suffix == '.gpkg':
        return "GeoPackage"
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
    
    elif suffix in ['.tif', '.tiff', '.jp2', '.j2k', '.jpx']:
        return "Raster"
    elif suffix in ['.las', '.laz', '.copc']:
        return "Point Cloud"
    elif suffix == '.pmtiles':
        return "PMTiles"
    elif suffix == '.fgb':
        return "FlatGeobuf"

    return None


def read_flatgeobuf(file_path: Path, verbose: bool = False, sample_count: Optional[int] = None) -> Dict[str, Any]:
    """Summarize FlatGeobuf using the shared vector summary."""
    return _summarize_geodataframe(gpd.read_file(file_path, engine="pyogrio"), file_path, verbose, sample_count)


def read_csv(file_path: Path, verbose: bool = False, sample_count: Optional[int] = None,
             encoding: Optional[str] = None) -> Dict[str, Any]:
    """Read and summarize a CSV file."""
    selected_encoding = encoding or "utf-8-sig"
    separator = "\t" if file_path.suffix.lower() == ".tsv" else ","
    try:
        df = pd.read_csv(file_path, encoding=selected_encoding, sep=separator)
    except UnicodeDecodeError:
        if encoding is not None:
            raise
        # Legacy spreadsheet exports commonly use Windows-1252. Keep decoding
        # strict so unsupported bytes are never silently dropped or replaced.
        selected_encoding = "cp1252"
        df = pd.read_csv(file_path, encoding=selected_encoding, sep=separator)
    summary = _summarize_dataframe(df, file_path, verbose, sample_count)
    summary["basic_info"]["Encoding"] = selected_encoding
    return summary


def read_parquet(file_path: Path, verbose: bool = False, sample_count: Optional[int] = None) -> Dict[str, Any]:
    """Read and summarize a Parquet file."""
    df = pd.read_parquet(file_path, engine="pyarrow")
    return _summarize_dataframe(df, file_path, verbose, sample_count)


def _summarize_dataframe(df: pd.DataFrame, file_path: Path, verbose: bool, sample_count: Optional[int]) -> Dict[str, Any]:
    """Build a tabular file summary from a DataFrame."""
    
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
                counts = df[col].value_counts()
                summary["statistics"][col] = {
                    "unique": df[col].nunique(),
                    "most_common": counts.index[0] if not counts.empty else None
                }
    
    # Add sample data if requested
    if sample_count is not None and sample_count > 0:
        sample_df = df.head(sample_count)
        summary["sample_data"] = sample_df.to_dict('records')
    
    return summary


def read_excel(file_path: Path, verbose: bool = False, select: Optional[str] = None, sample_count: Optional[int] = None) -> Dict[str, Any]:
    """Read and summarize an Excel file, optionally for specific sheets."""
    xl_file = pd.ExcelFile(file_path)
    
    # Parse the select parameter
    sheets_to_process = []
    if select:
        # Split by comma and strip whitespace
        selected_sheets = [s.strip() for s in select.split(',')]
        
        for sheet in selected_sheets:
            # Check if it's a number (sheet index)
            if sheet.isdigit():
                index = int(sheet)
                if 0 <= index < len(xl_file.sheet_names):
                    sheets_to_process.append(xl_file.sheet_names[index])
            # Otherwise treat as sheet name
            elif sheet in xl_file.sheet_names:
                sheets_to_process.append(sheet)
    else:
        # Default to first sheet if no selection
        if xl_file.sheet_names:
            sheets_to_process = [xl_file.sheet_names[0]]
    
    if not sheets_to_process:
        return {
            "basic_info": {
                "File": file_path.name,
                "Error": f"No valid sheets found. Available sheets: {', '.join(xl_file.sheet_names)}"
            }
        }
    
    # If multiple sheets selected, return summaries for each
    if len(sheets_to_process) > 1:
        summaries = {}
        for sheet_name in sheets_to_process:
            summaries[sheet_name] = _read_single_excel_sheet(file_path, sheet_name, verbose, xl_file, sample_count)
        
        # Create a combined summary
        summary = {
            "basic_info": {
                "File": file_path.name,
                "Total Sheets": len(xl_file.sheet_names),
                "Selected Sheets": len(sheets_to_process),
                "Sheet Names": ", ".join(sheets_to_process)
            },
            "sheets": summaries
        }
        return summary
    else:
        # Single sheet processing (backward compatible)
        sheet_name = sheets_to_process[0]
        summary = _read_single_excel_sheet(file_path, sheet_name, verbose, xl_file, sample_count)
        summary["basic_info"]["File"] = file_path.name
        summary["basic_info"]["Total Sheets"] = len(xl_file.sheet_names)
        summary["basic_info"]["All Sheet Names"] = ", ".join(xl_file.sheet_names)
        return summary


def _read_single_excel_sheet(file_path: Path, sheet_name: str, verbose: bool, xl_file: pd.ExcelFile, sample_count: Optional[int] = None) -> Dict[str, Any]:
    """Read and summarize a single Excel sheet."""
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    
    summary = {
        "basic_info": {
            "Sheet": sheet_name,
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
    
    # Add sample data if requested
    if sample_count is not None and sample_count > 0:
        sample_df = df.head(sample_count)
        summary["sample_data"] = sample_df.to_dict('records')
    
    return summary


def read_geojson(file_path: Path, verbose: bool = False, sample_count: Optional[int] = None) -> Dict[str, Any]:
    """Read and summarize a GeoJSON file."""
    if not verbose:
        warnings.filterwarnings('ignore')
    
    gdf = gpd.read_file(file_path)
    return _summarize_geodataframe(gdf, file_path, verbose, sample_count)


def read_geopackage(file_path: Path, verbose: bool = False, select: Optional[str] = None, sample_count: Optional[int] = None) -> Dict[str, Any]:
    """Summarize the first GeoPackage layer, or selected names/zero-based indices."""
    layer_names = [name for name, _ in pyogrio.list_layers(file_path)]
    if not layer_names:
        raise ValueError("GeoPackage has no readable vector or attribute layers")

    selected = []
    for token in select.split(',') if select is not None else [layer_names[0]]:
        token = token.strip()
        if token in layer_names:
            name = token
        elif token.isdigit() and int(token) < len(layer_names):
            name = layer_names[int(token)]
        else:
            raise ValueError(f"Unknown layer {token!r}. Available layers: {', '.join(layer_names)}")
        if name not in selected:
            selected.append(name)

    summaries = {}
    for name in selected:
        frame = gpd.read_file(file_path, layer=name, engine="pyogrio")
        if isinstance(frame, gpd.GeoDataFrame):
            summary = _summarize_geodataframe(frame, file_path, verbose, sample_count)
        else:
            summary = _summarize_dataframe(frame, file_path, verbose, sample_count)
        summary["basic_info"]["Layer"] = name
        summaries[name] = summary

    if len(selected) == 1:
        summary = summaries[selected[0]]
        summary["basic_info"].update({
            "Total Layers": len(layer_names),
            "All Layer Names": ", ".join(layer_names),
        })
        return summary
    return {
        "basic_info": {
            "File": file_path.name,
            "Total Layers": len(layer_names),
            "Selected Layers": len(selected),
            "Layer Names": ", ".join(selected),
        },
        "layers": summaries,
    }


def _summarize_geodataframe(gdf: gpd.GeoDataFrame, file_path: Path, verbose: bool, sample_count: Optional[int]) -> Dict[str, Any]:
    """Build a summary of a spatial layer, including empty layers."""
    
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
            area_sum = gdf.geometry.area.sum() if geom_types.index.isin(['Polygon', 'MultiPolygon']).any() else None
            length_sum = gdf.geometry.length.sum() if geom_types.index.isin(['LineString', 'MultiLineString']).any() else None
        
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
    
    # Add sample data if requested (excluding geometry column)
    if sample_count is not None and sample_count > 0:
        sample_gdf = gdf.head(sample_count)
        # Convert to dict excluding geometry for readability
        sample_data = []
        for _, row in sample_gdf.iterrows():
            row_dict = {}
            for col in sample_gdf.columns:
                if col != 'geometry':
                    row_dict[col] = row[col]
            sample_data.append(row_dict)
        summary["sample_data"] = sample_data
    
    return summary


def read_shapefile(file_path: Path, verbose: bool = False, sample_count: Optional[int] = None) -> Dict[str, Any]:
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
    # Add sample data if requested (excluding geometry column)
    if sample_count is not None and sample_count > 0:
        sample_gdf = gdf.head(sample_count)
        # Convert to dict excluding geometry for readability
        sample_data = []
        for _, row in sample_gdf.iterrows():
            row_dict = {}
            for col in sample_gdf.columns:
                if col != "geometry":
                    row_dict[col] = row[col]
            sample_data.append(row_dict)
        summary["sample_data"] = sample_data
    
    return summary
