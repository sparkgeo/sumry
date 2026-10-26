import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd
from typer.testing import CliRunner

from sumry.cli import app
from sumry.readers import detect_file_type, read_csv, read_parquet


class ParquetTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sample.parquet"
        self.frame = pd.DataFrame({
            "name": ["Ada", "Ben", "Ada"],
            "score": [10.0, None, 30.0],
            "active": [True, False, True],
            "missing": pd.Series([None] * 3, dtype="string"),
            "date": pd.to_datetime(["2025-01-01", None, "2025-01-03"]),
        })
        self.frame.to_parquet(self.path, index=False)
        self.runner = CliRunner()

    def test_detection(self):
        for name in ["data.parquet", "DATA.PARQUET"]:
            self.assertEqual(detect_file_type(Path(name)), "Parquet")

    def test_summary_statistics_and_samples(self):
        summary = read_parquet(self.path, verbose=True, sample_count=2)
        self.assertEqual(summary["basic_info"]["Rows"], 3)
        self.assertEqual(summary["basic_info"]["Columns"], 5)
        self.assertEqual([c["name"] for c in summary["columns"]], list(self.frame.columns))
        self.assertEqual(summary["statistics"]["score"], {
            "min": 10.0, "max": 30.0, "mean": 20.0, "unique": 2,
        })
        self.assertEqual(summary["statistics"]["name"]["most_common"], "Ada")
        self.assertIsNone(summary["statistics"]["missing"]["most_common"])
        self.assertEqual(len(summary["sample_data"]), 2)
        self.assertNotIn("sample_data", read_parquet(self.path))

    def test_empty_file(self):
        self.frame.iloc[:0].to_parquet(self.path, index=False)
        summary = read_parquet(self.path, verbose=True, sample_count=5)
        self.assertEqual(summary["basic_info"]["Rows"], 0)
        self.assertEqual(summary["sample_data"], [])
        self.assertIsNone(summary["statistics"]["score"]["min"])

    def test_cli_json_and_terminal(self):
        for extra in [[], ["--json"]]:
            result = self.runner.invoke(app, [str(self.path), "-v", "-n", "2", *extra])
            self.assertEqual(result.exit_code, 0, result.output)
            if extra:
                summary = json.loads(result.stdout)
                self.assertEqual(len(summary["sample_data"]), 2)
                self.assertEqual(summary["basic_info"]["Rows"], 3)
            else:
                self.assertIn("Parquet File Summary", result.stdout)
                self.assertIn("Sample Records", result.stdout)

    def test_formats_and_invalid_file(self):
        result = self.runner.invoke(app, ["--formats"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(".parquet", result.stdout)
        self.path.write_text("not parquet")
        result = self.runner.invoke(app, [str(self.path), "--json"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error reading file", json.loads(result.stderr)["error"])

    def test_csv_summary_regression(self):
        path = self.path.with_suffix(".csv")
        self.frame[["name", "score"]].to_csv(path, index=False)
        summary = read_csv(path, verbose=True, sample_count=1)
        self.assertEqual(summary["basic_info"]["Rows"], 3)
        self.assertEqual(summary["statistics"]["score"]["mean"], 20.0)
        self.assertEqual(summary["sample_data"], [{"name": "Ada", "score": 10.0}])


if __name__ == "__main__":
    unittest.main()
