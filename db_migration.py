"""
数据库迁移和版本管理模块
用于在程序更新时保持数据库结构的兼容性
"""
import os
import sys
import sqlite3
from datetime import datetime

# 数据库版本号
CURRENT_DB_VERSION = 1


def get_database_path():
    """获取数据库文件路径"""
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.abspath(".")
    
    db_path = os.path.join(app_dir, 'spare_parts.db')
    return db_path


def get_db_version(conn):
    """获取当前数据库版本"""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT version FROM db_version ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        return result[0] if result else 0
    except sqlite3.OperationalError:
        # db_version 表不存在，返回版本 0
        return 0


def create_db_version_table(conn):
    """创建数据库版本表"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS db_version (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL,
            description TEXT,
            migrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def set_db_version(conn, version, description=""):
    """设置数据库版本"""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO db_version (version, description) VALUES (?, ?)",
        (version, description)
    )
    conn.commit()


def check_and_migrate():
    """检查数据库版本并执行必要的迁移"""
    db_path = get_database_path()
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print("数据库文件不存在，将在首次启动时创建...")
        return True
    
    print(f"检查数据库版本: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        
        # 创建版本表（如果不存在）
        create_db_version_table(conn)
        
        # 获取当前数据库版本
        current_version = get_db_version(conn)
        print(f"当前数据库版本: {current_version}")
        print(f"程序要求版本: {CURRENT_DB_VERSION}")
        
        # 如果版本一致，无需迁移
        if current_version == CURRENT_DB_VERSION:
            print("✓ 数据库版本匹配，无需迁移")
            conn.close()
            return True
        
        # 执行迁移
        if current_version < CURRENT_DB_VERSION:
            print(f"需要升级数据库: 版本 {current_version} -> {CURRENT_DB_VERSION}")
            
            # 执行各个版本的迁移
            if current_version < 1:
                migrate_to_v1(conn)
            
            # 未来的迁移可以在这里添加
            # if current_version < 2:
            #     migrate_to_v2(conn)
            
            print("✓ 数据库迁移完成")
        else:
            print(f"⚠ 警告: 数据库版本 ({current_version}) 高于程序版本 ({CURRENT_DB_VERSION})")
            print("建议更新程序到最新版本")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ 数据库迁移失败: {str(e)}")
        return False


def migrate_to_v1(conn):
    """迁移到版本1 - 初始版本，确保所有表结构正确"""
    print("执行迁移: 版本 0 -> 1")
    cursor = conn.cursor()
    
    # 检查并添加可能缺失的表（兼容旧版本）
    try:
        # 检查 attachments 表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='attachments'
        """)
        if not cursor.fetchone():
            print("  - 创建 attachments 表")
            cursor.execute("""
                CREATE TABLE attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spare_part_id INTEGER NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    stored_filename VARCHAR(255) NOT NULL,
                    file_type VARCHAR(50),
                    file_size INTEGER,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    remarks TEXT,
                    FOREIGN KEY (spare_part_id) REFERENCES spare_parts (id)
                )
            """)
        
        # 检查 historical_documents 表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='historical_documents'
        """)
        if not cursor.fetchone():
            print("  - 创建 historical_documents 表")
            cursor.execute("""
                CREATE TABLE historical_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename VARCHAR(255) NOT NULL,
                    stored_filename VARCHAR(255) NOT NULL,
                    file_type VARCHAR(50),
                    file_size INTEGER,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    category VARCHAR(50),
                    remarks TEXT
                )
            """)
    except Exception as e:
        print(f"  ⚠ 迁移警告: {str(e)}")
    
    # 设置版本号
    set_db_version(conn, 1, "初始版本，包含文件管理和历史文件功能")
    print("  ✓ 迁移到版本 1 完成")


def backup_database():
    """备份数据库文件"""
    db_path = get_database_path()
    
    if not os.path.exists(db_path):
        print("数据库文件不存在，无需备份")
        return None
    
    # 创建备份目录
    backup_dir = os.path.join(os.path.dirname(db_path), 'db_backups')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # 生成备份文件名（带时间戳）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'spare_parts_backup_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # 复制数据库文件
    import shutil
    shutil.copy2(db_path, backup_path)
    
    print(f"✓ 数据库已备份到: {backup_path}")
    return backup_path


if __name__ == '__main__':
    print("="*60)
    print("数据库迁移工具")
    print("="*60)
    print()
    
    # 备份数据库
    backup_path = backup_database()
    
    # 执行迁移
    success = check_and_migrate()
    
    if success:
        print("\n数据库迁移成功！")
    else:
        print("\n数据库迁移失败！")
        if backup_path:
            print(f"如有问题，可以从备份恢复: {backup_path}")
