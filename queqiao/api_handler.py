'''
QueQiao MCDR 插件 - API 请求处理器
接收鹊桥通过 WebSocket 发来的 API 请求，在游戏内执行并返回响应
'''
import json
import time
from typing import Any

from mcdreforged.api.all import PluginServerInterface

from queqiao.config import Config
from queqiao import server_status as server_status_module


class ApiHandler:
	'''处理鹊桥 V2 API 请求'''

	def __init__(self, server: PluginServerInterface, config: Config):
		self.server = server
		self.config = config

	def handle_request(self, data: dict) -> dict:
		'''处理 API 请求，返回响应 dict'''
		api = data.get('api', '')
		api_data = data.get('data') or {}
		echo = data.get('echo', '')

		handler = {
			'broadcast': self._api_broadcast,
			'send_msg': self._api_broadcast,  # 兼容 nonebot-adapter-minecraft 的 send_msg API
			'send_private_msg': self._api_send_private_msg,
			'send_title': self._api_send_title,
			'send_actionbar': self._api_send_actionbar,
			'send_rcon_command': self._api_send_rcon_command,
			'get_status': self._api_get_status,
		}.get(api)

		if not handler:
			return self._response(404, api, 'FAILED', f'Unknown API: {api}', echo=echo)

		try:
			resp = handler(api_data, echo)
			resp['api'] = api  # 确保响应 api 字段与请求一致（兼容 send_msg 别名）
			return resp
		except Exception as e:
			self.server.logger.error(f'[QueQiao] API 执行异常 ({api}): {e}')
			return self._response(500, api, 'FAILED', str(e), echo=echo)

	# ==================== 响应构建 ====================

	def _response(self, code: int, api: str, status: str, message: str, data=None, echo: str = '') -> dict:
		resp = {
			'code': code,
			'api': api,
			'post_type': 'response',
			'status': status,
			'message': message,
		}
		if data is not None:
			resp['data'] = data
		if echo:
			resp['echo'] = echo
		return resp

	# ==================== API 实现 ====================

	def _api_broadcast(self, data: dict, echo: str) -> dict:
		'''广播消息到游戏'''
		message = data.get('message', [])
		msg_json = json.dumps(message, ensure_ascii=False)
		self.server.execute(f'tellraw @a {msg_json}')
		return self._response(200, 'broadcast', 'SUCCESS', 'success', echo=echo)

	def _api_send_private_msg(self, data: dict, echo: str) -> dict:
		'''发送私聊消息'''
		uuid = data.get('uuid') or ''
		nickname = data.get('nickname') or ''
		message = data.get('message', [])

		if not uuid and not nickname:
			return self._response(400, 'send_private_msg', 'FAILED', 'uuid or nickname required', echo=echo)

		# 优先使用 nickname，其次 uuid
		target = nickname or uuid
		msg_json = json.dumps(message, ensure_ascii=False)
		self.server.execute(f'tellraw {target} {msg_json}')

		return self._response(200, 'send_private_msg', 'SUCCESS', 'success', data={
			'target_player': {'nickname': nickname, 'uuid': uuid},
			'message': 'Send private message success.',
		}, echo=echo)

	def _api_send_title(self, data: dict, echo: str) -> dict:
		'''发送标题'''
		title = data.get('title')
		subtitle = data.get('subtitle')
		fade_in = data.get('fade_in', 20)
		stay = data.get('stay', 70)
		fade_out = data.get('fade_out', 20)

		if not title and not subtitle:
			return self._response(400, 'send_title', 'FAILED', 'title or subtitle required', echo=echo)

		# 设置时间
		self.server.execute(f'title @a times {fade_in} {stay} {fade_out}')

		if subtitle:
			sub_json = json.dumps(subtitle, ensure_ascii=False)
			self.server.execute(f'title @a subtitle {sub_json}')

		if title:
			title_json = json.dumps(title, ensure_ascii=False)
			self.server.execute(f'title @a title {title_json}')
		elif subtitle:
			# 只有 subtitle 时，用空 title 触发显示
			self.server.execute('title @a title {"text": ""}')

		return self._response(200, 'send_title', 'SUCCESS', 'success', echo=echo)

	def _api_send_actionbar(self, data: dict, echo: str) -> dict:
		'''发送 ActionBar 消息'''
		message = data.get('message', [])
		msg_json = json.dumps(message, ensure_ascii=False)
		self.server.execute(f'title @a actionbar {msg_json}')
		return self._response(200, 'send_actionbar', 'SUCCESS', 'success', echo=echo)

	def _api_send_rcon_command(self, data: dict, echo: str) -> dict:
		'''执行 RCON 命令'''
		command = data.get('command', '')
		if not command:
			return self._response(400, 'send_rcon_command', 'FAILED', 'command required', echo=echo)

		result = self.server.rcon_query(command)
		if result is None:
			return self._response(500, 'send_rcon_command', 'FAILED', 'RCON query failed or timed out', echo=echo)

		return self._response(200, 'send_rcon_command', 'SUCCESS', 'success', data=result, echo=echo)

	def _api_get_status(self, data: dict, echo: str) -> dict:
		'''
		获取服务器状态（严格对齐 QueQiao V2 协议 get_status 返回格式）
		返回 data 字段：
		  - timestamp
		  - server_type / server_version
		  - server_list_ping: {available, host, port, players{max, online}, ...}
		  - cpu_information: {cpu_cores, load_average, system_load, process_load}
		  - memory_information: {physical_memory{...}, jvm_memory{...}}
		'''
		status_data: dict[str, Any] = {
			'timestamp': int(time.time() * 1000),
		}

		# 服务器基础信息
		try:
			info = self.server.get_server_information()
			status_data['server_type'] = 'mcdr'
			status_data['server_version'] = getattr(info, 'version', None)
		except Exception:
			status_data['server_type'] = 'mcdr'
			status_data['server_version'] = None

		# server_list_ping（MCDR 端无法做真实 ping，用已知信息填充）
		try:
			info = self.server.get_server_information()
			players = server_status_module.get_online_players(self.server)
			status_data['server_list_ping'] = {
				'available': self.server.is_server_running(),
				'host': getattr(info, 'ip', None),
				'port': getattr(info, 'port', None),
				'reason': 'ok' if self.server.is_server_running() else 'server not running',
				'error': None,
				'players': {
					'max': -1,  # MCDR 端无法获取最大玩家数
					'online': len(players),
				},
				'description': None,
				'favicon': None,
			}
		except Exception:
			status_data['server_list_ping'] = {
				'available': False,
				'players': {'max': -1, 'online': 0},
			}

		# CPU 信息
		try:
			status_data['cpu_information'] = server_status_module.get_cpu_information(self.server)
		except Exception as e:
			self.server.logger.debug(f'[QueQiao] CPU 信息采集失败: {e}')

		# 内存信息
		try:
			status_data['memory_information'] = server_status_module.get_memory_information(self.server)
		except Exception as e:
			self.server.logger.debug(f'[QueQiao] 内存信息采集失败: {e}')

		return self._response(200, 'get_status', 'SUCCESS', 'success', data=status_data, echo=echo)