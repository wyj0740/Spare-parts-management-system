#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件夹管理路由模块
"""
import os
import logging
from datetime import datetime
from flask import Blueprint

from models import SparePart
from routes.common import APIResponse, login_required
from utils.folder_manager import (
    get_spare_part_folder_path, get_historical_documents_path, get_files_root_path,
    open_folder_in_explorer, create_spare_part_folder
)

folders_bp = Blueprint('folders', __name__)


@folders_bp.route('/api/folder/spare-part/<int:part_id>/open', methods=['POST'])
@login_required
def open_spare_part_folder(part_id):
    try:
        part = SparePart.query.get_or_404(part_id)
        folder_path = get_spare_part_folder_path(part.asset_number, part.name)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        open_folder_in_explorer(folder_path)
        logging.info(f'打开备件文件夹 - ID: {part_id}, 路径: {folder_path}')
        return APIResponse.success(data={'folder_path': folder_path}, message='已打开文件夹')
    except Exception as e:
        logging.error(f'打开备件文件夹失败 - ID: {part_id}, 错误: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@folders_bp.route('/api/folder/spare-part/<int:part_id>/info', methods=['GET'])
@login_required
def get_spare_part_folder_info(part_id):
    try:
        part = SparePart.query.get_or_404(part_id)
        folder_path = get_spare_part_folder_path(part.asset_number, part.name)
        folder_exists = os.path.exists(folder_path)
        file_count = 0
        total_size = 0
        files = []

        if folder_exists:
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                if os.path.isfile(item_path):
                    file_size = os.path.getsize(item_path)
                    file_count += 1
                    total_size += file_size
                    files.append({
                        'name': item,
                        'size': file_size,
                        'modified': datetime.fromtimestamp(os.path.getmtime(item_path)).strftime('%Y-%m-%d %H:%M:%S')
                    })

        return APIResponse.success(data={
            'folder_path': folder_path,
            'folder_exists': folder_exists,
            'file_count': file_count,
            'total_size': total_size,
            'files': files
        })
    except Exception as e:
        logging.error(f'获取备件文件夹信息失败 - ID: {part_id}, 错误: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@folders_bp.route('/api/folder/historical-documents/open', methods=['POST'])
@login_required
def open_historical_documents_folder():
    try:
        folder_path = get_historical_documents_path()
        open_folder_in_explorer(folder_path)
        logging.info(f'打开历史文件夹 - 路径: {folder_path}')
        return APIResponse.success(data={'folder_path': folder_path}, message='已打开文件夹')
    except Exception as e:
        logging.error(f'打开历史文件夹失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@folders_bp.route('/api/folder/historical-documents/info', methods=['GET'])
@login_required
def get_historical_documents_folder_info():
    try:
        folder_path = get_historical_documents_path()
        file_count = 0
        total_size = 0
        files = []

        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isfile(item_path):
                file_size = os.path.getsize(item_path)
                file_count += 1
                total_size += file_size
                files.append({
                    'name': item,
                    'size': file_size,
                    'modified': datetime.fromtimestamp(os.path.getmtime(item_path)).strftime('%Y-%m-%d %H:%M:%S')
                })

        return APIResponse.success(data={
            'folder_path': folder_path,
            'file_count': file_count,
            'total_size': total_size,
            'files': files
        })
    except Exception as e:
        logging.error(f'获取历史文件夹信息失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@folders_bp.route('/api/folder/root/open', methods=['POST'])
@login_required
def open_files_root_folder():
    try:
        folder_path = get_files_root_path()
        open_folder_in_explorer(folder_path)
        logging.info(f'打开文件根目录 - 路径: {folder_path}')
        return APIResponse.success(data={'folder_path': folder_path}, message='已打开文件夹')
    except Exception as e:
        logging.error(f'打开文件根目录失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@folders_bp.route('/api/folder/spare-parts/status', methods=['GET'])
@login_required
def get_all_spare_parts_folder_status():
    """获取所有备件的文件夹状态（优化：减少重复文件系统调用）"""
    try:
        parts = SparePart.query.all()
        folder_status = {}

        for part in parts:
            folder_path = get_spare_part_folder_path(part.asset_number, part.name)
            file_count = 0
            folder_modified = None

            if os.path.exists(folder_path):
                try:
                    entries = os.listdir(folder_path)
                    for item in entries:
                        if os.path.isfile(os.path.join(folder_path, item)):
                            file_count += 1
                    folder_modified = datetime.fromtimestamp(os.path.getmtime(folder_path)).strftime('%Y-%m-%d %H:%M')
                except OSError:
                    pass

            folder_status[part.id] = {
                'file_count': file_count,
                'folder_exists': os.path.exists(folder_path),
                'last_modified': folder_modified
            }

        return APIResponse.success(data=folder_status)
    except Exception as e:
        logging.error(f'获取备件文件夹状态失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@folders_bp.route('/api/folder/spare-parts/batch-init', methods=['POST'])
@login_required
def batch_init_spare_part_folders():
    try:
        parts = SparePart.query.all()
        created_count = 0
        existed_count = 0

        for part in parts:
            folder_path = get_spare_part_folder_path(part.asset_number, part.name)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                created_count += 1
            else:
                existed_count += 1

        logging.info(f'批量初始化备件文件夹 - 新建: {created_count}, 已存在: {existed_count}')
        return APIResponse.success(data={
            'created_count': created_count,
            'existed_count': existed_count,
            'total': created_count + existed_count
        }, message=f'文件夹初始化完成！新建 {created_count} 个，已存在 {existed_count} 个')
    except Exception as e:
        logging.error(f'批量初始化文件夹失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))
