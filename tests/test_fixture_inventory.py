import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


class InventoryTests(unittest.TestCase):
    def test_unregistered_consumers_missing_refs_and_private_values(self):
        from ai_test_framework.fixtures.inventory import inventory
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feature = root / 'features' / 'catalog'
            feature.mkdir(parents=True)
            (feature / 'smoke.spec.ts').write_text('const memberId = 12345; // CASE-CATALOG-001\n')
            (feature / 'execution_asset_register.json').write_text(json.dumps({'assets': [
                {'path': 'features/catalog/missing.ts'},
                {'path': 'features/catalog/smoke.spec.ts'}]}))
            (feature / 'other.py').write_text('service_id = 98765\n')
            (feature / '.env').write_text('PASSWORD=never-export-this\n')
            result = inventory(root)
            rows = {r['script_ref']: r for r in result['consumers']}
            self.assertEqual(rows['features/catalog/smoke.spec.ts']['registration'], 'registered_present')
            self.assertEqual(rows['features/catalog/other.py']['registration'], 'unregistered_present')
            self.assertEqual(rows['features/catalog/missing.ts']['registration'], 'registered_missing')
            self.assertEqual(rows['features/catalog/smoke.spec.ts']['case_ids'], ['CASE-CATALOG-001'])
            self.assertNotIn('12345', json.dumps(result))
            self.assertNotIn('never-export', json.dumps(result))
            self.assertEqual(rows['features/catalog/other.py']['operation'], 'pending_analysis')

    def test_symlink_outside_root_is_not_followed(self):
        from ai_test_framework.fixtures.inventory import inventory
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp); (root / 'features').mkdir()
            secret = Path(other) / 'leak.py'; secret.write_text('member_id = 67890')
            (root / 'features/leak.py').symlink_to(secret)
            self.assertEqual(inventory(root)['consumers'], [])
