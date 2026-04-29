#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
备品备件管理系统 - 主应用程序
Author: wyj
License: MIT License
"""
import os
import sys
import signal
import atexit
import threading
import time
import logging

from flask import Flask, render_template

from config import get_resource_path, CONFIG
from models import db
from utils.logger import setup_logging
from utils.helpers import check_single_instance, open_browser_delayed
from utils.backup_manager import init_backup_scheduler, shutdown_backup_scheduler

# 导入路由蓝图
from routes.auth import auth_bp
from routes.pages import pages_bp
from routes.spare_parts import spare_parts_bp
from routes.records import records_bp
from routes.folders import folders_bp
from routes.backup import backup_bp
from routes.export import export_bp
from routes.audit import audit_bp
from routes.settings import settings_bp

# 导入数据库迁移模块
try:
    from db_migration import check_and_migrate
    HAS_MIGRATION = True
except ImportError:
    HAS_MIGRATION = False
    print("⚠ 警告: 数据库迁移模块不可用")

# 系统托盘支持
try:
    from pystray import Icon, MenuItem, Menu
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False


def create_app():
    """应用工厂函数"""
    app = Flask(__name__,
                template_folder=get_resource_path('templates'),
                static_folder=get_resource_path('static'))

    # 使用 get_app_dir() 确保打包后路径指向 exe 所在目录，而非 _internal
    _db_dir = os.path.join(get_app_dir(), 'data')
    os.makedirs(_db_dir, exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(_db_dir, "spare_parts.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', CONFIG['secret_key'])
    app.config['MAX_CONTENT_LENGTH'] = CONFIG['max_upload_size_mb'] * 1024 * 1024
    app.config['PERMANENT_SESSION_LIFETIME'] = CONFIG['session_lifetime_hours'] * 3600

    db.init_app(app)

    # 注册蓝图
    app.register_blueprint(auth_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(spare_parts_bp)
    app.register_blueprint(records_bp)
    app.register_blueprint(folders_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(settings_bp)

    # 全局错误处理
    from routes.common import APIResponse

    @app.errorhandler(404)
    def not_found_error(error):
        logging.warning(f'404错误: {error}')
        from flask import request
        if request.path.startswith('/api/'):
            return APIResponse.not_found("请求的资源不存在")
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logging.error(f'500错误: {str(error)}', exc_info=True)
        db.session.rollback()
        from flask import request
        if request.path.startswith('/api/'):
            return APIResponse.server_error("服务器内部错误，请稍后重试")
        return render_template('500.html'), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        logging.error(f'未处理的异常: {str(error)}', exc_info=True)
        db.session.rollback()
        from flask import request
        if request.path.startswith('/api/'):
            return APIResponse.server_error(f"系统错误: {str(error)}")
        return render_template('500.html'), 500

    return app


def create_tray_icon():
    """创建系统托盘图标"""
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), color='#2c3e50')
    draw = ImageDraw.Draw(image)
    draw.rectangle([10, 10, 54, 54], fill='#3498db')
    draw.text((20, 18), 'B', fill='white')
    return image


def quit_app(icon=None, item=None):
    """优雅退出应用程序"""
    print("\n正在关闭服务器...")
    shutdown_backup_scheduler()
    if icon:
        icon.stop()
    # 使用 sys.exit 替代 os._exit 以允许清理
    sys.exit(0)


def open_browser_from_tray(icon=None, item=None):
    """从托盘打开浏览器"""
    import webbrowser
    host = CONFIG.get('host', '127.0.0.1')
    port = CONFIG.get('port', 5000)
    webbrowser.open(f'http://{host}:{port}')


def setup_tray_icon():
    """设置系统托盘图标"""
    if not HAS_TRAY:
        return None
    icon_image = create_tray_icon()
    menu = Menu(
        MenuItem('打开管理系统', open_browser_from_tray, default=True),
        MenuItem('退出程序', quit_app)
    )
    return Icon('备品备件管理系统', icon_image, '备品备件管理系统', menu)


def run_tray_icon():
    """在后台线程运行托盘图标"""
    icon = setup_tray_icon()
    if icon:
        icon.run()


def main():
    # 单实例检测
    if not check_single_instance():
        sys.exit(0)

    print("=" * 60)
    print("备品备件管理系统")
    print("Author: wyj | License: MIT")
    print("=" * 60)

    app = create_app()

    # 初始化数据库
    with app.app_context():
        db.create_all()

        # 执行数据库迁移检查
        if HAS_MIGRATION:
            print("\n正在检查数据库...")
            if not check_and_migrate():
                print("✘ 数据库迁移失败，程序无法启动")
                sys.exit(1)
            print("✓ 数据库检查完成\n")

    # 配置日志（需要在应用上下文之后）
    setup_logging(app)

    # 初始化备份调度器
    with app.app_context():
        init_backup_scheduler(app)

    host = CONFIG.get('host', '127.0.0.1')
    port = CONFIG.get('port', 5000)

    print(f"\n正在启动服务器...")
    print(f"访问地址：http://{host}:{port}")
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
    open_browser_delayed(delay=1.5)

    # 启动托盘图标
    if HAS_TRAY:
        threading.Thread(target=run_tray_icon, daemon=True).start()

    # 启动Flask服务器
    app.run(host=host, port=port, debug=CONFIG.get('debug', False), use_reloader=False)


if __name__ == '__main__':
    main()
