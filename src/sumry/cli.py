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
    detect_file_type
)

app = typer.Typer(
    name="sumry",
    help="Summarize various data sources (CSV, Excel, GeoJSON, Shapefiles)",
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
    Summarize a data file (CSV, Excel, GeoJSON, or Shapefile).
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
        else:
            console.print(f"[bold red]Error:[/bold red] Handler not implemented for {file_type}")
            raise typer.Exit(1)
            
        display_summary(summary, file_type, verbose)
        
        # Display sample records if requested
        if sample is not None or show_sample:
            sample_count = sample if sample and sample > 0 else 5
            display_sample_records(file_path, file_type, sample_count)
        
    except Exception as e:
        console.print(f"[bold red]Error reading file:[/bold red] {str(e)}")
        raise typer.Exit(1)


def display_sample_records(file_path: Path, file_type: str, sample_count: int):
    """Display sample records from the file."""
    import pandas as pd
    import geopandas as gpd
    
    console.print(f"\n[bold cyan]Sample Records (first {sample_count}):[/bold cyan]")
    
    try:
        # Read the data based on file type
        if file_type == "CSV":
            df = pd.read_csv(file_path, nrows=sample_count)
        elif file_type == "Excel":
            df = pd.read_excel(file_path, nrows=sample_count)
        elif file_type in ["GeoJSON", "Shapefile"]:
            # For spatial files, use geopandas
            if file_type == "GeoJSON":
                gdf = gpd.read_file(file_path, rows=sample_count)
            else:  # Shapefile
                gdf = gpd.read_file(file_path, rows=sample_count)
            
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


if __name__ == "__main__":
    app()