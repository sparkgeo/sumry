import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.geometry import Point, LineString
from typer.testing import CliRunner

from sumry.cli import app
from sumry.readers import detect_file_type, read_geopackage, read_geojson


class GeoPackageTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sample.gpkg"
        self.points = gpd.GeoDataFrame(
            {"name": ["A", "B"], "value": [10, 20]},
            geometry=[Point(1, 2), Point(3, 4)], crs="EPSG:4326",
        )
        self.points.to_file(self.path, layer="places", driver="GPKG", engine="pyogrio")
        gpd.GeoDataFrame(
            {"name": ["road"]}, geometry=[LineString([(0, 0), (3, 4)])], crs="EPSG:3857",
        ).to_file(self.path, layer="roads", driver="GPKG", engine="pyogrio")
        self.runner = CliRunner()

    def test_detection_and_default_summary(self):
        self.assertEqual(detect_file_type(Path("DATA.GPKG")), "GeoPackage")
        summary = read_geopackage(self.path, verbose=True, sample_count=1)
        self.assertEqual(summary["basic_info"]["Layer"], "places")
        self.assertEqual(summary["basic_info"]["Total Layers"], 2)
        self.assertEqual(summary["basic_info"]["Features"], 2)
        self.assertEqual(summary["basic_info"]["CRS"], "EPSG:4326")
        self.assertEqual(summary["statistics"]["value"]["mean"], 15)
        self.assertEqual(summary["sample_data"], [{"name": "A", "value": 10}])
        self.assertEqual(summary["geometry_info"]["Geometry Types"], "Point: 2")

    def test_selection(self):
        summary = read_geopackage(self.path, select="roads")
        self.assertEqual(summary["geometry_info"]["Total Length"], "5.000000")
        self.assertEqual(read_geopackage(self.path, select="1"), summary)
        summary = read_geopackage(self.path, select=" roads,0,roads ")
        self.assertEqual(list(summary["layers"]), ["roads", "places"])
        for selection in ["missing", "99", "places,missing", ""]:
            with self.assertRaisesRegex(ValueError, "Available layers"):
                read_geopackage(self.path, select=selection)

    def test_empty_null_and_attribute_layers(self):
        self.points.iloc[:0].to_file(self.path, layer="empty", driver="GPKG", engine="pyogrio")
        summary = read_geopackage(self.path, select="empty", verbose=True, sample_count=5)
        self.assertEqual(summary["basic_info"]["Features"], 0)
        self.assertEqual(summary["sample_data"], [])
        nulls = self.points.copy()
        nulls.geometry = [None, None]
        nulls.to_file(self.path, layer="nulls", driver="GPKG", engine="pyogrio")
        self.assertEqual(read_geopackage(self.path, select="nulls")["geometry_info"]["Total Area"], "N/A")
        pyogrio.write_dataframe(pd.DataFrame({"label": ["one", "two"]}), self.path, layer="attributes", driver="GPKG")
        summary = read_geopackage(self.path, select="attributes", verbose=True, sample_count=1)
        self.assertEqual(summary["basic_info"]["Rows"], 2)
        self.assertNotIn("geometry_info", summary)

    def test_cli(self):
        for selection in ["places", "places,roads"]:
            for extra in [[], ["--json"]]:
                result = self.runner.invoke(app, [str(self.path), "-s", selection, "-v", "-n", "1", *extra])
                self.assertEqual(result.exit_code, 0, result.output)
                if extra:
                    summary = json.loads(result.stdout)
                    self.assertIn("layers" if "," in selection else "geometry_info", summary)
                else:
                    self.assertIn("GeoPackage", result.stdout)
                    self.assertIn("EPSG:4326", result.stdout)
        self.assertIn(".gpkg", self.runner.invoke(app, ["--formats"]).stdout)
        result = self.runner.invoke(app, [str(self.path), "-s", "missing", "--json"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Available layers", json.loads(result.stderr)["error"])
        self.path.write_text("invalid")
        result = self.runner.invoke(app, [str(self.path), "--json"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error reading file", json.loads(result.stderr)["error"])

    def test_geojson_regression(self):
        path = self.path.with_suffix(".geojson")
        self.points.to_file(path, driver="GeoJSON")
        summary = read_geojson(path, verbose=True, sample_count=1)
        self.assertEqual(summary["basic_info"]["Features"], 2)
        self.assertEqual(summary["geometry_info"]["Geometry Types"], "Point: 2")
        self.assertEqual(summary["statistics"]["value"]["mean"], 15)


if __name__ == "__main__":
    unittest.main()
