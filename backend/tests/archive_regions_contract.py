"""Offline archive address contracts; runnable without a database or network."""
import hashlib
import importlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "app/data/regions"
KEYS = ("address_province", "address_city", "address_detail")


class ArchiveRegionsContract(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("app.services.archive_regions"),
            "archive_regions service must exist",
        )
        self.service = importlib.import_module("app.services.archive_regions")

    def assert_invalid(self, values, expected_fields):
        with self.assertRaises(HTTPException) as caught:
            self.service.validate_archive_address(values)
        exc = caught.exception
        self.assertEqual(exc.status_code, 422)
        self.assertEqual(exc.detail["code"], "FIELD_POLICY_VALIDATION_FAILED")
        fields = exc.detail["fields"]
        self.assertEqual({item["field_key"] for item in fields}, set(expected_fields))
        self.assertEqual(len(fields), len(expected_fields))
        for item in fields:
            self.assertEqual(set(item), {"field_key", "message"})
            self.assertTrue(isinstance(item["message"], str) and item["message"].strip())

    def test_offline_dataset_shape_and_scope(self):
        self.service._load_regions.cache_clear()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            regions = self.service.get_archive_regions()
        self.assertEqual(len(regions), 31)
        self.assertEqual(len({p["value"] for p in regions}), 31)
        self.assertFalse({"71", "81", "82"} & {p["value"] for p in regions})
        all_cities = []
        for province in regions:
            self.assertEqual(set(province), {"value", "label", "children"})
            self.assertRegex(province["value"], r"^\d{2}$")
            self.assertTrue(province["label"] and province["children"])
            for city in province["children"]:
                self.assertEqual(set(city), {"value", "label"})
                self.assertRegex(city["value"], r"^\d{4}(?:\d{2})?$")
                self.assertTrue(city["value"].startswith(province["value"]))
                self.assertTrue(city["label"])
                all_cities.append(city["value"])
        self.assertEqual(len(all_cities), len(set(all_cities)))

    def test_known_cities_and_municipality_labels(self):
        regions = {p["value"]: p for p in self.service.get_archive_regions()}
        for province, city, label in (
            ("11", "1101", "北京市"), ("12", "1201", "天津市"),
            ("31", "3101", "上海市"), ("50", "5001", "重庆市"),
            ("50", "5002", "重庆市（县）"), ("44", "4403", "深圳市"),
        ):
            self.assertIn({"value": city, "label": label}, regions[province]["children"])

    def test_direct_counties_use_real_codes_not_group_placeholders(self):
        regions = {p["value"]: p for p in self.service.get_archive_regions()}
        for province, city, label in (
            ("41", "419001", "济源市"), ("42", "429004", "仙桃市"),
            ("42", "429021", "神农架林区"), ("46", "469021", "定安县"),
            ("65", "659001", "石河子市"), ("65", "659012", "白杨市"),
        ):
            self.assertIn({"value": city, "label": label}, regions[province]["children"])
            self.assertNotIn(city[:4], {c["value"] for c in regions[province]["children"]})

    def test_returned_data_cannot_poison_later_validation(self):
        regions = self.service.get_archive_regions()
        regions[0]["children"].append({"value": "fake", "label": "fake"})
        regions[0]["label"] = "changed"
        self.assertEqual(self.service.get_archive_regions()[0]["label"], "北京市")
        self.assert_invalid(dict(zip(KEYS, ("11", "fake", "road"))), [KEYS[1]])

    def test_all_empty_is_optional(self):
        for empty in (None, "", " \t\n", "\u3000"):
            self.assertIsNone(self.service.validate_archive_address(dict.fromkeys(KEYS, empty)))
        self.assertIsNone(self.service.validate_archive_address({"other": "unchanged"}))

    def test_every_partial_combination_reports_missing_fields(self):
        full = ("44", "4403", "南山区科技园")
        for present in itertools.product((False, True), repeat=3):
            if all(present) or not any(present):
                continue
            with self.subTest(present=present):
                values = {key: value for key, value, include in zip(KEYS, full, present) if include}
                self.assert_invalid(values, [key for key, include in zip(KEYS, present) if not include])

    def test_whitespace_is_stripped_without_mutating_caller(self):
        values = dict(zip(KEYS, (" 44 ", "\t4403 ", " 科技园 ")))
        before = values.copy()
        self.assertIsNone(self.service.validate_archive_address(values))
        self.assertEqual(values, before)
        values[KEYS[2]] = " \t\u3000"
        self.assert_invalid(values, [KEYS[2]])

    def test_unknown_province_and_city(self):
        self.assert_invalid(dict(zip(KEYS, ("99", "4403", "road"))), [KEYS[0]])
        self.assert_invalid(dict(zip(KEYS, ("44", "9999", "road"))), [KEYS[1]])
        self.assert_invalid(dict(zip(KEYS, ("广东省", "深圳市", "road"))), [KEYS[0]])

    def test_cross_province_and_non_selectable_codes_rejected(self):
        for province, city in (("44", "1101"), ("11", "110101"), ("42", "4290"), ("44", "419001")):
            with self.subTest(province=province, city=city):
                self.assert_invalid(dict(zip(KEYS, (province, city, "road"))), [KEYS[1]])

    def test_every_selectable_city_validates(self):
        for province in self.service.get_archive_regions():
            for city in province["children"]:
                with self.subTest(province=province["value"], city=city["value"]):
                    self.assertIsNone(self.service.validate_archive_address(
                        dict(zip(KEYS, (province["value"], city["value"], "详细地址")))
                    ))

    def test_non_string_parts_are_structured_errors(self):
        for key in KEYS:
            for invalid in (0, False, [], {}):
                values = dict(zip(KEYS, ("44", "4403", "road")))
                values[key] = invalid
                self.assert_invalid(values, [key])

    def test_pinned_assets_and_provenance(self):
        metadata = json.loads((DATA / "source.json").read_text(encoding="utf-8"))
        self.assertRegex(metadata["revision"], r"^[0-9a-f]{40}$")
        self.assertEqual(metadata["data_cutoff"], "2023-06-30")
        self.assertEqual(metadata["scope"], "mainland-31")
        for filename, digest in metadata["sha256"].items():
            self.assertEqual(hashlib.sha256((DATA / filename).read_bytes()).hexdigest(), digest)
        self.assertIn("DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE", (DATA / "LICENSE").read_text(encoding="utf-8"))
        self.assertTrue((DATA / "README.md").is_file())


if __name__ == "__main__":
    unittest.main()
