#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
备份管理模块
"""
import os
import json
import shutil
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from utils.helpers import get_database_path, get_backup_path


def load_backup_config():
    """加载备份配置"""
    config_path = os.path.join(os.path.dirname(get_database_path()), '..', 'backup_config.json')
    config_path = os.path.abspath(config_path)
    default_config = {
        'enabled': True,
        'auto_backup_enabled': True,
        'backup_time': '02:00',
        'keep_days': 30,
        'backup_type': 'both'
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return {**default_config, **config}
        except Exception:
            pass

    return default_config


def save_backup_config(config):
    """保存备份配置"""
    config_path = os.path.join(os.path.dirname(get_database_path()), '..', 'backup_config.json')
    config_path = os.path.abspath(config_path)
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

        # 使用 SQLite 在线备份更安全
        import sqlite3
        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(backup_filepath)
        with dest:
            source.backup(dest)
        dest.close()
        source.close()

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


def perform_excel_backup(app):
    """执行Excel数据备份"""
    try:
        import pandas as pd
        backup_dir = get_backup_path()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'excel_backup_{timestamp}.xlsx'
        backup_filepath = os.path.join(backup_dir, backup_filename)

        with app.app_context():
            from models import SparePart, InboundRecord, OutboundRecord, MaintenanceRecord, FaultRecord
            spare_parts = SparePart.query.all()
            spare_part_ids = [part.id for part in spare_parts]

            with pd.ExcelWriter(backup_filepath, engine='openpyxl') as writer:
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

                if spare_part_ids:
                    inbound_records = InboundRecord.query.filter(
                        InboundRecord.spare_part_id.in_(spare_part_ids)
                    ).order_by(InboundRecord.inbound_date.desc()).all()
                    if inbound_records:
                        inbound_data = []
                        for record in inbound_records:
                            r_dict = record.to_dict(include_spare_part=False)
                            inbound_data.append({
                                'ID': r_dict['id'],
                                '备件名称': record.spare_part.name if record.spare_part else None,
                                '资产编号': record.spare_part.asset_number if record.spare_part else None,
                                '数量': r_dict['quantity'],
                                '操作者': r_dict['operator_name'],
                                '入库时间': r_dict['inbound_date'],
                                '供应商': r_dict['supplier'],
                                '批次号': r_dict['batch_number'],
                                '备注': r_dict['remarks']
                            })
                        df_inbound = pd.DataFrame(inbound_data)
                        df_inbound.to_excel(writer, index=False, sheet_name='入库记录')

                if spare_part_ids:
                    outbound_records = OutboundRecord.query.filter(
                        OutboundRecord.spare_part_id.in_(spare_part_ids)
                    ).order_by(OutboundRecord.outbound_date.desc()).all()
                    if outbound_records:
                        outbound_data = []
                        for record in outbound_records:
                            r_dict = record.to_dict(include_spare_part=False)
                            outbound_data.append({
                                'ID': r_dict['id'],
                                '备件名称': record.spare_part.name if record.spare_part else None,
                                '资产编号': record.spare_part.asset_number if record.spare_part else None,
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

                if spare_part_ids:
                    maintenance_records = MaintenanceRecord.query.filter(
                        MaintenanceRecord.spare_part_id.in_(spare_part_ids)
                    ).order_by(MaintenanceRecord.maintenance_date.desc()).all()
                    if maintenance_records:
                        maintenance_data = []
                        for record in maintenance_records:
                            r_dict = record.to_dict(include_spare_part=False)
                            maintenance_data.append({
                                'ID': r_dict['id'],
                                '备件名称': record.spare_part.name if record.spare_part else None,
                                '资产编号': record.spare_part.asset_number if record.spare_part else None,
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

                if spare_part_ids:
                    fault_records = FaultRecord.query.filter(
                        FaultRecord.spare_part_id.in_(spare_part_ids)
                    ).order_by(FaultRecord.fault_date.desc()).all()
                    if fault_records:
                        fault_data = []
                        for record in fault_records:
                            r_dict = record.to_dict(include_spare_part=False)
                            fault_data.append({
                                'ID': r_dict['id'],
                                '备件名称': record.spare_part.name if record.spare_part else None,
                                '资产编号': record.spare_part.asset_number if record.spare_part else None,
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


def perform_full_backup(app):
    """执行完整备份（数据库+Excel）"""
    logging.info('=' * 60)
    logging.info('开始执行自动备份')
    logging.info('=' * 60)

    config = load_backup_config()
    backup_type = config.get('backup_type', 'both')

    results = []

    if backup_type in ['both', 'database']:
        db_result = perform_database_backup()
        if db_result:
            results.append(db_result)

    if backup_type in ['both', 'excel']:
        excel_result = perform_excel_backup(app)
        if excel_result:
            results.append(excel_result)

    cleanup_old_backups()

    logging.info('=' * 60)
    logging.info(f'备份完成: 成功 {len(results)} 个文件')
    logging.info('=' * 60)

    return results


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


backup_scheduler = None


def init_backup_scheduler(app):
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
        lambda: perform_full_backup(app),
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
