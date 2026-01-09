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

echo [3/3] 打包完成！
echo.
echo 可执行文件位置: dist\备品备件管理系统\备品备件管理系统.exe
echo.
echo ============================================================
echo 提示：程序运行时会自动打开浏览器
echo       关闭方式：右键点击系统托盘图标选择退出
echo ============================================================
echo.
pause
