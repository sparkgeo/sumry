import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd
from typer.testing import CliRunner

from sumry.cli import app
from sumry.readers import read_csv


class CsvTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'sample.csv'

    def test_utf8_and_bom_preserve_unicode(self):
        for encoding in ('utf-8', 'utf-8-sig'):
            with self.subTest(encoding=encoding):
                self.path.write_text('name,value\n森林,1\n', encoding=encoding)
                summary = read_csv(self.path, sample_count=1)
                self.assertEqual(summary['sample_data'], [{'name': '森林', 'value': 1}])
                self.assertEqual(summary['basic_info']['Encoding'], 'utf-8-sig')

    def test_windows1252_cli_fallback(self):
        self.path.write_text('name,value\nSøren’s forest,2\n', encoding='cp1252')
        for extra in ([], ['--json']):
            result = CliRunner().invoke(app, [str(self.path), '-n', '1', *extra])
            self.assertEqual(result.exit_code, 0, result.output)
            if extra:
                summary = json.loads(result.stdout)
                self.assertEqual(summary['sample_data'][0]['name'], 'Søren’s forest')
                self.assertEqual(summary['basic_info']['Encoding'], 'cp1252')
            else:
                self.assertIn('cp1252', result.stdout)

    def test_explicit_encoding_and_strict_failure(self):
        self.path.write_text('name\n森林\n', encoding='utf-16')
        result = CliRunner().invoke(app, [str(self.path), '--encoding', 'utf-16', '--json', '-n', '1'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout)['sample_data'], [{'name': '森林'}])
        result = CliRunner().invoke(app, [str(self.path), '--encoding', 'utf-8', '--json'])
        self.assertEqual(result.exit_code, 1)
        self.assertIn('decode', json.loads(result.stderr)['error'])

    def test_fallback_does_not_replace_undefined_bytes(self):
        self.path.write_bytes(b'name\n\x81\n')
        with self.assertRaises(UnicodeDecodeError):
            read_csv(self.path)

    def test_parser_errors_are_preserved(self):
        self.path.write_text('a,b\n1,2\n3,4,5\n')
        with self.assertRaises(pd.errors.ParserError):
            read_csv(self.path)

    def test_tsv_fallback(self):
        path = self.path.with_suffix('.TSV')
        path.write_text('name\tvalue\nSøren\t2\n', encoding='cp1252')
        self.assertEqual(read_csv(path, sample_count=1)['sample_data'], [{'name': 'Søren', 'value': 2}])
