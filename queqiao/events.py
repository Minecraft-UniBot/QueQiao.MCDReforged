'''
QueQiao MCDR 插件 - 游戏事件转发
监听 MCDR 内置事件和 MoreGameEvents 事件，通过 WebSocket 发送到鹊桥
所有事件严格遵循 QueQiao V2 协议（见 queqiao/schema.py）
'''
from mcdreforged.api.all import PluginServerInterface, MCDRPluginEvents, Info

from queqiao.config import Config
from queqiao.websocket import QueQiaoConnection
from queqiao.schema import EventBuilder


def _first_attr(item, *names, default=None):
	'''从对象中按优先级取第一个非空的属性值'''
	for name in names:
		val = getattr(item, name, None)
		if val:
			return val
	return default


class GameEventForwarder:
	'''监听游戏事件并转发到鹊桥'''

	def __init__(self, server: PluginServerInterface, config: Config, connection: QueQiaoConnection):
		self.server = server
		self.config = config
		self.connection = connection
		# 在线玩家集合（自行维护，用于状态展示）
		self.online_players: set = set()
		# 事件构建器，封装 server 与 server_name
		self.builder = EventBuilder(server, config.server_name)

	def register(self):
		'''注册所有事件监听器'''
		self.server.logger.info('正在注册事件监听器……')
		# MCDR 内置事件
		self.server.register_event_listener(MCDRPluginEvents.PLAYER_JOINED, self._on_player_joined)
		self.server.register_event_listener(MCDRPluginEvents.PLAYER_LEFT, self._on_player_left)
		self.server.register_event_listener(MCDRPluginEvents.USER_INFO, self._on_user_info)
		# MoreGameEvents 事件（需要 mg_events 插件）
		self.server.register_event_listener('PlayerDeathEvent', self._on_player_death)
		self.server.register_event_listener('PlayerAdvancementEvent', self._on_player_advancement)

	def _send(self, event: dict):
		'''发送事件到鹊桥连接'''

	# ==================== MCDR 内置事件 ====================

	def _on_player_joined(self, server: PluginServerInterface, player: str, info):
		'''玩家加入事件 - MCDR 派发参数 (server, player, info)'''
		self.server.logger.debug('监测到玩家加入！转发给鹊桥连接……')
		self.online_players.add(player)
		self.connection.send_event(self.builder.player_join(player))

	def _on_player_left(self, server: PluginServerInterface, player: str):
		'''玩家离开事件 - MCDR 派发参数 (server, player)'''
		self.online_players.discard(player)
		self.connection.send_event(self.builder.player_quit(player))

	def _on_user_info(self, server: PluginServerInterface, info: Info):
		'''
		用户消息事件 - MCDR 派发参数 (server, info)
		仅处理玩家（is_user=True）发送的消息，区分聊天与命令
		'''
		if not info.is_user or info.player is None or info.content is None:
			return
		player = info.player
		raw = info.content
		if raw.startswith('/'):
			# 命令消息：去掉前导 '/'
			command = raw[1:]
			self.connection.send_event(self.builder.player_command(player, raw_message=raw, command=command))
		else:
			self.connection.send_event(self.builder.player_chat(player, raw_message=raw, message=raw))

	# ==================== MoreGameEvents 事件 ====================

	def _on_player_death(self, server: PluginServerInterface, player: str, event_type: str, content: list):
		'''玩家死亡事件 - 来自 MoreGameEvents'''
		death_text = _first_attr(content[0], 'raw') if content else None
		self.connection.send_event(self.builder.player_death(player, death_text=death_text))

	def _on_player_advancement(self, server: PluginServerInterface, player: str, event_type: str, content: list):
		'''玩家成就事件 - 来自 MoreGameEvents'''
		item = content[0] if content else None
		ach_key = _first_attr(item, 'advancement') if item else None
		ach_text = _first_attr(item, 'raw') if item else None
		self.connection.send_event(self.builder.player_achievement(player, ach_key=ach_key, ach_text=ach_text))