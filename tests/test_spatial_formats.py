import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import geopandas as gpd
import laspy
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.shutil import copy as raster_copy
from shapely.geometry import Point
from typer.testing import CliRunner
from pmtiles.writer import write
from pmtiles.tile import Compression, TileType

from sumry.cli import app
from sumry.readers import detect_file_type, read_flatgeobuf
from sumry.spatial_readers import read_raster, read_point_cloud, read_pmtiles


class SpatialTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def raster(self, name='image.tif', driver='GTiff', **extra):
        path = self.root / name
        options = dict(driver=driver, width=4, height=3, count=1, dtype='uint16',
                       crs='EPSG:32610', transform=from_origin(480000, 5450000, 10, 10))
        options.update(extra)
        with rasterio.open(path, 'w', **options) as dst:
            dst.write(np.arange(12, dtype='uint16').reshape(1, 3, 4))
        return path

    def cloud(self, suffix='.las', empty=False):
        path = self.root / ('points' + suffix)
        las = laspy.create(point_format=6, file_version='1.4')
        if not empty:
            las.x = [100.25, 101.5, 102.75]
            las.y = [200, 201, 202]
            las.z = [10, 20, 30]
            las.classification = [2, 2, 6]
        las.write(path)
        return path

    def tiles(self):
        path = self.root / 'map.pmtiles'
        with write(path) as writer:
            writer.write_tile(0, b'tile')
            writer.write_tile(1, b'tile')
            writer.finalize({'tile_type': TileType.MVT, 'tile_compression': Compression.NONE},
                            {'vector_layers': [{'id': 'roads'}]})
        return path

    def test_extensions(self):
        for extension, kind in [('tif', 'Raster'), ('TIFF', 'Raster'), ('jp2', 'Raster'),
                                ('j2k', 'Raster'), ('copc.laz', 'Point Cloud'), ('las', 'Point Cloud'),
                                ('pmtiles', 'PMTiles'), ('FGB', 'FlatGeobuf')]:
            self.assertEqual(detect_file_type(Path('file.' + extension)), kind)

    def test_raster_stats_masks_and_samples(self):
        path = self.raster(nodata=0)
        summary = read_raster(path, True, 2)
        self.assertEqual(summary['statistics']['Band 1']['mean'], 6)
        self.assertEqual(summary['statistics']['Band 1']['min'], 1)
        self.assertEqual(summary['sample_data'][0]['x'], 480005)
        self.assertEqual(summary['sample_data'][0]['y'], 5449995)
        self.assertIsNone(summary['sample_data'][0]['Band 1'])
        self.assertEqual(summary['sample_data'][1]['Band 1'], 11)
        self.assertNotIn('statistics', read_raster(path))
        json.dumps(summary, allow_nan=False)

    def test_all_nodata_and_bounded_stats(self):
        path = self.raster(nodata=0)
        with rasterio.open(path, 'r+') as dst:
            dst.write(np.zeros((1, 3, 4), dtype='uint16'))
        with patch('sumry.spatial_readers.STAT_SAMPLE_LIMIT', 4):
            summary = read_raster(path, True)
        self.assertLessEqual(summary['sampling_info']['Pixels Per Band'], 4)
        self.assertIsNone(summary['statistics']['Band 1']['mean'])
        json.dumps(summary, allow_nan=False)

    def test_cog_content_detection(self):
        source = self.raster()
        path = self.root / 'ordinary-name.tif'
        raster_copy(source, path, driver='COG')
        self.assertEqual(read_raster(path)['basic_info']['Format'], 'COG')
        self.assertEqual(read_raster(source)['basic_info']['Format'], 'GTiff')

    def test_worldfile_and_prj(self):
        path = self.raster(crs=None, transform=rasterio.Affine.identity())
        path.with_suffix('.tfw').write_text('10\n0\n0\n-10\n480005\n5449995\n')
        # Remove the identity transform embedded by the fixture writer.
        plain = self.root / 'plain.tiff'
        with rasterio.open(plain, 'w', driver='GTiff', width=4, height=3, count=1, dtype='uint8') as dst:
            dst.write(np.ones((1, 3, 4), dtype='uint8'))
        plain.with_suffix('.tfw').write_text(path.with_suffix('.tfw').read_text())
        summary = read_raster(plain)
        self.assertEqual(summary['spatial_info']['Bounds (left, bottom, right, top)'], [480000, 5449970, 480040, 5450000])
        self.assertIsNone(summary['basic_info']['CRS'])
        plain.with_suffix('.prj').write_text(rasterio.crs.CRS.from_epsg(32610).to_wkt())
        self.assertEqual(read_raster(plain)['basic_info']['CRS'], 'EPSG:32610')

    def test_jpeg2000(self):
        path = self.raster('image.jp2', driver='JP2OpenJPEG', REVERSIBLE='YES', QUALITY=100)
        summary = read_raster(path, True, 1)
        self.assertEqual(summary['basic_info']['Format'], 'JP2OpenJPEG')
        self.assertEqual(summary['statistics']['Band 1']['max'], 11)

    def test_las_laz(self):
        for extension in ('.las', '.laz'):
            path = self.cloud(extension)
            summary = read_point_cloud(path, True, 2)
            self.assertEqual(summary['basic_info']['Points'], 3)
            self.assertEqual(summary['statistics']['z']['mean'], 20)
            self.assertEqual(summary['sample_data'][0]['x'], 100.25)
            self.assertEqual(summary['sample_data'][1]['classification'], 2)
            json.dumps(summary, allow_nan=False)
            self.assertNotIn('sample_data', read_point_cloud(path))

    def test_empty_cloud(self):
        summary = read_point_cloud(self.cloud(empty=True), True, 3)
        self.assertEqual(summary['sample_data'], [])
        self.assertIsNone(summary['spatial_info']['Minimum (x, y, z)'])

    def test_pmtiles(self):
        summary = read_pmtiles(self.tiles(), True, 5)
        self.assertEqual(summary['basic_info']['Addressed Tiles'], 2)
        self.assertEqual(summary['basic_info']['Tile Contents'], 1)
        self.assertEqual(summary['sample_data'], [
            {'z': 0, 'x': 0, 'y': 0, 'Stored Bytes': 4},
            {'z': 1, 'x': 0, 'y': 0, 'Stored Bytes': 4}])
        self.assertEqual(summary['metadata']['vector_layers'][0]['id'], 'roads')
        json.dumps(summary, allow_nan=False)

    def test_pmtiles_uncompressed_directories(self):
        import gzip
        from pmtiles.tile import deserialize_header, serialize_header
        path = self.tiles()
        data = path.read_bytes()
        header = deserialize_header(data[:127])
        root = gzip.decompress(data[header['root_offset']:header['root_offset'] + header['root_length']])
        metadata = gzip.decompress(data[header['metadata_offset']:header['metadata_offset'] + header['metadata_length']])
        tiles = data[header['tile_data_offset']:]
        header.update(internal_compression=Compression.NONE, root_length=len(root),
                      metadata_offset=127 + len(root), metadata_length=len(metadata),
                      leaf_directory_offset=127 + len(root) + len(metadata),
                      tile_data_offset=127 + len(root) + len(metadata))
        path.write_bytes(serialize_header(header) + root + metadata + tiles)
        summary = read_pmtiles(path, True, 2)
        self.assertEqual(len(summary['sample_data']), 2)
        self.assertEqual(summary['metadata']['vector_layers'][0]['id'], 'roads')

    def test_multiband_raster_mask(self):
        path = self.root / 'multiband.tif'
        with rasterio.open(path, 'w', driver='GTiff', width=2, height=2, count=2,
                           dtype='float32', transform=from_origin(10, 20, 1, 1)) as dst:
            dst.write(np.array([[[1, 2], [3, 4]], [[10, 20], [30, 40]]], dtype='float32'))
            dst.write_mask(np.array([[0, 255], [255, 255]], dtype='uint8'))
        summary = read_raster(path, True, 2)
        self.assertEqual(len(summary['bands']), 2)
        self.assertEqual(summary['statistics']['Band 2']['mean'], 30)
        self.assertEqual(summary['statistics']['Band 1']['valid_percent'], 75)
        self.assertIsNone(summary['sample_data'][0]['Band 2'])
        self.assertEqual(summary['sample_data'][1]['Band 2'], 40)

    def test_point_cloud_bounded_statistics(self):
        with patch('sumry.spatial_readers.STAT_SAMPLE_LIMIT', 2):
            summary = read_point_cloud(self.cloud(), True, 3)
        self.assertEqual(len(summary['sample_data']), 3)
        self.assertEqual(summary['statistics']['z']['mean'], 15)
        self.assertEqual(summary['sampling_info']['Statistics Points'], 2)
        self.assertEqual(summary['sampling_info']['Statistics Method'], 'Approximate prefix sample')

    def test_flatgeobuf(self):
        path = self.root / 'points.fgb'
        gpd.GeoDataFrame({'name': ['A', 'B']}, geometry=[Point(1, 2), Point(3, 4)], crs=4326).to_file(path, driver='FlatGeobuf')
        summary = read_flatgeobuf(path, True, 1)
        self.assertEqual(summary['basic_info']['Features'], 2)
        self.assertEqual(len(summary['sample_data']), 1)
        self.check_cli(path)

    def check_cli(self, path):
        for mode in ([], ['--json']):
            result = CliRunner().invoke(app, [str(path), '-v', '-n', '2', *mode])
            self.assertEqual(result.exit_code, 0, result.output)
            if mode:
                self.assertIn('basic_info', json.loads(result.stdout))
            else:
                self.assertIn('Sample Records', result.stdout)

    def test_cli(self):
        for path in (self.raster(), self.cloud(), self.tiles()):
            self.check_cli(path)

    def test_corrupt_files(self):
        for extension in ('tif', 'las', 'pmtiles', 'fgb'):
            path = self.root / ('bad.' + extension)
            path.write_bytes(b'not a valid file')
            result = CliRunner().invoke(app, [str(path), '--json'])
            self.assertEqual(result.exit_code, 1)
            self.assertIn('Error reading file', json.loads(result.stderr)['error'])
