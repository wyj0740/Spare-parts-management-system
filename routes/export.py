#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据导出路由模块
"""
import logging
from datetime import datetime, date
from io import BytesIO
from flask import Blueprint, request, send_file
from dateutil.relativedelta import relativedelta
import pandas as pd

from models import db, SparePart, InboundRecord, OutboundRecord, MaintenanceRecord, FaultRecord
from routes.common import APIResponse, login_required

export_bp = Blueprint('export', __name__)


@export_bp.route('/api/export/spare-parts', methods=['GET'])
@login_required
def export_spare_parts():
    """导出备件列表为Excel（包含入库、出库、维护、故障记录）"""
    try:
        keyword = request.args.get('keyword', '')
        device_type = request.args.get('device_type', '')
        usage_status = request.args.get('usage_status', '')
        storage_location = request.args.get('storage_location', '')

        query = SparePart.query
        if keyword:
            kf = f'%{keyword}%'
            query = query.filter(db.or_(
                SparePart.name.like(kf),
                SparePart.asset_number.like(kf),
                SparePart.storage_location.like(kf)
            ))
        if device_type:
            query = query.filter(SparePart.device_type == device_type)
        if usage_status:
            query = query.filter(SparePart.usage_status == usage_status)
        if storage_location:
            query = query.filter(SparePart.storage_location.like(f'%{storage_location}%'))

        spare_parts = query.all()
        spare_part_ids = [part.id for part in spare_parts]

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Sheet 1
            data = []
            for part in spare_parts:
                d = part.to_dict()
                data.append({
                    'ID': d['id'], '名称': d['name'], '资产编号': d['asset_number'],
                    '系统': d['ownership'], '设备类型': d['device_type'],
                    '下次检定日期': d['next_inspection_date'],
                    '距离检定天数': d['days_to_inspection'],
                    '使用状态': d['usage_status'], '存放地点': d['storage_location'],
                    '规格型号': d['specifications'], '生产厂家': d['manufacturer'],
                    '出厂编号': d['product_number'], '采购日期': d['purchase_date'],
                    '质保期(月)': d['warranty_period'], '单价': d['unit_price'], '备注': d['remarks']
                })
            if data:
                pd.DataFrame(data).to_excel(writer, index=False, sheet_name='备件列表')

            _write_records_sheet(writer, spare_part_ids, InboundRecord, '入库记录', _inbound_mapper)
            _write_records_sheet(writer, spare_part_ids, OutboundRecord, '出库记录', _outbound_mapper)
            _write_records_sheet(writer, spare_part_ids, MaintenanceRecord, '维护记录', _maintenance_mapper)
            _write_records_sheet(writer, spare_part_ids, FaultRecord, '故障记录', _fault_mapper)

        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'备品备件列表及记录_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        logging.error(f'导出备件列表失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@export_bp.route('/api/export/records', methods=['GET'])
@login_required
def export_records():
    """导出记录为Excel"""
    try:
        part_id = request.args.get('spare_part_id', type=int)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            _write_records_sheet(writer, [part_id] if part_id else None, InboundRecord, '入库记录', _inbound_mapper)
            _write_records_sheet(writer, [part_id] if part_id else None, OutboundRecord, '出库记录', _outbound_mapper)
            _write_records_sheet(writer, [part_id] if part_id else None, FaultRecord, '故障记录', _fault_mapper)
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'备件记录_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        return APIResponse.server_error(str(e))


@export_bp.route('/api/export/calibration-plan', methods=['GET'])
@login_required
def export_calibration_plan():
    """导出计量工作计划"""
    try:
        current_year = datetime.now().year
        year_start = date(current_year, 1, 1)
        year_end = date(current_year, 12, 31)

        spare_parts = SparePart.query.filter(
            SparePart.next_inspection_date.isnot(None),
            SparePart.next_inspection_date >= year_start,
            SparePart.next_inspection_date <= year_end
        ).order_by(SparePart.next_inspection_date.asc()).all()

        data = []
        for idx, part in enumerate(spare_parts, start=1):
            d = part.to_dict()
            data.append({
                '序号': idx, '传感器名称': d['name'],
                '规格型号': d['specifications'] or '', '生产厂家': d['manufacturer'] or '',
                '出厂编号': d['product_number'] or '', '数量': 1,
                '系统': d['ownership'] or '', '检定/校准单位': '',
                '最后检定/校准日期': d['last_inspection_date'] or '',
                '检定/校准有效日期': d['next_inspection_date'] or '',
                '计划时间': '', '计划方式': '校准'
            })

        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f'{current_year}年计量工作计划')
            ws = writer.sheets[f'{current_year}年计量工作计划']
            _set_column_widths(ws, [8, 20, 20, 20, 18, 8, 15, 20, 18, 18, 15, 12])

        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'{current_year}年计量工作计划_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        logging.error(f'导出计量工作计划失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@export_bp.route('/api/export/instrument-details', methods=['GET'])
@login_required
def export_instrument_details():
    """导出计量器具明细表"""
    try:
        current_year = datetime.now().year
        spare_parts = SparePart.query.filter(
            SparePart.next_inspection_date.isnot(None)
        ).order_by(SparePart.ownership.asc(), SparePart.name.asc()).all()

        data = []
        for part in spare_parts:
            d = part.to_dict()
            maintenance_records = MaintenanceRecord.query.filter_by(
                spare_part_id=part.id
            ).filter(
                MaintenanceRecord.last_inspection_date.isnot(None)
            ).order_by(
                MaintenanceRecord.last_inspection_date.desc()
            ).limit(2).all()

            latest_inspection_date = ''
            previous_inspection_date = ''
            inspection_period = ''

            if len(maintenance_records) > 0:
                latest_inspection_date = maintenance_records[0].last_inspection_date.strftime('%Y-%m-%d')
                if maintenance_records[0].inspection_validity_period:
                    inspection_period = _format_period(maintenance_records[0].inspection_validity_period)

            if len(maintenance_records) > 1:
                previous_inspection_date = maintenance_records[1].last_inspection_date.strftime('%Y-%m-%d')

            if not latest_inspection_date and d['last_inspection_date']:
                latest_inspection_date = d['last_inspection_date']
            if latest_inspection_date and not previous_inspection_date:
                previous_inspection_date = latest_inspection_date
            if not inspection_period and d['last_inspection_date'] and d['next_inspection_date']:
                inspection_period = _calc_period_from_dates(d['last_inspection_date'], d['next_inspection_date'])

            data.append({
                '系统': d['ownership'] or '', '名称': d['name'],
                '规格型号': d['specifications'] or '', '测量范围': '', '分辨率': '',
                '生产厂家': d['manufacturer'] or '', '出厂编号': d['product_number'] or '',
                '上次检定/校准日期': previous_inspection_date,
                '最新检定/校准日期': latest_inspection_date,
                '检定/校准有效日期': d['next_inspection_date'] or '',
                '检定/校准方式': '权威校准',
                '检定/校准周期': inspection_period,
                '检定/校准单位': '', '校准测试记录': '', '备注': '合格', '状态': ''
            })

        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f'{current_year}年计量器具明细表')
            ws = writer.sheets[f'{current_year}年计量器具明细表']
            _set_column_widths(ws, [15, 20, 20, 15, 12, 20, 18, 18, 18, 18, 15, 15, 20, 18, 12, 12])

        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'{current_year}年计量器具明细表_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        logging.error(f'导出计量器具明细表失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


def _write_records_sheet(writer, part_ids, model, sheet_name, mapper):
    """通用记录Sheet写入"""
    if part_ids is None:
        records = model.query.all()
    elif part_ids:
        records = model.query.filter(model.spare_part_id.in_(part_ids)).all()
    else:
        records = []
    data = [mapper(r) for r in records]
    if data:
        pd.DataFrame(data).to_excel(writer, index=False, sheet_name=sheet_name)


def _inbound_mapper(r):
    d = r.to_dict(include_spare_part=False)
    return {
        'ID': d['id'], '备件名称': r.spare_part.name if r.spare_part else None,
        '资产编号': r.spare_part.asset_number if r.spare_part else None,
        '数量': d['quantity'], '操作者': d['operator_name'], '入库时间': d['inbound_date'],
        '供应商': d['supplier'], '批次号': d['batch_number'], '备注': d['remarks']
    }


def _outbound_mapper(r):
    d = r.to_dict(include_spare_part=False)
    return {
        'ID': d['id'], '备件名称': r.spare_part.name if r.spare_part else None,
        '资产编号': r.spare_part.asset_number if r.spare_part else None,
        '数量': d['quantity'], '操作者': d['operator_name'], '出库时间': d['outbound_date'],
        '领用人': d['recipient'], '用途': d['purpose'], '预计归还日期': d['expected_return_date'], '备注': d['remarks']
    }


def _maintenance_mapper(r):
    d = r.to_dict(include_spare_part=False)
    return {
        'ID': d['id'], '备件名称': r.spare_part.name if r.spare_part else None,
        '资产编号': r.spare_part.asset_number if r.spare_part else None,
        '操作者': d['operator_name'], '维护日期': d['maintenance_date'],
        '维护类型': d['maintenance_type'], '维护内容': d['maintenance_content'],
        '上次检定日期': d['last_inspection_date'], '检定有效期(月)': d['inspection_validity_period'],
        '下次检定日期': d['next_inspection_date'], '维护费用': d['maintenance_cost'], '备注': d['remarks']
    }


def _fault_mapper(r):
    d = r.to_dict(include_spare_part=False)
    return {
        'ID': d['id'], '备件名称': r.spare_part.name if r.spare_part else None,
        '资产编号': r.spare_part.asset_number if r.spare_part else None,
        '操作者': d['operator_name'], '故障时间': d['fault_date'],
        '故障描述': d['fault_description'], '故障类型': d['fault_type'],
        '维修状态': d['repair_status'], '维修完成日期': d['repair_date'],
        '维修费用': d['repair_cost'], '备注': d['remarks']
    }


def _set_column_widths(worksheet, widths):
    """批量设置列宽"""
    for i, width in enumerate(widths, start=1):
        col_letter = chr(64 + i) if i <= 26 else chr(64 + i // 26) + chr(64 + i % 26)
        worksheet.column_dimensions[col_letter].width = width


def _format_period(months):
    years = months / 12
    if years >= 1:
        return f'{years:.0f}年' if years == int(years) else f'{years:.1f}年'
    return f'{months}个月'


def _calc_period_from_dates(last_str, next_str):
    try:
        last_date = datetime.strptime(last_str, '%Y-%m-%d').date()
        next_date = datetime.strptime(next_str, '%Y-%m-%d').date()
        delta = relativedelta(next_date, last_date)
        months = delta.years * 12 + delta.months
        if months > 0:
            return _format_period(months)
    except Exception:
        pass
    return ''
