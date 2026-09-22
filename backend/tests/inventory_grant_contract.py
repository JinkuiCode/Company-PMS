import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.grant_inventory_reader import apply, statements, main


class InventoryGrants(unittest.TestCase):
    def test_fixed_minimal_columns(self):
        self.assertEqual(statements(), [
            'GRANT SELECT ([FID],[Organization],[Stock],[MaterialCode],[MaterialName],[FSPECIFICATION],[Brand],[Material],[SupplierNumber],[FBaseQty],[Unit]) ON OBJECT::[dbo].[YD_JIN_INVENTORY] TO [pms_purchase_reader]',
            'GRANT SELECT ([FID],[FSTOCKORGID]) ON OBJECT::[dbo].[T_STK_INVENTORY] TO [pms_purchase_reader]',
        ])

    def test_failure_rolls_back(self):
        connection = Mock()
        connection.cursor.return_value.execute.side_effect = RuntimeError('test')
        with self.assertRaises(RuntimeError):
            apply(connection)
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()
        connection.cursor.return_value.close.assert_called_once()

    def test_preview_does_not_request_credentials(self):
        with patch.object(sys, 'argv', ['grant_inventory_reader.py']), patch('builtins.input') as prompt, patch('builtins.print'):
            self.assertEqual(main(), 0)
            prompt.assert_not_called()


if __name__ == '__main__':
    unittest.main()
