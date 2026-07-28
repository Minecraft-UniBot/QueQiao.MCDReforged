'''
QueQiao MCDR 插件入口
鹊桥 V2 协议对接，支持正向/反向 WebSocket 连接
'''
from mcdreforged.api.all import (
	PluginServerInterface,
	CommandSource,
	Literal,
	RTextList,
)
from typing import Any, Optional

from queqiao.config import Config, load_config
from queqiao.websocket_manager import QueQiaoConnection
from queqiao.game_events import GameEventForwarder
from queqiao.api_handler import ApiHandler
from queqiao import server_status as server_status_module

# 全局实例（命名避免与子模块冲突）
plugin_config: Optional[Config] = None
plugin_connection: Optional[QueQiaoConnection] = None
plugin_game_events: Optional[GameEventForwarder] = None
plugin_server: Optional[PluginServerInterface] = None


def on_load(server: PluginServerInterface, prev_module: Any):
	'''插件加载'''
	global plugin_config, plugin_connection, plugin_game_events, plugin_server

	plugin_server = server
	plugin_config = load_config(server)

	# 热重载时继承旧连接
	if prev_module is not None and prev_module.plugin_connection is not None:
		conn: QueQiaoConnection = prev_module.plugin_connection
		conn.config = plugin_config
		inherited = True
		server.logger.info('[QueQiao] 已从旧实例继承 WebSocket 连接')
	else:
		conn = QueQiaoConnection(server, plugin_config)
		inherited = False
	plugin_connection = conn

	_init_components(server, conn)

	if not inherited:
		conn.start()

	_register_commands(server)
	server.register_help_message('!!queqiao', server.tr('queqiao_mcdr.help'))
	server.logger.info('[QueQiao] 插件已加载')


def on_unload(server: PluginServerInterface):
	'''插件卸载'''
	global plugin_connection
	if plugin_connection is not None:
		plugin_connection.stop()
		plugin_connection = None
	server.logger.info('[QueQiao] 插件已卸载')


def _register_commands(server: PluginServerInterface):
	'''注册 !!queqiao 命令树'''

	def cmd_status(source: CommandSource, context: dict):
		_show_status(source)

	def cmd_reload(source: CommandSource, context: dict):
		_reload(source)

	node = (
		Literal('!!queqiao')
		.requires(lambda src: src.has_permission(2))
		.then(Literal('status').runs(cmd_status))
		.then(Literal('reload').runs(cmd_reload))
		.runs(lambda src, ctx: _show_help(src))
	)
	server.register_command(node)


def _show_help(source: CommandSource):
	'''显示帮助信息'''
	server = source.get_server()
	lines = [
		server.tr('queqiao_mcdr.help'),
		server.tr('queqiao_mcdr.help.status'),
		server.tr('queqiao_mcdr.help.reload'),
	]
	source.reply(RTextList(*lines))


def _show_status(source: CommandSource):
	'''显示连接状态'''
	server = plugin_server
	if server is None:
		source.reply('插件未初始化')
		return
	cfg = plugin_config
	conn = plugin_connection
	if cfg is None or conn is None:
		source.reply('插件未初始化')
		return
	mode = []
	if cfg.client_enable:
		mode.append('客户端')
	if cfg.server_enable:
		mode.append('服务端')
	mode_str = '+'.join(mode) if mode else '未启用'

	client_status = '已连接' if conn.is_client_connected else '未连接'
	server_status = f'{conn.server_client_count} 个客户端'

	# 玩家数（由 GameEventForwarder 自行维护）
	player_count = 0
	if plugin_game_events is not None:
		player_count = len(plugin_game_events.online_players)

	# CPU 与内存（基于 psutil 采集服务器进程）
	cpu_percent = server_status_module.get_cpu_percent(server, interval=0.0)
	rss_mb, vms_mb = server_status_module.get_memory_info(server)

	cpu_str = f'{cpu_percent:.1f}%' if cpu_percent is not None else 'N/A'
	mem_str = f'{rss_mb:.1f} MB' if rss_mb is not None else 'N/A'

	lines = [
		server.tr('queqiao_mcdr.status.title'),
		server.tr('queqiao_mcdr.status.mode', mode_str),
		server.tr('queqiao_mcdr.status.server_name', cfg.server_name),
		server.tr('queqiao_mcdr.status.client', client_status),
		server.tr('queqiao_mcdr.status.server', server_status),
		server.tr('queqiao_mcdr.status.players', player_count),
		server.tr('queqiao_mcdr.status.cpu', cpu_str),
		server.tr('queqiao_mcdr.status.memory', mem_str),
	]
	source.reply(RTextList(*lines))


def _init_components(server: PluginServerInterface, conn: QueQiaoConnection):
	'''初始化 API 处理器和游戏事件转发'''
	global plugin_game_events

	api_handler = ApiHandler(server, conn.config)
	conn.on_api_request = api_handler.handle_request

	plugin_game_events = GameEventForwarder(server, conn.config, conn)
	plugin_game_events.register()


def _reload(source: CommandSource):
	'''重载配置'''
	global plugin_config, plugin_connection
	server = plugin_server
	if server is None:
		source.reply('插件未初始化')
		return

	if plugin_connection is not None:
		plugin_connection.stop()

	plugin_config = load_config(server)
	plugin_connection = QueQiaoConnection(server, plugin_config)
	_init_components(server, plugin_connection)
	plugin_connection.start()

	source.reply(server.tr('queqiao_mcdr.config_reloaded'))
	server.logger.info('[QueQiao] 配置已重载并重新连接')
