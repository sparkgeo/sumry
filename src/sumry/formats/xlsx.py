import os
from typing import Final
from pathlib import Path
from rich.console import Console
from rich.table import Table

import duckdb

from .base import BaseFormat
# from ..timing import timing, Timer


class XLSX(BaseFormat):
    verbose_name: Final = "Excel Open XML Spreadsheet"
    format: Final = "xlsx"
    _wb = None


    def __init__(self, file, layer=None, *args, **kwargs):
        self.file = Path(file)
        self.layer = layer

    # def _load(self, sheet_name, nrows=None):
    #     if not self._wb:
    #         self._wb =  CalamineWorkbook.from_path(self.file)

    #     return self._wb

    def _sheet_names(self):
        return self._wb.sheet_names

    def _get_fields(self, sheet_name: str):
        df = self._read_xlsx(self.file, num_rows=0, sheet_name=sheet_name)
        return df.dtypes

    @property
    def name(self):
        return self.file.name
    
    @property
    def size(self):
        return os.path.getsize(self.file)
    
    # def record_count(self, sheet):
    #     workbook = load_workbook(filename=self.file, read_only=True)
    #     sheet = workbook[sheet] if sheet else workbook.active
    #     return sheet.max_row

    def info(self, *args, **kwargs):
        # meta = super().metadata(*args, **kwargs)

        duckdb.install_extension('spatial')
        duckdb.load_extension('spatial')
        
        sheet_names_query = f"""
            SELECT * FROM st_read('{self.file}', layer='')
        """

        # Execute the query
        result = duckdb.sql(sheet_names_query).df()

        # Display sheet names
        print(result)
    
    def sample(self, count: int = 5, *args, **kwargs):
        duckdb.install_extension('spatial')
        duckdb.load_extension('spatial')
        
        console = Console()
        
        # If no layer specified, list available layers
        if not self.layer:
            sheet_names_query = f"""
                SELECT * FROM st_read('{self.file}', layer='')
            """
            result = duckdb.sql(sheet_names_query).df()
            console.print("\n[bold]Available layers:[/bold]")
            for idx, row in result.iterrows():
                console.print(f"  {idx}: {row['layer_name']}")
            console.print("\n[yellow]Please specify a layer using the layer argument[/yellow]")
            return
        
        # Read sample data from the specified layer
        try:
            sample_query = f"""
                SELECT * FROM st_read('{self.file}', layer='{self.layer}')
                LIMIT {count}
            """
            df = duckdb.sql(sample_query).df()
            
            if df.empty:
                console.print(f"[yellow]No data found in layer '{self.layer}'[/yellow]")
                return
            
            # Create a Rich table
            table = Table(title=f"Sample data from '{self.layer}' (showing {min(count, len(df))} of {count} requested records)")
            
            # Add columns to the table
            for col in df.columns:
                table.add_column(col, style="cyan", no_wrap=False)
            
            # Add rows to the table
            for _, row in df.iterrows():
                row_data = []
                for col in df.columns:
                    value = row[col]
                    # Check if column name suggests geometry or if value looks like geometry
                    if 'geom' in col.lower() or 'geometry' in col.lower():
                        row_data.append("<geometry>")
                    elif isinstance(value, (bytes, str)) and (
                        (isinstance(value, str) and (value.startswith('POLYGON') or value.startswith('POINT') or 
                         value.startswith('LINE') or value.startswith('MULTI'))) or
                        (isinstance(value, bytes))
                    ):
                        row_data.append("<geometry>")
                    else:
                        row_data.append(str(value) if value is not None else "")
                table.add_row(*row_data)
            
            console.print()
            console.print(table)
            console.print()
            
        except Exception as e:
            console.print(f"[red]Error reading data from layer '{self.layer}': {e}[/red]")




    #     if not self.layer:
    #         print("Layers available:")
    #         for n, sheet_name in  enumerate(self._sheet_names()):
    #             print(f"{n}: {sheet_name}")
            
    #         return

    #     print()
    #     print(f"Name: {self.file.name}")
    #     print(f"Size: {self.size}")
    #     print(f"\tSheet Name: {self.layer}")

    #     df = self._load(self.layer)

    #     print(f"\tRecord Count: {len(df.index)}")
    

    # def sample_data(self, sample_size: int = 20, *args, **kwargs):
    #     self._load(nrows=sample_size)
    #     return self._pd
