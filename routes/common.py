#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
路由公共模块
"""
from functools import wraps
from flask import jsonify, request, session, redirect, url_for


class APIResponse:
    """统一的API响应格式"""

    @staticmethod
    def success(data=None, message="操作成功", code=200):
        response = {
            'success': True,
            'code': code,
            'message': message
        }
        if data is not None:
            response['data'] = data
        return jsonify(response), code

    @staticmethod
    def error(message="操作失败", code=400, error_type=None):
        response = {
            'success': False,
            'code': code,
            'message': message
        }
        if error_type:
            response['error_type'] = error_type
        return jsonify(response), code

    @staticmethod
    def not_found(message="资源不存在"):
        return APIResponse.error(message=message, code=404, error_type='NOT_FOUND')

    @staticmethod
    def validation_error(message="数据验证失败", errors=None):
        response = {
            'success': False,
            'code': 422,
            'message': message,
            'error_type': 'VALIDATION_ERROR'
        }
        if errors:
            response['errors'] = errors
        return jsonify(response), 422

    @staticmethod
    def server_error(message="服务器内部错误"):
        return APIResponse.error(message=message, code=500, error_type='SERVER_ERROR')


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            if request.path.startswith('/api/'):
                return APIResponse.error(message="未登录", code=401, error_type='UNAUTHORIZED')
            return redirect(url_for('pages.login_page'))
        return f(*args, **kwargs)
    return decorated_function
