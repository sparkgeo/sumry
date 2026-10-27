import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.layout import Layout
from rich.box import ROUNDED, DOUBLE_EDGE, MINIMAL_DOUBLE_HEAD
from rich.syntax import Syntax
from rich.text import Text
from rich.rule import Rule
from rich.columns import Columns
import warnings
import os
import json
import sys

from sumry.readers import (
    read_flatgeobuf,
    read_csv,
    read_excel,
    read_parquet,
    read_geojson,
    read_geopackage,
    read_shapefile,
    detect_file_type
)

from sumry.spatial_readers import read_raster, read_point_cloud, read_pmtiles

app = typer.Typer(
    name="sumry",
    help="Summarize various data sources (tables, vectors, rasters, point clouds, and tile archives)",
    add_completion=False
)

console = Console()


def show_formats(value: bool):
    if value:
        table = Table(title="Supported File Formats")
        table.add_column("Format")
        table.add_column("Extensions")
        table.add_row("CSV", ".csv, .tsv")
        table.add_row("Excel", ".xlsx, .xls, .xlsm")
        table.add_row("Parquet", ".parquet")
        table.add_row("GeoJSON", ".geojson, .json (GeoJSON content)")
        table.add_row("GeoPackage", ".gpkg")
        table.add_row("Shapefile", ".shp")
        table.add_row("GeoTIFF / COG / TIFF + worldfile", ".tif, .tiff")
        table.add_row("JPEG2000", ".jp2, .j2k, .jpx")
        table.add_row("LAS / LAZ / COPC", ".las, .laz, .copc")
        table.add_row("PMTiles", ".pmtiles (v3)")
        table.add_row("FlatGeobuf", ".fgb")
        console.print(table)
        raise typer.Exit()


@app.command()
def main(
    file_path: Path = typer.Argument(
        ...,
        help="Path to the file to summarize",
        exists=True
    ),
    formats: bool = typer.Option(
        False,
        "--formats",
        "-f",
        help="Show supported file formats and exit",
        callback=show_formats,
        is_eager=True
    ),
    verbose: bool = typer.Option(
        False, 
        "--verbose", 
        "-v",
        help="Show detailed information"
    ),
    select: Optional[str] = typer.Option(
        None,
        "--select",
        "-s",
        help="Select Excel sheets or GeoPackage layers by name or zero-based index, separated by commas"
    ),
    count: Optional[int] = typer.Option(
        None,
        "--count",
        "-n",
        help="Display N sample records in table format (default: 5)"
    ),
    encoding: Optional[str] = typer.Option(
        None,
        "--encoding",
        help="CSV/TSV encoding (default: UTF-8, falling back to Windows-1252)"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output results in JSON format"
    )
):
    """
    Summarize a table, vector file, raster, point cloud, or tile archive.
    """
    
    # Suppress warnings and verbose output in non-verbose mode
    if not verbose:
        warnings.filterwarnings('ignore')
        os.environ['PYOGRIO_USE_ARROW'] = '0'  # Suppress pyogrio Arrow warnings
    
    if not file_path.exists():
        if json_output:
            print(json.dumps({"error": f"File {file_path} does not exist"}), file=sys.stderr)
        else:
            console.print(f"[bold red]Error:[/bold red] File {file_path} does not exist")
        raise typer.Exit(1)
    
    file_type = detect_file_type(file_path)
    
    if not file_type:
        if json_output:
            print(json.dumps({"error": f"Unsupported file type for {file_path}"}), file=sys.stderr)
        else:
            console.print(f"[bold red]Error:[/bold red] Unsupported file type for {file_path}")
        raise typer.Exit(1)
    
    try:
        # Set default count to 5 if count option is used without value
        sample_count = 5 if count is not None and count <= 0 else count
        
        readers = {
            "CSV": read_csv, "Parquet": read_parquet, "GeoJSON": read_geojson,
            "Shapefile": read_shapefile, "FlatGeobuf": read_flatgeobuf,
            "Raster": read_raster, "Point Cloud": read_point_cloud,
            "PMTiles": read_pmtiles,
        }

        def read_summary():
            if encoding is not None and file_type != "CSV":
                raise ValueError("--encoding is only supported for CSV/TSV files")
            if file_type == "CSV":
                return read_csv(file_path, verbose, sample_count, encoding=encoding)
            if file_type == "Excel":
                return read_excel(file_path, verbose, select, sample_count)
            if file_type == "GeoPackage":
                return read_geopackage(file_path, verbose, select, sample_count)
            return readers[file_type](file_path, verbose, sample_count)

        if json_output:
            summary = read_summary()
        else:
            with console.status(f"Reading {file_type} file...", spinner="dots"):
                summary = read_summary()

        # Clear the line after loading (only for non-JSON output)
        if not json_output:
            console.print()
        
        if json_output:
            # Output as JSON
            print(json.dumps(summary, indent=2, default=str))
        else:
            display_summary(summary, file_type, verbose, sample_count)
        
    except Exception as e:
        if json_output:
            print(json.dumps({"error": f"Error reading file: {str(e)}"}), file=sys.stderr)
        else:
            console.print(f"[bold red]Error reading file:[/bold red] {str(e)}")
        raise typer.Exit(1)


def display_summary(summary: dict, file_type: str, verbose: bool, sample_count: Optional[int] = None):
    """Display the file summary using Rich formatting."""
    
    title_text = Text(f"📊 {file_type} File Summary", style="bold magenta")
    panel = Panel(
        title_text,
        border_style="bright_cyan",
        box=DOUBLE_EDGE,
        padding=(1, 2)
    )
    console.print(panel)
    console.print()
    
    table = Table(
        show_header=False, 
        box=MINIMAL_DOUBLE_HEAD, 
        padding=(0, 2),
        title="[bold cyan]📋 File Information[/bold cyan]",
        title_style="bold",
        border_style="bright_blue"
    )
    table.add_column("Property", style="bright_cyan", no_wrap=True)
    table.add_column("Value", style="bright_white")
    
    for key, value in summary.get("basic_info", {}).items():
        if isinstance(value, (list, dict)):
            value_str = str(value)
        else:
            value_str = str(value)
        
        # Style different value types
        if isinstance(value, (int, float)):
            value_text = Text(value_str, style="bold yellow")
        elif isinstance(value, bool):
            value_text = Text(value_str, style="bold green" if value else "bold red")
        else:
            value_text = Text(value_str, style="bright_white")
        
        key_text = Text(key, style="bright_cyan")
        table.add_row(key_text, value_text)
    
    console.print(table)
    
    # Handle multiple sheets if present
    if "sheets" in summary or "layers" in summary:
        collection = "layers" if "layers" in summary else "sheets"
        console.print(Rule(f"[bold bright_magenta]📑 {collection.title()}[/bold bright_magenta]", style="bright_magenta"))
        for sheet_name, sheet_summary in summary[collection].items():
            if collection == "layers":
                display_summary(sheet_summary, f"GeoPackage Layer: {sheet_name}", verbose, sample_count)
                continue
            sheet_panel = Panel(
                f"[bold bright_yellow]📄 {sheet_name}[/bold bright_yellow]",
                border_style="yellow",
                box=ROUNDED,
                expand=False
            )
            console.print(sheet_panel)
            _display_sheet_summary(sheet_summary, verbose, sample_count)
        return
    
    # Single sheet/file display
    _display_sheet_summary(summary, verbose, sample_count)


def _display_sheet_summary(summary: dict, verbose: bool, sample_count: Optional[int] = None):
    """Display summary for a single sheet or file."""
    for section in ("spatial_info", "sampling_info", "metadata"):
        if section in summary:
            table = Table(title=section.replace("_", " ").title(), box=ROUNDED)
            table.add_column("Property")
            table.add_column("Value")
            for key, value in summary[section].items():
                table.add_row(Text(str(key)), Text(str(value)))
            console.print(table)
    if summary.get("bands"):
        table = Table(title="Bands", box=ROUNDED)
        keys = list(summary["bands"][0])
        for key in keys:
            table.add_column(key)
        for band in summary["bands"]:
            table.add_row(*(Text(str(band[key])) for key in keys))
        console.print(table)

    if "columns" in summary and summary["columns"]:
        console.print(Rule("[bold bright_cyan]🔤 Columns/Fields[/bold bright_cyan]", style="bright_cyan"))
        col_table = Table(
            show_header=True, 
            box=ROUNDED,
            border_style="bright_green",
            header_style="bold white"
        )
        col_table.add_column("#", style="dim white", width=4)
        col_table.add_column("Name", style="bold green")
        col_table.add_column("Type", style="bold yellow")
        
        if verbose and "sample_values" in summary:
            col_table.add_column("Sample Values", style="bright_white", overflow="fold")
            
        for idx, col_info in enumerate(summary["columns"], 1):
            if verbose and "sample_values" in summary:
                sample = summary["sample_values"].get(col_info["name"], [])
                sample_str = " | ".join(f"[italic]{str(v)}[/italic]" for v in sample[:3])
                col_table.add_row(
                    str(idx),
                    Text(col_info["name"], style="bold green"),
                    Text(col_info["type"], style="yellow"),
                    sample_str
                )
            else:
                col_table.add_row(
                    str(idx),
                    Text(col_info["name"], style="bold green"),
                    Text(col_info["type"], style="yellow")
                )
        
        console.print(col_table)
    
    if verbose and "statistics" in summary:
        console.print(Rule("[bold bright_magenta]📈 Statistics[/bold bright_magenta]", style="bright_magenta"))
        stats_table = Table(
            show_header=True,
            box=ROUNDED,
            border_style="bright_magenta",
            header_style="bold"
        )
        stats_table.add_column("Column", style="bold green")
        stats_table.add_column("Min", style="cyan")
        stats_table.add_column("Max", style="cyan")
        stats_table.add_column("Mean", style="yellow")
        stats_table.add_column("Unique", style="bright_magenta")
        if "sampling_info" in summary:
            stats_table.add_column("Std Dev")
            stats_table.add_column("Valid %")
        
        for col_name, stats in summary["statistics"].items():
            min_val = str(stats.get("min", "N/A"))
            max_val = str(stats.get("max", "N/A"))
            mean_val = str(stats.get("mean", "N/A"))
            unique_val = str(stats.get("unique", "N/A"))
            
            # Format numbers nicely
            if mean_val != "N/A" and "." in mean_val:
                try:
                    mean_val = f"{float(mean_val):.2f}"
                except:
                    pass
            
            stats_table.add_row(
                Text(col_name, style="bold green"),
                Text(min_val, style="cyan"),
                Text(max_val, style="cyan"),
                Text(mean_val, style="yellow"),
                Text(unique_val, style="bright_magenta"),
                *([str(stats.get("std", "N/A")), str(stats.get("valid_percent", "N/A"))]
                  if "sampling_info" in summary else [])
            )
        
        console.print(stats_table)
    
    if "geometry_info" in summary:
        console.print(Rule("[bold bright_blue]🌍 Geometry Information[/bold bright_blue]", style="bright_blue"))
        geo_table = Table(
            show_header=False,
            box=ROUNDED,
            padding=(0, 2),
            border_style="bright_blue"
        )
        geo_table.add_column("Property", style="bold cyan", no_wrap=True)
        geo_table.add_column("Value", style="bright_white")
        
        for key, value in summary["geometry_info"].items():
            key_text = Text(key, style="bold cyan")
            value_text = Text(str(value), style="bright_yellow" if isinstance(value, (int, float)) else "bright_white")
            geo_table.add_row(key_text, value_text)
        
        console.print(geo_table)
    
    # Display sample data if count option is used
    if sample_count is not None and "sample_data" in summary:
        console.print(Rule(f"[bold bright_yellow]📝 Sample Records (showing {len(summary['sample_data'])})[/bold bright_yellow]", style="bright_yellow"))
        _display_sample_records(summary["sample_data"])


def _sample_value(value) -> Text:
    """Render source values literally, preserving their existing type colors."""
    if isinstance(value, bool):
        return Text(str(value), style="bold green" if value else "bold red")
    if isinstance(value, (int, float)):
        return Text(str(value), style="bold yellow")
    if isinstance(value, str) and value == "":
        return Text("null", style="dim italic")
    return Text(str(value))


def _display_sample_records(records: list[dict]):
    if not records:
        console.print(Text("No sample records.", style="dim"))
        return

    columns = list(dict.fromkeys(key for row in records for key in row))
    headers = [Text(str(column)) for column in columns]
    rows = [[_sample_value(row.get(column, "")) for column in columns] for row in records]
    # Include padding and borders when checking whether all values fit naturally.
    widths = [
        max(line.cell_len for cell in [header, *(row[index] for row in rows)]
            for line in cell.split("\n"))
        for index, header in enumerate(headers)
    ]
    wide = sum(widths) + 3 * len(columns) + 1 > console.width

    def make_table(**kwargs):
        return Table(box=ROUNDED, border_style="bright_yellow",
                     header_style="bold yellow", show_lines=True, **kwargs)

    if wide:
        for index, row in enumerate(rows, 1):
            table = make_table(title=f"Record {index}")
            table.add_column("Field", style="bold yellow", overflow="fold",
                             max_width=max(1, (console.width - 7) // 3))
            table.add_column("Value", style="bright_white", overflow="fold", ratio=1)
            for header, value in zip(headers, row):
                table.add_row(header, value)
            console.print(table)
    else:
        table = make_table(row_styles=["none", "dim"])
        for header in headers:
            table.add_column(header, style="bright_white", overflow="fold")
        for row in rows:
            table.add_row(*row)
        console.print(table)



if __name__ == "__main__":
    app()
