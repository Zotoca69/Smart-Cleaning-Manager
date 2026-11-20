"""Loopback test through the real websockets library and TLS (no HA, no external network).

A throw-away self-signed certificate is generated with the `openssl` CLI and a
synthetic HA-like server runs on 127.0.0.1. Verifies that real text frames are
stored byte-for-byte and that only auth + subscribe_entities reach the server.
Skipped if `openssl` is unavailable.
"""
import asyncio
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


@unittest.skipUnless(OPENSSL, "openssl CLI unavailable")
class LoopbackTlsTests(unittest.TestCase):
    def test_real_websocket_tls_roundtrip(self):
        from websockets.asyncio.client import connect
        from websockets.asyncio.server import serve

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cert, key = Path(tmp.name) / "c.pem", Path(tmp.name) / "k.pem"
        subprocess.run([OPENSSL, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=localhost",
                        "-addext", "subjectAltName=IP:127.0.0.1", "-keyout", str(key), "-out", str(cert)],
                       check=True, capture_output=True)
        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.load_cert_chain(cert, key)
        client_ctx = ssl.create_default_context(cafile=str(cert))

        frames = [json.dumps({"type": "auth_required", "ha_version": "2026.11.2"}),
                  json.dumps({"type": "auth_ok", "ha_version": "2026.11.2"}),
                  json.dumps(ACK), json.dumps(snapshot()),
                  ' {"id":1,"type":"event","event":{"c":{"vacuum.synthetic_robot":{"+":{"s":"cleaning","lc":1001.5}}}}} ',
                  json.dumps(change(IDS[1], "ok", 1002.0), ensure_ascii=False)]
        received = []

        async def handler(ws):
            await ws.send(frames[0])
            received.append(await ws.recv())
            await ws.send(frames[1])
            received.append(await ws.recv())
            for frame in frames[2:]:
                await ws.send(frame)
            await asyncio.sleep(3)

        async def main():
            async with serve(handler, "127.0.0.1", 0, ssl=server_ctx) as server:
                port = server.sockets[0].getsockname()[1]
                url = f"wss://127.0.0.1:{port}/api/websocket"
                stop = threading.Event()
                return await capture(url, TOKEN, IDS, Path(tmp.name) / "capture", 2, stop,
                                     lambda u: connect(u, ssl=client_ctx, proxy=None, compression=None,
                                                       max_size=config.MAX_MESSAGE_BYTES),
                                     lambda n: stop.set() if n >= 5 else None)

        manifest = asyncio.run(main())
        self.assertTrue(manifest["complete"], manifest["reason"])
        self.assertEqual(manifest["provenance"]["ha_version"], "2026.11.2")
        rows = [json.loads(l) for l in (Path(tmp.name) / "capture" / config.MESSAGES_FILE).read_bytes().splitlines()]
        import base64
        stored = [base64.b64decode(r["payload_b64"]) for r in rows]
        self.assertEqual(stored[1:], [f.encode("utf-8") for f in frames[2:6]])
        self.assertEqual(json.loads(received[0]), {"type": "auth", "access_token": TOKEN})
        self.assertEqual(json.loads(received[1]), {"id": 1, "type": "subscribe_entities", "entity_ids": IDS})
        self.assertEqual(stored[0], received[1].encode("utf-8"))
        files = b"".join(p.read_bytes() for p in (Path(tmp.name) / "capture").iterdir())
        self.assertNotIn(TOKEN.encode(), files)


if __name__ == "__main__":
    unittest.main()
