"""Loopback tests through the real websockets library (no HA, no external network).

A synthetic HA-like server runs on 127.0.0.1. Verifies that real text frames are
stored byte-for-byte and that only auth + subscribe_entities reach the server.
The plain ws:// test runs everywhere (owner decision 7068495713 allows local ws://);
the TLS test needs the `openssl` CLI for a throw-away certificate and is skipped
without it.
"""
import asyncio
import base64
import json
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

import config
from collector import capture
from _testsupport import ACK, IDS, TOKEN, snapshot, change

OPENSSL = shutil.which("openssl")
FRAMES = [json.dumps({"type": "auth_required", "ha_version": "2026.11.2"}),
          json.dumps({"type": "auth_ok", "ha_version": "2026.11.2"}),
          json.dumps(ACK), json.dumps(snapshot()),
          ' {"id":1,"type":"event","event":{"c":{"vacuum.synthetic_robot":{"+":{"s":"cleaning","lc":1001.5}}}}} ',
          json.dumps(change(IDS[1], "ok", 1002.0), ensure_ascii=False)]


class LoopbackTests(unittest.TestCase):
    def roundtrip(self, scheme, server_ssl=None, client_ssl=None):
        from websockets.asyncio.client import connect
        from websockets.asyncio.server import serve

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / "capture"
        received = []

        async def handler(ws):
            await ws.send(FRAMES[0])
            received.append(await ws.recv())
            await ws.send(FRAMES[1])
            received.append(await ws.recv())
            for frame in FRAMES[2:]:
                await ws.send(frame)
            await asyncio.sleep(3)

        def connect_fn(url):
            kwargs = {"proxy": None, "compression": None, "max_size": config.MAX_MESSAGE_BYTES}
            if client_ssl is not None:
                kwargs["ssl"] = client_ssl
            return connect(url, **kwargs)

        async def main():
            async with serve(handler, "127.0.0.1", 0, ssl=server_ssl) as server:
                port = server.sockets[0].getsockname()[1]
                stop = threading.Event()
                return await capture(f"{scheme}://127.0.0.1:{port}/api/websocket", TOKEN, IDS, target, 2, stop,
                                     connect_fn, lambda n: stop.set() if n >= 5 else None)

        manifest = asyncio.run(main())
        self.assertTrue(manifest["complete"], manifest["reason"])
        self.assertEqual(manifest["provenance"]["ha_version"], "2026.11.2")
        rows = [json.loads(line) for line in (target / config.MESSAGES_FILE).read_bytes().splitlines()]
        stored = [base64.b64decode(r["payload_b64"]) for r in rows]
        self.assertEqual(stored[1:], [f.encode("utf-8") for f in FRAMES[2:6]])
        self.assertEqual(json.loads(received[0]), {"type": "auth", "access_token": TOKEN})
        self.assertEqual(json.loads(received[1]), {"id": 1, "type": "subscribe_entities", "entity_ids": IDS})
        self.assertEqual(stored[0], received[1].encode("utf-8"))
        self.assertNotIn(TOKEN.encode(), b"".join(p.read_bytes() for p in target.iterdir()))

    def test_real_websocket_plain_roundtrip(self):
        self.roundtrip("ws")

    @unittest.skipUnless(OPENSSL, "openssl CLI unavailable")
    def test_real_websocket_tls_roundtrip(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cert, key = Path(tmp.name) / "c.pem", Path(tmp.name) / "k.pem"
        subprocess.run([OPENSSL, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=localhost",
                        "-addext", "subjectAltName=IP:127.0.0.1", "-keyout", str(key), "-out", str(cert)],
                       check=True, capture_output=True)
        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.load_cert_chain(cert, key)
        self.roundtrip("wss", server_ctx, ssl.create_default_context(cafile=str(cert)))


if __name__ == "__main__":
    unittest.main()
