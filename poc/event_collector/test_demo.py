import unittest, asyncio, tempfile, threading, json
from pathlib import Path
from unittest.mock import patch
from app import demo, DemoSocket, export
from collector import capture
class DemoTests(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'capture'; stop=threading.Event()
            asyncio.run(demo(['sensor.example'],p,2,stop,lambda n:stop.set() if n>=4 else None))
            m=json.loads((p/'manifest.json').read_text()); self.assertTrue(m['complete']); self.assertEqual(m['messages'],4); export(p,Path(d)/'capture.zip')
            self.assertNotIn('synthetic-only',(p/'messages.jsonl').read_text())
    def test_unexpected_entity(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'capture'; sock=DemoSocket(['sensor.other'])
            with patch('collector.connect',return_value=sock):
                with self.assertRaises(ValueError): asyncio.run(capture('wss://synthetic.invalid','secret',['sensor.example'],p,1,threading.Event()))
            m=json.loads((p/'manifest.json').read_text()); self.assertFalse(m['complete']); self.assertEqual(m['messages'],2)
    def test_early_stop(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'capture'; stop=threading.Event(); stop.set(); asyncio.run(demo(['sensor.example'],p,1,stop,lambda n:None)); self.assertFalse(json.loads((p/'manifest.json').read_text())['complete'])
    def test_disconnect(self):
        class Broken(DemoSocket):
            async def recv(self,**kw):
                if self.step==4: raise OSError('disconnected')
                return await super().recv(**kw)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'capture'
            with patch('collector.connect',return_value=Broken(['sensor.example'])):
                with self.assertRaises(OSError): asyncio.run(capture('wss://synthetic.invalid','secret',['sensor.example'],p,1,threading.Event()))
            self.assertFalse(json.loads((p/'manifest.json').read_text())['complete'])
