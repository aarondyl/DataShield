@echo off
chcp 65001 >nul
title 数盾 DataShield
cd /d "%~dp0"

REM ================= 数盾 DataShield 一键启动 =================
REM 双击本文件即可启动应用，浏览器会自动打开页面。
REM 关闭本黑色窗口即可停止应用。

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10 或更高版本。
    pause
    exit /b 1
)

REM 首次运行自动安装依赖（已安装则跳过）
python -c "import streamlit" >nul 2>nul
if errorlevel 1 (
    echo 首次运行，正在安装依赖（清华镜像）...
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络后重试。
        pause
        exit /b 1
    )
)

echo.
echo  正在启动 数盾 DataShield ...
echo  浏览器将自动打开 http://localhost:8501
echo  关闭本窗口即可停止应用。
echo.
python -m streamlit run app.py
pause
