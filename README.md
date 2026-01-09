# 备品备件管理系统

一个基于Flask的现代化备品备件管理系统，提供完整的设备管理、检定追踪、记录管理和数据导出功能。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![Flask](https://img.shields.io/badge/flask-3.0.0-lightgrey.svg)

## ✨ 核心功能

### 📦 备件管理
- **完整信息记录**：资产编号、设备类型、规格型号、存放地点等
- **状态跟踪**：在库、在用、维修中、报废等状态管理
- **智能搜索**：支持关键字、系统归属、设备类型等多维度筛选
- **批量导出**：一键导出备件列表及所有关联记录

### 🔍 检定管理
- **自动提醒**：根据检定日期智能提醒待检设备
- **状态分级**：已过期、紧急(3个月内)、预警(3-6个月)、正常
- **周期管理**：自动计算下次检定日期
- **计划导出**：生成年度计量工作计划和器具明细表

### 📝 记录管理
- **入库记录**：供应商、批次号、入库数量等信息
- **出库记录**：领用人、用途、预计归还日期
- **维护记录**：维护类型、内容、费用，自动同步检定信息
- **故障记录**：故障描述、维修状态、维修费用追踪

### 📄 文件管理
- **附件上传**：支持图片、PDF、Word、Excel等多种格式
- **历史文档**：独立的文档管理，不绑定特定设备
- **文件预览**：在线查看图片和PDF文档
- **分类存储**：自动识别文件类型并分类

### 💾 数据备份
- **自动备份**：可配置定时自动备份（默认每天凌晨2点）
- **手动备份**：支持随时手动执行备份
- **双重保护**：数据库文件备份 + Excel数据导出
- **备份管理**：查看、下载、删除历史备份文件

### 📊 数据导出
- **Excel导出**：多Sheet格式，包含备件、入库、出库、维护、故障所有数据
- **计量计划**：生成符合要求的年度计量工作计划表
- **器具明细**：导出计量器具明细表，自动计算检定周期
- **格式规范**：导出文件格式清晰，列宽自动调整

## 🚀 快速开始

### 环境要求
- Python 3.8+
- Windows / Linux / macOS

### 安装步骤

1. **克隆项目**
```bash
git clone <repository_url>
cd Project3
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **运行程序**
```bash
python app.py
```

4. **访问系统**
- 浏览器自动打开，或手动访问：http://127.0.0.1:5000
- 默认账号：`admin`
- 默认密码：`admin`

### 打包为可执行文件

```bash
# Windows
build.bat

# 或手动执行
pyinstaller build.spec
```

生成的exe文件位于 `dist/备品备件管理系统.exe`

## 📁 项目结构

```
Project3/
├── app.py                          # 主程序入口
├── db_migration.py                 # 数据库迁移工具
├── requirements.txt                # Python依赖
├── build.spec                      # PyInstaller配置
├── build.bat                       # Windows打包脚本
│
├── templates/                      # HTML模板
│   ├── base.html                  # 基础模板
│   ├── login.html                 # 登录页面
│   ├── index.html                 # 备件列表
│   ├── create.html                # 创建备件
│   ├── detail.html                # 备件详情
│   ├── backup.html                # 备份管理
│   └── historical_documents.html  # 历史文件
│
├── static/                         # 静态资源
│   ├── css/                       # 样式文件（Bootstrap）
│   ├── js/                        # JavaScript（jQuery, Bootstrap）
│   └── fonts/                     # 字体文件（Bootstrap Icons）
│
├── data/                           # 数据目录（自动创建）
│   └── spare_parts.db             # SQLite数据库
│
├── uploads/                        # 上传文件目录（自动创建）
├── backups/                        # 备份目录（自动创建）
├── logs/                           # 日志目录（自动创建）
└── db_backups/                     # 数据库备份（自动创建）
```

## 🛠️ 技术栈

### 后端
- **Flask 3.0.0** - Web框架
- **Flask-SQLAlchemy 3.1.1** - ORM
- **SQLite** - 数据库
- **APScheduler 3.10.4** - 定时任务调度
- **pandas 2.1.4** - 数据处理
- **openpyxl 3.1.2** - Excel文件操作

### 前端
- **Bootstrap 5** - UI框架
- **jQuery 3.6.0** - JavaScript库
- **Bootstrap Icons** - 图标库

### 打包
- **PyInstaller 6.3.0** - Python打包工具
- **pystray 0.19.5** - 系统托盘（可选）

## 💡 使用说明

### 1. 创建备件
1. 点击导航栏"创建备件"
2. 填写必填项：名称、资产编号
3. 选填项：设备类型、检定日期、存放地点等
4. 点击"创建"保存

### 2. 管理记录
1. 在备件列表点击"查看详情"
2. 切换不同标签页：入库、出库、维护、故障
3. 点击"新建"按钮添加记录
4. 维护记录会自动同步检定信息到备件

### 3. 文件上传
1. 在备件详情页切换到"附件"标签
2. 点击"上传文件"选择文件
3. 支持图片、PDF、Office文档等
4. 单文件最大100MB

### 4. 数据导出
- **导出备件列表**：首页点击"导出Excel"，包含所有关联记录
- **计量工作计划**：首页点击"制作计量工作计划"
- **计量器具明细**：首页点击"计量器具明细表"
- **历史文件**：导航栏"历史文件"页面管理独立文档

### 5. 数据备份
1. 导航栏点击"数据备份"
2. 配置自动备份时间和保留天数
3. 点击"立即备份"手动执行备份
4. 查看、下载或删除历史备份

## 🔧 配置说明

### 备份配置
备份配置文件：`backup_config.json`（自动生成）

```json
{
  "auto_backup_enabled": true,      // 启用自动备份
  "backup_time": "02:00",           // 备份时间（24小时制）
  "keep_days": 30,                   // 保留天数
  "backup_type": "both"              // 备份类型：database/excel/both
}
```

### 修改默认密码
编辑 `app.py`，修改以下配置：

```python
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'admin'
```

### 数据库位置
- 开发环境：`./data/spare_parts.db`
- 打包后：`{exe目录}/data/spare_parts.db`

## 📊 数据库表结构

- **spare_parts** - 备件主表
- **inbound_records** - 入库记录
- **outbound_records** - 出库记录
- **maintenance_records** - 维护记录
- **fault_records** - 故障记录
- **attachments** - 附件表
- **historical_documents** - 历史文件
- **db_version** - 数据库版本管理

详细字段说明请参考 `app.py` 中的数据模型定义。

## 🔄 更新升级

### 保留数据更新

1. **关闭旧版本程序**
2. **保留以下目录**（重要！）：
   - `data/` - 数据库文件
   - `uploads/` - 上传的文件
   - `backups/` - 备份文件（可选）
3. **替换新版本程序**
4. **启动程序** - 自动检测并升级数据库

详细说明请查看 [DATABASE_UPDATE.md](DATABASE_UPDATE.md)

## ⚠️ 注意事项

1. **首次运行**：程序会自动创建数据库和必要的目录
2. **端口占用**：默认使用5000端口，如被占用请修改代码
3. **文件大小**：单个上传文件限制100MB
4. **浏览器兼容**：推荐使用Chrome、Edge、Firefox等现代浏览器
5. **数据备份**：建议定期备份数据，保留天数根据需求调整

## 🐛 故障排查

### 程序无法启动
- 检查Python版本（需要3.8+）
- 检查依赖是否完整安装：`pip install -r requirements.txt`
- 查看日志文件：`logs/spare_parts.log`

### 数据库错误
- 检查 `data/` 目录是否有写权限
- 尝试从 `db_backups/` 恢复备份
- 查看控制台错误信息

### 文件上传失败
- 检查 `uploads/` 目录是否存在
- 确认文件大小未超过100MB
- 检查文件类型是否在允许列表中

## 📝 更新日志

### v1.0.0 (2024)
- ✅ 完整的备件管理功能
- ✅ 入库、出库、维护、故障记录
- ✅ 检定日期追踪和提醒
- ✅ 文件附件管理
- ✅ 数据导出（Excel多Sheet）
- ✅ 定时自动备份
- ✅ 计量工作计划导出
- ✅ 计量器具明细表导出
- ✅ 用户登录认证
- ✅ 数据库版本管理
- ✅ 系统托盘支持

## 📄 许可证

MIT License

Copyright (c) 2024 wyj

详见 [LICENSE](LICENSE) 文件

## 👨‍💻 作者

**wyj**
- Email: 1796085559@qq.com
- License: MIT

## 🙏 致谢

- [Flask](https://flask.palletsprojects.com/) - 优秀的Python Web框架
- [Bootstrap](https://getbootstrap.com/) - 强大的前端UI框架
- [jQuery](https://jquery.com/) - 简化JavaScript开发
- [pandas](https://pandas.pydata.org/) - 数据处理利器

---

**如有问题或建议，欢迎提交Issue或Pull Request！**
