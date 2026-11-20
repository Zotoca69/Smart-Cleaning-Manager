import unittest,tempfile,zipfile
from pathlib import Path
from collector import Store
from app import export
class ExportTests(unittest.TestCase):
    def test_export(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'capture'; s=Store(p); s.record('receive',b'{}'); s.close(); z=Path(d)/'out.zip'; export(p,z)
            with zipfile.ZipFile(z) as f:
                self.assertEqual(f.read('messages.jsonl'),(p/'messages.jsonl').read_bytes())
                self.assertEqual(f.read('manifest.json'),(p/'manifest.json').read_bytes())
            with self.assertRaises(FileExistsError): export(p,z)
    def test_tampered(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'capture'; s=Store(p); s.close(); (p/'messages.jsonl').write_text('changed')
            with self.assertRaises(ValueError): export(p,Path(d)/'out.zip')
