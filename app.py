#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
备品备件管理系统 - 主应用程序
Author: wyj
License: MIT License
"""
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from functools import wraps
import os
import sys
import pandas as pd
from io import BytesIO
import webbrowser
import threading
import time
import signal
import atexit
import logging
from logging.handlers import RotatingFileHandler
from werkzeug.utils import secure_filename
import shutil
import json
import configparser
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
try:
    from pystray import Icon, MenuItem, Menu
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# 导入数据库迁移模块
try:
    from db_migration import check_and_migrate, backup_database
    HAS_MIGRATION = True
except ImportError:
    HAS_MIGRATION = False
    print("⚠ 警告: 数据库迁移模块不可用")


# ==================== 工具函数 ====================

def get_app_dir():
    """获取应用程序目录（开发环境或打包后）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后的exe目录
        return os.path.dirname(sys.executable)
    else:
        # 开发环境
        return os.path.abspath(".")


# ==================== 配置文件加载 ====================

def load_config():
    """加载外部配置文件"""
    config = configparser.ConfigParser()
    config_path = os.path.join(get_app_dir(), 'config.ini')
    
    # 默认配置
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
            
            # 读取配置
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
    
    # 返回默认配置
    default_config['allowed_extensions'] = set(default_config['allowed_extensions'].split(','))
    return default_config


# ==================== 常量配置 ====================

# 加载配置
CONFIG = load_config()

# 文件上传配置
ALLOWED_EXTENSIONS = CONFIG['allowed_extensions']
MAX_UPLOAD_SIZE = CONFIG['max_upload_size_mb'] * 1024 * 1024

# 日志配置
LOG_MAX_SIZE = CONFIG['max_log_size_mb'] * 1024 * 1024
LOG_BACKUP_COUNT = CONFIG['log_backup_count']

# 会话配置
SESSION_LIFETIME_HOURS = CONFIG['session_lifetime_hours']

# 默认账号密码
DEFAULT_USERNAME = CONFIG['default_username']
DEFAULT_PASSWORD = CONFIG['default_password']


# ==================== 其他工具函数 ====================

def get_upload_path():
    """获取文件上传目录"""
    upload_dir = os.path.join(get_app_dir(), 'uploads')
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    return upload_dir


def allowed_file(filename):
    """检查文件类型是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_resource_path(relative_path):
    """获取资源文件的绝对路径，支持PyInstaller打包"""
    try:
        # PyInstaller创建的临时文件夹
        base_path = sys._MEIPASS
    except Exception:
        # 开发环境
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


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


# ==================== 日志配置 ====================

def setup_logging():
    """配置日志系统"""
    log_file = get_log_path()
    
    # 创建日志格式
    log_format = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 文件处理器 - 使用 RotatingFileHandler 自动轮转日志
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_SIZE,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_format)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 配置 Flask 日志
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    logging.info('='*60)
    logging.info('备品备件管理系统启动')
    logging.info(f'日志文件: {log_file}')
    logging.info('='*60)


# ==================== Flask应用初始化 ====================

app = Flask(__name__, 
            template_folder=get_resource_path('templates'),
            static_folder=get_resource_path('static'))

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{get_database_path()}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', CONFIG['secret_key'])
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE
app.config['UPLOAD_FOLDER'] = get_upload_path()
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=SESSION_LIFETIME_HOURS)

db = SQLAlchemy(app)

# 设置日志
setup_logging()


# ==================== API统一响应格式 ====================

class APIResponse:
    """统一的API响应格式"""
    
    @staticmethod
    def success(data=None, message="操作成功", code=200):
        """成功响应"""
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
        """错误响应"""
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
        """资源不存在响应"""
        return APIResponse.error(message=message, code=404, error_type='NOT_FOUND')
    
    @staticmethod
    def validation_error(message="数据验证失败", errors=None):
        """数据验证错误响应"""
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
        """服务器错误响应"""
        return APIResponse.error(message=message, code=500, error_type='SERVER_ERROR')


# ==================== 全局错误处理 ====================

@app.errorhandler(404)
def not_found_error(error):
    """处理04错误"""
    logging.warning(f'404错误: {request.url}')
    if request.path.startswith('/api/'):
        return APIResponse.not_found("请求的资源不存在")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """处理500错误"""
    logging.error(f'500错误: {str(error)}', exc_info=True)
    db.session.rollback()
    if request.path.startswith('/api/'):
        return APIResponse.server_error("服务器内部错误，请稍后重试")
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_exception(error):
    """处理所有未捕获的异常"""
    logging.error(f'未处理的异常: {str(error)}', exc_info=True)
    db.session.rollback()
    if request.path.startswith('/api/'):
        return APIResponse.server_error(f"系统错误: {str(error)}")
    return render_template('500.html'), 500


# ==================== 登录验证装饰器 ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== 备份配置管理 ====================

def load_backup_config():
    """加载备份配置"""
    config_path = get_backup_config_path()
    default_config = {
        'enabled': True,
        'auto_backup_enabled': True,
        'backup_time': '02:00',  # 默认凌晨2点备份
        'keep_days': 30,  # 保留30天的备份
        'backup_type': 'both'  # both/database/excel
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return {**default_config, **config}
        except:
            pass
    
    return default_config

def save_backup_config(config):
    """保存备份配置"""
    config_path = get_backup_config_path()
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def perform_database_backup():
    """执行数据库文件备份"""
    try:
        db_path = get_database_path()
        if not os.path.exists(db_path):
            logging.warning('数据库文件不存在，无需备份')
            return None
        
        backup_dir = get_backup_path()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'database_backup_{timestamp}.db'
        backup_filepath = os.path.join(backup_dir, backup_filename)
        
        # 复制数据库文件
        shutil.copy2(db_path, backup_filepath)
        
        file_size = os.path.getsize(backup_filepath)
        logging.info(f'数据库备份成功: {backup_filename} ({file_size} bytes)')
        
        return {
            'filename': backup_filename,
            'filepath': backup_filepath,
            'size': file_size,
            'type': 'database',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        logging.error(f'数据库备份失败: {str(e)}', exc_info=True)
        return None


def perform_excel_backup():
    """执行Excel数据备份"""
    try:
        backup_dir = get_backup_path()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'excel_backup_{timestamp}.xlsx'
        backup_filepath = os.path.join(backup_dir, backup_filename)
        
        with app.app_context():
            # 获取所有数据
            spare_parts = SparePart.query.all()
            spare_part_ids = [part.id for part in spare_parts]
            
            with pd.ExcelWriter(backup_filepath, engine='openpyxl') as writer:
                # Sheet 1: 备件列表
                if spare_parts:
                    data = []
                    for part in spare_parts:
                        part_dict = part.to_dict()
                        data.append({
                            'ID': part_dict['id'],
                            '名称': part_dict['name'],
                            '资产编号': part_dict['asset_number'],
                            '系统': part_dict['ownership'],
                            '设备类型': part_dict['device_type'],
                            '上次检定日期': part_dict['last_inspection_date'],
                            '下次检定日期': part_dict['next_inspection_date'],
                            '使用状态': part_dict['usage_status'],
                            '存放地点': part_dict['storage_location'],
                            '规格型号': part_dict['specifications'],
                            '生产厂家': part_dict['manufacturer'],
                            '出厂编号': part_dict['product_number'],
                            '采购日期': part_dict['purchase_date'],
                            '质保期(月)': part_dict['warranty_period'],
                            '单价': part_dict['unit_price'],
                            '备注': part_dict['remarks']
                        })
                    df = pd.DataFrame(data)
                    df.to_excel(writer, index=False, sheet_name='备件列表')
                
                # Sheet 2: 入库记录
                if spare_part_ids:
                    inbound_records = InboundRecord.query.filter(InboundRecord.spare_part_id.in_(spare_part_ids)).order_by(InboundRecord.inbound_date.desc()).all()
                    if inbound_records:
                        inbound_data = []
                        for record in inbound_records:
                            r_dict = record.to_dict()
                            inbound_data.append({
                                'ID': r_dict['id'],
                                '备件名称': r_dict['spare_part_name'],
                                '资产编号': r_dict['spare_part_asset_number'],
                                '数量': r_dict['quantity'],
                                '操作者': r_dict['operator_name'],
                                '入库时间': r_dict['inbound_date'],
                                '供应商': r_dict['supplier'],
                                '批次号': r_dict['batch_number'],
                                '备注': r_dict['remarks']
                            })
                        df_inbound = pd.DataFrame(inbound_data)
                        df_inbound.to_excel(writer, index=False, sheet_name='入库记录')
                
                # Sheet 3: 出库记录
                if spare_part_ids:
                    outbound_records = OutboundRecord.query.filter(OutboundRecord.spare_part_id.in_(spare_part_ids)).order_by(OutboundRecord.outbound_date.desc()).all()
                    if outbound_records:
                        outbound_data = []
                        for record in outbound_records:
                            r_dict = record.to_dict()
                            outbound_data.append({
                                'ID': r_dict['id'],
                                '备件名称': r_dict['spare_part_name'],
                                '资产编号': r_dict['spare_part_asset_number'],
                                '数量': r_dict['quantity'],
                                '操作者': r_dict['operator_name'],
                                '出库时间': r_dict['outbound_date'],
                                '领用人': r_dict['recipient'],
                                '用途': r_dict['purpose'],
                                '预计归还日期': r_dict['expected_return_date'],
                                '备注': r_dict['remarks']
                            })
                        df_outbound = pd.DataFrame(outbound_data)
                        df_outbound.to_excel(writer, index=False, sheet_name='出库记录')
                
                # Sheet 4: 维护记录
                if spare_part_ids:
                    maintenance_records = MaintenanceRecord.query.filter(MaintenanceRecord.spare_part_id.in_(spare_part_ids)).order_by(MaintenanceRecord.maintenance_date.desc()).all()
                    if maintenance_records:
                        maintenance_data = []
                        for record in maintenance_records:
                            r_dict = record.to_dict()
                            maintenance_data.append({
                                'ID': r_dict['id'],
                                '备件名称': r_dict['spare_part_name'],
                                '资产编号': r_dict['spare_part_asset_number'],
                                '操作者': r_dict['operator_name'],
                                '维护日期': r_dict['maintenance_date'],
                                '维护类型': r_dict['maintenance_type'],
                                '维护内容': r_dict['maintenance_content'],
                                '上次检定日期': r_dict['last_inspection_date'],
                                '检定有效期(月)': r_dict['inspection_validity_period'],
                                '下次检定日期': r_dict['next_inspection_date'],
                                '维护费用': r_dict['maintenance_cost'],
                                '备注': r_dict['remarks']
                            })
                        df_maintenance = pd.DataFrame(maintenance_data)
                        df_maintenance.to_excel(writer, index=False, sheet_name='维护记录')
                
                # Sheet 5: 故障记录
                if spare_part_ids:
                    fault_records = FaultRecord.query.filter(FaultRecord.spare_part_id.in_(spare_part_ids)).order_by(FaultRecord.fault_date.desc()).all()
                    if fault_records:
                        fault_data = []
                        for record in fault_records:
                            r_dict = record.to_dict()
                            fault_data.append({
                                'ID': r_dict['id'],
                                '备件名称': r_dict['spare_part_name'],
                                '资产编号': r_dict['spare_part_asset_number'],
                                '操作者': r_dict['operator_name'],
                                '故障时间': r_dict['fault_date'],
                                '故障描述': r_dict['fault_description'],
                                '故障类型': r_dict['fault_type'],
                                '维修状态': r_dict['repair_status'],
                                '维修完成日期': r_dict['repair_date'],
                                '维修费用': r_dict['repair_cost'],
                                '备注': r_dict['remarks']
                            })
                        df_fault = pd.DataFrame(fault_data)
                        df_fault.to_excel(writer, index=False, sheet_name='故障记录')
        
        file_size = os.path.getsize(backup_filepath)
        logging.info(f'Excel备份成功: {backup_filename} ({file_size} bytes)')
        
        return {
            'filename': backup_filename,
            'filepath': backup_filepath,
            'size': file_size,
            'type': 'excel',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        logging.error(f'Excel备份失败: {str(e)}', exc_info=True)
        return None

# 执行完整备份
def perform_full_backup():
    """执行完整备份（数据库+Excel）"""
    logging.info('='*60)
    logging.info('开始执行自动备份')
    logging.info('='*60)
    
    config = load_backup_config()
    backup_type = config.get('backup_type', 'both')
    
    results = []
    
    if backup_type in ['both', 'database']:
        db_result = perform_database_backup()
        if db_result:
            results.append(db_result)
    
    if backup_type in ['both', 'excel']:
        excel_result = perform_excel_backup()
        if excel_result:
            results.append(excel_result)
    
    # 清理旧备份
    cleanup_old_backups()
    
    logging.info('='*60)
    logging.info(f'备份完成: 成功 {len(results)} 个文件')
    logging.info('='*60)
    
    return results

# 清理旧备份
def cleanup_old_backups():
    """清理过期的备份文件"""
    try:
        config = load_backup_config()
        keep_days = config.get('keep_days', 30)
        backup_dir = get_backup_path()
        
        if not os.path.exists(backup_dir):
            return
        
        cutoff_time = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0
        
        for filename in os.listdir(backup_dir):
            if not (filename.startswith('database_backup_') or filename.startswith('excel_backup_')):
                continue
            
            filepath = os.path.join(backup_dir, filename)
            file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            if file_mtime < cutoff_time:
                os.remove(filepath)
                deleted_count += 1
                logging.info(f'删除过期备份: {filename}')
        
        if deleted_count > 0:
            logging.info(f'清理完成: 删除 {deleted_count} 个过期备份')
    except Exception as e:
        logging.error(f'清理旧备份失败: {str(e)}', exc_info=True)

# 初始化备份调度器
backup_scheduler = None

def init_backup_scheduler():
    """初始化备份调度器"""
    global backup_scheduler
    
    config = load_backup_config()
    
    if not config.get('auto_backup_enabled', True):
        logging.info('自动备份已禁用')
        return
    
    backup_time = config.get('backup_time', '02:00')
    hour, minute = map(int, backup_time.split(':'))
    
    backup_scheduler = BackgroundScheduler()
    backup_scheduler.add_job(
        perform_full_backup,
        trigger=CronTrigger(hour=hour, minute=minute),
        id='auto_backup',
        name='自动备份任务',
        replace_existing=True
    )
    backup_scheduler.start()
    
    logging.info(f'自动备份已启用: 每天 {backup_time} 执行')

def shutdown_backup_scheduler():
    """关闭备份调度器"""
    global backup_scheduler
    if backup_scheduler:
        backup_scheduler.shutdown()
        logging.info('备份调度器已关闭')

# 数据模型
class SparePart(db.Model):
    """备品备件主表"""
    __tablename__ = 'spare_parts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)  # 名称 - 添加索引
    asset_number = db.Column(db.String(50), unique=True, nullable=False, index=True)  # 资产编号 - 添加索引
    device_type = db.Column(db.String(50))  # 设备类型
    last_inspection_date = db.Column(db.Date)  # 上次检定日期
    next_inspection_date = db.Column(db.Date, index=True)  # 下次检定日期 - 添加索引
    usage_status = db.Column(db.String(20), default='在库', index=True)  # 使用状态 - 添加索引
    storage_location = db.Column(db.String(100), index=True)  # 存放地点 - 添加索引
    specifications = db.Column(db.Text)  # 规格型号
    manufacturer = db.Column(db.String(100))  # 生产厂家
    purchase_date = db.Column(db.Date)  # 采购日期
    warranty_period = db.Column(db.Integer)  # 质保期（月）
    unit_price = db.Column(db.Float)  # 单价
    remarks = db.Column(db.Text)  # 备注
    ownership = db.Column(db.String(100), index=True)  # 归属 - 添加索引
    product_number = db.Column(db.String(50))  # 产品编号
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    inbound_records = db.relationship('InboundRecord', backref='spare_part', lazy=True, cascade='all, delete-orphan')
    outbound_records = db.relationship('OutboundRecord', backref='spare_part', lazy=True, cascade='all, delete-orphan')
    fault_records = db.relationship('FaultRecord', backref='spare_part', lazy=True, cascade='all, delete-orphan')
    attachments = db.relationship('Attachment', backref='spare_part', lazy=True, cascade='all, delete-orphan')
    maintenance_records = db.relationship('MaintenanceRecord', backref='spare_part', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        days_to_inspection = None
        inspection_progress = 0  # 进度条百分比
        if self.next_inspection_date:
            delta = self.next_inspection_date - datetime.now().date()
            days_to_inspection = delta.days
            
            # 计算进度条百分比（剩余时间占总周期的百分比）
            if self.last_inspection_date:
                total_days = (self.next_inspection_date - self.last_inspection_date).days
                remaining_days = days_to_inspection
                if total_days > 0:
                    # 剩余时间百分比：100%表示刚检定完，0%表示到期
                    inspection_progress = max(0, min(100, (remaining_days / total_days) * 100))
                else:
                    inspection_progress = 0 if days_to_inspection < 0 else 100
            else:
                # 如果没有上次检定日期，假设检定周期为365天
                if days_to_inspection >= 365:
                    inspection_progress = 100
                elif days_to_inspection < 0:
                    inspection_progress = 0
                else:
                    inspection_progress = (days_to_inspection / 365) * 100
            
        return {
            'id': self.id,
            'name': self.name,
            'asset_number': self.asset_number,
            'device_type': self.device_type,
            'last_inspection_date': self.last_inspection_date.strftime('%Y-%m-%d') if self.last_inspection_date else None,
            'next_inspection_date': self.next_inspection_date.strftime('%Y-%m-%d') if self.next_inspection_date else None,
            'days_to_inspection': days_to_inspection,
            'inspection_progress': round(inspection_progress, 2),
            'usage_status': self.usage_status,
            'storage_location': self.storage_location,
            'specifications': self.specifications,
            'manufacturer': self.manufacturer,
            'purchase_date': self.purchase_date.strftime('%Y-%m-%d') if self.purchase_date else None,
            'warranty_period': self.warranty_period,
            'unit_price': self.unit_price,
            'remarks': self.remarks,
            'ownership': self.ownership,
            'product_number': self.product_number,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class InboundRecord(db.Model):
    """入库记录表"""
    __tablename__ = 'inbound_records'
    
    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)  # 数量
    operator_name = db.Column(db.String(50), nullable=False)  # 操作者姓名
    inbound_date = db.Column(db.DateTime, default=datetime.utcnow)  # 入库时间
    supplier = db.Column(db.String(100))  # 供应商
    batch_number = db.Column(db.String(50))  # 批次号
    remarks = db.Column(db.Text)  # 备注
    
    def to_dict(self):
        return {
            'id': self.id,
            'spare_part_id': self.spare_part_id,
            'spare_part_name': self.spare_part.name if self.spare_part else None,
            'spare_part_asset_number': self.spare_part.asset_number if self.spare_part else None,
            'quantity': self.quantity,
            'operator_name': self.operator_name,
            'inbound_date': self.inbound_date.strftime('%Y-%m-%d %H:%M:%S'),
            'supplier': self.supplier,
            'batch_number': self.batch_number,
            'remarks': self.remarks
        }


class OutboundRecord(db.Model):
    """出库记录表"""
    __tablename__ = 'outbound_records'
    
    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)  # 数量
    operator_name = db.Column(db.String(50), nullable=False)  # 操作者姓名
    outbound_date = db.Column(db.DateTime, default=datetime.utcnow)  # 出库时间
    recipient = db.Column(db.String(50))  # 领用人
    purpose = db.Column(db.String(200))  # 用途
    expected_return_date = db.Column(db.Date)  # 预计归还日期
    remarks = db.Column(db.Text)  # 备注
    
    def to_dict(self):
        return {
            'id': self.id,
            'spare_part_id': self.spare_part_id,
            'spare_part_name': self.spare_part.name if self.spare_part else None,
            'spare_part_asset_number': self.spare_part.asset_number if self.spare_part else None,
            'quantity': self.quantity,
            'operator_name': self.operator_name,
            'outbound_date': self.outbound_date.strftime('%Y-%m-%d %H:%M:%S'),
            'recipient': self.recipient,
            'purpose': self.purpose,
            'expected_return_date': self.expected_return_date.strftime('%Y-%m-%d') if self.expected_return_date else None,
            'remarks': self.remarks
        }


class FaultRecord(db.Model):
    """故障记录表"""
    __tablename__ = 'fault_records'
    
    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    operator_name = db.Column(db.String(50), nullable=False)  # 操作者姓名
    fault_date = db.Column(db.DateTime, default=datetime.utcnow)  # 故障时间
    fault_description = db.Column(db.Text, nullable=False)  # 故障描述
    fault_type = db.Column(db.String(50))  # 故障类型
    repair_status = db.Column(db.String(20), default='待维修')  # 维修状态：待维修、维修中、已维修、无法修复
    repair_date = db.Column(db.Date)  # 维修完成日期
    repair_cost = db.Column(db.Float)  # 维修费用
    remarks = db.Column(db.Text)  # 备注
    
    def to_dict(self):
        return {
            'id': self.id,
            'spare_part_id': self.spare_part_id,
            'spare_part_name': self.spare_part.name if self.spare_part else None,
            'spare_part_asset_number': self.spare_part.asset_number if self.spare_part else None,
            'operator_name': self.operator_name,
            'fault_date': self.fault_date.strftime('%Y-%m-%d %H:%M:%S'),
            'fault_description': self.fault_description,
            'fault_type': self.fault_type,
            'repair_status': self.repair_status,
            'repair_date': self.repair_date.strftime('%Y-%m-%d') if self.repair_date else None,
            'repair_cost': self.repair_cost,
            'remarks': self.remarks
        }


class Attachment(db.Model):
    """附件表（图片、说明书、校准记录等）"""
    __tablename__ = 'attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)  # 原始文件名
    stored_filename = db.Column(db.String(255), nullable=False)  # 存储文件名
    file_type = db.Column(db.String(50))  # 文件类型（图片/说明书/校准记录/其他）
    file_size = db.Column(db.Integer)  # 文件大小（字节）
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)  # 上传时间
    remarks = db.Column(db.Text)  # 备注
    
    def to_dict(self):
        return {
            'id': self.id,
            'spare_part_id': self.spare_part_id,
            'filename': self.filename,
            'stored_filename': self.stored_filename,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'upload_date': self.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
            'remarks': self.remarks
        }


class HistoricalDocument(db.Model):
    """历史文件表（不与设备绑定的文档）"""
    __tablename__ = 'historical_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)  # 原始文件名
    stored_filename = db.Column(db.String(255), nullable=False)  # 存储文件名
    file_type = db.Column(db.String(50))  # 文件类型
    file_size = db.Column(db.Integer)  # 文件大小（字节）
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)  # 上传时间
    category = db.Column(db.String(50))  # 分类（可选）
    remarks = db.Column(db.Text)  # 备注
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'stored_filename': self.stored_filename,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'upload_date': self.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
            'category': self.category,
            'remarks': self.remarks
        }


class MaintenanceRecord(db.Model):
    """维护记录表"""
    __tablename__ = 'maintenance_records'
    
    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    operator_name = db.Column(db.String(50), nullable=False)  # 操作者姓名
    maintenance_date = db.Column(db.Date, nullable=False)  # 维护日期
    maintenance_type = db.Column(db.String(50))  # 维护类型：日常维护/检定校准/大修/其他
    maintenance_content = db.Column(db.Text)  # 维护内容
    last_inspection_date = db.Column(db.Date)  # 上次检定日期（可修改）
    inspection_validity_period = db.Column(db.Integer)  # 检定有效期（月）
    next_inspection_date = db.Column(db.Date)  # 下次检定日期（自动计算）
    maintenance_cost = db.Column(db.Float)  # 维护费用
    remarks = db.Column(db.Text)  # 备注
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'spare_part_id': self.spare_part_id,
            'spare_part_name': self.spare_part.name if self.spare_part else None,
            'spare_part_asset_number': self.spare_part.asset_number if self.spare_part else None,
            'operator_name': self.operator_name,
            'maintenance_date': self.maintenance_date.strftime('%Y-%m-%d'),
            'maintenance_type': self.maintenance_type,
            'maintenance_content': self.maintenance_content,
            'last_inspection_date': self.last_inspection_date.strftime('%Y-%m-%d') if self.last_inspection_date else None,
            'inspection_validity_period': self.inspection_validity_period,
            'next_inspection_date': self.next_inspection_date.strftime('%Y-%m-%d') if self.next_inspection_date else None,
            'maintenance_cost': self.maintenance_cost,
            'remarks': self.remarks,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


# 初始化数据库
with app.app_context():
    db.create_all()


# ==================== 路由和API ====================

# 登录路由
@app.route('/login', methods=['GET'])
def login_page():
    """登录页面"""
    if 'logged_in' in session:
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def login():
    """处理登录"""
    try:
        data = request.get_json()
        username = data.get('username', '')
        password = data.get('password', '')
        
        logging.info(f'登录尝试 - 用户名: {username}')
        
        if username == DEFAULT_USERNAME and password == DEFAULT_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            session.permanent = True
            logging.info(f'登录成功 - 用户: {username}')
            return jsonify({'success': True, 'message': '登录成功'})
        else:
            logging.warning(f'登录失败 - 用户名: {username}')
            return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
    except Exception as e:
        logging.error(f'登录失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/logout', methods=['POST'])
def logout():
    """登出"""
    username = session.get('username', 'Unknown')
    session.clear()
    logging.info(f'用户登出 - 用户: {username}')
    return jsonify({'success': True, 'message': '登出成功'})


# 页面路由
@app.route('/')
@login_required
def index():
    """主页 - 备件列表"""
    return render_template('index.html')


@app.route('/create')
@login_required
def create_page():
    """创建备件页面"""
    return render_template('create.html')


@app.route('/detail/<int:part_id>')
@login_required
def detail_page(part_id):
    """备件详情页面"""
    return render_template('detail.html', part_id=part_id)


@app.route('/historical-documents')
@login_required
def historical_documents_page():
    """历史文件管理页面"""
    return render_template('historical_documents.html')


@app.route('/backup')
@login_required
def backup_page():
    """备份管理页面"""
    return render_template('backup.html')


# API路由 - 备件管理
@app.route('/api/spare-parts', methods=['GET'])
def get_spare_parts():
    """获取备件列表（支持搜索和筛选）"""
    try:
        # 获取查询参数
        keyword = request.args.get('keyword', '')
        ownership = request.args.get('ownership', '')
        device_type = request.args.get('device_type', '')
        usage_status = request.args.get('usage_status', '')
        inspection_status = request.args.get('inspection_status', '')
        storage_location = request.args.get('storage_location', '')
        
        logging.info(f'查询备件列表 - 关键字: {keyword}, 归属: {ownership}, 状态: {usage_status}, 检定: {inspection_status}, 地点: {storage_location}')
        
        # 构建查询
        query = SparePart.query
        
        # 关键字搜索（名称、资产编号、地点）
        if keyword:
            keyword_filter = f'%{keyword}%'
            query = query.filter(
                db.or_(
                    SparePart.name.like(keyword_filter),
                    SparePart.asset_number.like(keyword_filter),
                    SparePart.storage_location.like(keyword_filter)
                )
            )
        
        # 筛选条件
        if ownership:
            query = query.filter(SparePart.ownership == ownership)
        if device_type:
            query = query.filter(SparePart.device_type == device_type)
        if usage_status:
            query = query.filter(SparePart.usage_status == usage_status)
        if storage_location:
            query = query.filter(SparePart.storage_location.like(f'%{storage_location}%'))
        
        # 执行查询
        spare_parts = query.all()
        
        # 检定状态筛选（在应用层过滤）
        if inspection_status:
            from datetime import date
            today = date.today()
            filtered_parts = []
            
            for part in spare_parts:
                if not part.next_inspection_date:
                    # 无需检定
                    if inspection_status == 'no_inspection':
                        filtered_parts.append(part)
                else:
                    days_diff = (part.next_inspection_date - today).days
                    months_diff = days_diff / 30
                    
                    if inspection_status == 'expired' and days_diff < 0:
                        # 已过期
                        filtered_parts.append(part)
                    elif inspection_status == 'urgent' and 0 <= months_diff <= 3:
                        # 紧急（3个月内）
                        filtered_parts.append(part)
                    elif inspection_status == 'warning' and 3 < months_diff <= 6:
                        # 即将过期（3-6个月）
                        filtered_parts.append(part)
                    elif inspection_status == 'normal' and months_diff > 6:
                        # 正常（6个月以上）
                        filtered_parts.append(part)
            
            spare_parts = filtered_parts
        
        logging.info(f'查询备件列表成功 - 数量: {len(spare_parts)}')
        
        return jsonify({
            'success': True,
            'data': [part.to_dict() for part in spare_parts]
        })
    except Exception as e:
        logging.error(f'获取备件列表失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/spare-parts/<int:part_id>', methods=['GET'])
def get_spare_part(part_id):
    """获取单个备件详情"""
    try:
        part = SparePart.query.get_or_404(part_id)
        return jsonify({
            'success': True,
            'data': part.to_dict()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 404


@app.route('/api/spare-parts', methods=['POST'])
def create_spare_part():
    """创建新备件"""
    try:
        data = request.get_json()
        
        logging.info(f'创建新备件 - 名称: {data.get("name")}, 资产编号: {data.get("asset_number")}')
        
        # 数据验证
        if not data.get('name') or not data.get('asset_number'):
            logging.warning('创建备件失败: 缺少必填项')
            return jsonify({'success': False, 'message': '名称和资产编号为必填项'}), 400
        
        # 检查资产编号是否已存在
        if SparePart.query.filter_by(asset_number=data['asset_number']).first():
            logging.warning(f'创建备件失败: 资产编号已存在 - {data["asset_number"]}')
            return jsonify({'success': False, 'message': '资产编号已存在'}), 400
        
        # 创建新备件
        spare_part = SparePart(
            name=data['name'],
            asset_number=data['asset_number'],
            device_type=data.get('device_type'),
            last_inspection_date=datetime.strptime(data['last_inspection_date'], '%Y-%m-%d').date() if data.get('last_inspection_date') else None,
            next_inspection_date=datetime.strptime(data['next_inspection_date'], '%Y-%m-%d').date() if data.get('next_inspection_date') else None,
            usage_status=data.get('usage_status', '在库'),
            storage_location=data.get('storage_location'),
            specifications=data.get('specifications'),
            manufacturer=data.get('manufacturer'),
            purchase_date=datetime.strptime(data['purchase_date'], '%Y-%m-%d').date() if data.get('purchase_date') else None,
            warranty_period=data.get('warranty_period'),
            unit_price=data.get('unit_price'),
            remarks=data.get('remarks'),
            ownership=data.get('ownership'),
            product_number=data.get('product_number')
        )
        
        db.session.add(spare_part)
        db.session.commit()
        
        logging.info(f'备件创建成功 - ID: {spare_part.id}, 名称: {spare_part.name}')
        
        return jsonify({
            'success': True,
            'message': '备件创建成功',
            'data': spare_part.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f'创建备件失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/spare-parts/<int:part_id>', methods=['PUT'])
def update_spare_part(part_id):
    """更新备件信息"""
    try:
        part = SparePart.query.get_or_404(part_id)
        data = request.get_json()
        
        logging.info(f'更新备件 - ID: {part_id}, 名称: {part.name}')
        
        # 更新字段
        if 'name' in data:
            part.name = data['name']
        if 'device_type' in data:
            part.device_type = data['device_type']
        if 'last_inspection_date' in data:
            if data['last_inspection_date']:
                part.last_inspection_date = datetime.strptime(data['last_inspection_date'], '%Y-%m-%d').date()
            else:
                part.last_inspection_date = None
        if 'next_inspection_date' in data:
            if data['next_inspection_date']:
                part.next_inspection_date = datetime.strptime(data['next_inspection_date'], '%Y-%m-%d').date()
            else:
                part.next_inspection_date = None
        if 'usage_status' in data:
            part.usage_status = data['usage_status']
        if 'storage_location' in data:
            part.storage_location = data['storage_location']
        if 'specifications' in data:
            part.specifications = data['specifications']
        if 'manufacturer' in data:
            part.manufacturer = data['manufacturer']
        if 'purchase_date' in data and data['purchase_date']:
            part.purchase_date = datetime.strptime(data['purchase_date'], '%Y-%m-%d').date()
        if 'warranty_period' in data:
            part.warranty_period = data['warranty_period']
        if 'unit_price' in data:
            part.unit_price = data['unit_price']
        if 'remarks' in data:
            part.remarks = data['remarks']
        if 'ownership' in data:
            part.ownership = data['ownership']
        if 'product_number' in data:
            part.product_number = data['product_number']
        
        db.session.commit()
        
        logging.info(f'备件更新成功 - ID: {part_id}')
        
        return jsonify({
            'success': True,
            'message': '备件更新成功',
            'data': part.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f'更新备件失败 - ID: {part_id}, 错误: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/spare-parts/<int:part_id>', methods=['DELETE'])
def delete_spare_part(part_id):
    """删除备件"""
    try:
        part = SparePart.query.get_or_404(part_id)
        part_name = part.name
        db.session.delete(part)
        db.session.commit()
        
        logging.info(f'备件删除成功 - ID: {part_id}, 名称: {part_name}')
        
        return jsonify({
            'success': True,
            'message': '备件删除成功'
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f'删除备件失败 - ID: {part_id}, 错误: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


# API路由 - 入库记录
@app.route('/api/inbound-records', methods=['GET'])
def get_inbound_records():
    """获取入库记录列表"""
    try:
        part_id = request.args.get('spare_part_id', type=int)
        
        if part_id:
            records = InboundRecord.query.filter_by(spare_part_id=part_id).order_by(InboundRecord.inbound_date.desc()).all()
        else:
            records = InboundRecord.query.order_by(InboundRecord.inbound_date.desc()).all()
        
        return jsonify({
            'success': True,
            'data': [record.to_dict() for record in records]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/inbound-records', methods=['POST'])
def create_inbound_record():
    """创建入库记录"""
    try:
        data = request.get_json()
        
        record = InboundRecord(
            spare_part_id=data['spare_part_id'],
            quantity=data.get('quantity', 1),
            operator_name=data['operator_name'],
            supplier=data.get('supplier'),
            batch_number=data.get('batch_number'),
            remarks=data.get('remarks')
        )
        
        db.session.add(record)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '入库记录创建成功',
            'data': record.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# API路由 - 出库记录
@app.route('/api/outbound-records', methods=['GET'])
def get_outbound_records():
    """获取出库记录列表"""
    try:
        part_id = request.args.get('spare_part_id', type=int)
        
        if part_id:
            records = OutboundRecord.query.filter_by(spare_part_id=part_id).order_by(OutboundRecord.outbound_date.desc()).all()
        else:
            records = OutboundRecord.query.order_by(OutboundRecord.outbound_date.desc()).all()
        
        return jsonify({
            'success': True,
            'data': [record.to_dict() for record in records]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/outbound-records', methods=['POST'])
def create_outbound_record():
    """创建出库记录"""
    try:
        data = request.get_json()
        
        record = OutboundRecord(
            spare_part_id=data['spare_part_id'],
            quantity=data.get('quantity', 1),
            operator_name=data['operator_name'],
            recipient=data.get('recipient'),
            purpose=data.get('purpose'),
            expected_return_date=datetime.strptime(data['expected_return_date'], '%Y-%m-%d').date() if data.get('expected_return_date') else None,
            remarks=data.get('remarks')
        )
        
        db.session.add(record)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '出库记录创建成功',
            'data': record.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# API路由 - 故障记录
@app.route('/api/fault-records', methods=['GET'])
def get_fault_records():
    """获取故障记录列表"""
    try:
        part_id = request.args.get('spare_part_id', type=int)
        
        if part_id:
            records = FaultRecord.query.filter_by(spare_part_id=part_id).order_by(FaultRecord.fault_date.desc()).all()
        else:
            records = FaultRecord.query.order_by(FaultRecord.fault_date.desc()).all()
        
        return jsonify({
            'success': True,
            'data': [record.to_dict() for record in records]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/fault-records', methods=['POST'])
def create_fault_record():
    """创建故障记录"""
    try:
        data = request.get_json()
        
        record = FaultRecord(
            spare_part_id=data['spare_part_id'],
            operator_name=data['operator_name'],
            fault_description=data['fault_description'],
            fault_type=data.get('fault_type'),
            repair_status=data.get('repair_status', '待维修'),
            repair_date=datetime.strptime(data['repair_date'], '%Y-%m-%d').date() if data.get('repair_date') else None,
            repair_cost=data.get('repair_cost'),
            remarks=data.get('remarks')
        )
        
        db.session.add(record)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '故障记录创建成功',
            'data': record.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# API路由 - 维护记录
@app.route('/api/maintenance-records', methods=['GET'])
def get_maintenance_records():
    """获取维护记录列表"""
    try:
        spare_part_id = request.args.get('spare_part_id', type=int)
        
        if spare_part_id:
            records = MaintenanceRecord.query.filter_by(spare_part_id=spare_part_id).order_by(MaintenanceRecord.maintenance_date.desc()).all()
        else:
            records = MaintenanceRecord.query.order_by(MaintenanceRecord.maintenance_date.desc()).all()
        
        return jsonify({
            'success': True,
            'data': [record.to_dict() for record in records]
        })
    except Exception as e:
        logging.error(f'获取维护记录失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/maintenance-records', methods=['POST'])
def create_maintenance_record():
    """创建维护记录，并同步更新备件信息"""
    try:
        data = request.get_json()
        logging.info(f'创建维护记录 - 备件ID: {data.get("spare_part_id")}')
        
        # 计算下次检定日期
        next_inspection_date = None
        if data.get('last_inspection_date') and data.get('inspection_validity_period'):
            from dateutil.relativedelta import relativedelta
            last_date = datetime.strptime(data['last_inspection_date'], '%Y-%m-%d').date()
            validity_months = int(data['inspection_validity_period'])
            next_inspection_date = last_date + relativedelta(months=validity_months)
        
        # 创建维护记录
        record = MaintenanceRecord(
            spare_part_id=data['spare_part_id'],
            operator_name=data['operator_name'],
            maintenance_date=datetime.strptime(data['maintenance_date'], '%Y-%m-%d').date(),
            maintenance_type=data.get('maintenance_type'),
            maintenance_content=data.get('maintenance_content'),
            last_inspection_date=datetime.strptime(data['last_inspection_date'], '%Y-%m-%d').date() if data.get('last_inspection_date') else None,
            inspection_validity_period=data.get('inspection_validity_period'),
            next_inspection_date=next_inspection_date,
            maintenance_cost=data.get('maintenance_cost'),
            remarks=data.get('remarks')
        )
        
        db.session.add(record)
        
        # 同步更新备件的检定日期
        spare_part = SparePart.query.get(data['spare_part_id'])
        if spare_part:
            if record.last_inspection_date:
                spare_part.last_inspection_date = record.last_inspection_date
            if record.next_inspection_date:
                spare_part.next_inspection_date = record.next_inspection_date
            spare_part.updated_at = datetime.utcnow()
            
            logging.info(f'同步更新备件信息 - ID: {spare_part.id}, 上次检定: {spare_part.last_inspection_date}, 下次检定: {spare_part.next_inspection_date}')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '维护记录创建成功，备件信息已同步更新',
            'data': record.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f'创建维护记录失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/maintenance-records/<int:record_id>', methods=['GET'])
def get_maintenance_record(record_id):
    """获取单个维护记录详情"""
    try:
        record = MaintenanceRecord.query.get_or_404(record_id)
        return jsonify({
            'success': True,
            'data': record.to_dict()
        })
    except Exception as e:
        logging.error(f'获取维护记录详情失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/maintenance-records/<int:record_id>', methods=['PUT'])
def update_maintenance_record(record_id):
    """更新维护记录，并同步更新备件信息"""
    try:
        data = request.get_json()
        record = MaintenanceRecord.query.get_or_404(record_id)
        logging.info(f'更新维护记录 - ID: {record_id}')
        
        # 计算下次检定日期
        next_inspection_date = None
        if data.get('last_inspection_date') and data.get('inspection_validity_period'):
            from dateutil.relativedelta import relativedelta
            last_date = datetime.strptime(data['last_inspection_date'], '%Y-%m-%d').date()
            validity_months = int(data['inspection_validity_period'])
            next_inspection_date = last_date + relativedelta(months=validity_months)
        
        # 更新维护记录
        record.operator_name = data['operator_name']
        record.maintenance_date = datetime.strptime(data['maintenance_date'], '%Y-%m-%d').date()
        record.maintenance_type = data.get('maintenance_type')
        record.maintenance_content = data.get('maintenance_content')
        record.last_inspection_date = datetime.strptime(data['last_inspection_date'], '%Y-%m-%d').date() if data.get('last_inspection_date') else None
        record.inspection_validity_period = data.get('inspection_validity_period')
        record.next_inspection_date = next_inspection_date
        record.maintenance_cost = data.get('maintenance_cost')
        record.remarks = data.get('remarks')
        
        # 同步更新备件的检定日期
        spare_part = SparePart.query.get(record.spare_part_id)
        if spare_part:
            if record.last_inspection_date:
                spare_part.last_inspection_date = record.last_inspection_date
            if record.next_inspection_date:
                spare_part.next_inspection_date = record.next_inspection_date
            spare_part.updated_at = datetime.utcnow()
            
            logging.info(f'同步更新备件信息 - ID: {spare_part.id}, 上次检定: {spare_part.last_inspection_date}, 下次检定: {spare_part.next_inspection_date}')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '维护记录更新成功，备件信息已同步更新',
            'data': record.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f'更新维护记录失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/maintenance-records/<int:record_id>', methods=['DELETE'])
def delete_maintenance_record(record_id):
    """删除维护记录"""
    try:
        record = MaintenanceRecord.query.get_or_404(record_id)
        
        db.session.delete(record)
        db.session.commit()
        
        logging.info(f'维护记录删除成功 - ID: {record_id}')
        
        return jsonify({
            'success': True,
            'message': '维护记录删除成功'
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f'删除维护记录失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


# API路由 - 待检定备件
@app.route('/api/spare-parts/pending-inspection', methods=['GET'])
def get_pending_inspection_parts():
    """获取待检定备件列表（按日期排序）"""
    try:
        # 获取所有有检定日期的备件
        spare_parts = SparePart.query.filter(SparePart.next_inspection_date.isnot(None)).order_by(SparePart.next_inspection_date.asc()).all()
        
        return jsonify({
            'success': True,
            'data': [part.to_dict() for part in spare_parts]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# API路由 - 导出功能
@app.route('/api/export/spare-parts', methods=['GET'])
def export_spare_parts():
    """导出备件列表为Excel（包含入库、出库、维护、故障记录）"""
    try:
        logging.info('开始导出备件列表为Excel')
        # 获取筛选参数（与获取列表相同的逻辑）
        keyword = request.args.get('keyword', '')
        device_type = request.args.get('device_type', '')
        usage_status = request.args.get('usage_status', '')
        storage_location = request.args.get('storage_location', '')
        
        query = SparePart.query
        
        if keyword:
            keyword_filter = f'%{keyword}%'
            query = query.filter(
                db.or_(
                    SparePart.name.like(keyword_filter),
                    SparePart.asset_number.like(keyword_filter),
                    SparePart.storage_location.like(keyword_filter)
                )
            )
        
        if device_type:
            query = query.filter(SparePart.device_type == device_type)
        if usage_status:
            query = query.filter(SparePart.usage_status == usage_status)
        if storage_location:
            query = query.filter(SparePart.storage_location.like(f'%{storage_location}%'))
        
        spare_parts = query.all()
        spare_part_ids = [part.id for part in spare_parts]
        
        # 创建Excel文件
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Sheet 1: 备件列表
            data = []
            for part in spare_parts:
                part_dict = part.to_dict()
                data.append({
                    'ID': part_dict['id'],
                    '名称': part_dict['name'],
                    '资产编号': part_dict['asset_number'],
                    '系统': part_dict['ownership'],
                    '设备类型': part_dict['device_type'],
                    '下次检定日期': part_dict['next_inspection_date'],
                    '距离检定天数': part_dict['days_to_inspection'],
                    '使用状态': part_dict['usage_status'],
                    '存放地点': part_dict['storage_location'],
                    '规格型号': part_dict['specifications'],
                    '生产厂家': part_dict['manufacturer'],
                    '出厂编号': part_dict['product_number'],
                    '采购日期': part_dict['purchase_date'],
                    '质保期(月)': part_dict['warranty_period'],
                    '单价': part_dict['unit_price'],
                    '备注': part_dict['remarks']
                })
            
            if data:
                df = pd.DataFrame(data)
                df.to_excel(writer, index=False, sheet_name='备件列表')
            
            # Sheet 2: 入库记录
            if spare_part_ids:
                inbound_records = InboundRecord.query.filter(InboundRecord.spare_part_id.in_(spare_part_ids)).order_by(InboundRecord.inbound_date.desc()).all()
            else:
                inbound_records = []
            
            inbound_data = []
            for record in inbound_records:
                r_dict = record.to_dict()
                inbound_data.append({
                    'ID': r_dict['id'],
                    '备件名称': r_dict['spare_part_name'],
                    '资产编号': r_dict['spare_part_asset_number'],
                    '数量': r_dict['quantity'],
                    '操作者': r_dict['operator_name'],
                    '入库时间': r_dict['inbound_date'],
                    '供应商': r_dict['supplier'],
                    '批次号': r_dict['batch_number'],
                    '备注': r_dict['remarks']
                })
            
            if inbound_data:
                df_inbound = pd.DataFrame(inbound_data)
                df_inbound.to_excel(writer, index=False, sheet_name='入库记录')
            
            # Sheet 3: 出库记录
            if spare_part_ids:
                outbound_records = OutboundRecord.query.filter(OutboundRecord.spare_part_id.in_(spare_part_ids)).order_by(OutboundRecord.outbound_date.desc()).all()
            else:
                outbound_records = []
            
            outbound_data = []
            for record in outbound_records:
                r_dict = record.to_dict()
                outbound_data.append({
                    'ID': r_dict['id'],
                    '备件名称': r_dict['spare_part_name'],
                    '资产编号': r_dict['spare_part_asset_number'],
                    '数量': r_dict['quantity'],
                    '操作者': r_dict['operator_name'],
                    '出库时间': r_dict['outbound_date'],
                    '领用人': r_dict['recipient'],
                    '用途': r_dict['purpose'],
                    '预计归还日期': r_dict['expected_return_date'],
                    '备注': r_dict['remarks']
                })
            
            if outbound_data:
                df_outbound = pd.DataFrame(outbound_data)
                df_outbound.to_excel(writer, index=False, sheet_name='出库记录')
            
            # Sheet 4: 维护记录
            if spare_part_ids:
                maintenance_records = MaintenanceRecord.query.filter(MaintenanceRecord.spare_part_id.in_(spare_part_ids)).order_by(MaintenanceRecord.maintenance_date.desc()).all()
            else:
                maintenance_records = []
            
            maintenance_data = []
            for record in maintenance_records:
                r_dict = record.to_dict()
                maintenance_data.append({
                    'ID': r_dict['id'],
                    '备件名称': r_dict['spare_part_name'],
                    '资产编号': r_dict['spare_part_asset_number'],
                    '操作者': r_dict['operator_name'],
                    '维护日期': r_dict['maintenance_date'],
                    '维护类型': r_dict['maintenance_type'],
                    '维护内容': r_dict['maintenance_content'],
                    '上次检定日期': r_dict['last_inspection_date'],
                    '检定有效期(月)': r_dict['inspection_validity_period'],
                    '下次检定日期': r_dict['next_inspection_date'],
                    '维护费用': r_dict['maintenance_cost'],
                    '备注': r_dict['remarks']
                })
            
            if maintenance_data:
                df_maintenance = pd.DataFrame(maintenance_data)
                df_maintenance.to_excel(writer, index=False, sheet_name='维护记录')
            
            # Sheet 5: 故障记录
            if spare_part_ids:
                fault_records = FaultRecord.query.filter(FaultRecord.spare_part_id.in_(spare_part_ids)).order_by(FaultRecord.fault_date.desc()).all()
            else:
                fault_records = []
            
            fault_data = []
            for record in fault_records:
                r_dict = record.to_dict()
                fault_data.append({
                    'ID': r_dict['id'],
                    '备件名称': r_dict['spare_part_name'],
                    '资产编号': r_dict['spare_part_asset_number'],
                    '操作者': r_dict['operator_name'],
                    '故障时间': r_dict['fault_date'],
                    '故障描述': r_dict['fault_description'],
                    '故障类型': r_dict['fault_type'],
                    '维修状态': r_dict['repair_status'],
                    '维修完成日期': r_dict['repair_date'],
                    '维修费用': r_dict['repair_cost'],
                    '备注': r_dict['remarks']
                })
            
            if fault_data:
                df_fault = pd.DataFrame(fault_data)
                df_fault.to_excel(writer, index=False, sheet_name='故障记录')
        
        output.seek(0)
        
        logging.info(f'导出备件列表成功 - 备件数量: {len(spare_parts)}, 入库: {len(inbound_data)}, 出库: {len(outbound_data)}, 维护: {len(maintenance_data)}, 故障: {len(fault_data)}')
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'备品备件列表及记录_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        logging.error(f'导出备件列表失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/export/records', methods=['GET'])
def export_records():
    """导出记录为Excel（包含入库、出库、故障记录）"""
    try:
        part_id = request.args.get('spare_part_id', type=int)
        
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 导出入库记录
            if part_id:
                inbound_records = InboundRecord.query.filter_by(spare_part_id=part_id).all()
            else:
                inbound_records = InboundRecord.query.all()
            
            inbound_data = []
            for record in inbound_records:
                r_dict = record.to_dict()
                inbound_data.append({
                    'ID': r_dict['id'],
                    '备件名称': r_dict['spare_part_name'],
                    '资产编号': r_dict['spare_part_asset_number'],
                    '数量': r_dict['quantity'],
                    '操作者': r_dict['operator_name'],
                    '入库时间': r_dict['inbound_date'],
                    '供应商': r_dict['supplier'],
                    '批次号': r_dict['batch_number'],
                    '备注': r_dict['remarks']
                })
            
            if inbound_data:
                df_inbound = pd.DataFrame(inbound_data)
                df_inbound.to_excel(writer, index=False, sheet_name='入库记录')
            
            # 导出出库记录
            if part_id:
                outbound_records = OutboundRecord.query.filter_by(spare_part_id=part_id).all()
            else:
                outbound_records = OutboundRecord.query.all()
            
            outbound_data = []
            for record in outbound_records:
                r_dict = record.to_dict()
                outbound_data.append({
                    'ID': r_dict['id'],
                    '备件名称': r_dict['spare_part_name'],
                    '资产编号': r_dict['spare_part_asset_number'],
                    '数量': r_dict['quantity'],
                    '操作者': r_dict['operator_name'],
                    '出库时间': r_dict['outbound_date'],
                    '领用人': r_dict['recipient'],
                    '用途': r_dict['purpose'],
                    '预计归还日期': r_dict['expected_return_date'],
                    '备注': r_dict['remarks']
                })
            
            if outbound_data:
                df_outbound = pd.DataFrame(outbound_data)
                df_outbound.to_excel(writer, index=False, sheet_name='出库记录')
            
            # 导出故障记录
            if part_id:
                fault_records = FaultRecord.query.filter_by(spare_part_id=part_id).all()
            else:
                fault_records = FaultRecord.query.all()
            
            fault_data = []
            for record in fault_records:
                r_dict = record.to_dict()
                fault_data.append({
                    'ID': r_dict['id'],
                    '备件名称': r_dict['spare_part_name'],
                    '资产编号': r_dict['spare_part_asset_number'],
                    '操作者': r_dict['operator_name'],
                    '故障时间': r_dict['fault_date'],
                    '故障描述': r_dict['fault_description'],
                    '故障类型': r_dict['fault_type'],
                    '维修状态': r_dict['repair_status'],
                    '维修完成日期': r_dict['repair_date'],
                    '维修费用': r_dict['repair_cost'],
                    '备注': r_dict['remarks']
                })
            
            if fault_data:
                df_fault = pd.DataFrame(fault_data)
                df_fault.to_excel(writer, index=False, sheet_name='故障记录')
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'备件记录_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/export/calibration-plan', methods=['GET'])
def export_calibration_plan():
    """导出计量工作计划（只导出本年度需要检定的设备）"""
    try:
        logging.info('开始导出计量工作计划')
        
        # 获取当前年份
        current_year = datetime.now().year
        year_start = datetime(current_year, 1, 1).date()
        year_end = datetime(current_year, 12, 31).date()
        
        # 查询本年度内需要检定的设备（下次检定日期在本年度内）
        spare_parts = SparePart.query.filter(
            SparePart.next_inspection_date.isnot(None),
            SparePart.next_inspection_date >= year_start,
            SparePart.next_inspection_date <= year_end
        ).order_by(SparePart.next_inspection_date.asc()).all()
        
        # 转换为DataFrame
        data = []
        for index, part in enumerate(spare_parts, start=1):
            part_dict = part.to_dict()
            
            data.append({
                '序号': index,
                '传感器名称': part_dict['name'],
                '规格型号': part_dict['specifications'] or '',
                '生产厂家': part_dict['manufacturer'] or '',
                '出厂编号': part_dict['product_number'] or '',
                '数量': 1,
                '系统': part_dict['ownership'] or '',
                '检定/校准单位': '',
                '最后检定/校准日期': part_dict['last_inspection_date'] or '',
                '检定/校准有效日期': part_dict['next_inspection_date'] or '',
                '计划时间': '',
                '计划方式': '校准'
            })
        
        df = pd.DataFrame(data)
        
        # 创建Excel文件
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f'{current_year}年计量工作计划')
            
            # 获取worksheet调整列宽
            worksheet = writer.sheets[f'{current_year}年计量工作计划']
            worksheet.column_dimensions['A'].width = 8   # 序号
            worksheet.column_dimensions['B'].width = 20  # 传感器名称
            worksheet.column_dimensions['C'].width = 20  # 规格型号
            worksheet.column_dimensions['D'].width = 20  # 生产厂家
            worksheet.column_dimensions['E'].width = 18  # 出厂编号
            worksheet.column_dimensions['F'].width = 8   # 数量
            worksheet.column_dimensions['G'].width = 15  # 系统
            worksheet.column_dimensions['H'].width = 20  # 检定/校准单位
            worksheet.column_dimensions['I'].width = 18  # 最后检定/校准日期
            worksheet.column_dimensions['J'].width = 18  # 检定/校准有效日期
            worksheet.column_dimensions['K'].width = 15  # 计划时间
            worksheet.column_dimensions['L'].width = 12  # 计划方式
        
        output.seek(0)
        
        logging.info(f'导出{current_year}年计量工作计划成功 - 数量: {len(spare_parts)}')
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'{current_year}年计量工作计划_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        logging.error(f'导出计量工作计划失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/export/instrument-details', methods=['GET'])
def export_instrument_details():
    """导出计量器具明细表（本年度所有计量器具）"""
    try:
        logging.info('开始导出计量器具明细表')
        
        # 获取当前年份
        current_year = datetime.now().year
        
        # 查询所有有检定日期的设备（计量器具）
        spare_parts = SparePart.query.filter(
            SparePart.next_inspection_date.isnot(None)
        ).order_by(SparePart.ownership.asc(), SparePart.name.asc()).all()
        
        # 转换为DataFrame
        data = []
        for part in spare_parts:
            part_dict = part.to_dict()
            
            # 获取维护记录以找到最近两次检定日期
            maintenance_records = MaintenanceRecord.query.filter_by(
                spare_part_id=part.id
            ).filter(
                MaintenanceRecord.last_inspection_date.isnot(None)
            ).order_by(
                MaintenanceRecord.last_inspection_date.desc()
            ).limit(2).all()
            
            # 最近的检定日期（最新）
            latest_inspection_date = ''
            # 次近的检定日期（上次）
            previous_inspection_date = ''
            # 检定周期（年）
            inspection_period = ''
            # 检定单位
            inspection_unit = ''
            
            if len(maintenance_records) > 0:
                latest_inspection_date = maintenance_records[0].last_inspection_date.strftime('%Y-%m-%d')
                if maintenance_records[0].inspection_validity_period:
                    # 转换为年制
                    months = maintenance_records[0].inspection_validity_period
                    years = months / 12
                    if years >= 1:
                        inspection_period = f'{years:.0f}年' if years == int(years) else f'{years:.1f}年'
                    else:
                        inspection_period = f'{months}个月'
            
            if len(maintenance_records) > 1:
                previous_inspection_date = maintenance_records[1].last_inspection_date.strftime('%Y-%m-%d')
            
            # 如果没有维护记录，就用备件的上次检定日期
            if not latest_inspection_date and part_dict['last_inspection_date']:
                latest_inspection_date = part_dict['last_inspection_date']
            
            # 如果最新检定之前没有了，上次和最新保持一致
            if latest_inspection_date and not previous_inspection_date:
                previous_inspection_date = latest_inspection_date
            
            # 计算检定周期（如果没有维护记录，转换为年制）
            if not inspection_period and part_dict['last_inspection_date'] and part_dict['next_inspection_date']:
                try:
                    from dateutil.relativedelta import relativedelta
                    last_date = datetime.strptime(part_dict['last_inspection_date'], '%Y-%m-%d').date()
                    next_date = datetime.strptime(part_dict['next_inspection_date'], '%Y-%m-%d').date()
                    delta = relativedelta(next_date, last_date)
                    months = delta.years * 12 + delta.months
                    if months > 0:
                        years = months / 12
                        if years >= 1:
                            inspection_period = f'{years:.0f}年' if years == int(years) else f'{years:.1f}年'
                        else:
                            inspection_period = f'{months}个月'
                except:
                    pass
            
            data.append({
                '系统': part_dict['ownership'] or '',
                '名称': part_dict['name'],
                '规格型号': part_dict['specifications'] or '',
                '测量范围': '',  # 备件表中没有此字段，留空
                '分辨率': '',  # 备件表中没有此字段，留空
                '生产厂家': part_dict['manufacturer'] or '',
                '出厂编号': part_dict['product_number'] or '',
                '上次检定/校准日期': previous_inspection_date,
                '最新检定/校准日期': latest_inspection_date,
                '检定/校准有效日期': part_dict['next_inspection_date'] or '',
                '检定/校准方式': '权威校准',
                '检定/校准周期': inspection_period,
                '检定/校准单位': inspection_unit,
                '校准测试记录': '',  # 新增列，留空
                '备注': '合格',
                '状态': ''  # 状态留空
            })
        
        df = pd.DataFrame(data)
        
        # 创建Excel文件
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f'{current_year}年计量器具明细表')
            
            # 获取worksheet调整列宽
            worksheet = writer.sheets[f'{current_year}年计量器具明细表']
            worksheet.column_dimensions['A'].width = 15  # 系统
            worksheet.column_dimensions['B'].width = 20  # 名称
            worksheet.column_dimensions['C'].width = 20  # 规格型号
            worksheet.column_dimensions['D'].width = 15  # 测量范围
            worksheet.column_dimensions['E'].width = 12  # 分辨率
            worksheet.column_dimensions['F'].width = 20  # 生产厂家
            worksheet.column_dimensions['G'].width = 18  # 出厂编号
            worksheet.column_dimensions['H'].width = 18  # 上次检定/校准日期
            worksheet.column_dimensions['I'].width = 18  # 最新检定/校准日期
            worksheet.column_dimensions['J'].width = 18  # 检定/校准有效日期
            worksheet.column_dimensions['K'].width = 15  # 检定/校准方式
            worksheet.column_dimensions['L'].width = 15  # 检定/校准周期
            worksheet.column_dimensions['M'].width = 20  # 检定/校准单位
            worksheet.column_dimensions['N'].width = 18  # 校准测试记录
            worksheet.column_dimensions['O'].width = 12  # 备注
            worksheet.column_dimensions['P'].width = 12  # 状态
        
        output.seek(0)
        
        logging.info(f'导出{current_year}年计量器具明细表成功 - 数量: {len(spare_parts)}')
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'{current_year}年计量器具明细表_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        logging.error(f'导出计量器具明细表失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


# API路由 - 文件管理
@app.route('/api/attachments/<int:part_id>', methods=['GET'])
def get_attachments(part_id):
    """获取某个备件的所有附件"""
    try:
        attachments = Attachment.query.filter_by(spare_part_id=part_id).order_by(Attachment.upload_date.desc()).all()
        return jsonify({
            'success': True,
            'data': [att.to_dict() for att in attachments]
        })
    except Exception as e:
        logging.error(f'获取附件列表失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/attachments/upload', methods=['POST'])
def upload_attachment():
    """上传附件"""
    try:
        logging.info(f'收到文件上传请求 - files: {list(request.files.keys())}, form: {list(request.form.keys())}')
        
        if 'file' not in request.files:
            logging.warning('上传请求中没有file字段')
            return jsonify({'success': False, 'message': '没有文件'}), 400
        
        file = request.files['file']
        part_id = request.form.get('spare_part_id')
        remarks = request.form.get('remarks', '')
        
        logging.info(f'文件信息 - 备件ID: {part_id}, 文件名: {file.filename}')
        
        if not part_id:
            logging.warning('缺少备件ID')
            return jsonify({'success': False, 'message': '缺少备件ID'}), 400
        
        if file.filename == '':
            logging.warning('文件名为空')
            return jsonify({'success': False, 'message': '没有选择文件'}), 400
        
        if not allowed_file(file.filename):
            logging.warning(f'不允许的文件类型: {file.filename}')
            return jsonify({'success': False, 'message': f'不允许的文件类型，支持的类型: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
        
        # 保存完整的原始文件名（包括中文）
        original_filename = file.filename
        # 生成安全的存储文件名（用于物理存储）
        safe_filename = secure_filename(file.filename)
        # 如果secure_filename处理后为空，使用时间戳 + 扩展名
        if not safe_filename or safe_filename == '':
            ext = original_filename.rsplit('.', 1)[1] if '.' in original_filename else 'file'
            safe_filename = f'file.{ext}'
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        stored_filename = f"{part_id}_{timestamp}_{safe_filename}"
        
        # 根据文件扩展名自动判断文件类型
        ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
        if ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp']:
            file_type = '图片'
        elif ext == 'pdf':
            file_type = 'PDF文档'
        elif ext in ['doc', 'docx']:
            file_type = 'Word文档'
        elif ext in ['xls', 'xlsx']:
            file_type = 'Excel表格'
        elif ext in ['zip', 'rar']:
            file_type = '压缩包'
        elif ext == 'txt':
            file_type = '文本文件'
        else:
            file_type = '其他'
        
        # 保存文件
        upload_dir = get_upload_path()
        file_path = os.path.join(upload_dir, stored_filename)
        
        logging.info(f'开始保存文件到: {file_path}')
        file.save(file_path)
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        logging.info(f'文件保存成功，大小: {file_size} bytes, 类型: {file_type}')
        
        # 创建数据库记录
        attachment = Attachment(
            spare_part_id=int(part_id),
            filename=original_filename,  # 保存完整的原始文件名
            stored_filename=stored_filename,
            file_type=file_type,
            file_size=file_size,
            remarks=remarks
        )
        
        db.session.add(attachment)
        db.session.commit()
        
        logging.info(f'文件上传成功 - 备件ID: {part_id}, 文件: {original_filename}, 附件ID: {attachment.id}')
        
        return jsonify({
            'success': True,
            'message': '文件上传成功',
            'data': attachment.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f'上传文件失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'}), 500


@app.route('/api/attachments/<int:attachment_id>', methods=['DELETE'])
def delete_attachment(attachment_id):
    """删除附件"""
    try:
        attachment = Attachment.query.get_or_404(attachment_id)
        
        # 删除物理文件
        upload_dir = get_upload_path()
        file_path = os.path.join(upload_dir, attachment.stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # 删除数据库记录
        db.session.delete(attachment)
        db.session.commit()
        
        logging.info(f'附件删除成功 - ID: {attachment_id}, 文件: {attachment.filename}')
        
        return jsonify({
            'success': True,
            'message': '附件删除成功'
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f'删除附件失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/attachments/download/<int:attachment_id>', methods=['GET'])
def download_attachment(attachment_id):
    """下载附件"""
    try:
        attachment = Attachment.query.get_or_404(attachment_id)
        upload_dir = get_upload_path()
        
        logging.info(f'下载附件 - ID: {attachment_id}, 文件: {attachment.filename}')
        
        return send_from_directory(
            upload_dir,
            attachment.stored_filename,
            as_attachment=True,
            download_name=attachment.filename
        )
    except Exception as e:
        logging.error(f'下载附件失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 404


# ==================== 历史文件管理 API ====================

@app.route('/api/historical-documents', methods=['GET'])
def get_historical_documents():
    """获取历史文件列表"""
    try:
        category = request.args.get('category', '')
        
        query = HistoricalDocument.query
        if category:
            query = query.filter(HistoricalDocument.category == category)
        
        documents = query.order_by(HistoricalDocument.upload_date.desc()).all()
        
        logging.info(f'查询历史文件列表成功 - 数量: {len(documents)}')
        
        return jsonify({
            'success': True,
            'data': [doc.to_dict() for doc in documents]
        })
    except Exception as e:
        logging.error(f'获取历史文件列表失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/historical-documents/upload', methods=['POST'])
def upload_historical_document():
    """上传历史文件"""
    try:
        logging.info(f'收到历史文件上传请求 - files: {list(request.files.keys())}, form: {list(request.form.keys())}')
        
        if 'file' not in request.files:
            logging.warning('上传请求中没有file字段')
            return jsonify({'success': False, 'message': '没有文件'}), 400
        
        file = request.files['file']
        category = request.form.get('category', '')
        remarks = request.form.get('remarks', '')
        
        logging.info(f'文件信息 - 分类: {category}, 文件名: {file.filename}')
        
        if file.filename == '':
            logging.warning('文件名为空')
            return jsonify({'success': False, 'message': '没有选择文件'}), 400
        
        if not allowed_file(file.filename):
            logging.warning(f'不允许的文件类型: {file.filename}')
            return jsonify({'success': False, 'message': f'不允许的文件类型，支持的类型: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
        
        # 保存完整的原始文件名（包括中文）
        original_filename = file.filename
        # 生成安全的存储文件名（用于物理存储）
        safe_filename = secure_filename(file.filename)
        # 如果secure_filename处理后为空，使用时间戳 + 扩展名
        if not safe_filename or safe_filename == '':
            ext = original_filename.rsplit('.', 1)[1] if '.' in original_filename else 'file'
            safe_filename = f'file.{ext}'
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        stored_filename = f"historical_{timestamp}_{safe_filename}"
        
        # 根据文件扩展名自动判断文件类型
        ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
        if ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp']:
            file_type = '图片'
        elif ext == 'pdf':
            file_type = 'PDF文档'
        elif ext in ['doc', 'docx']:
            file_type = 'Word文档'
        elif ext in ['xls', 'xlsx']:
            file_type = 'Excel表格'
        elif ext in ['zip', 'rar']:
            file_type = '压缩包'
        elif ext == 'txt':
            file_type = '文本文件'
        else:
            file_type = '其他'
        
        # 保存文件
        upload_dir = get_upload_path()
        file_path = os.path.join(upload_dir, stored_filename)
        
        logging.info(f'开始保存文件到: {file_path}')
        file.save(file_path)
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        logging.info(f'文件保存成功，大小: {file_size} bytes, 类型: {file_type}')
        
        # 创建数据库记录
        document = HistoricalDocument(
            filename=original_filename,
            stored_filename=stored_filename,
            file_type=file_type,
            file_size=file_size,
            category=category,
            remarks=remarks
        )
        
        db.session.add(document)
        db.session.commit()
        
        logging.info(f'历史文件上传成功 - 文件: {original_filename}, ID: {document.id}')
        
        return jsonify({
            'success': True,
            'message': '文件上传成功',
            'data': document.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f'上传历史文件失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'}), 500


@app.route('/api/historical-documents/<int:doc_id>', methods=['DELETE'])
def delete_historical_document(doc_id):
    """删除历史文件"""
    try:
        document = HistoricalDocument.query.get_or_404(doc_id)
        
        # 删除物理文件
        upload_dir = get_upload_path()
        file_path = os.path.join(upload_dir, document.stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # 删除数据库记录
        db.session.delete(document)
        db.session.commit()
        
        logging.info(f'历史文件删除成功 - ID: {doc_id}, 文件: {document.filename}')
        
        return jsonify({
            'success': True,
            'message': '文件删除成功'
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f'删除历史文件失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/historical-documents/download/<int:doc_id>', methods=['GET'])
def download_historical_document(doc_id):
    """下载历史文件"""
    try:
        document = HistoricalDocument.query.get_or_404(doc_id)
        upload_dir = get_upload_path()
        
        logging.info(f'下载历史文件 - ID: {doc_id}, 文件: {document.filename}')
        
        return send_from_directory(
            upload_dir,
            document.stored_filename,
            as_attachment=True,
            download_name=document.filename
        )
    except Exception as e:
        logging.error(f'下载历史文件失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 404


# API路由 - 备份管理
@app.route('/api/backup/config', methods=['GET'])
def get_backup_config():
    """获取备份配置"""
    try:
        config = load_backup_config()
        return jsonify({
            'success': True,
            'data': config
        })
    except Exception as e:
        logging.error(f'获取备份配置失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/backup/config', methods=['PUT'])
def update_backup_config():
    """更新备份配置"""
    try:
        data = request.get_json()
        config = load_backup_config()
        
        # 更新配置
        if 'auto_backup_enabled' in data:
            config['auto_backup_enabled'] = data['auto_backup_enabled']
        if 'backup_time' in data:
            config['backup_time'] = data['backup_time']
        if 'keep_days' in data:
            config['keep_days'] = int(data['keep_days'])
        if 'backup_type' in data:
            config['backup_type'] = data['backup_type']
        
        save_backup_config(config)
        
        # 重新启动调度器
        shutdown_backup_scheduler()
        init_backup_scheduler()
        
        logging.info(f'备份配置已更新: {config}')
        
        return jsonify({
            'success': True,
            'message': '配置更新成功',
            'data': config
        })
    except Exception as e:
        logging.error(f'更新备份配置失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/backup/now', methods=['POST'])
def backup_now():
    """立即执行备份"""
    try:
        backup_type = request.get_json().get('backup_type', 'both')
        
        results = []
        
        if backup_type in ['both', 'database']:
            db_result = perform_database_backup()
            if db_result:
                results.append(db_result)
        
        if backup_type in ['both', 'excel']:
            excel_result = perform_excel_backup()
            if excel_result:
                results.append(excel_result)
        
        if results:
            return jsonify({
                'success': True,
                'message': f'备份完成，成功 {len(results)} 个文件',
                'data': results
            })
        else:
            return jsonify({
                'success': False,
                'message': '备份失败'
            }), 500
    except Exception as e:
        logging.error(f'手动备份失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/backup/list', methods=['GET'])
def list_backups():
    """获取备份文件列表"""
    try:
        backup_dir = get_backup_path()
        
        if not os.path.exists(backup_dir):
            return jsonify({
                'success': True,
                'data': []
            })
        
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
        
        # 按创建时间降序排列
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': backups
        })
    except Exception as e:
        logging.error(f'获取备份列表失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/backup/download/<filename>', methods=['GET'])
def download_backup(filename):
    """下载备份文件"""
    try:
        # 安全检查：只允许下载备份文件
        if not (filename.startswith('database_backup_') or filename.startswith('excel_backup_')):
            return jsonify({'success': False, 'message': '非法的文件名'}), 400
        
        backup_dir = get_backup_path()
        filepath = os.path.join(backup_dir, filename)
        
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'message': '文件不存在'}), 404
        
        logging.info(f'下载备份文件: {filename}')
        
        return send_from_directory(
            backup_dir,
            filename,
            as_attachment=True
        )
    except Exception as e:
        logging.error(f'下载备份失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/backup/delete/<filename>', methods=['DELETE'])
def delete_backup(filename):
    """删除备份文件"""
    try:
        # 安全检查
        if not (filename.startswith('database_backup_') or filename.startswith('excel_backup_')):
            return jsonify({'success': False, 'message': '非法的文件名'}), 400
        
        backup_dir = get_backup_path()
        filepath = os.path.join(backup_dir, filename)
        
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'message': '文件不存在'}), 404
        
        os.remove(filepath)
        logging.info(f'备份文件已删除: {filename}')
        
        return jsonify({
            'success': True,
            'message': '备份文件删除成功'
        })
    except Exception as e:
        logging.error(f'删除备份失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


def create_tray_icon():
    """创建系统托盘图标"""
    # 创建一个简单的图标
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), color='#2c3e50')
    draw = ImageDraw.Draw(image)
    
    # 绘制一个简单的图标（字母 B 代表备件）
    draw.rectangle([10, 10, 54, 54], fill='#3498db')
    draw.text((20, 18), 'B', fill='white')
    
    return image


def quit_app(icon=None, item=None):
    """退出应用程序"""
    print("\n正在关闭服务器...")
    if icon:
        icon.stop()
    os._exit(0)


def open_browser_window(icon=None, item=None):
    """打开浏览器窗口"""
    webbrowser.open('http://127.0.0.1:5000')


def setup_tray_icon():
    """设置系统托盘图标"""
    if not HAS_TRAY:
        return None
    
    icon_image = create_tray_icon()
    menu = Menu(
        MenuItem('打开管理系统', open_browser_window, default=True),
        MenuItem('退出程序', quit_app)
    )
    
    icon = Icon('备品备件管理系统', icon_image, '备品备件管理系统', menu)
    return icon


def run_tray_icon():
    """在后台线程运行托盘图标"""
    icon = setup_tray_icon()
    if icon:
        icon.run()


def open_browser():
    """延迟打开浏览器"""
    time.sleep(1.5)  # 等待服务器启动
    webbrowser.open('http://127.0.0.1:5000')


if __name__ == '__main__':
    print("="*60)
    print("备品备件管理系统")
    print("Author: wyj | License: MIT")
    print("="*60)
    
    # 执行数据库迁移检查
    if HAS_MIGRATION:
        print("\n正在检查数据库...")
        if not check_and_migrate():
            print("✘ 数据库迁移失败，程序无法启动")
            sys.exit(1)
        print("✓ 数据库检查完成\n")
    
    print("\n正在启动服务器...")
    print("访问地址：http://127.0.0.1:5000")
    if HAS_TRAY:
        print("提示：程序已最小化到系统托盘，右键托盘图标可退出")
    else:
        print("按 Ctrl+C 可停止服务器")
    print()
    
    # 注册退出处理
    atexit.register(lambda: print("\n服务器已关闭"))
    signal.signal(signal.SIGINT, lambda s, f: quit_app())
    signal.signal(signal.SIGTERM, lambda s, f: quit_app())
    
    # 启动浏览器
    threading.Thread(target=open_browser, daemon=True).start()
    
    # 如果支持托盘图标，在后台线程启动
    if HAS_TRAY:
        threading.Thread(target=run_tray_icon, daemon=True).start()
    
    # 启动Flask服务器
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
