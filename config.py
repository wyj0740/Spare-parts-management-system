#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置加载模块
"""
import os
import sys
import configparser
import logging


def get_app_dir():
    """获取应用程序目录（开发环境或打包后）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")


def get_resource_path(relative_path):
    """获取资源文件的绝对路径，支持PyInstaller打包"""
    try:
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            path = os.path.join(base_path, relative_path)
            if os.path.exists(path):
                return path
            internal_path = os.path.join(base_path, '_internal', relative_path)
            if os.path.exists(internal_path):
                return internal_path
            return path
        return os.path.abspath(os.path.join(".", relative_path))
    except Exception:
        return os.path.abspath(os.path.join(".", relative_path))


def load_config():
    """加载外部配置文件"""
    config = configparser.ConfigParser()
    config_path = os.path.join(get_app_dir(), 'config.ini')

    default_config = {
        'secret_key': 'spare-parts-management-system-wyj-change-in-production',
        'default_username': 'admin',
        'default_password': 'admin',
        'session_lifetime_hours': 24,
        'allowed_extensions': 'png,jpg,jpeg,gif,bmp,pdf,doc,docx,xls,xlsx,txt,zip,rar',
        'max_upload_size_mb': 100,
        'max_log_size_mb': 50,
        'log_backup_count': 100,
        'host': '127.0.0.1',
        'port': 5000,
        'debug': False
    }

    try:
        if os.path.exists(config_path):
            config.read(config_path, encoding='utf-8')
            result = {
                'secret_key': config.get('security', 'secret_key', fallback=default_config['secret_key']),
                'default_username': config.get('security', 'default_username', fallback=default_config['default_username']),
                'default_password': config.get('security', 'default_password', fallback=default_config['default_password']),
                'session_lifetime_hours': config.getint('session', 'lifetime_hours', fallback=default_config['session_lifetime_hours']),
                'allowed_extensions': set(config.get('upload', 'allowed_extensions', fallback=default_config['allowed_extensions']).split(',')),
                'max_upload_size_mb': config.getint('upload', 'max_upload_size_mb', fallback=default_config['max_upload_size_mb']),
                'max_log_size_mb': config.getint('logging', 'max_log_size_mb', fallback=default_config['max_log_size_mb']),
                'log_backup_count': config.getint('logging', 'log_backup_count', fallback=default_config['log_backup_count']),
                'host': config.get('server', 'host', fallback=default_config['host']),
                'port': config.getint('server', 'port', fallback=default_config['port']),
                'debug': config.getboolean('server', 'debug', fallback=default_config['debug'])
            }
            logging.info(f'已加载外部配置文件: {config_path}')
            return result
        else:
            logging.warning(f'配置文件不存在: {config_path}，使用默认配置')
    except Exception as e:
        logging.error(f'加载配置文件失败: {str(e)}，使用默认配置')

    default_config['allowed_extensions'] = set(default_config['allowed_extensions'].split(','))
    return default_config


CONFIG = load_config()
