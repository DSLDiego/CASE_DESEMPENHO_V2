@echo off
CHCP 65001 > nul
cls
:menu
echo =======================================================================
echo          PETROANALYTICS PoC - Benchmark Petrobras vs Pares
echo =======================================================================
echo 1. Pipeline ETL completo + efetivo + painel Web
echo 2. Gerar e servir o painel Web (http://localhost:8080)
echo 3. Refazer ETL: varre o Container e processa SO os arquivos novos
echo 4. Descobrir o que foi anunciado (SEC/RI) e ainda falta no acervo
echo 5. Interface Desktop GUI (PySide6)
echo 6. Status do banco
echo 7. Coleta SEC EDGAR (XBRL, requer internet)
echo 8. Ancoras anuais de efetivo
echo 9. Coleta web RI + Investidor10 (descoberta + snapshot mercado)
echo 10. Exportar slide deck em PDF
echo 11. Enviar benchmark por e-mail (HTML + PNG + CSV)
echo 12. Sair
echo =======================================================================
set /p op="Escolha uma opcao (1-12): "
if "%op%"=="1" ( python "%~dp0app_main.py" full & pause & goto menu )
if "%op%"=="2" ( python "%~dp0app_main.py" web --periodo 2026Q2 --serve & pause & goto menu )
if "%op%"=="3" ( python "%~dp0app_main.py" etl --novos & pause & goto menu )
if "%op%"=="4" ( python "%~dp0app_main.py" descoberta & pause & goto menu )
if "%op%"=="5" ( python "%~dp0app_main.py" gui & pause & goto menu )
if "%op%"=="6" ( python "%~dp0app_main.py" status & pause & goto menu )
if "%op%"=="7" ( python "%~dp0app_main.py" sec & pause & goto menu )
if "%op%"=="8" ( python "%~dp0app_main.py" efetivo & pause & goto menu )
if "%op%"=="9" ( python "%~dp0app_main.py" coleta --site all --mercado & pause & goto menu )
if "%op%"=="10" ( python "%~dp0app_main.py" pdf --periodo 2026Q2 & pause & goto menu )
if "%op%"=="11" ( set /p dest="E-mail do destinatario: " & python "%~dp0app_main.py" email --para %dest% --abrir & pause & goto menu )
if "%op%"=="12" exit
goto menu
