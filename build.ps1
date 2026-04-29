# 备品备件管理系统 - PowerShell 打包脚本
# Author: wyj

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "备品备件管理系统 - 打包脚本" -ForegroundColor Cyan
Write-Host "Author: wyj" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# [1/3] 清理旧的打包文件
Write-Host "[1/3] 清理旧的打包文件..." -ForegroundColor Yellow
if (Test-Path "dist") {
    Remove-Item -Path "dist" -Recurse -Force
}
if (Test-Path "build") {
    Remove-Item -Path "build" -Recurse -Force
}
Write-Host "清理完成！" -ForegroundColor Green
Write-Host ""

# [2/3] 开始打包程序
Write-Host "[2/3] 开始打包程序..." -ForegroundColor Yellow
pyinstaller build.spec
if ($LASTEXITCODE -ne 0) {
    Write-Host "打包失败！请检查错误信息。" -ForegroundColor Red
    Read-Host "按 Enter 键退出"
    exit $LASTEXITCODE
}
Write-Host ""

# [3/3] 整理打包文件
Write-Host "[3/3] 整理打包文件..." -ForegroundColor Yellow
$DistDir = "dist\备品备件管理系统"

# 确保外部配置文件和说明文档在根目录
Copy-Item -Path "config.ini" -Destination "$DistDir\" -Force
Copy-Item -Path "使用说明.txt" -Destination "$DistDir\" -Force

# 确保 templates 和 static 在根目录（防止 PyInstaller 6+ 将其移动到 _internal）
$InternalTemplates = "$DistDir\_internal\templates"
$InternalStatic = "$DistDir\_internal\static"
$RootTemplates = "$DistDir\templates"
$RootStatic = "$DistDir\static"

if ((Test-Path $InternalTemplates) -and -not (Test-Path $RootTemplates)) {
    Copy-Item -Path $InternalTemplates -Destination $RootTemplates -Recurse -Force
}
if ((Test-Path $InternalStatic) -and -not (Test-Path $RootStatic)) {
    Copy-Item -Path $InternalStatic -Destination $RootStatic -Recurse -Force
}

Write-Host "整理完成！" -ForegroundColor Green
Write-Host ""

Write-Host "打包完成！" -ForegroundColor Green
Write-Host ""
Write-Host "可执行文件位置: $DistDir\备品备件管理系统.exe" -ForegroundColor Cyan
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "提示：将整个 `"dist\备品备件管理系统`" 文件夹复制到其他电脑即可运行" -ForegroundColor Cyan
Write-Host "      不要只复制单个 .exe 文件，否则会缺少依赖文件" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "按 Enter 键退出"
