# 备品备件管理系统

一个基于 Flask 和 Bootstrap 的现代化备品备件管理系统，用于设备资产的全生命周期管理。

**Author:** wyj  
**License:** MIT License

---

## ✨ 功能特性

### 核心功能
- 📦 **备件管理**：完整的备件信息录入、编辑、查询和删除功能
- 🏷️ **归属分类**：支持自观系统、信息系统、观测场三类归属管理
- 📊 **状态跟踪**：实时监控备件的使用状态（在库、在用、维修中、报废）
- ⏰ **检定管理**：智能检定日期提醒，带进度条可视化显示
- 📝 **记录管理**：入库、出库、故障维修记录的完整追溯
- 🔍 **高级搜索**：支持关键字、状态、地点等多维度筛选
- 📤 **数据导出**：一键导出 Excel 报表，便于数据分析

### 特色亮点
- ✅ 渐变色彩设计，界面明艳舒适
- ✅ 动效交互，提升用户体验
- ✅ 绿色进度条展示检定倒计时，状态一目了然
- ✅ 待检定备件列表，按日期自动排序
- ✅ 响应式设计，支持各种屏幕尺寸
- ✅ 操作者下拉选择，保证数据一致性
- ✅ 支持打包成可执行程序，无需 Python 环境

---

## 🛠️ 技术栈

- **后端框架**：Flask 3.0.0
- **ORM 框架**：Flask-SQLAlchemy 3.1.1
- **数据库**：SQLite
- **前端框架**：Bootstrap 5.1.3
- **UI 图标**：Bootstrap Icons
- **JavaScript**：jQuery 3.6.0
- **数据导出**：pandas 2.1.4 + openpyxl 3.1.2
- **打包工具**：PyInstaller

---

## 📦 快速开始

### 环境要求
- Python 3.7+
- pip 包管理工具

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd Project3
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **启动服务**
```bash
python app.py
```

4. **访问系统**
```
浏览器访问：http://127.0.0.1:5000
```

### 测试数据
运行测试脚本生成示例数据：
```bash
python test_data.py
```

---

## 📦 打包可执行程序

### 一键打包
双击运行 `一键打包.bat`，等待打包完成后，可执行文件位于 `dist\备品备件管理系统\` 目录。

### 打包后部署
1. 将 `dist\备品备件管理系统` 整个文件夹复制到目标电脑
2. 双击 `备品备件管理系统.exe` 启动
3. 浏览器自动打开管理界面

**打包后特点：**
- ✅ 无需安装 Python 环境
- ✅ 无需网络连接
- ✅ 支持离线运行
- ✅ 数据本地存储

---

## 📖 使用指南

### 1. 创建备件
- 点击导航栏「创建备件」
- 填写备件基本信息（名称、编号、归属等）
- 设置检定日期（可选）
- 点击「创建备件」保存

### 2. 编辑备件
- 在备件列表点击「编辑」按钮
- 修改任意字段（所有信息均可编辑）
- 点击「保存」更新信息

### 3. 查看详情
- 点击备件列表的「查看详情」按钮
- 查看完整的备件信息
- 管理入库、出库、故障记录
- 导出记录为 Excel 文件

### 4. 待检定管理
- 点击主页「待检定备件」按钮
- 查看所有需要检定的设备
- 按日期从近到远自动排序
- 快速定位即将到期的设备

### 5. 数据导出
- 使用筛选条件定位目标数据
- 点击「导出 Excel」按钮
- 自动生成带时间戳的 Excel 文件

---

## 📊 数据库结构

### 主要数据表

#### 1. spare_parts（备件主表）
- 基本信息：名称、资产编号、归属、产品编号
- 规格信息：规格型号、生产厂家
- 状态信息：使用状态、存放地点
- 日期信息：采购日期、上次/下次检定日期
- 财务信息：单价、质保期

#### 2. inbound_records（入库记录）
- 操作者、入库时间、备注

#### 3. outbound_records（出库记录）
- 操作者、出库时间、备注

#### 4. fault_records（故障记录）
- 操作者、故障描述、故障类型
- 维修状态、维修日期、维修费用

---

## 🎨 界面设计

系统采用明艳的渐变色彩方案：
- 主色调：紫蓝渐变（#667eea → #764ba2）
- 成功色：青绿渐变（#11998e → #38ef7d）
- 警告色：橙黄渐变（#f39c12 → #e67e22）
- 危险色：红粉渐变（#eb3349 → #f45c43）

所有按钮、卡片、表格均有悬停动效，提升交互体验。

---

## 📁 项目结构

```
Project3/
├── app.py                 # Flask 应用主文件
├── requirements.txt       # 依赖包列表
├── test_data.py          # 测试数据生成脚本
├── build_exe.spec        # PyInstaller 打包配置
├── 一键打包.bat           # 一键打包脚本
├── LICENSE               # MIT 许可证
├── README.md             # 项目文档
├── templates/            # HTML 模板目录
│   ├── base.html        # 基础模板（包含样式）
│   ├── index.html       # 主页（备件列表）
│   ├── create.html      # 创建备件页面
│   └── detail.html      # 备件详情页面
├── static/              # 静态资源目录
│   ├── css/            # 样式文件
│   │   ├── bootstrap.min.css
│   │   └── bootstrap-icons.css
│   └── js/             # JavaScript 文件
│       ├── bootstrap.bundle.min.js
│       └── jquery-3.6.0.min.js
└── instance/            # 数据库目录
    └── spare_parts.db   # SQLite 数据库
```

---

## 🔧 配置说明

### 归属分类
系统预设三个归属类别：
- 自观系统
- 信息系统
- 观测场

### 操作者列表
系统预设操作者：
- 陈凯
- 严峻
- 王丽华
- 艾丹妮
- 吴宜骏
- 张伟

如需修改，请编辑对应模板文件中的下拉选项。

---

## 📄 许可证

**MIT License**

Copyright (c) 2026 wyj

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

**Built with ❤️ using Flask & Bootstrap**
