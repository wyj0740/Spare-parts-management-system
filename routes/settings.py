#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系统配置路由模块
"""
import os
import json
import logging
import configparser
from flask import Blueprint, request, session
from werkzeug.security import generate_password_hash, check_password_hash

from config import CONFIG, get_app_dir
from models import APP_VERSION
from routes.common import APIResponse, login_required

settings_bp = Blueprint('settings', __name__)


def get_users_path():
    return os.path.join(get_app_dir(), 'data', 'users.json')


def _read_config_raw():
    """读取config.ini原始内容"""
    config = configparser.ConfigParser()
    config_path = os.path.join(get_app_dir(), 'config.ini')
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
    return config, config_path


def _write_config(config, config_path):
    with open(config_path, 'w', encoding='utf-8') as f:
        config.write(f)


@settings_bp.route('/api/settings/info', methods=['GET'])
@login_required
def get_system_info():
    """获取系统基本信息"""
    try:
        config, _ = _read_config_raw()
        return APIResponse.success(data={
            'version': APP_VERSION,
            'host': config.get('server', 'host', fallback='127.0.0.1'),
            'port': config.getint('server', 'port', fallback=5000),
            'session_lifetime_hours': config.getint('session', 'lifetime_hours', fallback=24),
            'auto_backup_enabled': config.getboolean('backup', 'auto_backup_enabled', fallback=True),
            'backup_time': config.get('backup', 'backup_time', fallback='02:00'),
            'backup_keep_days': config.getint('backup', 'backup_keep_days', fallback=30),
            'backup_type': config.get('backup', 'backup_type', fallback='both'),
        })
    except Exception as e:
        logging.error(f'获取系统信息失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@settings_bp.route('/api/settings/server', methods=['PUT'])
@login_required
def update_server_settings():
    """更新服务器配置（端口/会话时长），重启后生效"""
    try:
        data = request.get_json()
        config, config_path = _read_config_raw()

        if not config.has_section('server'):
            config.add_section('server')
        if not config.has_section('session'):
            config.add_section('session')

        if 'port' in data:
            port = int(data['port'])
            if not (1024 <= port <= 65535):
                return APIResponse.error('端口范围须在 1024~65535 之间'), 400
            config.set('server', 'port', str(port))

        if 'host' in data:
            if data['host'] not in ('127.0.0.1', '0.0.0.0'):
                return APIResponse.error('host 只能为 127.0.0.1 或 0.0.0.0'), 400
            config.set('server', 'host', data['host'])

        if 'session_lifetime_hours' in data:
            hours = int(data['session_lifetime_hours'])
            if not (1 <= hours <= 168):
                return APIResponse.error('会话时长范围须在 1~168 小时之间'), 400
            config.set('session', 'lifetime_hours', str(hours))

        _write_config(config, config_path)
        logging.info(f'服务器配置已更新: {data}, 操作人: {session.get("username")}')
        return APIResponse.success(message='配置已保存，重启程序后生效')
    except Exception as e:
        logging.error(f'更新服务器配置失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@settings_bp.route('/api/settings/password', methods=['PUT'])
@login_required
def change_password():
    """修改当前用户密码"""
    try:
        data = request.get_json()
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')

        if not old_password or not new_password:
            return APIResponse.error('请填写完整的密码信息'), 400
        if len(new_password) < 4:
            return APIResponse.error('新密码长度不能少于4位'), 400
        if new_password != confirm_password:
            return APIResponse.error('两次输入的新密码不一致'), 400

        username = session.get('username')
        users_path = get_users_path()

        if not os.path.exists(users_path):
            return APIResponse.error('用户数据文件不存在'), 500

        with open(users_path, 'r', encoding='utf-8') as f:
            users = json.load(f)

        if username not in users:
            return APIResponse.error('用户不存在'), 404

        from werkzeug.security import check_password_hash
        if not check_password_hash(users[username], old_password):
            # 兼容旧配置明文密码
            if users[username] != old_password:
                return APIResponse.error('原密码错误'), 400

        users[username] = generate_password_hash(new_password)
        with open(users_path, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False)

        logging.info(f'用户 {username} 修改了密码')
        return APIResponse.success(message='密码修改成功，下次登录使用新密码')
    except Exception as e:
        logging.error(f'修改密码失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))
