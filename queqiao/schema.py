'''
QueQiao MCDR 插件 - 事件 Schema
严格按照 QueQiao V2 协议定义事件结构，所有字段均保留，无法获取的字段以 None 占位
'''
import time
from typing import Any, Callable, Optional

# minecraft_data_api 为可选依赖，未安装时仅 nickname 可用
try:
    import minecraft_data_api as data_api
except ImportError:
    data_api: Any = None


def _safe(fn: Callable, default=None):
    '''安全执行，异常时返回默认值'''
    try:
        return fn()
    except Exception:
        return default


# ==================== 服务器信息 ====================

def get_server_version(server) -> Optional[str]:
    '''服务器版本，来源 MCDR ServerInformation.version（可能为 None）'''
    return _safe(lambda: server.get_server_information().version)


def get_server_type(server) -> str:
    '''
    服务器类型
    本插件运行于 MCDReforged 之上，固定返回 'mcdr'
    '''
    return 'mcdr'


# ==================== Player 模型 ====================
# 文档: .docs/queqiao/events/v2/model/player.md
#
# 字段可获取性：
#   ✅ nickname            : 来自事件参数
#   ❌ uuid                : MCDR 不解析玩家 UUID
#   ❌ is_op               : MCDR 权限系统与 OP 无法直接映射
#   ❌ address             : MCDR 不解析玩家 IP
#   ✅ health              : minecraft_data_api.get_player_info('Health')
#   ❌ max_health          : minecraft_data_api 未提供
#   ✅ experience_level    : minecraft_data_api.get_player_info('Level')
#   ❌ experience_progress : minecraft_data_api 未提供
#   ❌ total_experience    : minecraft_data_api 未提供
#   ❌ walk_speed          : minecraft_data_api 未提供
#   ✅ x / y / z           : minecraft_data_api.get_player_coordinate
#   注: dimension 不在 Player 模型字段中，故不输出

def build_player(server, player_name: str, *, with_full_data: bool = True) -> dict:
    '''构建 Player 对象，严格遵循 V2 协议字段'''
    player = {
        'nickname': player_name,
        'uuid': None,
        'is_op': None,
        'address': None,
        'health': None,
        'max_health': None,
        'experience_level': None,
        'experience_progress': None,
        'total_experience': None,
        'walk_speed': None,
        'x': None,
        'y': None,
        'z': None,
    }

    # 玩家已离线或无 minecraft_data_api 时仅保留 nickname
    if not with_full_data or data_api is None:
        return player

    # 坐标 x / y / z
    coord = _safe(lambda: data_api.get_player_coordinate(player_name, timeout=2))
    if coord is not None:
        player['x'] = round(coord.x, 2)
        player['y'] = round(coord.y, 2)
        player['z'] = round(coord.z, 2)

    # 生命值 health
    health = _safe(lambda: data_api.get_player_info(player_name, 'Health', timeout=2))
    if health is not None:
        player['health'] = float(health)

    # 经验等级 experience_level
    level = _safe(lambda: data_api.get_player_info(player_name, 'Level', timeout=2))
    if level is not None:
        player['experience_level'] = int(level)

    return player


# ==================== Translate 模型 ====================
# 文档: .docs/queqiao/events/v2/model/translate.md
# 自 QueQiao v0.4.1 起引入，用于 Death / Achievement / Display 的文本

def build_translate(*, key: Optional[str] = None, args: Optional[list] = None, text: Optional[str] = None) -> dict:
    '''构建 Translate 对象（key: 翻译键, args: 翻译参数数组, text: 回退文本）'''
    return {'key': key, 'args': args or [], 'text': text}


# ==================== 事件构建器 ====================

class EventBuilder:
    '''
    事件构建器，封装 server 与 server_name，避免每个事件函数重复传参

    公共字段（所有 V2 事件均包含）：
      - timestamp       : 事件时间戳（毫秒）
      - post_type        : 事件类型（notice / message）
      - event_name       : 事件名
      - server_name      : 服务器名称
      - server_version   : 服务器版本（✅ MCDR ServerInformation）
      - server_type      : 服务器类型（✅ 固定为 'mcdr'）
      - sub_type         : 事件子类型
    '''

    def __init__(self, server, server_name: str):
        self.server = server
        self.server_name = server_name

    def _base(self, *, event_name: str, post_type: str, sub_type: str) -> dict:
        '''构建事件公共字段'''
        return {
            'timestamp': int(time.time() * 1000),
            'post_type': post_type,
            'event_name': event_name,
            'server_name': self.server_name,
            'server_version': get_server_version(self.server),
            'server_type': get_server_type(self.server),
            'sub_type': sub_type,
        }

    # -------------------- Notice 事件 --------------------

    def player_join(self, player_name: str) -> dict:
        '''PlayerJoinEvent (sub_type: player_join)'''
        event = self._base(event_name='PlayerJoinEvent', post_type='notice', sub_type='player_join')
        event['player'] = build_player(self.server, player_name, with_full_data=True)
        return event

    def player_quit(self, player_name: str) -> dict:
        '''PlayerQuitEvent (sub_type: player_quit) — 玩家已离线，仅填充 nickname'''
        event = self._base(event_name='PlayerQuitEvent', post_type='notice', sub_type='player_quit')
        event['player'] = build_player(self.server, player_name, with_full_data=False)
        return event

    def player_death(self, player_name: str, *, death_text: Optional[str] = None) -> dict:
        '''
        PlayerDeathEvent (sub_type: player_death)
        death 字段（v0.4.1+ 采用 Translate 模型）：
          - key  : ❌ MCDR/mg_events 不提供翻译键
          - args : ❌ MCDR/mg_events 不提供翻译参数
          - text : ✅ 来自 MoreGameEvents 的 raw 文本
        '''
        event = self._base(event_name='PlayerDeathEvent', post_type='notice', sub_type='player_death')
        event['player'] = build_player(self.server, player_name, with_full_data=True)
        event['death'] = build_translate(text=death_text)
        return event

    def player_achievement(self, player_name: str, *, ach_key: Optional[str] = None, ach_text: Optional[str] = None) -> dict:
        '''
        PlayerAchievementEvent (sub_type: player_achievement)
        achievement 字段：
          - key       : ✅ 来自 MoreGameEvents 的 advancement
          - display   : ❌ title/description/frame 均不可获取（MCDR/mg_events 不解析）
          - text      : 兼容 v0.4.0 及以下
          - translate : v0.4.1+ 新增，采用 Translate 模型
        '''
        event = self._base(event_name='PlayerAchievementEvent', post_type='notice', sub_type='player_achievement')
        event['player'] = build_player(self.server, player_name, with_full_data=True)
        event['achievement'] = {
            'key': ach_key,
            'display': {'title': None, 'description': None, 'frame': None},
            'text': ach_text,
            'translate': build_translate(key=ach_key, text=ach_text),
        }
        return event

    # -------------------- Message 事件 --------------------

    def player_chat(self, player_name: str, *, raw_message: Optional[str] = None, message: Optional[str] = None) -> dict:
        '''
        PlayerChatEvent (sub_type: player_chat)
          - message_id  : ❌ MCDR 不生成消息 ID
          - raw_message : ✅ 玩家原始聊天内容
          - message     : ✅ 玩家聊天消息文本
        '''
        event = self._base(event_name='PlayerChatEvent', post_type='message', sub_type='player_chat')
        event['message_id'] = None
        event['raw_message'] = raw_message
        event['player'] = build_player(self.server, player_name, with_full_data=True)
        event['message'] = message
        return event

    def player_command(self, player_name: str, *, raw_message: Optional[str] = None, command: Optional[str] = None) -> dict:
        '''
        PlayerCommandEvent (sub_type: player_command)
          - message_id  : ❌ MCDR 不生成消息 ID
          - raw_message : ✅ 一般与 command 相同
          - command     : ✅ 玩家输入的命令内容
        '''
        event = self._base(event_name='PlayerCommandEvent', post_type='message', sub_type='player_command')
        event['message_id'] = None
        event['raw_message'] = raw_message
        event['player'] = build_player(self.server, player_name, with_full_data=True)
        event['command'] = command
        return event
