#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
操作日志与字段变更记录路由模块
"""
import json
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, session

from models import db, OperationLog, FieldChangeLog, SparePart
from routes.common import APIResponse, login_required

audit_bp = Blueprint('audit', __name__)

# 字段名中文映射
FIELD_LABELS = {
    'name': '名称',
    'asset_number': '资产编号',
    'ownership': '系统',
    'device_type': '设备类型',
    'specifications': '规格型号',
    'manufacturer': '生产厂家',
    'product_number': '出厂编号',
    'usage_status': '使用状态',
    'storage_location': '存放地点',
    'purchase_date': '采购日期',
    'last_inspection_date': '上次检定日期',
    'next_inspection_date': '下次检定日期',
    'warranty_period': '质保期(月)',
    'unit_price': '单价',
    'remarks': '备注',
}


def write_operation_log(action, target_id=None, target_name=None, detail=None, target_type='spare_part'):
    """写入操作日志（在请求上下文中调用）"""
    try:
        operator = session.get('username', '系统')
        log = OperationLog(
            operator=operator,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            detail=json.dumps(detail, ensure_ascii=False) if detail and not isinstance(detail, str) else detail
        )
        db.session.add(log)
        # 不单独commit，由调用方一并提交
    except Exception as e:
        logging.error(f'写入操作日志失败: {str(e)}')


def write_field_changes(spare_part_id, old_data, new_data):
    """比较并写入字段变更记录"""
    try:
        operator = session.get('username', '系统')
        for field, label in FIELD_LABELS.items():
            old_val = str(old_data.get(field) or '') if old_data.get(field) is not None else ''
            new_val = str(new_data.get(field) or '') if new_data.get(field) is not None else ''
            if old_val != new_val:
                change = FieldChangeLog(
                    spare_part_id=spare_part_id,
                    operator=operator,
                    field_name=field,
                    field_label=label,
                    old_value=old_val or None,
                    new_value=new_val or None
                )
                db.session.add(change)
    except Exception as e:
        logging.error(f'写入字段变更记录失败: {str(e)}')


@audit_bp.route('/api/audit/logs', methods=['GET'])
@login_required
def get_operation_logs():
    """获取操作日志列表"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        action = request.args.get('action', '')
        keyword = request.args.get('keyword', '')
        days = int(request.args.get('days', 30))

        query = OperationLog.query

        if days > 0:
            since = datetime.now() - timedelta(days=days)
            query = query.filter(OperationLog.created_at >= since)
        if action:
            query = query.filter(OperationLog.action == action)
        if keyword:
            query = query.filter(
                db.or_(
                    OperationLog.target_name.like(f'%{keyword}%'),
                    OperationLog.operator.like(f'%{keyword}%')
                )
            )

        total = query.count()
        logs = query.order_by(OperationLog.created_at.desc()) \
                    .offset((page - 1) * per_page).limit(per_page).all()

        return APIResponse.success(data={
            'total': total,
            'page': page,
            'per_page': per_page,
            'logs': [l.to_dict() for l in logs]
        })
    except Exception as e:
        logging.error(f'获取操作日志失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@audit_bp.route('/api/audit/field-changes/<int:part_id>', methods=['GET'])
@login_required
def get_field_changes(part_id):
    """获取指定备件的字段变更历史"""
    try:
        changes = FieldChangeLog.query.filter_by(spare_part_id=part_id) \
                                      .order_by(FieldChangeLog.changed_at.desc()).all()
        return APIResponse.success(data=[c.to_dict() for c in changes])
    except Exception as e:
        logging.error(f'获取字段变更记录失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))
