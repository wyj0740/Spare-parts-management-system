#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
备份管理路由模块
"""
import os
import logging
from datetime import datetime
from flask import Blueprint, request, send_from_directory

from routes.common import APIResponse, login_required
from utils.backup_manager import (
    load_backup_config, save_backup_config, perform_database_backup,
    perform_excel_backup, init_backup_scheduler, shutdown_backup_scheduler
)

backup_bp = Blueprint('backup', __name__)


@backup_bp.route('/api/backup/config', methods=['GET'])
@login_required
def get_backup_config():
    try:
        config = load_backup_config()
        return APIResponse.success(data=config)
    except Exception as e:
        logging.error(f'获取备份配置失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@backup_bp.route('/api/backup/config', methods=['PUT'])
@login_required
def update_backup_config():
    try:
        data = request.get_json()
        config = load_backup_config()

        if 'auto_backup_enabled' in data:
            config['auto_backup_enabled'] = data['auto_backup_enabled']
        if 'backup_time' in data:
            config['backup_time'] = data['backup_time']
        if 'keep_days' in data:
            config['keep_days'] = int(data['keep_days'])
        if 'backup_type' in data:
            config['backup_type'] = data['backup_type']

        save_backup_config(config)
        shutdown_backup_scheduler()
        from flask import current_app
        init_backup_scheduler(current_app)

        logging.info(f'备份配置已更新: {config}')
        return APIResponse.success(data=config, message='配置更新成功')
    except Exception as e:
        logging.error(f'更新备份配置失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@backup_bp.route('/api/backup/now', methods=['POST'])
@login_required
def backup_now():
    try:
        backup_type = request.get_json().get('backup_type', 'both')
        results = []

        if backup_type in ['both', 'database']:
            db_result = perform_database_backup()
            if db_result:
                results.append(db_result)

        if backup_type in ['both', 'excel']:
            from flask import current_app
            excel_result = perform_excel_backup(current_app)
            if excel_result:
                results.append(excel_result)

        if results:
            return APIResponse.success(data=results, message=f'备份完成，成功 {len(results)} 个文件')
        else:
            return APIResponse.error(message='备份失败'), 500
    except Exception as e:
        logging.error(f'手动备份失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@backup_bp.route('/api/backup/list', methods=['GET'])
@login_required
def list_backups():
    try:
        from utils.helpers import get_backup_path
        backup_dir = get_backup_path()

        if not os.path.exists(backup_dir):
            return APIResponse.success(data=[])

        backups = []
        for filename in os.listdir(backup_dir):
            if not (filename.startswith('database_backup_') or filename.startswith('excel_backup_')):
                continue

            filepath = os.path.join(backup_dir, filename)
            file_stat = os.stat(filepath)
            backup_type = 'database' if filename.startswith('database_backup_') else 'excel'

            backups.append({
                'filename': filename,
                'type': backup_type,
                'size': file_stat.st_size,
                'created_at': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            })

        backups.sort(key=lambda x: x['created_at'], reverse=True)
        return APIResponse.success(data=backups)
    except Exception as e:
        logging.error(f'获取备份列表失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@backup_bp.route('/api/backup/download/<filename>', methods=['GET'])
@login_required
def download_backup(filename):
    try:
        if not (filename.startswith('database_backup_') or filename.startswith('excel_backup_')):
            return APIResponse.error(message='非法的文件名'), 400

        from utils.helpers import get_backup_path
        backup_dir = get_backup_path()
        filepath = os.path.join(backup_dir, filename)

        if not os.path.exists(filepath):
            return APIResponse.error(message='文件不存在'), 404

        logging.info(f'下载备份文件: {filename}')
        return send_from_directory(backup_dir, filename, as_attachment=True)
    except Exception as e:
        logging.error(f'下载备份失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@backup_bp.route('/api/backup/delete/<filename>', methods=['DELETE'])
@login_required
def delete_backup(filename):
    try:
        if not (filename.startswith('database_backup_') or filename.startswith('excel_backup_')):
            return APIResponse.error(message='非法的文件名'), 400

        from utils.helpers import get_backup_path
        backup_dir = get_backup_path()
        filepath = os.path.join(backup_dir, filename)

        if not os.path.exists(filepath):
            return APIResponse.error(message='文件不存在'), 404

        os.remove(filepath)
        logging.info(f'备份文件已删除: {filename}')
        return APIResponse.success(message='备份文件删除成功')
    except Exception as e:
        logging.error(f'删除备份失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))

