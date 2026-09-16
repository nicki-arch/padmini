@echo off
setlocal
cd /d "%~dp0"
title Padmini

rem Padmini - inicia o site no seu computador.
rem Usa o uv (github.com/astral-sh/uv) para ter um Python 3.11 so deste projeto,
rem sem depender do Anaconda. Tudo fica dentro desta pasta (.ferramentas e .venv).

set "UVDIR=%~dp0.ferramentas"
set "UV=%UVDIR%\uv.exe"
set "UV_PYTHON_INSTALL_DIR=%UVDIR%\python"
set "UV_HTTP_TIMEOUT=120"
set "PY=%~dp0.venv\Scripts\python.exe"

if exist "%UV%" goto venv
echo.
echo [1/4] Baixando o uv, o instalador de Python. So na primeira vez...
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $z=Join-Path $env:TEMP 'uv-padmini.zip'; Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' -OutFile $z; Expand-Archive -Path $z -DestinationPath '%UVDIR%' -Force; Remove-Item $z"
if not exist "%UV%" goto erro_uv

:venv
if exist "%PY%" goto dependencias
echo.
echo [2/4] Preparando o Python 3.11 do Padmini. So na primeira vez...
"%UV%" venv --python 3.11 --python-preference only-managed .venv
if errorlevel 1 goto erro_ambiente

:dependencias
"%PY%" -c "import swisseph, timezonefinder, tzdata, fastapi, uvicorn, anthropic" 1>nul 2>nul
if not errorlevel 1 goto chave
echo.
echo [3/4] Instalando as bibliotecas do Padmini...
"%UV%" pip install --python "%PY%" -r requirements.txt
if errorlevel 1 goto erro_pip

:chave
rem Um .env com o texto de exemplo (SUA-CHAVE) ou sem chave valida e refeito.
if exist ".env" findstr /c:"SUA-CHAVE" ".env" 1>nul 2>nul && del ".env" 1>nul 2>nul
if exist ".env" findstr /c:"sk-ant-" ".env" 1>nul 2>nul || del ".env" 1>nul 2>nul
if exist ".env" goto iniciar
echo.
echo Para liberar o texto por IA, cole sua chave da Anthropic e aperte Enter.
echo Para pular, aperte Enter sem digitar nada.
set "CHAVE="
set /p "CHAVE=Chave: "
if not defined CHAVE goto iniciar
> ".env" echo ANTHROPIC_API_KEY=%CHAVE%
echo Chave salva no arquivo .env desta pasta.

:iniciar
echo.
echo [4/4] Site no ar em http://127.0.0.1:8000
echo Para desligar, feche esta janela.
echo.
start "" cmd /c "timeout /t 8 /nobreak >nul && start http://127.0.0.1:8000"
"%PY%" -m uvicorn app:app --host 127.0.0.1 --port 8000
pause
exit /b 0

:erro_uv
echo Nao foi possivel baixar o uv. Copie as mensagens acima e mande para o Claude.
pause
exit /b 1

:erro_ambiente
echo Nao foi possivel preparar o Python. Copie as mensagens acima e mande para o Claude.
pause
exit /b 1

:erro_pip
echo Nao foi possivel instalar as bibliotecas. Copie as mensagens acima e mande para o Claude.
pause
exit /b 1
