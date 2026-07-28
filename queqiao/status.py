'''
QueQiao MCDR 插件 - 服务器状态采集
严格对齐 QueQiao V2 协议 get_status 返回格式：
  - cpu_information: {cpu_cores, load_average, system_load, process_load}
  - memory_information: {physical_memory{total,free,used,percentage}, jvm_memory{total,free,used,max,percentage}}
  - server_list_ping.players: {max, online}

在线玩家列表通过 online_player_api 插件获取。
'''
import os
import time

import psutil

from mcdreforged.api.all import PluginServerInterface


# ==================== 进程采集 ====================

def _get_server_processes(server: PluginServerInterface):
	'''获取服务器进程及其所有子进程（JVM 通常是 bash 的子进程）'''
	pids = server.get_server_pid_all()
	procs = []
	for pid in pids:
		try:
			procs.append(psutil.Process(pid))
		except (psutil.NoSuchProcess, psutil.AccessDenied):
			continue
	return procs


# CPU 占用采集的内部缓存
# psutil.Process.cpu_percent 首次调用返回 0.0，需要先有一次"预热"调用，
# 间隔一段时间后再调用才能得到真实的占用率。
# 这里缓存每个 pid 是否已预热，避免每次都从 0 开始。
_cpu_warmed: set = set()  # 已预热的 pid 集合


def _get_process_cpu_load(server: PluginServerInterface) -> float:
	'''
	获取服务器进程（含子进程）的 CPU 占用率（百分比，按逻辑核心数归一化）。
	内部维护预热缓存：首次调用返回 0.0 并完成预热，后续调用返回真实值。
	'''
	procs = _get_server_processes(server)
	if not procs:
		return 0.0

	global _cpu_warmed
	total = 0.0
	current_pids = set()
	for p in procs:
		try:
			pid = p.pid
			current_pids.add(pid)
			if pid not in _cpu_warmed:
				# 预热：触发 psutil 记录起始时间，本次返回 0.0
				p.cpu_percent(interval=None)
				_cpu_warmed.add(pid)
			else:
				total += p.cpu_percent(interval=None)
		except (psutil.NoSuchProcess, psutil.AccessDenied):
			continue
	# 清理已退出进程的缓存
	_cpu_warmed -= (_cpu_warmed - current_pids)
	return total


def _get_system_cpu_load() -> float:
	'''获取系统整体 CPU 占用率（百分比）'''
	try:
		# cpu_percent 首次调用返回 0，模块级已预热
		return psutil.cpu_percent(interval=None)
	except Exception:
		return 0.0


def _get_load_average() -> float:
	'''获取系统平均负载（1 分钟），不支持返回 -1.0'''
	try:
		# psutil.getloadavg() 返回 (1min, 5min, 15min)
		return psutil.getloadavg()[0]
	except Exception:
		return -1.0


def get_cpu_information(server: PluginServerInterface) -> dict:
	'''
	CPU 信息（对齐协议 cpu_information 字段）
	  - cpu_cores: 逻辑核心数
	  - load_average: 系统平均负载（1 分钟）
	  - system_load: 系统 CPU 占用率（百分比）
	  - process_load: 服务器进程 CPU 占用率（百分比）
	'''
	return {
		'cpu_cores': psutil.cpu_count(logical=True) or 0,
		'load_average': _get_load_average(),
		'system_load': _get_system_cpu_load(),
		'process_load': _get_process_cpu_load(server),
	}


def get_memory_information(server: PluginServerInterface) -> dict:
	'''
	内存信息（对齐协议 memory_information 字段）
	  - physical_memory: 物理内存 {total, free, used, percentage}
	  - jvm_memory: 服务器进程内存 {total, free, used, max, percentage}
	    注: MCDR 端无法获取 JVM 堆内存，此处用进程 RSS/VMS 近似
	'''
	# 物理内存
	try:
		vm = psutil.virtual_memory()
		physical = {
			'total': vm.total,
			'free': vm.available,
			'used': vm.used,
			'percentage': vm.percent,
		}
	except Exception:
		physical = {'total': 0, 'free': 0, 'used': 0, 'percentage': 0.0}

	# 服务器进程内存（RSS/VMS 近似 JVM 内存）
	procs = _get_server_processes(server)
	rss = 0
	vms = 0
	for p in procs:
		try:
			mem = p.memory_info()
			rss += getattr(mem, 'rss', 0) or 0
			vms += getattr(mem, 'vms', 0) or 0
		except (psutil.NoSuchProcess, psutil.AccessDenied):
			continue

	if vms > 0:
		percentage = round(rss / vms * 100, 2)
	else:
		percentage = 0.0

	jvm = {
		'total': vms,
		'free': max(vms - rss, 0),
		'used': rss,
		'max': vms,
		'percentage': percentage,
	}
	return {'physical_memory': physical, 'jvm_memory': jvm}


def reset_cpu_cache():
	'''清理 CPU 采样缓存（服务器重启/插件重载时调用）'''
	global _cpu_warmed
	_cpu_warmed.clear()


# 模块加载时预热系统级 cpu_percent
try:
	psutil.cpu_percent(interval=None)
except Exception:
	pass


# ==================== 在线玩家采集 ====================

def get_online_players(server: PluginServerInterface) -> list:
	'''获取在线玩家列表（玩家名），通过 online_player_api 插件'''
	try:
		api = server.get_plugin_instance('online_player_api')
		if api is not None and hasattr(api, 'get_player_list'):
			return list(api.get_player_list())
	except Exception:
		pass
	return []


def get_player_count(server: PluginServerInterface) -> int:
	'''获取在线玩家数量'''
	return len(get_online_players(server))
