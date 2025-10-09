from typing import Optional
import typer
from sumry.formats import XLSX

app = typer.Typer(help="A CLI tool for XLSX files.")


@app.command()
def info(
    file: str = typer.Argument(..., help="Source file."),
    layer: str = typer.Argument(None, help="Layer name."),
):
    xlsx = XLSX(file, layer=layer)
    xlsx.info()


@app.command()
def sample(
    file: str = typer.Argument(..., help="Source file."),
    layer: str = typer.Argument(None, help="Layer name."),
    count: int = typer.Option(5, "--count", "-n", help="Number of sample records to display."),
):
    xlsx = XLSX(file, layer=layer)
    xlsx.sample(count=count)


if __name__ == "__main__":
    app()
