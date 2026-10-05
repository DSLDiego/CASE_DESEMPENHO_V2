@echo off
REM main_vis.bat — menu dos visualizadores: 1=web (Plotly) 2=GUI (PySide6)
cd /d "%~dp0"
:menu
echo ================================
echo  Visualizadores do Benchmark
echo ================================
echo  1 - Web  (Plotly, http://localhost:8000)
echo  2 - GUI  (PySide6)
echo  0 - Sair
set "op="
set /p op="Escolha: "
if not defined op exit /b 0
set "op=%op: =%"
if "%op%"=="1" goto web
if "%op%"=="2" goto gui
if "%op%"=="0" exit /b 0
echo Opcao invalida.
goto menu
:web
echo Iniciando visualizador WEB ...
start "Benchmark-Web" python app_web.py --port 8000
goto menu
:gui
echo Abrindo visualizador GUI ...
python app_main.py
goto menu
