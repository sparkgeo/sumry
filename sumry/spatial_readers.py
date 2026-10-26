"""Metadata-first summaries for rasters, point clouds, and tile archives."""
from itertools import islice
from pathlib import Path

import numpy as np

STAT_SAMPLE_LIMIT = 100_000


def _number(value):
    """Return JSON-safe scalar values, including masked and nonfinite values."""
    if np.ma.is_masked(value):
        return None
    value = value.item() if isinstance(value, np.generic) else value
    if isinstance(value, complex):
        return str(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _stats(values):
    values = np.ma.masked_invalid(values)
    valid = values.compressed()
    # Complex rasters are summarized by magnitude, explicitly labelled by caller.
    if np.iscomplexobj(valid):
        valid = np.abs(valid)
    return {
        "min": _number(valid.min()) if valid.size else None,
        "max": _number(valid.max()) if valid.size else None,
        "mean": _number(valid.mean()) if valid.size else None,
        "std": _number(valid.std()) if valid.size else None,
        "valid_percent": 100 * valid.size / values.size if values.size else None,
    }


def read_raster(file_path: Path, verbose=False, sample_count=None):
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import Window

    with rasterio.open(file_path) as src:
        crs = src.crs
        # Worldfiles contain a transform, never a CRS. Use a companion PRJ if present.
        prj = next((p for p in file_path.parent.iterdir()
                    if p.stem.lower() == file_path.stem.lower() and p.suffix.lower() == '.prj'), None)
        if crs is None and prj:
            crs = rasterio.crs.CRS.from_wkt(prj.read_text())
        layout = src.tags(ns="IMAGE_STRUCTURE").get("LAYOUT")
        summary = {
            "basic_info": {
                "File": file_path.name, "Format": "COG" if layout == "COG" else src.driver,
                "File Size (bytes)": file_path.stat().st_size,
                "Width": src.width, "Height": src.height,
                "Pixels": src.width * src.height, "Bands": src.count,
                "CRS": str(crs) if crs else None,
                "Compression": src.compression.value if src.compression else None,
            },
            "spatial_info": {
                "Bounds (left, bottom, right, top)": list(src.bounds),
                "Pixel Size": list(src.res),
                "Coordinate Units": crs.linear_units if crs and crs.is_projected else "degrees" if crs and crs.is_geographic else "Unknown",
                "Transform (a, b, c, d, e, f)": list(src.transform)[:6],
                "Associated Files": src.files,
            },
            "bands": [
                {"Band": i, "Description": src.descriptions[i-1], "Type": src.dtypes[i-1],
                 "Units": src.units[i-1], "NoData": _number(src.nodatavals[i-1]),
                 "Color": src.colorinterp[i-1].name, "Scale": src.scales[i-1],
                 "Offset": src.offsets[i-1], "Overviews": src.overviews(i)}
                for i in src.indexes
            ],
        }
        if verbose:
            ratio = min(1, (STAT_SAMPLE_LIMIT / (src.width * src.height)) ** 0.5)
            height, width = max(1, int(src.height * ratio)), max(1, int(src.width * ratio))
            # Also cap extremely narrow or tall rasters.
            width = min(width, STAT_SAMPLE_LIMIT)
            height = min(height, STAT_SAMPLE_LIMIT // width)
            summary["sampling_info"] = {
                "Statistics Method": "Exact" if (height, width) == (src.height, src.width) else "Approximate nearest-neighbour grid",
                "Pixels Per Band": height * width,
                "Values": "Stored values; masks and nonfinite values excluded; complex values use magnitude",
            }
            summary["statistics"] = {
                f"Band {i}": _stats(src.read(i, out_shape=(height, width), masked=True, resampling=Resampling.nearest))
                for i in src.indexes
            }
        if sample_count is not None and sample_count > 0:
            total = src.width * src.height
            summary.setdefault("sampling_info", {})["Sample Method"] = "Evenly spaced pixel indices; zero-based row/column; pixel-centre coordinates"
            summary["sample_data"] = []
            for index in np.linspace(0, total - 1, min(sample_count, total), dtype=np.int64):
                row, col = divmod(int(index), src.width)
                x, y = src.xy(row, col)
                values = src.read(window=Window(col, row, 1, 1), masked=True)[:, 0, 0]
                summary["sample_data"].append({"row": row, "column": col, "x": x, "y": y,
                    **{f"Band {i}": _number(values[i-1]) for i in src.indexes}})
        return summary


def read_point_cloud(file_path: Path, verbose=False, sample_count=None):
    import laspy

    with laspy.open(file_path) as src:
        header = src.header
        crs = header.parse_crs()
        copc = any(v.user_id == "copc" and v.record_id == 1 for v in header.vlrs)
        dimensions = list(header.point_format.dimension_names)
        summary = {
            "basic_info": {
                "File": file_path.name, "Format": "COPC" if copc else "LAZ" if header.are_points_compressed else "LAS",
                "File Size (bytes)": file_path.stat().st_size, "Points": header.point_count,
                "LAS Version": str(header.version), "Point Format": header.point_format.id,
                "CRS": str(crs) if crs else None,
            },
            "spatial_info": {
                "Minimum (x, y, z)": header.mins.tolist() if header.point_count else None,
                "Maximum (x, y, z)": header.maxs.tolist() if header.point_count else None,
                "Scale": header.scales.tolist(), "Offset": header.offsets.tolist(),
            },
            "columns": [{"name": d.name, "type": str(d.dtype) if d.dtype else f"uint{d.num_bits}"}
                        for d in header.point_format.dimensions],
        }
        count = min(header.point_count, max(STAT_SAMPLE_LIMIT if verbose else 0, sample_count or 0))
        if count:
            points = src.read_points(count)
            names = ["x", "y", "z"] + [d for d in dimensions if d not in ("X", "Y", "Z")]
            summary["sampling_info"] = {"Method": "First points in file order (not spatially representative)",
                                        "Points Read": len(points), "Coordinates": "Scaled x/y/z in the source CRS"}
            if verbose:
                size = min(len(points), STAT_SAMPLE_LIMIT)
                summary["sampling_info"]["Statistics Points"] = size
                summary["sampling_info"]["Statistics Method"] = "Exact" if size == header.point_count else "Approximate prefix sample"
                summary["statistics"] = {name: _stats(np.asarray(points[name])[:size])
                                         for name in names if np.asarray(points[name]).ndim == 1}
            if sample_count:
                summary["sample_data"] = [
                    {name: _number(points[name][i]) if np.ndim(points[name][i]) == 0 else np.asarray(points[name][i]).tolist()
                     for name in names} for i in range(min(sample_count, len(points)))
                ]
        elif sample_count:
            summary["sample_data"] = []
        return summary


def read_pmtiles(file_path: Path, verbose=False, sample_count=None):
    import gzip
    from pmtiles.reader import Reader
    from pmtiles.tile import Compression, deserialize_directory, tileid_to_zxy

    with file_path.open('rb') as stream:
        def get_bytes(offset, length):
            stream.seek(offset)
            data = stream.read(length)
            if len(data) != length:
                raise ValueError("Truncated PMTiles archive")
            return data

        if get_bytes(0, 8) != b'PMTiles\x03':
            raise ValueError("Only PMTiles version 3 archives are supported")
        reader = Reader(get_bytes)
        h = reader.header()
        if h['internal_compression'] not in (Compression.NONE, Compression.GZIP):
            raise ValueError("Unsupported PMTiles internal compression")
        metadata = reader.metadata() if h['metadata_length'] else {}
        summary = {
            "basic_info": {
                "File": file_path.name, "Format": "PMTiles", "Version": h['version'],
                "File Size (bytes)": file_path.stat().st_size,
                "Tile Type": h['tile_type'].name, "Tile Compression": h['tile_compression'].name,
                "Minimum Zoom": h['min_zoom'], "Maximum Zoom": h['max_zoom'],
                "Addressed Tiles": h['addressed_tiles_count'], "Tile Entries": h['tile_entries_count'],
                "Tile Contents": h['tile_contents_count'], "Clustered": h['clustered'],
            },
            "spatial_info": {
                "Bounds CRS": "EPSG:4326",
                "Bounds (west, south, east, north)": [h[k] / 1e7 for k in ('min_lon_e7', 'min_lat_e7', 'max_lon_e7', 'max_lat_e7')],
                "Center (longitude, latitude, zoom)": [h['center_lon_e7'] / 1e7, h['center_lat_e7'] / 1e7, h['center_zoom']],
            },
        }
        if verbose:
            summary['metadata'] = metadata
        elif metadata.get('vector_layers'):
            summary['basic_info']['Vector Layers'] = [layer.get('id') for layer in metadata['vector_layers']]
        if sample_count and sample_count > 0:
            summary['sampling_info'] = {'Sample Method': 'First tile addresses in archive order; payloads are not decoded'}
            def tile_addresses(offset, length, depth=0):
                if depth > 3:
                    raise ValueError("PMTiles directory nesting exceeds maximum depth")
                data = get_bytes(offset, length)
                # The library directory decoder expects gzip even for uncompressed archives.
                if h['internal_compression'] == Compression.NONE:
                    data = gzip.compress(data)
                for entry in deserialize_directory(data):
                    if entry.run_length:
                        for tile_id in range(entry.tile_id, entry.tile_id + entry.run_length):
                            z, x, y = tileid_to_zxy(tile_id)
                            yield {'z': z, 'x': x, 'y': y, 'Stored Bytes': entry.length}
                    else:
                        yield from tile_addresses(h['leaf_directory_offset'] + entry.offset, entry.length, depth + 1)
            summary['sample_data'] = list(islice(tile_addresses(h['root_offset'], h['root_length']), sample_count))
        return summary
