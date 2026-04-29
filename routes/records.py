#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
记录管理路由模块（入库、出库、维护、故障）
"""
import logging
from datetime import datetime
from flask import Blueprint, request
from dateutil.relativedelta import relativedelta

from models import db, InboundRecord, OutboundRecord, FaultRecord, MaintenanceRecord, SparePart
from routes.common import APIResponse, login_required

records_bp = Blueprint('records', __name__)


# ==================== 入库记录 ====================

@records_bp.route('/api/inbound-records', methods=['GET'])
@login_required
def get_inbound_records():
    try:
        part_id = request.args.get('spare_part_id', type=int)
        if part_id:
            records = InboundRecord.query.filter_by(spare_part_id=part_id).order_by(InboundRecord.inbound_date.desc()).all()
        else:
            records = InboundRecord.query.order_by(InboundRecord.inbound_date.desc()).all()
        return APIResponse.success(data=[r.to_dict(include_spare_part=True) for r in records])
    except Exception as e:
        return APIResponse.server_error(str(e))


@records_bp.route('/api/inbound-records', methods=['POST'])
@login_required
def create_inbound_record():
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
        return APIResponse.success(data=record.to_dict(), message='入库记录创建成功'), 201
    except Exception as e:
        db.session.rollback()
        return APIResponse.server_error(str(e))


# ==================== 出库记录 ====================

@records_bp.route('/api/outbound-records', methods=['GET'])
@login_required
def get_outbound_records():
    try:
        part_id = request.args.get('spare_part_id', type=int)
        if part_id:
            records = OutboundRecord.query.filter_by(spare_part_id=part_id).order_by(OutboundRecord.outbound_date.desc()).all()
        else:
            records = OutboundRecord.query.order_by(OutboundRecord.outbound_date.desc()).all()
        return APIResponse.success(data=[r.to_dict(include_spare_part=True) for r in records])
    except Exception as e:
        return APIResponse.server_error(str(e))


@records_bp.route('/api/outbound-records', methods=['POST'])
@login_required
def create_outbound_record():
    try:
        data = request.get_json()
        record = OutboundRecord(
            spare_part_id=data['spare_part_id'],
            quantity=data.get('quantity', 1),
            operator_name=data['operator_name'],
            recipient=data.get('recipient'),
            purpose=data.get('purpose'),
            expected_return_date=__parse_date(data.get('expected_return_date')),
            remarks=data.get('remarks')
        )
        db.session.add(record)
        db.session.commit()
        return APIResponse.success(data=record.to_dict(), message='出库记录创建成功'), 201
    except Exception as e:
        db.session.rollback()
        return APIResponse.server_error(str(e))


# ==================== 故障记录 ====================

@records_bp.route('/api/fault-records', methods=['GET'])
@login_required
def get_fault_records():
    try:
        part_id = request.args.get('spare_part_id', type=int)
        if part_id:
            records = FaultRecord.query.filter_by(spare_part_id=part_id).order_by(FaultRecord.fault_date.desc()).all()
        else:
            records = FaultRecord.query.order_by(FaultRecord.fault_date.desc()).all()
        return APIResponse.success(data=[r.to_dict(include_spare_part=True) for r in records])
    except Exception as e:
        return APIResponse.server_error(str(e))


@records_bp.route('/api/fault-records', methods=['POST'])
@login_required
def create_fault_record():
    try:
        data = request.get_json()
        record = FaultRecord(
            spare_part_id=data['spare_part_id'],
            operator_name=data['operator_name'],
            fault_description=data['fault_description'],
            fault_type=data.get('fault_type'),
            repair_status=data.get('repair_status', '待维修'),
            repair_date=__parse_date(data.get('repair_date')),
            repair_cost=data.get('repair_cost'),
            remarks=data.get('remarks')
        )
        db.session.add(record)
        db.session.commit()
        return APIResponse.success(data=record.to_dict(), message='故障记录创建成功'), 201
    except Exception as e:
        db.session.rollback()
        return APIResponse.server_error(str(e))


# ==================== 维护记录 ====================

@records_bp.route('/api/maintenance-records', methods=['GET'])
@login_required
def get_maintenance_records():
    try:
        spare_part_id = request.args.get('spare_part_id', type=int)
        if spare_part_id:
            records = MaintenanceRecord.query.filter_by(spare_part_id=spare_part_id).order_by(MaintenanceRecord.maintenance_date.desc()).all()
        else:
            records = MaintenanceRecord.query.order_by(MaintenanceRecord.maintenance_date.desc()).all()
        return APIResponse.success(data=[r.to_dict(include_spare_part=True) for r in records])
    except Exception as e:
        logging.error(f'获取维护记录失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@records_bp.route('/api/maintenance-records', methods=['POST'])
@login_required
def create_maintenance_record():
    try:
        data = request.get_json()
        logging.info(f'创建维护记录 - 备件ID: {data.get("spare_part_id")}')

        next_inspection_date = __calc_next_inspection(
            data.get('last_inspection_date'),
            data.get('inspection_validity_period')
        )

        record = MaintenanceRecord(
            spare_part_id=data['spare_part_id'],
            operator_name=data['operator_name'],
            maintenance_date=__parse_date(data['maintenance_date']),
            maintenance_type=data.get('maintenance_type'),
            maintenance_content=data.get('maintenance_content'),
            last_inspection_date=__parse_date(data.get('last_inspection_date')),
            inspection_validity_period=data.get('inspection_validity_period'),
            next_inspection_date=next_inspection_date,
            maintenance_cost=data.get('maintenance_cost'),
            remarks=data.get('remarks')
        )

        db.session.add(record)

        spare_part = SparePart.query.get(data['spare_part_id'])
        if spare_part:
            if record.last_inspection_date:
                spare_part.last_inspection_date = record.last_inspection_date
            if record.next_inspection_date:
                spare_part.next_inspection_date = record.next_inspection_date
            spare_part.updated_at = db.func.now()

        db.session.commit()
        return APIResponse.success(data=record.to_dict(), message='维护记录创建成功，备件信息已同步更新'), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f'创建维护记录失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@records_bp.route('/api/maintenance-records/<int:record_id>', methods=['GET'])
@login_required
def get_maintenance_record(record_id):
    try:
        record = MaintenanceRecord.query.get_or_404(record_id)
        return APIResponse.success(data=record.to_dict())
    except Exception as e:
        logging.error(f'获取维护记录详情失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@records_bp.route('/api/maintenance-records/<int:record_id>', methods=['PUT'])
@login_required
def update_maintenance_record(record_id):
    try:
        data = request.get_json()
        record = MaintenanceRecord.query.get_or_404(record_id)
        logging.info(f'更新维护记录 - ID: {record_id}')

        next_inspection_date = __calc_next_inspection(
            data.get('last_inspection_date'),
            data.get('inspection_validity_period')
        )

        record.operator_name = data['operator_name']
        record.maintenance_date = __parse_date(data['maintenance_date'])
        record.maintenance_type = data.get('maintenance_type')
        record.maintenance_content = data.get('maintenance_content')
        record.last_inspection_date = __parse_date(data.get('last_inspection_date'))
        record.inspection_validity_period = data.get('inspection_validity_period')
        record.next_inspection_date = next_inspection_date
        record.maintenance_cost = data.get('maintenance_cost')
        record.remarks = data.get('remarks')

        spare_part = SparePart.query.get(record.spare_part_id)
        if spare_part:
            if record.last_inspection_date:
                spare_part.last_inspection_date = record.last_inspection_date
            if record.next_inspection_date:
                spare_part.next_inspection_date = record.next_inspection_date
            spare_part.updated_at = db.func.now()

        db.session.commit()
        return APIResponse.success(data=record.to_dict(), message='维护记录更新成功，备件信息已同步更新')
    except Exception as e:
        db.session.rollback()
        logging.error(f'更新维护记录失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@records_bp.route('/api/maintenance-records/<int:record_id>', methods=['DELETE'])
@login_required
def delete_maintenance_record(record_id):
    try:
        record = MaintenanceRecord.query.get_or_404(record_id)
        db.session.delete(record)
        db.session.commit()
        logging.info(f'维护记录删除成功 - ID: {record_id}')
        return APIResponse.success(message='维护记录删除成功')
    except Exception as e:
        db.session.rollback()
        logging.error(f'删除维护记录失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


def __parse_date(date_str):
    if not date_str:
        return None
    return datetime.strptime(date_str, '%Y-%m-%d').date()


def __calc_next_inspection(last_date_str, validity_period):
    if not last_date_str or not validity_period:
        return None
    last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
    validity_months = int(validity_period)
    return last_date + relativedelta(months=validity_months)
