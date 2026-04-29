#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件夹管理工具
"""
import os
import sys
import shutil
import re
import subprocess
import logging
from config import get_app_dir


def get_files_root_path():
    """获取文件管理根目录"""
    files_dir = os.path.join(get_app_dir(), 'files')
    if not os.path.exists(files_dir):
        os.makedirs(files_dir)
    return files_dir


def get_spare_parts_files_path():
    """获取备件文件夹根目录"""
    spare_parts_dir = os.path.join(get_files_root_path(), 'spare_parts')
    if not os.path.exists(spare_parts_dir):
        os.makedirs(spare_parts_dir)
    return spare_parts_dir


def get_historical_documents_path():
    """获取历史文件夹目录"""
    historical_dir = os.path.join(get_files_root_path(), 'historical_documents')
    if not os.path.exists(historical_dir):
        os.makedirs(historical_dir)
    return historical_dir


def sanitize_folder_name(name):
    """清理文件夹名称，移除或替换不允许的字符"""
    invalid_chars = r'[\\/:*?"<>|]'
    sanitized = re.sub(invalid_chars, '_', name)
    sanitized = sanitized.strip(' .')
    return sanitized if sanitized else 'unnamed'


def get_spare_part_folder_name(asset_number, name):
    """生成备件文件夹名称"""
    safe_asset = sanitize_folder_name(asset_number)
    safe_name = sanitize_folder_name(name)
    return f"{safe_asset}_{safe_name}"


def get_spare_part_folder_path(asset_number, name):
    """获取指定备件的文件夹路径"""
    folder_name = get_spare_part_folder_name(asset_number, name)
    return os.path.join(get_spare_parts_files_path(), folder_name)


def create_spare_part_folder(asset_number, name):
    """创建备件对应的文件夹"""
    folder_path = get_spare_part_folder_path(asset_number, name)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        logging.info(f'创建备件文件夹: {folder_path}')
    return folder_path


def delete_spare_part_folder(asset_number, name):
    """删除备件对应的文件夹"""
    folder_path = get_spare_part_folder_path(asset_number, name)
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        logging.info(f'删除备件文件夹: {folder_path}')
        return True
    return False


def rename_spare_part_folder(old_asset_number, old_name, new_asset_number, new_name):
    """重命名备件文件夹（当资产编号或名称变更时）"""
    old_folder_path = get_spare_part_folder_path(old_asset_number, old_name)
    new_folder_path = get_spare_part_folder_path(new_asset_number, new_name)

    if old_folder_path == new_folder_path:
        return True

    if os.path.exists(old_folder_path):
        if os.path.exists(new_folder_path):
            for item in os.listdir(old_folder_path):
                src = os.path.join(old_folder_path, item)
                dst = os.path.join(new_folder_path, item)
                if os.path.exists(dst):
                    base, ext = os.path.splitext(item)
                    counter = 1
                    while os.path.exists(dst):
                        dst = os.path.join(new_folder_path, f"{base}_{counter}{ext}")
                        counter += 1
                shutil.move(src, dst)
            shutil.rmtree(old_folder_path)
        else:
            os.rename(old_folder_path, new_folder_path)
        logging.info(f'重命名备件文件夹: {old_folder_path} -> {new_folder_path}')
        return True
    else:
        create_spare_part_folder(new_asset_number, new_name)
        return True


def open_folder_in_explorer(folder_path):
    """在Windows资源管理器中打开指定文件夹"""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    if sys.platform == 'win32':
        os.startfile(folder_path)
        return True
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', folder_path])
        return True
    else:
        subprocess.Popen(['xdg-open', folder_path])
        return True
