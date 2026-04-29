#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
备件管理路由模块
"""
import logging
import io
import pandas as pd
from datetime import date, timedelta, datetime
from flask import Blueprint, request, send_file

from models import db, SparePart
from routes.common import APIResponse, login_required
from routes.audit import write_operation_log, write_field_changes
from utils.folder_manager import create_spare_part_folder, rename_spare_part_folder, delete_spare_part_folder

spare_parts_bp = Blueprint('spare_parts', __name__)

# 导入模板列配置
IMPORT_COLUMNS = [
    ('名称', 'name', True),
    ('资产编号', 'asset_number', True),
    ('系统', 'ownership', False),
    ('设备类型', 'device_type', False),
    ('规格型号', 'specifications', False),
    ('生产厂家', 'manufacturer', False),
    ('出厂编号', 'product_number', False),
    ('使用状态', 'usage_status', False),
    ('存放地点', 'storage_location', False),
    ('采购日期', 'purchase_date', False),
    ('上次检定日期', 'last_inspection_date', False),
    ('下次检定日期', 'next_inspection_date', False),
    ('质保期(月)', 'warranty_period', False),
    ('单价', 'unit_price', False),
    ('备注', 'remarks', False)
]


@spare_parts_bp.route('/api/spare-parts', methods=['GET'])
@login_required
def get_spare_parts():
    """获取备件列表（支持搜索和筛选）"""
    try:
        keyword = request.args.get('keyword', '')
        ownership = request.args.get('ownership', '')
        device_type = request.args.get('device_type', '')
        usage_status = request.args.get('usage_status', '')
        inspection_status = request.args.get('inspection_status', '')
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

        if ownership:
            query = query.filter(SparePart.ownership == ownership)
        if device_type:
            query = query.filter(SparePart.device_type == device_type)
        if usage_status:
            query = query.filter(SparePart.usage_status == usage_status)
        if storage_location:
            query = query.filter(SparePart.storage_location.like(f'%{storage_location}%'))

        # 检定状态筛选下沉到 SQL 层
        if inspection_status:
            today = date.today()
            if inspection_status == 'no_inspection':
                query = query.filter(SparePart.next_inspection_date.is_(None))
            elif inspection_status == 'expired':
                query = query.filter(SparePart.next_inspection_date < today)
            elif inspection_status == 'urgent':
                query = query.filter(
                    SparePart.next_inspection_date >= today,
                    SparePart.next_inspection_date <= today + timedelta(days=90)
                )
            elif inspection_status == 'warning':
                query = query.filter(
                    SparePart.next_inspection_date > today + timedelta(days=90),
                    SparePart.next_inspection_date <= today + timedelta(days=180)
                )
            elif inspection_status == 'normal':
                query = query.filter(
                    SparePart.next_inspection_date.isnot(None),
                    SparePart.next_inspection_date > today + timedelta(days=180)
                )

        spare_parts = query.all()

        return APIResponse.success(data=[part.to_dict() for part in spare_parts])
    except Exception as e:
        logging.error(f'获取备件列表失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@spare_parts_bp.route('/api/spare-parts/<int:part_id>', methods=['GET'])
@login_required
def get_spare_part(part_id):
    """获取单个备件详情"""
    try:
        part = SparePart.query.get_or_404(part_id)
        return APIResponse.success(data=part.to_dict())
    except Exception as e:
        return APIResponse.not_found(str(e))


@spare_parts_bp.route('/api/spare-parts/options', methods=['GET'])
@login_required
def get_spare_parts_options():
    """获取备件字段的已有选项"""
    try:
        ownerships = db.session.query(SparePart.ownership).filter(
            SparePart.ownership.isnot(None),
            SparePart.ownership != ''
        ).distinct().all()
        ownership_list = sorted([o[0] for o in ownerships if o[0]])

        locations = db.session.query(SparePart.storage_location).filter(
            SparePart.storage_location.isnot(None),
            SparePart.storage_location != ''
        ).distinct().all()
        location_list = sorted([l[0] for l in locations if l[0]])

        manufacturers = db.session.query(SparePart.manufacturer).filter(
            SparePart.manufacturer.isnot(None),
            SparePart.manufacturer != ''
        ).distinct().all()
        manufacturer_list = sorted([m[0] for m in manufacturers if m[0]])

        return APIResponse.success(data={
            'ownerships': ownership_list,
            'storage_locations': location_list,
            'manufacturers': manufacturer_list
        })
    except Exception as e:
        logging.error(f'获取选项列表失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@spare_parts_bp.route('/api/spare-parts', methods=['POST'])
@login_required
def create_spare_part():
    """创建新备件"""
    try:
        data = request.get_json()

        if not data.get('name') or not data.get('asset_number'):
            return APIResponse.error('名称和资产编号为必填项'), 400

        if SparePart.query.filter_by(asset_number=data['asset_number']).first():
            return APIResponse.error('资产编号已存在'), 400

        spare_part = SparePart(
            name=data['name'],
            asset_number=data['asset_number'],
            device_type=data.get('device_type'),
            last_inspection_date=__parse_date(data.get('last_inspection_date')),
            next_inspection_date=__parse_date(data.get('next_inspection_date')),
            usage_status=data.get('usage_status', '在库'),
            storage_location=data.get('storage_location'),
            specifications=data.get('specifications'),
            manufacturer=data.get('manufacturer'),
            purchase_date=__parse_date(data.get('purchase_date')),
            warranty_period=data.get('warranty_period'),
            unit_price=data.get('unit_price'),
            remarks=data.get('remarks'),
            ownership=data.get('ownership'),
            product_number=data.get('product_number')
        )

        db.session.add(spare_part)
        write_operation_log('CREATE', target_id=None, target_name=data['name'],
                            detail={'asset_number': data['asset_number']})
        db.session.commit()

        create_spare_part_folder(spare_part.asset_number, spare_part.name)

        return APIResponse.success(data=spare_part.to_dict(), message='备件创建成功'), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f'创建备件失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@spare_parts_bp.route('/api/spare-parts/<int:part_id>', methods=['PUT'])
@login_required
def update_spare_part(part_id):
    """更新备件信息"""
    try:
        part = SparePart.query.get_or_404(part_id)
        data = request.get_json()

        old_asset_number = part.asset_number
        old_name = part.name
        old_snapshot = part.to_dict()

        if 'name' in data:
            part.name = data['name']
        if 'device_type' in data:
            part.device_type = data['device_type']
        if 'last_inspection_date' in data:
            part.last_inspection_date = __parse_date(data['last_inspection_date'])
        if 'next_inspection_date' in data:
            part.next_inspection_date = __parse_date(data['next_inspection_date'])
        if 'usage_status' in data:
            part.usage_status = data['usage_status']
        if 'storage_location' in data:
            part.storage_location = data['storage_location']
        if 'specifications' in data:
            part.specifications = data['specifications']
        if 'manufacturer' in data:
            part.manufacturer = data['manufacturer']
        if 'purchase_date' in data and data['purchase_date']:
            part.purchase_date = __parse_date(data['purchase_date'])
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

        if old_asset_number != part.asset_number or old_name != part.name:
            rename_spare_part_folder(old_asset_number, old_name, part.asset_number, part.name)

        return APIResponse.success(data=part.to_dict(), message='备件更新成功')
    except Exception as e:
        db.session.rollback()
        logging.error(f'更新备件失败 - ID: {part_id}, 错误: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@spare_parts_bp.route('/api/spare-parts/<int:part_id>', methods=['DELETE'])
@login_required
def delete_spare_part(part_id):
    """删除备件"""
    try:
        delete_folder = request.args.get('delete_folder', 'false').lower() == 'true'

        part = SparePart.query.get_or_404(part_id)
        part_name = part.name
        part_asset_number = part.asset_number

        db.session.delete(part)
        write_operation_log('DELETE', target_id=part_id, target_name=part_name,
                            detail={'asset_number': part_asset_number})
        db.session.commit()

        folder_deleted = False
        if delete_folder:
            folder_deleted = delete_spare_part_folder(part_asset_number, part_name)

        return APIResponse.success(data={'folder_deleted': folder_deleted}, message='备件删除成功')
    except Exception as e:
        db.session.rollback()
        logging.error(f'删除备件失败 - ID: {part_id}, 错误: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@spare_parts_bp.route('/api/spare-parts/stats', methods=['GET'])
@login_required
def get_spare_parts_stats():
    """获取全局统计信息（不受筛选条件影响）"""
    try:
        total = SparePart.query.count()
        in_stock = SparePart.query.filter_by(usage_status='在库').count()
        today = date.today()
        expired = SparePart.query.filter(
            SparePart.next_inspection_date.isnot(None),
            SparePart.next_inspection_date < today
        ).count()
        pending = SparePart.query.filter(
            SparePart.next_inspection_date.isnot(None),
            SparePart.next_inspection_date >= today,
            SparePart.next_inspection_date <= today + timedelta(days=90)
        ).count()

        now = datetime.now()
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_this_month = SparePart.query.filter(SparePart.created_at >= this_month_start).count()

        return APIResponse.success(data={
            'total': total,
            'in_stock': in_stock,
            'expired': expired,
            'pending': pending,
            'new_this_month': new_this_month
        })
    except Exception as e:
        logging.error(f'获取统计信息失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@spare_parts_bp.route('/api/spare-parts/pending-inspection', methods=['GET'])
@login_required
def get_pending_inspection_parts():
    """获取待检定备件列表（按日期排序）"""
    try:
        spare_parts = SparePart.query.filter(
            SparePart.next_inspection_date.isnot(None)
        ).order_by(SparePart.next_inspection_date.asc()).all()

        return APIResponse.success(data=[part.to_dict() for part in spare_parts])
    except Exception as e:
        return APIResponse.server_error(str(e))


def __parse_date(date_str):
    """辅助函数：解析日期字符串"""
    if not date_str:
        return None
    from datetime import datetime
    return datetime.strptime(date_str, '%Y-%m-%d').date()


def __parse_date_flexible(date_val):
    """灵活解析日期，支持字符串和pandas Timestamp"""
    if pd.isna(date_val) or date_val is None or date_val == '':
        return None
    if isinstance(date_val, pd.Timestamp):
        return date_val.date()
    if isinstance(date_val, date):
        return date_val
    date_str = str(date_val).strip()
    if not date_str or date_str.lower() in ('nan', 'none', 'null', '-'):
        return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y%m%d', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            from datetime import datetime
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


@spare_parts_bp.route('/api/spare-parts/import-template', methods=['GET'])
@login_required
def download_import_template():
    """下载批量导入模板"""
    try:
        output = io.BytesIO()
        columns = [c[0] for c in IMPORT_COLUMNS]
        df = pd.DataFrame(columns=columns)
        # 添加示例行
        example = {
            '名称': '示例设备',
            '资产编号': 'EXAMPLE-001',
            '系统': '自观系统',
            '设备类型': '传感器',
            '规格型号': 'Model-A',
            '生产厂家': '示例厂家',
            '出厂编号': 'SN123456',
            '使用状态': '在库',
            '存放地点': '仓库A区',
            '采购日期': '2024-01-15',
            '上次检定日期': '2024-06-15',
            '下次检定日期': '2025-06-15',
            '质保期(月)': 12,
            '单价': 5000.00,
            '备注': '示例数据，导入后请删除此行'
        }
        df = pd.concat([df, pd.DataFrame([example])], ignore_index=True)

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='备件导入模板')
            worksheet = writer.sheets['备件导入模板']
            # 设置列宽
            for idx, col in enumerate(df.columns, 1):
                worksheet.column_dimensions[worksheet.cell(row=1, column=idx).column_letter].width = max(len(col) * 2 + 2, 14)

        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='备件批量导入模板.xlsx'
        )
    except Exception as e:
        logging.error(f'生成导入模板失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))


@spare_parts_bp.route('/api/spare-parts/import-preview', methods=['POST'])
@login_required
def import_spare_parts_preview():
    """批量导入预览：解析Excel，返回数据预览（不写入数据库）"""
    try:
        if 'file' not in request.files:
            return APIResponse.error('请上传Excel文件'), 400
        file = request.files['file']
        if not file or file.filename == '':
            return APIResponse.error('请上传Excel文件'), 400
        if not file.filename.endswith(('.xlsx', '.xls')):
            return APIResponse.error('仅支持 .xlsx 或 .xls 格式的Excel文件'), 400

        df = pd.read_excel(file)
        if df.empty:
            return APIResponse.error('Excel文件为空'), 400

        col_mapping = {c[0]: c[1] for c in IMPORT_COLUMNS}
        for c in IMPORT_COLUMNS:
            col_mapping[c[1]] = c[1]
        rename_map = {}
        for col in df.columns:
            col_str = str(col).strip()
            if col_str in col_mapping:
                rename_map[col] = col_mapping[col_str]
        df = df.rename(columns=rename_map)

        required_cols = [c[1] for c in IMPORT_COLUMNS if c[2]]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            return APIResponse.error('Excel缺少必填列: ' + ', '.join(missing_cols)), 400

        existing_asset_numbers = {sp.asset_number for sp in SparePart.query.with_entities(SparePart.asset_number).all()}

        preview_rows = []
        for idx, row in df.iterrows():
            row_num = idx + 2
            name = str(row.get('name', '')).strip()
            asset_number = str(row.get('asset_number', '')).strip()
            error_msg = None
            if not name or not asset_number:
                error_msg = '名称和资产编号不能为空'
            elif asset_number in existing_asset_numbers:
                error_msg = f'资产编号 "{asset_number}" 已存在'
            preview_rows.append({
                'row': row_num,
                'name': name,
                'asset_number': asset_number,
                'ownership': str(row.get('ownership', '')).strip() or None,
                'device_type': str(row.get('device_type', '')).strip() or None,
                'specifications': str(row.get('specifications', '')).strip() or None,
                'manufacturer': str(row.get('manufacturer', '')).strip() or None,
                'usage_status': str(row.get('usage_status', '在库')).strip() or '在库',
                'storage_location': str(row.get('storage_location', '')).strip() or None,
                'purchase_date': str(row.get('purchase_date', '')).strip() if row.get('purchase_date') else None,
                'next_inspection_date': str(row.get('next_inspection_date', '')).strip() if row.get('next_inspection_date') else None,
                'error': error_msg,
                'valid': error_msg is None
            })

        valid_count = sum(1 for r in preview_rows if r['valid'])
        invalid_count = len(preview_rows) - valid_count
        return APIResponse.success(data={
            'total': len(preview_rows),
            'valid': valid_count,
            'invalid': invalid_count,
            'rows': preview_rows
        })
    except Exception as e:
        logging.error(f'导入预览失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))



@spare_parts_bp.route('/api/spare-parts/import', methods=['POST'])
@login_required
def import_spare_parts():
    """批量导入备件（Excel上传）"""
    try:
        if 'file' not in request.files:
            return APIResponse.error('请上传Excel文件'), 400

        file = request.files['file']
        if not file or file.filename == '':
            return APIResponse.error('请上传Excel文件'), 400

        if not file.filename.endswith(('.xlsx', '.xls')):
            return APIResponse.error('仅支持 .xlsx 或 .xls 格式的Excel文件'), 400

        df = pd.read_excel(file)
        if df.empty:
            return APIResponse.error('Excel文件为空'), 400

        # 列名映射（中文列名 -> 英文字段名）
        col_mapping = {c[0]: c[1] for c in IMPORT_COLUMNS}
        # 也支持英文列名直接导入
        for c in IMPORT_COLUMNS:
            col_mapping[c[1]] = c[1]

        # 重命名列
        rename_map = {}
        for col in df.columns:
            col_str = str(col).strip()
            if col_str in col_mapping:
                rename_map[col] = col_mapping[col_str]
        df = df.rename(columns=rename_map)

        # 检查必填列
        required_cols = [c[1] for c in IMPORT_COLUMNS if c[2]]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            return APIResponse.error('Excel缺少必填列: ' + ', '.join(missing_cols)), 400

        success_count = 0
        failed_rows = []
        created_parts = []

        # 预加载已有资产编号
        existing_asset_numbers = {sp.asset_number for sp in SparePart.query.with_entities(SparePart.asset_number).all()}

        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel行号（含表头）
            try:
                name = str(row.get('name', '')).strip()
                asset_number = str(row.get('asset_number', '')).strip()

                if not name or not asset_number:
                    failed_rows.append({'row': row_num, 'reason': '名称和资产编号不能为空'})
                    continue

                if asset_number in existing_asset_numbers:
                    failed_rows.append({'row': row_num, 'reason': f'资产编号 "{asset_number}" 已存在'})
                    continue

                usage_status = str(row.get('usage_status', '在库')).strip() or '在库'
                if usage_status not in ('在库', '在用', '维修中', '报废'):
                    usage_status = '在库'

                spare_part = SparePart(
                    name=name,
                    asset_number=asset_number,
                    ownership=str(row.get('ownership', '')).strip() or None,
                    device_type=str(row.get('device_type', '')).strip() or None,
                    specifications=str(row.get('specifications', '')).strip() or None,
                    manufacturer=str(row.get('manufacturer', '')).strip() or None,
                    product_number=str(row.get('product_number', '')).strip() or None,
                    usage_status=usage_status,
                    storage_location=str(row.get('storage_location', '')).strip() or None,
                    purchase_date=__parse_date_flexible(row.get('purchase_date')),
                    last_inspection_date=__parse_date_flexible(row.get('last_inspection_date')),
                    next_inspection_date=__parse_date_flexible(row.get('next_inspection_date')),
                    warranty_period=int(row['warranty_period']) if pd.notna(row.get('warranty_period')) else None,
                    unit_price=float(row['unit_price']) if pd.notna(row.get('unit_price')) else None,
                    remarks=str(row.get('remarks', '')).strip() or None
                )

                db.session.add(spare_part)
                db.session.flush()  # 获取ID但不提交
                created_parts.append(spare_part)
                existing_asset_numbers.add(asset_number)
                success_count += 1

            except Exception as e:
                failed_rows.append({'row': row_num, 'reason': str(e)})
                continue

        db.session.commit()

        # 为成功导入的备件创建文件夹
        for part in created_parts:
            try:
                create_spare_part_folder(part.asset_number, part.name)
            except Exception as e:
                logging.warning(f'为导入备件创建文件夹失败: {part.asset_number}, {str(e)}')

        return APIResponse.success(data={
            'total': len(df),
            'success': success_count,
            'failed': len(failed_rows),
            'failed_rows': failed_rows
        }, message=f'导入完成：成功 {success_count} 条，失败 {len(failed_rows)} 条')

    except Exception as e:
        db.session.rollback()
        logging.error(f'批量导入备件失败: {str(e)}', exc_info=True)
        return APIResponse.server_error(str(e))
