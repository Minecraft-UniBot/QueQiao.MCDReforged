'''
QueQiao MCDR 插件 - 配置管理
'''
import os
import json

from mcdreforged.api.all import PluginServerInterface

DEFAULT_CONFIG = {
	'server_name': 'MCDR',
	'access_token': '',
	'client_origin': 'mcdr',
	'minecraft': {
		# Minecraft 服务器地址，用于 Server List Ping 获取 MOTD/最大玩家数
		# 留空则自动从 MCDR 解析的服务器信息获取，解析不到时回退 127.0.0.1:25565
		'host': '',
		'port': 0
	},
	'client': {
		'enable': False,
		'url': 'ws://127.0.0.1:8080/minecraft/ws',
		'reconnect_interval': 5,
		'reconnect_max_times': 0
	},
	'server': {
		'enable': False,
		'host': '0.0.0.0',
		'port': 8080
	},
	'log_events': True
}


class Config:
	def __init__(self, data: dict):
		self._data = {**DEFAULT_CONFIG, **data}
		# merge nested dicts
		for key in ('minecraft', 'client', 'server'):
			if key in data and isinstance(data[key], dict):
				self._data[key] = {**DEFAULT_CONFIG.get(key, {}), **data[key]}

	@property
	def server_name(self) -> str:
		return self._data.get('server_name', 'MCDR')

	@property
	def access_token(self) -> str:
		return self._data.get('access_token', '')

	@property
	def client_origin(self) -> str:
		return self._data.get('client_origin', 'mcdr')

	@property
	def minecraft_host(self) -> str:
		'''Minecraft 服务器地址（用于 Server List Ping），空则自动解析'''
		return self._data.get('minecraft', {}).get('host', '') or ''

	@property
	def minecraft_port(self) -> int:
		'''Minecraft 服务器端口（用于 Server List Ping），0 则自动解析'''
		return self._data.get('minecraft', {}).get('port', 0) or 0

	@property
	def client_enable(self) -> bool:
		return self._data.get('client', {}).get('enable', False)

	@property
	def client_url(self) -> str:
		return self._data.get('client', {}).get('url', 'ws://127.0.0.1:8080/minecraft/ws')

	@property
	def client_reconnect_interval(self) -> int:
		return self._data.get('client', {}).get('reconnect_interval', 5)

	@property
	def client_reconnect_max_times(self) -> int:
		return self._data.get('client', {}).get('reconnect_max_times', 0)

	@property
	def server_enable(self) -> bool:
		return self._data.get('server', {}).get('enable', False)

	@property
	def server_host(self) -> str:
		return self._data.get('server', {}).get('host', '0.0.0.0')

	@property
	def server_port(self) -> int:
		return self._data.get('server', {}).get('port', 8080)

	@property
	def log_events(self) -> bool:
		return self._data.get('log_events', True)

	def to_dict(self) -> dict:
		return self._data.copy()


def load_config(server: PluginServerInterface) -> Config:
	'''加载配置文件，不存在则创建默认配置'''
	config_path = os.path.join(server.get_data_folder(), 'config.json')
	os.makedirs(server.get_data_folder(), exist_ok=True)

	if not os.path.exists(config_path):
		save_config(server, DEFAULT_CONFIG)
		server.logger.info(f'[QueQiao] 已创建默认配置文件: {config_path}')
		return Config(DEFAULT_CONFIG)

	try:
		with open(config_path, 'r', encoding='utf-8') as f:
			data = json.load(f)
		return Config(data)
	except Exception as e:
		server.logger.error(f'[QueQiao] 配置文件加载失败: {e}')
		return Config(DEFAULT_CONFIG)


def save_config(server: PluginServerInterface, data: dict):
	'''保存配置到文件'''
	config_path = os.path.join(server.get_data_folder(), 'config.json')
	os.makedirs(server.get_data_folder(), exist_ok=True)
	with open(config_path, 'w', encoding='utf-8') as f:
		json.dump(data, f, indent=2, ensure_ascii=False)
