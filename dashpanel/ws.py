"""Minimal WebSocket (RFC 6455) över asyncio, bara det som behövs: klient mot Home Assistant (ws://)
och serversidan för låtsas-HA i testverktyget. Inga beroenden; hanterar ping/pong, stängning och
fragmenterade meddelanden."""
import asyncio
import base64
import hashlib
import os
import socket
import struct

GUID = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
OP_CONT, OP_TEXT, OP_BIN, OP_CLOSE, OP_PING, OP_PONG = 0, 1, 2, 8, 9, 10
MAX_MESSAGE = 24 * 1024 * 1024


class WSError(Exception):
    pass


def _xor(data, key):
    n = len(data)
    if not n:
        return data
    k = (key * (n // 4 + 1))[:n]
    return (int.from_bytes(data, 'big') ^ int.from_bytes(k, 'big')).to_bytes(n, 'big')


def encode_frame(opcode, payload=b'', mask=True, fin=True):
    b0 = (0x80 if fin else 0) | opcode
    n = len(payload)
    m = 0x80 if mask else 0
    if n < 126:
        hdr = struct.pack('!BB', b0, m | n)
    elif n < 65536:
        hdr = struct.pack('!BBH', b0, m | 126, n)
    else:
        hdr = struct.pack('!BBQ', b0, m | 127, n)
    if mask:
        key = os.urandom(4)
        return hdr + key + _xor(payload, key)
    return hdr + payload


async def read_frame(reader):
    b0, b1 = await reader.readexactly(2)
    fin = bool(b0 & 0x80)
    opcode = b0 & 0x0f
    n = b1 & 0x7f
    if n == 126:
        n = struct.unpack('!H', await reader.readexactly(2))[0]
    elif n == 127:
        n = struct.unpack('!Q', await reader.readexactly(8))[0]
    if n > MAX_MESSAGE:
        raise WSError('för stort meddelande (%d byte)' % n)
    key = await reader.readexactly(4) if (b1 & 0x80) else None
    data = await reader.readexactly(n) if n else b''
    if key:
        data = _xor(data, key)
    return fin, opcode, data


def accept_key(key):
    return base64.b64encode(hashlib.sha1(key.encode() + GUID).digest()).decode()


class WebSocket(object):
    def __init__(self, reader, writer, client=True):
        self.reader, self.writer, self.client = reader, writer, client
        self.closed = False
        self.last_rx = 0.0

    def send_text(self, s):
        if self.closed:
            raise WSError('stängd')
        self.writer.write(encode_frame(OP_TEXT, s.encode('utf-8'), mask=self.client))

    async def drain(self):
        await self.writer.drain()

    async def recv(self):
        """Nästa textmeddelande som str, eller None när den andra sidan stängt."""
        parts = []
        while True:
            try:
                fin, op, data = await read_frame(self.reader)
            except (asyncio.IncompleteReadError, ConnectionError, OSError):
                self.closed = True
                return None
            loop = asyncio.get_event_loop()
            self.last_rx = loop.time()
            if op == OP_PING:
                try:
                    self.writer.write(encode_frame(OP_PONG, data, mask=self.client))
                except Exception:
                    pass
                continue
            if op == OP_PONG:
                continue
            if op == OP_CLOSE:
                try:
                    self.writer.write(encode_frame(OP_CLOSE, data[:2], mask=self.client))
                except Exception:
                    pass
                self.closed = True
                return None
            if op in (OP_TEXT, OP_BIN, OP_CONT):
                parts.append(data)
                if sum(len(p) for p in parts) > MAX_MESSAGE:
                    raise WSError('för stort meddelande')
                if fin:
                    return b''.join(parts).decode('utf-8', 'replace')

    def abort(self):
        """Kasta anslutningen direkt (används när hjärtslaget uteblir)."""
        self.closed = True
        try:
            self.writer.transport.abort()
        except Exception:
            pass

    async def close(self):
        if not self.closed:
            self.closed = True
            try:
                self.writer.write(encode_frame(OP_CLOSE, struct.pack('!H', 1000), mask=self.client))
                await asyncio.wait_for(self.writer.drain(), 1.0)
            except Exception:
                pass
        try:
            self.writer.close()
        except Exception:
            pass


def _tune(writer):
    sock = writer.get_extra_info('socket')
    if sock is None:
        return
    for opt in (
        (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
        (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
        (socket.IPPROTO_TCP, getattr(socket, 'TCP_KEEPIDLE', 4), 30),
        (socket.IPPROTO_TCP, getattr(socket, 'TCP_KEEPINTVL', 5), 10),
        (socket.IPPROTO_TCP, getattr(socket, 'TCP_KEEPCNT', 6), 3),
        (socket.IPPROTO_TCP, getattr(socket, 'TCP_USER_TIMEOUT', 18), 30000),
    ):
        try:
            sock.setsockopt(*opt)
        except (OSError, AttributeError):
            pass


def parse_url(url):
    if not url.startswith('ws://'):
        raise WSError('bara ws:// stöds: %s' % url)
    rest = url[5:]
    hostport, _, path = rest.partition('/')
    host, _, port = hostport.partition(':')
    return host, int(port or 80), '/' + path


async def connect(url, timeout=8.0):
    host, port, path = parse_url(url)
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    _tune(writer)
    key = base64.b64encode(os.urandom(16)).decode()
    req = ('GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
           'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n') % (path, host, port, key)
    writer.write(req.encode())
    try:
        head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), timeout)
    except Exception:
        writer.close()
        raise
    lines = head.decode('latin-1').split('\r\n')
    if ' 101 ' not in lines[0]:
        writer.close()
        raise WSError('uppgradering nekades: ' + lines[0])
    hdrs = {}
    for ln in lines[1:]:
        if ':' in ln:
            k, _, v = ln.partition(':')
            hdrs[k.strip().lower()] = v.strip()
    if hdrs.get('sec-websocket-accept') != accept_key(key):
        writer.close()
        raise WSError('fel Sec-WebSocket-Accept')
    ws = WebSocket(reader, writer, client=True)
    ws.last_rx = asyncio.get_event_loop().time()
    return ws


async def server_handshake(reader, writer):
    """Serversidan (för låtsas-HA): läs uppgraderingsbegäran och svara. Ger WebSocket eller None."""
    try:
        head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 10)
    except Exception:
        writer.close()
        return None
    lines = head.decode('latin-1').split('\r\n')
    hdrs = {}
    for ln in lines[1:]:
        if ':' in ln:
            k, _, v = ln.partition(':')
            hdrs[k.strip().lower()] = v.strip()
    key = hdrs.get('sec-websocket-key')
    if not key or 'websocket' not in hdrs.get('upgrade', '').lower():
        writer.write(b'HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n')
        writer.close()
        return None
    writer.write(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                  'Sec-WebSocket-Accept: %s\r\n\r\n' % accept_key(key)).encode())
    _tune(writer)
    ws = WebSocket(reader, writer, client=False)
    ws.last_rx = asyncio.get_event_loop().time()
    return ws
