import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ReaderGrant(unittest.TestCase):
    def test_only_approved_columns_are_granted(self):
        from scripts.grant_product_line_reader import grant_statements
        statements = grant_statements()
        self.assertEqual(statements, [
            'GRANT SELECT ([FORGID],[FNUMBER],[FFORBIDSTATUS],[FDOCUMENTSTATUS]) ON OBJECT::[dbo].[T_ORG_ORGANIZATIONS] TO [pms_purchase_reader]',
            'GRANT SELECT ([FORGID],[FLOCALEID],[FNAME]) ON OBJECT::[dbo].[T_ORG_ORGANIZATIONS_L] TO [pms_purchase_reader]',
            'GRANT SELECT ([FSTOCKORGID]) ON OBJECT::[dbo].[T_PUR_RECEIVE] TO [pms_purchase_reader]',
            'GRANT SELECT ([FSTOCKORGID]) ON OBJECT::[dbo].[T_PUR_MRB] TO [pms_purchase_reader]',
        ])

    def test_failure_rolls_back_without_commit(self):
        from scripts.grant_product_line_reader import apply_grants
        connection = Mock()
        connection.cursor.return_value.execute.side_effect = RuntimeError('test failure')
        with self.assertRaises(RuntimeError):
            apply_grants(connection)
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()
        connection.cursor.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
