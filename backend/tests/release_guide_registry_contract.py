"""Published changes can link the same registered help pages as the frontend."""
import re
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pydantic import ValidationError
from app.services.runtime_release import GUIDES, ReleaseChange, validated_manifest
from app.services.database_revision import CURRENT_DATABASE_REVISION


class ReleaseGuideRegistry(unittest.TestCase):
    def test_registered_navigation_and_release_targets_stay_in_sync(self):
        navigation = (Path(__file__).resolve().parents[2] / 'frontend/src/page-guide/navigation.ts').read_text()
        names = set(re.findall(r'^  (\w+): \{ permission:', navigation, re.M))
        self.assertEqual(set(GUIDES), names)

    def test_role_and_enum_help_links_validate_in_fixed_manifests(self):
        for guide in ('roles', 'enums'):
            with self.subTest(guide=guide):
                manifest = dict(version='v1.1.1', title='表单保护修复', summary='隔离测试',
                    build_id='test-fixture', commit='b' * 40,
                    database_revision=CURRENT_DATABASE_REVISION, built_at='2026-10-18T00:00:00Z',
                    changes=[dict(kind='修复', title='保存保护', description='关闭前确认未保存修改', guide=guide)])
                self.assertEqual(validated_manifest(manifest)['changes'][0]['guide'], guide)

    def test_unregistered_links_remain_rejected(self):
        for guide in ('', 'unregistered', '/api/users', '__proto__'):
            with self.subTest(guide=guide), self.assertRaises(ValidationError):
                ReleaseChange(kind='修复', title='fixture', description='fixture', guide=guide)


if __name__ == '__main__':
    unittest.main(verbosity=2)
