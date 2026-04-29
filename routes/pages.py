#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
页面路由模块
"""
import os
from flask import Blueprint, render_template, redirect, url_for, session, send_from_directory

from routes.common import login_required

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/login', methods=['GET'])
def login_page():
    """登录页面"""
    if 'logged_in' in session:
        return redirect(url_for('pages.index'))
    return render_template('login.html')


@pages_bp.route('/')
@login_required
def index():
    """主页 - 备件列表"""
    return render_template('index.html')


@pages_bp.route('/create')
@login_required
def create_page():
    """创建备件页面"""
    return render_template('create.html')


@pages_bp.route('/detail/<int:part_id>')
@login_required
def detail_page(part_id):
    """备件详情页面"""
    return render_template('detail.html', part_id=part_id)


@pages_bp.route('/historical-documents')
@login_required
def historical_documents_page():
    """历史文件管理页面"""
    return render_template('historical_documents.html')


@pages_bp.route('/backup')
@login_required
def backup_page():
    """备份管理页面"""
    return render_template('backup.html')


@pages_bp.route('/audit')
@login_required
def audit_page():
    """操作日志页面"""
    return render_template('audit.html')


@pages_bp.route('/settings')
@login_required
def settings_page():
    """系统配置页面"""
    return render_template('settings.html')


@pages_bp.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(os.path.dirname(__file__), '..', 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')
