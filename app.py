#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
备品备件管理系统 - 主应用程序
Author: wyj
License: MIT License
"""
from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import sys
import pandas as pd
from io import BytesIO
import webbrowser
import threading
import time
import signal
import atexit
try:
    from pystray import Icon, MenuItem, Menu
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# 处理PyInstaller打包后的资源路径
def get_resource_path(relative_path):
    """获取资源文件的绝对路径，支持PyInstaller打包"""
    try:
        # PyInstaller创建的临时文件夹
        base_path = sys._MEIPASS
    except Exception:
        # 开发环境
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 获取数据库路径（放在可写目录）
def get_database_path():
    """获取数据库路径，确保可写"""
    if getattr(sys, 'frozen', False):
        # 打包后，数据库放在exe同级目录
        app_dir = os.path.dirname(sys.executable)
    else:
        # 开发环境
        app_dir = os.path.abspath(".")
    
    # 创建数据库目录
    db_dir = os.path.join(app_dir, 'data')
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    return os.path.join(db_dir, 'spare_parts.db')

app = Flask(__name__, 
            template_folder=get_resource_path('templates'),
            static_folder=get_resource_path('static'))

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{get_database_path()}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'spare-parts-management-system-wyj'

db = SQLAlchemy(app)

# 数据模型
class SparePart(db.Model):
    """备品备件主表"""
    __tablename__ = 'spare_parts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 名称
    asset_number = db.Column(db.String(50), unique=True, nullable=False)  # 资产编号
    device_type = db.Column(db.String(50))  # 设备类型
    last_inspection_date = db.Column(db.Date)  # 上次检定日期
    next_inspection_date = db.Column(db.Date)  # 下次检定日期
    usage_status = db.Column(db.String(20), default='在库')  # 使用状态：在库、在用、维修中、报废
    storage_location = db.Column(db.String(100))  # 存放地点
    specifications = db.Column(db.Text)  # 规格型号
    manufacturer = db.Column(db.String(100))  # 生产厂家
    purchase_date = db.Column(db.Date)  # 采购日期
    warranty_period = db.Column(db.Integer)  # 质保期（月）
    unit_price = db.Column(db.Float)  # 单价
    remarks = db.Column(db.Text)  # 备注
    ownership = db.Column(db.String(100))  # 归属
    product_number = db.Column(db.String(50))  # 产品编号
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    inbound_records = db.relationship('InboundRecord', backref='spare_part', lazy=True, cascade='all, delete-orphan')
    outbound_records = db.relationship('OutboundRecord', backref='spare_part', lazy=True, cascade='all, delete-orphan')
    fault_records = db.relationship('FaultRecord', backref='spare_part', lazy=True, cascade='all, delete-orphan')
    
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


# 初始化数据库
with app.app_context():
    db.create_all()


# ==================== 路由和API ====================

# 页面路由
@app.route('/')
def index():
    """主页 - 备件列表"""
    return render_template('index.html')


@app.route('/create')
def create_page():
    """创建备件页面"""
    return render_template('create.html')


@app.route('/detail/<int:part_id>')
def detail_page(part_id):
    """备件详情页面"""
    return render_template('detail.html', part_id=part_id)


# API路由 - 备件管理
@app.route('/api/spare-parts', methods=['GET'])
def get_spare_parts():
    """获取备件列表（支持搜索和筛选）"""
    try:
        # 获取查询参数
        keyword = request.args.get('keyword', '')
        device_type = request.args.get('device_type', '')
        usage_status = request.args.get('usage_status', '')
        storage_location = request.args.get('storage_location', '')
        
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
        if device_type:
            query = query.filter(SparePart.device_type == device_type)
        if usage_status:
            query = query.filter(SparePart.usage_status == usage_status)
        if storage_location:
            query = query.filter(SparePart.storage_location.like(f'%{storage_location}%'))
        
        # 执行查询
        spare_parts = query.all()
        
        return jsonify({
            'success': True,
            'data': [part.to_dict() for part in spare_parts]
        })
    except Exception as e:
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
        
        # 数据验证
        if not data.get('name') or not data.get('asset_number'):
            return jsonify({'success': False, 'message': '名称和资产编号为必填项'}), 400
        
        # 检查资产编号是否已存在
        if SparePart.query.filter_by(asset_number=data['asset_number']).first():
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
        
        return jsonify({
            'success': True,
            'message': '备件创建成功',
            'data': spare_part.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/spare-parts/<int:part_id>', methods=['PUT'])
def update_spare_part(part_id):
    """更新备件信息"""
    try:
        part = SparePart.query.get_or_404(part_id)
        data = request.get_json()
        
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
        
        return jsonify({
            'success': True,
            'message': '备件更新成功',
            'data': part.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/spare-parts/<int:part_id>', methods=['DELETE'])
def delete_spare_part(part_id):
    """删除备件"""
    try:
        part = SparePart.query.get_or_404(part_id)
        db.session.delete(part)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '备件删除成功'
        })
    except Exception as e:
        db.session.rollback()
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
    """导出备件列表为Excel"""
    try:
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
        
        # 转换为DataFrame
        data = []
        for part in spare_parts:
            part_dict = part.to_dict()
            data.append({
                'ID': part_dict['id'],
                '名称': part_dict['name'],
                '资产编号': part_dict['asset_number'],
                '设备类型': part_dict['device_type'],
                '下次检定日期': part_dict['next_inspection_date'],
                '距离检定天数': part_dict['days_to_inspection'],
                '使用状态': part_dict['usage_status'],
                '存放地点': part_dict['storage_location'],
                '规格型号': part_dict['specifications'],
                '生产厂家': part_dict['manufacturer'],
                '采购日期': part_dict['purchase_date'],
                '质保期(月)': part_dict['warranty_period'],
                '单价': part_dict['unit_price'],
                '备注': part_dict['remarks']
            })
        
        df = pd.DataFrame(data)
        
        # 创建Excel文件
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='备品备件列表')
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'备品备件列表_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
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
