import unittest, tempfile, json, base64, hashlib
from pathlib import Path
from collector import Store, request, validate
class Tests(unittest.TestCase):
    def test_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'capture'; s=Store(p); raw=b'{ "a": 1 }\n'; s.record('receive',raw); s.close()
            row=json.loads((p/'messages.jsonl').read_text()); self.assertEqual(base64.b64decode(row['payload_b64']),raw); self.assertEqual(row['sha256'],hashlib.sha256(raw).hexdigest()); self.assertFalse(json.loads((p/'manifest.json').read_text())['complete'])
    def test_request(self):
        self.assertEqual(json.loads(request(['sensor.example']))['type'],'subscribe_entities')
        for ids in [[],['*'],['sensor.example','sensor.example']]:
            with self.assertRaises(ValueError): request(ids)
    def test_delta(self):
        validate({'id':1,'type':'event','event':{'c':{'sensor.example':{'+':{'s':'on'}}}}},['sensor.example'])
    def test_reject(self):
        for msg in [{'id':2,'type':'event'},{'id':1,'type':'event','event':{'a':{'sensor.other':{}}}},{'id':1,'type':'result','success':False}]:
            with self.assertRaises(ValueError): validate(msg,['sensor.example'])
if __name__=='__main__': unittest.main()
