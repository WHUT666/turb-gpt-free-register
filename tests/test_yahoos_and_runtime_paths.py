# -*- coding: utf-8 -*-
import unittest

from config.runtime_paths import data_root, is_frozen, resource_root
from core.email_provider import parse_email_sources
from core.yahoos_client import generate_local_part


class RuntimePathsTests(unittest.TestCase):
    def test_roots_exist_in_source_mode(self):
        self.assertFalse(is_frozen())
        self.assertTrue((resource_root() / "config").is_dir())
        self.assertEqual(data_root(), resource_root())


class YahoosDefaultsTests(unittest.TestCase):
    def test_yahoos_is_valid_email_source(self):
        self.assertEqual(parse_email_sources("yahoos"), ["yahoos"])

    def test_faker_local_part_shape(self):
        local = generate_local_part()
        self.assertRegex(local, r"^[a-z][a-z0-9]{2,31}$")
        self.assertTrue(local[-4:].isdigit())


if __name__ == "__main__":
    unittest.main()
