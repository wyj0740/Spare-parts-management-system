#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日志配置模块
"""
import logging
from logging.handlers import RotatingFileHandler
from config import CONFIG
from utils.helpers import get_log_path


LOG_MAX_SIZE = CONFIG['max_upload_size_mb'] * 1024 * 1024
LOG_BACKUP_COUNT = CONFIG['log_backup_count']


def setup_logging(app=None):
    """配置日志系统"""
    log_file = get_log_path()

    log_format = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_SIZE,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_format)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # 避免重复添加 handler
    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        root_logger.addHandler(file_handler)
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(console_handler)

    if app:
        app.logger.setLevel(logging.INFO)
        if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
            app.logger.addHandler(file_handler)

    logging.info('=' * 60)
    logging.info('备品备件管理系统启动')
    from config import get_app_dir, get_resource_path
    import sys
    logging.info(f'程序目录: {get_app_dir()}')
    logging.info(f'资源目录: {getattr(sys, "_MEIPASS", "开发环境")}')
    logging.info(f'模板目录: {app.template_folder if app else "N/A"}')
    logging.info(f'静态目录: {app.static_folder if app else "N/A"}')
    from utils.helpers import get_database_path
    logging.info(f'数据库文件: {get_database_path()}')
    logging.info(f'日志文件: {log_file}')
    logging.info('=' * 60)
