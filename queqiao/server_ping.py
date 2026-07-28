'''
QueQiao MCDR 插件 - Minecraft Server List Ping
自行实现 MC 1.7+ 的 SLP（Server List Ping）协议，获取 MOTD、最大玩家数、favicon 等。

协议参考: https://wiki.vg/Server_List_Ping

流程:
  1. TCP 连接服务器
  2. 发送 Handshake 包（协议版本 -1 表示 ping，下一状态 1 = status）
  3. 发送 Status Request 包（空包）
  4. 接收 Status Response（JSON）

不引入外部依赖，仅用标准库 socket + json。
'''
import json
import socket
import struct
import time
from typing import Optional

from mcdreforged.api.all import PluginServerInterface


# ==================== Varint 编解码 ====================

def _read_varint(sock: socket.socket) -> int:
    '''从 socket 读取一个 VarInt'''
    value = 0
    length = 0
    while True:
        raw = sock.recv(1)
        if not raw:
            raise ConnectionError('连接断开：读取 VarInt 时无数据')
        byte = raw[0]
        value |= (byte & 0x7F) << (7 * length)
        length += 1
        if length > 5:
            raise ValueError('VarInt 过长')
        if not (byte & 0x80):
            break
    return value


def _write_varint(value: int) -> bytes:
    '''将整数编码为 VarInt 字节'''
    if value < 0:
        # 负数用无符号 32 位表示
        value = value & 0xFFFFFFFF
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            byte |= 0x80
            out.append(byte)
        else:
            out.append(byte)
            break
    return bytes(out)


# ==================== 包读写 ====================

def _read_packet(sock: socket.socket) -> bytes:
    '''读取一个完整包（长度前缀 + 包体）'''
    length = _read_varint(sock)
    data = b''
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise ConnectionError('连接断开：读取包体时无数据')
        data += chunk
    return data


def _write_packet(sock: socket.socket, payload: bytes):
    '''发送一个完整包（长度前缀 + 包体）'''
    sock.sendall(_write_varint(len(payload)) + payload)


# ==================== Handshake / Status ====================

def _build_handshake(host: str, port: int, protocol_version: int = -1) -> bytes:
    '''
    构建 Handshake 包
      packet_id = 0x00
      protocol_version: VarInt（-1 表示不关心版本，仅用于 ping）
      server_addr: String（UTF-8，前缀 VarInt 长度）
      server_port: Unsigned Short（大端）
      next_state: VarInt（1 = status）
    '''
    addr_bytes = host.encode('utf-8')
    payload = b'\x00'  # packet id
    payload += _write_varint(protocol_version)
    payload += _write_varint(len(addr_bytes)) + addr_bytes
    payload += struct.pack('>H', port)
    payload += _write_varint(1)  # next_state = status
    return payload


def _build_status_request() -> bytes:
    '''构建 Status Request 包（空包，仅 packet_id = 0x00）'''
    return b'\x00'


def _parse_description(desc) -> str:
    '''
    解析 description 字段。
    MC 1.7+ 可能是字符串，也可能是 {text: ...} 对象，也可能是 extra 数组。
    '''
    if desc is None:
        return ''
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        parts = []
        if 'text' in desc:
            parts.append(str(desc['text']))
        for extra in desc.get('extra', []) or []:
            parts.append(_parse_description(extra))
        return ''.join(parts)
    if isinstance(desc, list):
        return ''.join(_parse_description(x) for x in desc)
    return str(desc)


def server_list_ping(host: str, port: int, timeout: float = 5.0) -> dict:
    '''
    执行 Minecraft Server List Ping，返回解析后的状态 dict。

    返回字段（对齐 QueQiao V2 协议 server_list_ping）:
      - available: bool
      - host: str
      - port: int
      - reason: str ('ok' / 错误描述)
      - error: Optional[str]
      - version: {name, protocol}
      - players: {max, online}
      - description: str
      - favicon: Optional[str]
      - enforcesSecureChat: Optional[bool]

    失败时 available=False，reason/error 填充错误信息。
    '''
    result = {
        'available': False,
        'host': host,
        'port': port,
        'reason': 'unknown',
        'error': None,
        'version': {'name': None, 'protocol': None},
        'players': {'max': -1, 'online': 0},
        'description': None,
        'favicon': None,
        'enforcesSecureChat': None,
    }

    if not host or not port:
        result['reason'] = 'no host/port'
        result['error'] = '服务器地址未知，无法 ping'
        return result

    sock = None
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.settimeout(timeout)

        # 1. Handshake
        _write_packet(sock, _build_handshake(host, port, protocol_version=-1))
        # 2. Status Request
        _write_packet(sock, _build_status_request())
        # 3. 读取 Status Response
        body = _read_packet(sock)
        if not body:
            raise ConnectionError('空响应')

        # 第一个字节是 packet id（应为 0x00）
        packet_id = body[0]
        if packet_id != 0x00:
            raise ValueError(f'意外的 packet id: {packet_id}')

        # 剩余是 JSON 字符串（VarInt 长度前缀 + UTF-8 数据）
        rest = body[1:]
        # 读取字符串长度
        str_len = 0
        shift = 0
        idx = 0
        while True:
            if idx >= len(rest):
                raise ValueError('字符串长度读取越界')
            byte = rest[idx]
            str_len |= (byte & 0x7F) << (7 * shift)
            shift += 1
            idx += 1
            if not (byte & 0x80):
                break
        json_bytes = rest[idx:idx + str_len]
        raw = json.loads(json_bytes.decode('utf-8'))

        # 解析字段
        result['available'] = True
        result['reason'] = 'ok'
        result['error'] = None

        version = raw.get('version') or {}
        result['version'] = {
            'name': version.get('name'),
            'protocol': version.get('protocol'),
        }

        players = raw.get('players') or {}
        result['players'] = {
            'max': players.get('max', -1),
            'online': players.get('online', 0),
        }

        result['description'] = _parse_description(raw.get('description'))
        result['favicon'] = raw.get('favicon')
        result['enforcesSecureChat'] = raw.get('enforcesSecureChat')

        return result

    except (socket.timeout, ConnectionError, OSError) as e:
        result['reason'] = 'connection error'
        result['error'] = str(e)
        return result
    except (ValueError, json.JSONDecodeError) as e:
        result['reason'] = 'parse error'
        result['error'] = str(e)
        return result
    except Exception as e:
        result['reason'] = 'unknown error'
        result['error'] = str(e)
        return result
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


# ==================== 缓存层 ====================
# MOTD 不常变化，缓存一段时间避免每次 get_status 都 TCP 连接

_ping_cache: dict = {}  # key -> {data, expire_at}
_PING_CACHE_TTL = 30.0  # 缓存 30 秒


def get_server_list_ping(
        server: PluginServerInterface,
        host: Optional[str] = None,
        port: Optional[int] = None,
        use_cache: bool = True,
) -> dict:
    '''
    获取服务器 Server List Ping 结果。
    优先使用缓存（TTL 30s），缓存失效或 use_cache=False 时重新 ping。

    服务器地址来源（按优先级）:
      1. 参数 host/port（非空时优先）
      2. server.get_server_information() 的 ip/port
      3. 回退 127.0.0.1:25565
    '''
    # 获取服务器地址
    if not host:
        try:
            info = server.get_server_information()
            host = getattr(info, 'ip', None) or '127.0.0.1'
        except Exception:
            host = '127.0.0.1'
    if not port:
        try:
            info = server.get_server_information()
            port = getattr(info, 'port', None) or 25565
        except Exception:
            port = 25565

    cache_key = f'{host}:{port}'
    now = time.time()

    # 检查缓存
    if use_cache and cache_key in _ping_cache:
        entry = _ping_cache[cache_key]
        if now < entry['expire_at']:
            return entry['data']

    # 服务器未运行时直接返回不可用
    if not server.is_server_running():
        result = {
            'available': False,
            'host': host,
            'port': port,
            'reason': 'server not running',
            'error': '服务器未运行',
            'version': {'name': None, 'protocol': None},
            'players': {'max': -1, 'online': 0},
            'description': None,
            'favicon': None,
            'enforcesSecureChat': None,
        }
    else:
        # 到这里 host/port 一定已被赋值（有回退逻辑）
        assert host is not None and port is not None
        result = server_list_ping(host, port)

    # 写入缓存
    _ping_cache[cache_key] = {
        'data': result,
        'expire_at': now + _PING_CACHE_TTL,
    }
    return result


def clear_ping_cache():
    '''清空 ping 缓存（服务器重启/插件重载时调用）'''
    _ping_cache.clear()
