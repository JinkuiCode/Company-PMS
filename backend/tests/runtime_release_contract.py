import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services import runtime_release as runtime
from app.services.database_revision import CURRENT_DATABASE_REVISION


class RuntimeRelease(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'release.json'
        self.env = patch.dict(os.environ, {'PMS_RELEASE_MANIFEST': str(self.path)})
        self.env.start(); self.addCleanup(self.env.stop); runtime._load_manifest.cache_clear()
        self.manifest = {'version': 'v1.0.0', 'title': '发布', 'summary': '说明', 'build_id': 'fixture',
            'commit': 'a'*40, 'database_revision': CURRENT_DATABASE_REVISION, 'built_at': '2026-10-15T00:00:00Z',
            'changes': [{'kind': '新增', 'title': '记录', 'description': '查看记录', 'guide': 'archive'}]}

    def test_missing_development_manifest_is_not_mislabeled_as_official_version(self):
        with patch.object(runtime.settings, 'PMS_ENV', 'development'):
            self.assertEqual(runtime.runtime_info({})['version'], '开发中')

    def test_production_requires_a_valid_deployed_manifest(self):
        with patch.object(runtime.settings, 'PMS_ENV', 'production'):
            with self.assertRaises(RuntimeError): runtime.load_runtime_manifest()
            self.path.write_text('{invalid', encoding='utf-8')
            with self.assertRaises(RuntimeError): runtime.load_runtime_manifest()

    def test_runtime_version_is_stable_for_running_process_and_technical_data_is_separately_authorized(self):
        self.path.write_text(json.dumps(self.manifest), encoding='utf-8')
        first = runtime.runtime_info({})
        self.assertEqual(first['version'], 'v1.0.0'); self.assertNotIn('technical', first)
        self.manifest['version'] = 'v1.0.1'; self.path.write_text(json.dumps(self.manifest), encoding='utf-8')
        self.assertEqual(runtime.runtime_info({})['version'], 'v1.0.0')
        admin = runtime.runtime_info({'permissions': ['system:release:manage']})
        self.assertEqual(admin['technical']['commit'], 'a'*40)

    def test_notice_guide_is_registered_for_release_links(self):
        self.manifest['changes'][0]['guide'] = 'businessNotices'
        self.assertEqual(runtime.validated_manifest(self.manifest)['changes'][0]['guide'], 'businessNotices')

    def test_manifest_rejects_unregistered_guides_wrong_schema_and_multiline_subject(self):
        for change in ({'database_revision': 'wrong'}, {'title': 'bad\nSubject: injected'},
                       {'changes': [{'kind': '新增', 'title': 't', 'description': 'd', 'guide': 'unregistered'}]}):
            with self.assertRaises(ValueError): runtime.validated_manifest({**self.manifest, **change})


if __name__ == '__main__': unittest.main()
