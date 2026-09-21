import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class PurchaseConnectionContract(unittest.TestCase):
    def setUp(self):
        from app.services.purchase_connection import PurchaseDatabaseSettings, purchase_connection, PurchaseUnavailable
        self.Settings, self.connect, self.Unavailable = PurchaseDatabaseSettings, purchase_connection, PurchaseUnavailable

    def configured(self):
        return self.Settings(PURCHASE_DB_HOST='test-host', PURCHASE_DB_NAME='test-db',
                             PURCHASE_DB_USER='pms_purchase_reader', PURCHASE_DB_PASSWORD='not-a-real-password')

    def test_credentials_are_redacted_and_disabled_by_default(self):
        settings = self.configured()
        self.assertNotIn('not-a-real-password', repr(settings))
        self.assertNotIn('not-a-real-password', settings.model_dump_json())
        with self.assertRaises(self.Unavailable):
            with self.connect(self.Settings()):
                self.fail('Unconfigured report must not connect')

    def test_explicit_file_is_independent_of_main_pms_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.env'
            path.write_text('PURCHASE_DB_HOST=test-host\nPURCHASE_DB_NAME=test-db\nPURCHASE_DB_USER=pms_purchase_reader\nPURCHASE_DB_PASSWORD=not-real\n')
            settings = self.Settings(_env_file=path)
            self.assertEqual(settings.PURCHASE_DB_NAME, 'test-db')

    def test_success_checks_database_rolls_back_and_closes(self):
        calls = []
        class Cursor:
            def execute(self, sql): calls.append(sql)
            def fetchone(self): return {'database_name': 'test-db', 'login_name': 'pms_purchase_reader'}
        class Connection:
            def cursor(self): return Cursor()
            def rollback(self): calls.append('rollback')
            def close(self): calls.append('close')
        def factory(**kwargs):
            self.assertTrue(kwargs['read_only'])
            self.assertEqual(kwargs['encryption'], 'require')
            self.assertLessEqual(kwargs['timeout'], 30)
            return Connection()
        with self.connect(self.configured(), connector=factory):
            pass
        self.assertEqual(calls[-2:], ['rollback', 'close'])

    def test_wrong_target_closes_connection_and_hides_error(self):
        closed = []
        class BadConnection:
            def cursor(self): return self
            def execute(self, sql): pass
            def fetchone(self): return {'database_name': 'wrong', 'login_name': 'sa'}
            def rollback(self): pass
            def close(self): closed.append(True)
        with self.assertRaises(self.Unavailable):
            with self.connect(self.configured(), connector=lambda **kw: BadConnection()):
                self.fail('Must not yield an unexpected database')
        self.assertEqual(closed, [True])

    def test_driver_error_never_exposes_connection_or_password(self):
        def failure(**kwargs): raise RuntimeError('secret-driver-password')
        with self.assertRaises(self.Unavailable) as result:
            with self.connect(self.configured(), connector=failure): pass
        self.assertNotIn('secret-driver-password', str(result.exception))


if __name__ == '__main__': unittest.main()
