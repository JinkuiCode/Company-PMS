"""Offline provisioning guards; never opens a database connection."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


class AccountContract(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/provision_purchase_reader.py'
        spec = importlib.util.spec_from_file_location('provision', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_select_grants_are_column_scoped_and_only_for_fixed_tables(self):
        sql = self.module.grant_statements()
        self.assertTrue(sql)
        self.assertTrue(all(s.startswith('GRANT SELECT (') for s in sql))
        self.assertTrue(all(' TO [pms_purchase_reader]' in s for s in sql))
        self.assertFalse(any('db_datareader' in s or 'SCHEMA::' in s for s in sql))
        self.assertNotIn('FPRICE', ' '.join(sql))

    def test_existing_account_is_never_replaced(self):
        with self.assertRaises(RuntimeError):
            self.module.check_absent({'login_exists': 1, 'user_exists': 0})
        with self.assertRaises(RuntimeError):
            self.module.check_absent({'login_exists': 0, 'user_exists': 1})
        self.module.check_absent({'login_exists': 0, 'user_exists': 0})

    def test_secret_file_is_exclusive_and_private(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'reader.env'
            self.module.write_private_config(path, 'generated-test-password')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                self.module.write_private_config(path, 'replacement')
            self.assertIn('generated-test-password', path.read_text())

    def test_password_has_fixed_safe_format_and_entropy(self):
        password = self.module.new_password()
        self.assertGreaterEqual(len(password), 40)
        self.assertTrue(any(c.isupper() for c in password))
        self.assertTrue(any(c.islower() for c in password))
        self.assertTrue(any(c.isdigit() for c in password))
        self.assertNotIn("'", password)
        self.assertNotIn('\n', password)

    def test_permission_audit_rejects_privileged_identity(self):
        with self.assertRaises(RuntimeError):
            self.module.check_permissions(['CONNECT', 'CONTROL'], ['CONNECT SQL'])
        with self.assertRaises(RuntimeError):
            self.module.check_permissions(['CONNECT'], ['CONNECT SQL', 'CONTROL SERVER'])
        self.module.check_permissions(['CONNECT'], ['CONNECT SQL', 'VIEW ANY DATABASE'])


if __name__ == '__main__':
    unittest.main()
