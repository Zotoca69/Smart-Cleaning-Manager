"""Offline prototype: scoped HA WebSocket capture. No device commands."""
import asyncio, hashlib, json, os, base64, time, re
from pathlib import Path
from datetime import datetime, timezone
from websockets.asyncio.client import connect

class Store:
    def __init__(self, path):
        self.path=Path(path); self.path.mkdir(mode=0o700, parents=False, exist_ok=False)
        self.file=(self.path/'messages.jsonl').open('x', encoding='utf-8')
        self.n=0; self.start=time.monotonic_ns(); self.complete=False; self.reason='unfinished'; self.size=0
        self.manifest()
    def manifest(self):
        self.file.flush()
        data=dict(messages=self.n, complete=self.complete, reason=self.reason, sha256=hashlib.sha256((self.path/'messages.jsonl').read_bytes()).hexdigest(), freshness='UNKNOWN')
        tmp=self.path/'manifest.tmp'; tmp.write_text(json.dumps(data,indent=2)); tmp.replace(self.path/'manifest.json')
    def record(self, direction, raw):
        if isinstance(raw,str): raw=raw.encode('utf-8')
        if self.size+len(raw)>10_000_000: raise ValueError('capture limit')
        self.n+=1; self.size+=len(raw)
        row=dict(seq=self.n,direction=direction,utc=datetime.now(timezone.utc).isoformat(),elapsed_ns=time.monotonic_ns()-self.start,sha256=hashlib.sha256(raw).hexdigest(),payload_b64=base64.b64encode(raw).decode('ascii'))
        self.file.write(json.dumps(row)+'\n'); self.file.flush()
    def close(self):
        try: self.manifest()
        finally: self.file.close()

def request(ids):
    if not ids or len(ids)>100 or len(set(ids))!=len(ids) or any(not re.fullmatch(r'[a-z0-9_]+\.[a-z0-9_]+',x) for x in ids): raise ValueError('exact unique entity IDs required')
    return json.dumps(dict(id=1,type='subscribe_entities',entity_ids=ids))

def validate(message, ids):
    if message.get('id')!=1: raise ValueError('unexpected ID')
    if message.get('type')=='result':
        if message.get('success') is not True: raise ValueError('subscription rejected')
    elif message.get('type')=='event':
        event=message['event']
        if not isinstance(event,dict) or set(event)-{'a','c','r'}: raise ValueError('unknown delta schema')
        for key, value in event.items():
            if key=='r':
                if not isinstance(value,list): raise ValueError('invalid removal')
            elif not isinstance(value,dict): raise ValueError('invalid delta')
            if set(value)-set(ids): raise ValueError('unexpected entity')
    else: raise ValueError('unexpected type')

async def capture(url, token, ids, path, seconds, stop, notify=lambda n:None):
    req=request(ids)
    if not 1<=seconds<=900: raise ValueError('duration must be 1–900 seconds')
    if not url.startswith('wss://'): raise ValueError('TLS WebSocket URL required')
    store=Store(path)
    try:
        async with connect(url, max_size=1_000_000, open_timeout=10, close_timeout=3) as ws:
            if json.loads(await asyncio.wait_for(ws.recv(),10)).get('type')!='auth_required': raise ValueError('unexpected authentication handshake')
            await ws.send(json.dumps(dict(type='auth',access_token=token)))
            auth=json.loads(await asyncio.wait_for(ws.recv(),10))
            if auth.get('type')!='auth_ok': raise ValueError('authentication rejected')
            store.record('send',req); await ws.send(req)
            deadline=time.monotonic()+seconds; ack=False; initial=False
            while not stop.is_set() and time.monotonic()<deadline:
                try: raw=await asyncio.wait_for(ws.recv(decode=False), min(0.25,max(0.001,deadline-time.monotonic())))
                except asyncio.TimeoutError: continue
                msg=json.loads(raw); validate(msg,ids)
                store.record('receive',raw); notify(store.n)
                if msg['type']=='result':
                    if ack: raise ValueError('duplicate acknowledgement')
                    ack=True
                else:
                    if not ack: raise ValueError('event before acknowledgement')
                    if not initial:
                        if set(msg['event'].get('a',{}))!=set(ids): raise ValueError('incomplete initial snapshot')
                        initial=True
            store.complete=ack and initial; store.reason='bounded observation ended' if store.complete else 'missing acknowledgement or snapshot'
    except BaseException as exc:
        store.complete=False; store.reason=type(exc).__name__; raise
    finally: store.close()
