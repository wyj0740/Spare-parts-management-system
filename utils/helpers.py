#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通用工具函数
"""
import os
import sys
import socket
import webbrowser
import time
import threading
from config import get_app_dir, get_resource_path, CONFIG


def get_database_path():
    """获取数据库路径，确保可写"""
    db_dir = os.path.join(get_app_dir(), 'data')
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    return os.path.join(db_dir, 'spare_parts.db')


def get_log_path():
    """获取日志文件路径"""
    log_dir = os.path.join(get_app_dir(), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    return os.path.join(log_dir, 'spare_parts.log')


def get_backup_path():
    """获取备份目录"""
    backup_dir = os.path.join(get_app_dir(), 'backups')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    return backup_dir


def get_backup_config_path():
    """获取备份配置文件路径"""
    return os.path.join(get_app_dir(), 'backup_config.json')


def open_browser_delayed(url=None, delay=1.5):
    """延迟打开浏览器"""
    if url is None:
        host = CONFIG.get('host', '127.0.0.1')
        port = CONFIG.get('port', 5000)
        url = f'http://{host}:{port}'

    def _open():
        time.sleep(delay)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


def is_port_in_use(port):
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((CONFIG.get('host', '127.0.0.1'), port))
            return False
        except OSError:
            return True


def check_single_instance():
    """检查是否已有实例在运行，如果有则激活浏览器并退出"""
    port = CONFIG.get('port', 5000)
    host = CONFIG.get('host', '127.0.0.1')
    if is_port_in_use(port):
        print("=" * 60)
        print("备品备件管理系统")
        print("=" * 60)
        print(f"\n⚠ 程序已在运行中！")
        print(f"正在打开浏览器访问已运行的实例...")
        webbrowser.open(f'http://{host}:{port}')
        time.sleep(2)
        return False
    return True
