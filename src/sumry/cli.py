import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
import warnings
import os

from sumry.readers import (
    read_csv,
    read_excel,
    read_geojson,
    read_shapefile,
    read_parquet,
    read_geoparquet,
    read_raster,
    detect_file_type
)

app = typer.Typer(
    name="sumry",
    help="Summarize various data sources (CSV, Excel, GeoJSON, Shapefiles, Parquet, GeoParquet, Raster)",
    add_completion=False
)

console = Console()


@app.command()
def main(
    file_path: Path = typer.Argument(
        ...,
        help="Path to the file to summarize",
        exists=True
    ),
    verbose: bool = typer.Option(
        False, 
        "--verbose", 
        "-v",
        help="Show detailed information"
    ),
    sample: Optional[int] = typer.Option(
        None,
        "--sample",
        "-n",
        help="Number of sample records to display (default: 5)"
    ),
    show_sample: bool = typer.Option(
        False,
        "--show-sample",
        "-s",
        help="Show sample records (displays 5 records)"
    )
):
    """
    Summarize a data file (CSV, Excel, GeoJSON, Shapefile, Parquet, GeoParquet, or Raster).
    """
    
    # Suppress warnings and verbose output in non-verbose mode
    if not verbose:
        warnings.filterwarnings('ignore')
        os.environ['PYOGRIO_USE_ARROW'] = '0'  # Suppress pyogrio Arrow warnings
    
    if not file_path.exists():
        console.print(f"[bold red]Error:[/bold red] File {file_path} does not exist")
        raise typer.Exit(1)
    
    file_type = detect_file_type(file_path)
    
    if not file_type:
        console.print(f"[bold red]Error:[/bold red] Unsupported file type for {file_path}")
        raise typer.Exit(1)
    
    try:
        if file_type == "CSV":
            summary = read_csv(file_path, verbose)
        elif file_type == "Excel":
            summary = read_excel(file_path, verbose)
        elif file_type == "GeoJSON":
            summary = read_geojson(file_path, verbose)
        elif file_type == "Shapefile":
            summary = read_shapefile(file_path, verbose)
        elif file_type == "Parquet":
            summary = read_parquet(file_path, verbose)
        elif file_type == "GeoParquet":
            summary = read_geoparquet(file_path, verbose)
        elif file_type == "Raster":
            summary = read_raster(file_path, verbose)
        else:
            console.print(f"[bold red]Error:[/bold red] Handler not implemented for {file_type}")
            raise typer.Exit(1)

        display_summary(summary, file_type, verbose)

        # Display sample records/pixels if requested
        if sample is not None or show_sample:
            sample_count = sample if sample is not None and sample != 0 else 5
            if file_type == "Raster":
                display_raster_sample(file_path, sample_count)
            else:
                display_sample_records(file_path, file_type, sample_count)
        
    except Exception as e:
        console.print(f"[bold red]Error reading file:[/bold red] {str(e)}")
        raise typer.Exit(1)


def display_sample_records(file_path: Path, file_type: str, sample_count: int):
    """Display sample records from the file.

    Args:
        sample_count: Number of records to show. Positive for first N, negative for last N.
    """
    import pandas as pd
    import geopandas as gpd

    # Determine if we're showing first or last records
    show_last = sample_count < 0
    abs_count = abs(sample_count)
    position = "last" if show_last else "first"

    console.print(f"\n[bold cyan]Sample Records ({position} {abs_count}):[/bold cyan]")

    try:
        # Read the data based on file type
        if file_type == "CSV":
            if show_last:
                df = pd.read_csv(file_path).tail(abs_count)
            else:
                df = pd.read_csv(file_path, nrows=abs_count)
        elif file_type == "Excel":
            if show_last:
                df = pd.read_excel(file_path).tail(abs_count)
            else:
                df = pd.read_excel(file_path, nrows=abs_count)
        elif file_type == "Parquet":
            full_df = pd.read_parquet(file_path)
            df = full_df.tail(abs_count) if show_last else full_df.head(abs_count)
        elif file_type in ["GeoJSON", "Shapefile", "GeoParquet"]:
            # For spatial files, use geopandas
            if file_type == "GeoJSON":
                if show_last:
                    gdf = gpd.read_file(file_path).tail(abs_count)
                else:
                    gdf = gpd.read_file(file_path, rows=abs_count)
            elif file_type == "Shapefile":
                if show_last:
                    gdf = gpd.read_file(file_path).tail(abs_count)
                else:
                    gdf = gpd.read_file(file_path, rows=abs_count)
            else:  # GeoParquet
                full_gdf = gpd.read_parquet(file_path)
                gdf = full_gdf.tail(abs_count) if show_last else full_gdf.head(abs_count)

            # Replace geometry column with placeholder
            df = gdf.copy()
            if 'geometry' in df.columns:
                df['geometry'] = '<geometry>'
        else:
            console.print(f"[yellow]Sample display not supported for {file_type}[/yellow]")
            return
        
        # Create a Rich table for displaying the sample
        from rich.box import ROUNDED
        table = Table(show_header=True, box=ROUNDED)
        
        # Add columns
        for col in df.columns:
            table.add_column(str(col), style="white", overflow="fold")
        
        # Add rows
        for _, row in df.iterrows():
            row_values = []
            for val in row.values:
                if pd.isna(val):
                    row_values.append("N/A")
                elif isinstance(val, (int, float)):
                    if pd.isna(val):
                        row_values.append("N/A")
                    elif isinstance(val, float):
                        row_values.append(f"{val:.2f}" if val != int(val) else str(int(val)))
                    else:
                        row_values.append(str(val))
                else:
                    # Truncate long strings
                    str_val = str(val)
                    if len(str_val) > 50:
                        str_val = str_val[:47] + "..."
                    row_values.append(str_val)
            table.add_row(*row_values)
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error displaying sample records: {str(e)}[/red]")


def display_raster_sample(file_path: Path, sample_count: int):
    """Display sample pixel values from a raster file.

    Args:
        file_path: Path to the raster file.
        sample_count: Number of pixels to show. Positive for top-left corner,
                      negative for bottom-right corner.
    """
    import rasterio
    from rich.box import ROUNDED

    # Determine if we're showing from top-left or bottom-right
    show_last = sample_count < 0
    abs_count = abs(sample_count)
    position = "bottom-right" if show_last else "top-left"

    console.print(f"\n[bold cyan]Sample Pixel Values ({position}, {abs_count} pixels):[/bold cyan]")

    try:
        with rasterio.open(file_path) as src:
            # Check if we have subdatasets but no bands in the main dataset
            if src.count == 0 and src.subdatasets:
                # Display samples from each subdataset
                for subdataset in src.subdatasets:
                    var_name = subdataset.split(":")[-1] if ":" in subdataset else subdataset
                    try:
                        with rasterio.open(subdataset) as sub_src:
                            _display_raster_sample_from_source(sub_src, var_name, abs_count, show_last)
                    except Exception as e:
                        console.print(f"[yellow]Could not read subdataset {var_name}: {str(e)}[/yellow]")
            elif src.count > 0:
                # Display samples from the main dataset bands
                _display_raster_sample_from_source(src, file_path.name, abs_count, show_last)
            else:
                console.print("[yellow]No bands or subdatasets found in raster file[/yellow]")

    except Exception as e:
        console.print(f"[red]Error displaying raster sample: {str(e)}[/red]")


def _display_raster_sample_from_source(src, name: str, abs_count: int, show_last: bool):
    """Helper function to display sample pixel values from a rasterio source.

    Args:
        src: An open rasterio dataset.
        name: Name to display for this dataset/subdataset.
        abs_count: Number of pixels to sample.
        show_last: If True, sample from bottom-right; otherwise top-left.
    """
    import math
    from rich.box import ROUNDED

    # Calculate window dimensions (try to make it roughly square)
    side = int(math.ceil(math.sqrt(abs_count)))
    width = min(side, src.width)
    height = min(int(math.ceil(abs_count / width)), src.height)

    # Calculate window position
    if show_last:
        # Bottom-right corner
        col_off = max(0, src.width - width)
        row_off = max(0, src.height - height)
    else:
        # Top-left corner
        col_off = 0
        row_off = 0

    import rasterio.windows
    window = rasterio.windows.Window(col_off, row_off, width, height)

    # Create table
    table = Table(show_header=True, box=ROUNDED, title=f"[bold]{name}[/bold]")
    table.add_column("Band", style="green")
    table.add_column("Sample Values", style="white")

    # Read and display sample values for each band
    for band_idx in range(1, src.count + 1):
        band_data = src.read(band_idx, window=window)
        # Flatten and take up to abs_count values
        flat_values = band_data.flatten()[:abs_count]
        # Format values appropriately
        if band_data.dtype in ['float32', 'float64']:
            values_str = ", ".join(f"{v:.4f}" for v in flat_values)
        else:
            values_str = ", ".join(str(v) for v in flat_values)
        table.add_row(f"Band {band_idx}", values_str)

    console.print(table)


def display_summary(summary: dict, file_type: str, verbose: bool):
    """Display the file summary using Rich formatting."""
    
    panel = Panel.fit(
        f"[bold green]{file_type} File Summary[/bold green]",
        border_style="cyan"
    )
    console.print(panel)
    
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    
    for key, value in summary.get("basic_info", {}).items():
        if isinstance(value, (list, dict)):
            value_str = str(value)
        else:
            value_str = str(value)
        table.add_row(key, value_str)
    
    console.print(table)
    
    if "columns" in summary and summary["columns"]:
        console.print("\n[bold cyan]Columns/Fields:[/bold cyan]")
        col_table = Table(show_header=True, box=None)
        col_table.add_column("Name", style="green")
        col_table.add_column("Type", style="yellow")
        
        if verbose and "sample_values" in summary:
            col_table.add_column("Sample Values", style="white")
            
        for col_info in summary["columns"]:
            if verbose and "sample_values" in summary:
                sample = summary["sample_values"].get(col_info["name"], [])
                sample_str = ", ".join(str(v) for v in sample[:3])
                col_table.add_row(col_info["name"], col_info["type"], sample_str)
            else:
                col_table.add_row(col_info["name"], col_info["type"])
        
        console.print(col_table)
    
    if verbose and "statistics" in summary:
        console.print("\n[bold cyan]Statistics:[/bold cyan]")
        stats_table = Table(show_header=True, box=None)
        stats_table.add_column("Column", style="green")
        stats_table.add_column("Min", style="yellow")
        stats_table.add_column("Max", style="yellow")
        stats_table.add_column("Mean", style="yellow")
        stats_table.add_column("Unique", style="yellow")
        
        for col_name, stats in summary["statistics"].items():
            stats_table.add_row(
                col_name,
                str(stats.get("min", "N/A")),
                str(stats.get("max", "N/A")),
                str(stats.get("mean", "N/A")),
                str(stats.get("unique", "N/A"))
            )
        
        console.print(stats_table)
    
    if "geometry_info" in summary:
        console.print("\n[bold cyan]Geometry Information:[/bold cyan]")
        geo_table = Table(show_header=False, box=None, padding=(0, 2))
        geo_table.add_column("Property", style="cyan", no_wrap=True)
        geo_table.add_column("Value", style="white")

        for key, value in summary["geometry_info"].items():
            geo_table.add_row(key, str(value))

        console.print(geo_table)

    # Display subdataset information for raster files (NetCDF, HDF, etc.)
    if "subdatasets" in summary and summary["subdatasets"]:
        console.print("\n[bold cyan]Subdatasets:[/bold cyan]")
        sub_table = Table(show_header=True, box=None)
        sub_table.add_column("Name", style="green")
        sub_table.add_column("Size", style="yellow")
        sub_table.add_column("Bands", style="white")
        sub_table.add_column("Type", style="white")

        for sub_info in summary["subdatasets"]:
            sub_table.add_row(
                sub_info["name"],
                str(sub_info["size"]),
                str(sub_info["bands"]),
                str(sub_info["dtype"])
            )

        console.print(sub_table)

    # Display band information for raster files
    if "bands" in summary and summary["bands"]:
        console.print("\n[bold cyan]Bands:[/bold cyan]")
        band_table = Table(show_header=True, box=None)
        band_table.add_column("Band", style="green")
        band_table.add_column("Type", style="yellow")
        band_table.add_column("NoData", style="white")
        band_table.add_column("Color", style="white")

        for band_info in summary["bands"]:
            band_table.add_row(
                str(band_info["number"]),
                band_info["dtype"],
                str(band_info["nodata"]),
                band_info["color"]
            )

        console.print(band_table)

    # Display raster info
    if "raster_info" in summary:
        console.print("\n[bold cyan]Raster Information:[/bold cyan]")
        raster_table = Table(show_header=False, box=None, padding=(0, 2))
        raster_table.add_column("Property", style="cyan", no_wrap=True)
        raster_table.add_column("Value", style="white")

        for key, value in summary["raster_info"].items():
            raster_table.add_row(key, str(value))

        console.print(raster_table)

    # Display band statistics in verbose mode
    if verbose and "band_statistics" in summary:
        console.print("\n[bold cyan]Band Statistics:[/bold cyan]")
        stats_table = Table(show_header=True, box=None)
        stats_table.add_column("Band", style="green")
        stats_table.add_column("Min", style="yellow")
        stats_table.add_column("Max", style="yellow")
        stats_table.add_column("Mean", style="yellow")
        stats_table.add_column("Std Dev", style="yellow")

        for stats in summary["band_statistics"]:
            stats_table.add_row(
                str(stats["band"]),
                str(stats["min"]),
                str(stats["max"]),
                str(stats["mean"]),
                str(stats["std"])
            )

        console.print(stats_table)

    # Display raster metadata in verbose mode
    if verbose and "metadata" in summary:
        console.print("\n[bold cyan]Metadata:[/bold cyan]")
        meta_table = Table(show_header=False, box=None, padding=(0, 2))
        meta_table.add_column("Key", style="cyan", no_wrap=True)
        meta_table.add_column("Value", style="white")

        for key, value in summary["metadata"].items():
            meta_table.add_row(key, str(value))

        console.print(meta_table)


if __name__ == "__main__":
    app()