from io import StringIO
import unittest
from unittest.mock import patch

from rich.console import Console

from sumry.cli import _display_sample_records


class SampleDisplayTests(unittest.TestCase):
    def render(self, records, width=80):
        output = StringIO()
        with patch('sumry.cli.console', Console(file=output, width=width, color_system=None)):
            _display_sample_records(records)
        result = output.getvalue()
        self.assertTrue(all(len(line) <= width for line in result.splitlines()))
        return result

    def test_wide_records_preserve_every_field_and_value(self):
        records = [{f'column_{i}': f'value_{r}_{i}' for i in range(20)} for r in range(2)]
        for width in (40, 80, 120):
            with self.subTest(width=width):
                output = self.render(records, width)
                self.assertIn('Record 1', output)
                self.assertIn('Record 2', output)
                for row in records:
                    for field, value in row.items():
                        self.assertIn(field, output)
                        self.assertIn(value, output)

    def test_small_sample_stays_tabular_and_markup_is_literal(self):
        output = self.render([{'name': '[red]Ada[/red]', 'score': 42}])
        self.assertNotIn('Record 1', output)
        self.assertIn('[red]Ada[/red]', output)
        self.assertIn('42', output)

    def test_long_value_wraps_without_losing_characters(self):
        value = 'abcdefghijklmnopqrstuvwxyz' * 10
        output = self.render([{'description': value}], width=40)
        value_lines = [line.split('│')[2].strip() for line in output.splitlines()
                       if line.startswith('│')][1:]
        self.assertEqual(''.join(value_lines), value)

    def test_empty_sample(self):
        self.assertIn('No sample records.', self.render([]))
