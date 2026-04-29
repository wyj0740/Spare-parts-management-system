#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库模型模块
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# 系统版本号
APP_VERSION = 'v2.2.0'


class OperationLog(db.Model):
    """操作日志表"""
    __tablename__ = 'operation_logs'

    id = db.Column(db.Integer, primary_key=True)
    operator = db.Column(db.String(50), nullable=False)          # 操作人
    action = db.Column(db.String(30), nullable=False)            # 操作类型: CREATE/UPDATE/DELETE/IMPORT
    target_type = db.Column(db.String(30), default='spare_part') # 目标对象类型
    target_id = db.Column(db.Integer)                            # 目标对象ID
    target_name = db.Column(db.String(100))                      # 目标对象名称（冗余，删除后仍可显示）
    detail = db.Column(db.Text)                                  # 操作详情/变更内容JSON
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'operator': self.operator,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'target_name': self.target_name,
            'detail': self.detail,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class FieldChangeLog(db.Model):
    """字段变更记录表"""
    __tablename__ = 'field_change_logs'

    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id', ondelete='CASCADE'), nullable=False)
    operator = db.Column(db.String(50), nullable=False)
    field_name = db.Column(db.String(50), nullable=False)        # 变更字段
    field_label = db.Column(db.String(50))                       # 字段中文名
    old_value = db.Column(db.Text)                               # 变更前
    new_value = db.Column(db.Text)                               # 变更后
    changed_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'spare_part_id': self.spare_part_id,
            'operator': self.operator,
            'field_name': self.field_name,
            'field_label': self.field_label or self.field_name,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'changed_at': self.changed_at.strftime('%Y-%m-%d %H:%M:%S') if self.changed_at else None
        }


class SparePart(db.Model):
    """备品备件主表"""
    __tablename__ = 'spare_parts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    asset_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    device_type = db.Column(db.String(50))
    last_inspection_date = db.Column(db.Date)
    next_inspection_date = db.Column(db.Date, index=True)
    usage_status = db.Column(db.String(20), default='在库', index=True)
    storage_location = db.Column(db.String(100), index=True)
    specifications = db.Column(db.Text)
    manufacturer = db.Column(db.String(100))
    purchase_date = db.Column(db.Date)
    warranty_period = db.Column(db.Integer)
    unit_price = db.Column(db.Float)
    remarks = db.Column(db.Text)
    ownership = db.Column(db.String(100), index=True)
    product_number = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    inbound_records = db.relationship('InboundRecord', backref='spare_part', lazy=True, cascade='all, delete-orphan')
    outbound_records = db.relationship('OutboundRecord', backref='spare_part', lazy=True, cascade='all, delete-orphan')
    fault_records = db.relationship('FaultRecord', backref='spare_part', lazy=True, cascade='all, delete-orphan')
    maintenance_records = db.relationship('MaintenanceRecord', backref='spare_part', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        days_to_inspection = None
        inspection_progress = 0
        if self.next_inspection_date:
            delta = self.next_inspection_date - datetime.now().date()
            days_to_inspection = delta.days

            if self.last_inspection_date:
                total_days = (self.next_inspection_date - self.last_inspection_date).days
                remaining_days = days_to_inspection
                if total_days > 0:
                    inspection_progress = max(0, min(100, (remaining_days / total_days) * 100))
                else:
                    inspection_progress = 0 if days_to_inspection < 0 else 100
            else:
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
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }


class InboundRecord(db.Model):
    """入库记录表"""
    __tablename__ = 'inbound_records'

    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    operator_name = db.Column(db.String(50), nullable=False)
    inbound_date = db.Column(db.DateTime, default=db.func.now())
    supplier = db.Column(db.String(100))
    batch_number = db.Column(db.String(50))
    remarks = db.Column(db.Text)

    def to_dict(self, include_spare_part=True):
        result = {
            'id': self.id,
            'spare_part_id': self.spare_part_id,
            'quantity': self.quantity,
            'operator_name': self.operator_name,
            'inbound_date': self.inbound_date.strftime('%Y-%m-%d %H:%M:%S') if self.inbound_date else None,
            'supplier': self.supplier,
            'batch_number': self.batch_number,
            'remarks': self.remarks
        }
        if include_spare_part:
            result['spare_part_name'] = self.spare_part.name if self.spare_part else None
            result['spare_part_asset_number'] = self.spare_part.asset_number if self.spare_part else None
        return result


class OutboundRecord(db.Model):
    """出库记录表"""
    __tablename__ = 'outbound_records'

    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    operator_name = db.Column(db.String(50), nullable=False)
    outbound_date = db.Column(db.DateTime, default=db.func.now())
    recipient = db.Column(db.String(50))
    purpose = db.Column(db.String(200))
    expected_return_date = db.Column(db.Date)
    remarks = db.Column(db.Text)

    def to_dict(self, include_spare_part=True):
        result = {
            'id': self.id,
            'spare_part_id': self.spare_part_id,
            'quantity': self.quantity,
            'operator_name': self.operator_name,
            'outbound_date': self.outbound_date.strftime('%Y-%m-%d %H:%M:%S') if self.outbound_date else None,
            'recipient': self.recipient,
            'purpose': self.purpose,
            'expected_return_date': self.expected_return_date.strftime('%Y-%m-%d') if self.expected_return_date else None,
            'remarks': self.remarks
        }
        if include_spare_part:
            result['spare_part_name'] = self.spare_part.name if self.spare_part else None
            result['spare_part_asset_number'] = self.spare_part.asset_number if self.spare_part else None
        return result


class FaultRecord(db.Model):
    """故障记录表"""
    __tablename__ = 'fault_records'

    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    operator_name = db.Column(db.String(50), nullable=False)
    fault_date = db.Column(db.DateTime, default=db.func.now())
    fault_description = db.Column(db.Text, nullable=False)
    fault_type = db.Column(db.String(50))
    repair_status = db.Column(db.String(20), default='待维修')
    repair_date = db.Column(db.Date)
    repair_cost = db.Column(db.Float)
    remarks = db.Column(db.Text)

    def to_dict(self, include_spare_part=True):
        result = {
            'id': self.id,
            'spare_part_id': self.spare_part_id,
            'operator_name': self.operator_name,
            'fault_date': self.fault_date.strftime('%Y-%m-%d %H:%M:%S') if self.fault_date else None,
            'fault_description': self.fault_description,
            'fault_type': self.fault_type,
            'repair_status': self.repair_status,
            'repair_date': self.repair_date.strftime('%Y-%m-%d') if self.repair_date else None,
            'repair_cost': self.repair_cost,
            'remarks': self.remarks
        }
        if include_spare_part:
            result['spare_part_name'] = self.spare_part.name if self.spare_part else None
            result['spare_part_asset_number'] = self.spare_part.asset_number if self.spare_part else None
        return result


class MaintenanceRecord(db.Model):
    """维护记录表"""
    __tablename__ = 'maintenance_records'

    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    operator_name = db.Column(db.String(50), nullable=False)
    maintenance_date = db.Column(db.Date, nullable=False)
    maintenance_type = db.Column(db.String(50))
    maintenance_content = db.Column(db.Text)
    last_inspection_date = db.Column(db.Date)
    inspection_validity_period = db.Column(db.Integer)
    next_inspection_date = db.Column(db.Date)
    maintenance_cost = db.Column(db.Float)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.now())

    def to_dict(self, include_spare_part=True):
        result = {
            'id': self.id,
            'spare_part_id': self.spare_part_id,
            'operator_name': self.operator_name,
            'maintenance_date': self.maintenance_date.strftime('%Y-%m-%d') if self.maintenance_date else None,
            'maintenance_type': self.maintenance_type,
            'maintenance_content': self.maintenance_content,
            'last_inspection_date': self.last_inspection_date.strftime('%Y-%m-%d') if self.last_inspection_date else None,
            'inspection_validity_period': self.inspection_validity_period,
            'next_inspection_date': self.next_inspection_date.strftime('%Y-%m-%d') if self.next_inspection_date else None,
            'maintenance_cost': self.maintenance_cost,
            'remarks': self.remarks,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
        if include_spare_part:
            result['spare_part_name'] = self.spare_part.name if self.spare_part else None
            result['spare_part_asset_number'] = self.spare_part.asset_number if self.spare_part else None
        return result
