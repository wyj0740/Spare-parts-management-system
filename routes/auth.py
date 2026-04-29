#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
认证路由模块
"""
import os
import json
import logging
from flask import Blueprint, request, session
from werkzeug.security import generate_password_hash, check_password_hash

from config import CONFIG, get_app_dir
from routes.common import APIResponse

auth_bp = Blueprint('auth', __name__)


def get_users_path():
    return os.path.join(get_app_dir(), 'data', 'users.json')


def init_users():
    """初始化用户文件，首次运行将 config.ini 中的默认密码哈希化存储"""
    path = get_users_path()
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        users = {
            CONFIG['default_username']: generate_password_hash(CONFIG['default_password'])
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(users, f)


def verify_password(username, password):
    """验证用户名密码"""
    init_users()
    path = get_users_path()
    with open(path, 'r', encoding='utf-8') as f:
        users = json.load(f)
    if username not in users:
        # 兼容旧配置：如果用户不存在但匹配默认账号，也允许登录并创建记录
        if username == CONFIG['default_username'] and password == CONFIG['default_password']:
            users[username] = generate_password_hash(password)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(users, f)
            return True
        return False
    return check_password_hash(users[username], password)


@auth_bp.route('/api/login', methods=['POST'])
def login():
    """处理登录"""
    try:
        data = request.get_json()
        username = data.get('username', '')
        password = data.get('password', '')

        logging.info(f'登录尝试 - 用户名: {username}')

        if verify_password(username, password):
            session['logged_in'] = True
            session['username'] = username
            session.permanent = True
            logging.info(f'登录成功 - 用户: {username}')
            return APIResponse.success(message='登录成功')
        else:
            logging.warning(f'登录失败 - 用户名: {username}')
            return APIResponse.error(message='用户名或密码错误', code=401)
    except Exception as e:
        logging.error(f'登录失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    """登出"""
    username = session.get('username', 'Unknown')
    session.clear()
    logging.info(f'用户登出 - 用户: {username}')
    return APIResponse.success(message='登出成功')
