@echo off
chcp 65001 > nul
echo ============================================================
echo 备品备件管理系统 - 打包脚本
echo Author: wyj
echo ============================================================
echo.

echo [1/3] 清理旧的打包文件...
if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"
echo 清理完成！
echo.

echo [2/3] 开始打包程序...
pyinstaller build.spec
echo.

if %errorlevel% neq 0 (
    echo 打包失败！请检查错误信息。
    pause
    exit /b %errorlevel%
)

echo [3/3] 整理打包文件...
set DIST_DIR=dist\备品备件管理系统

:: 确保外部配置文件和说明文档在根目录
copy /y config.ini "%DIST_DIR%\"
copy /y 使用说明.txt "%DIST_DIR%\"

:: 确保 templates 和 static 在根目录（防止 PyInstaller 6+ 将其移动到 _internal）
if not exist "%DIST_DIR%\templates" xcopy /e /i /y "%DIST_DIR%\_internal\templates" "%DIST_DIR%\templates"
if not exist "%DIST_DIR%\static" xcopy /e /i /y "%DIST_DIR%\_internal\static" "%DIST_DIR%\static"

echo 整理完成！
echo.
echo 打包完成！
echo.
echo 可执行文件位置: %DIST_DIR%\备品备件管理系统.exe
echo.
echo ============================================================
echo 提示：将整个 "dist\备品备件管理系统" 文件夹复制到其他电脑即可运行
echo       不要只复制单个 .exe 文件，否则会缺少依赖文件
echo ============================================================
echo.
pause
