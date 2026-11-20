import asyncio, json, os, stat, tempfile, threading, unittest
from pathlib import Path
from unittest.mock import patch
from collector import capture, Store

class Socket:
    def __init__(self, messages):
        self.messages=iter([{"type":"auth_required"},{"type":"auth_ok"}]+messages)
        self.sent=[]
    async def __aenter__(self): return self
    async def __aexit__(self,*args): pass
    async def send(self,raw): self.sent.append(json.loads(raw))
    async def recv(self,**kwargs):
        try: msg=next(self.messages)
        except StopIteration:
            await asyncio.sleep(10)
            return b""
        return msg if isinstance(msg,bytes) else json.dumps(msg).encode()

ACK={"id":1,"type":"result","success":True}
SNAP={"id":1,"type":"event","event":{"a":{"sensor.example":{"s":"on"}}}}
REMOVE={"id":1,"type":"event","event":{"r":["sensor.example"]}}

class NegativeTests(unittest.TestCase):
    def run_case(self,messages,failed=True,stop_after=None):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"capture"; sock=Socket(messages); stop=threading.Event()
            def notify(n):
                if stop_after and n>=stop_after: stop.set()
            with patch("collector.connect",return_value=sock):
                task=capture("wss://synthetic.invalid","test-secret",["sensor.example"],path,1,stop,notify)
                if failed:
                    with self.assertRaises((ValueError,TypeError,AttributeError)): asyncio.run(task)
                else: asyncio.run(task)
            self.assertEqual(sock.sent,[{"type":"auth","access_token":"test-secret"},{"id":1,"type":"subscribe_entities","entity_ids":["sensor.example"]}])
            self.assertNotIn("test-secret",(path/"messages.jsonl").read_text())
            return json.loads((path/"manifest.json").read_text())
    def test_malformed(self): self.assertFalse(self.run_case([ACK,b"{"])["complete"])
    def test_duplicate_ack(self): self.assertFalse(self.run_case([ACK,ACK])["complete"])
    def test_early_event(self): self.assertFalse(self.run_case([SNAP])["complete"])
    def test_missing_snapshot(self): self.assertFalse(self.run_case([ACK,{"id":1,"type":"event","event":{"a":{}}}])["complete"])
    def test_removal(self):
        m=self.run_case([ACK,SNAP,REMOVE])
        self.assertFalse(m["complete"]); self.assertIn("gap",m["reason"])
    def test_duplicate_event(self):
        delta={"id":1,"type":"event","event":{"c":{"sensor.example":{"+":{"s":"off"}}}}}
        m=self.run_case([ACK,SNAP,delta,delta],False,5)
        self.assertTrue(m["complete"]); self.assertEqual(m["messages"],5)
    def test_timeout(self): self.assertFalse(self.run_case([],False)["complete"])
    def test_limits(self):
        for url,seconds in [("ws://synthetic.invalid",1),("wss://synthetic.invalid",0),("wss://synthetic.invalid",901)]:
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ValueError): asyncio.run(capture(url,"secret",["sensor.example"],Path(d)/"capture",seconds,threading.Event()))
    def test_size(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/"capture")
            try:
                with self.assertRaises(ValueError): s.record("receive",b"x"*10000001)
            finally: s.close()
    @unittest.skipUnless(os.name=="posix","POSIX permissions only")
    def test_modes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"capture"; s=Store(p); s.close()
            self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o700)
            self.assertEqual(stat.S_IMODE((p/"messages.jsonl").stat().st_mode),0o600)
