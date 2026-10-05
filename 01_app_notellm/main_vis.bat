@echo off
CHCP 65001 > nul
cls
:menu
echo =======================================================================
echo          PETROANALYTICS PoC - Benchmark Petrobras vs Pares
echo =======================================================================
echo 1. Pipeline ETL completo + efetivo + painel Web
echo 2. Gerar e servir o painel Web (http://localhost:8080)
echo 3. Interface Desktop GUI (PySide6)
echo 4. Status do banco
echo 5. Coleta SEC EDGAR (XBRL, requer internet)
echo 6. Ancoras anuais de efetivo
echo 7. Coleta web RI + Investidor10 (descoberta + snapshot mercado)
echo 8. Exportar slide deck em PDF
echo 9. Enviar benchmark por e-mail (HTML + PNG + CSV)
echo 10. Sair
echo =======================================================================
set /p op="Escolha uma opcao (1-10): "
if "%op%"=="1" ( python "%~dp0app_main.py" full & pause & goto menu )
if "%op%"=="2" ( python "%~dp0app_main.py" web --periodo 2026Q2 --serve & pause & goto menu )
if "%op%"=="3" ( python "%~dp0app_main.py" gui & pause & goto menu )
if "%op%"=="4" ( python "%~dp0app_main.py" status & pause & goto menu )
if "%op%"=="5" ( python "%~dp0app_main.py" sec & pause & goto menu )
if "%op%"=="6" ( python "%~dp0app_main.py" efetivo & pause & goto menu )
if "%op%"=="7" ( python "%~dp0app_main.py" coleta --site all --mercado & pause & goto menu )
if "%op%"=="8" ( python "%~dp0app_main.py" pdf --periodo 2026Q2 & pause & goto menu )
if "%op%"=="9" ( set /p dest="E-mail do destinatario: " & python "%~dp0app_main.py" email --para %dest% --abrir & pause & goto menu )
if "%op%"=="10" exit
goto menu
