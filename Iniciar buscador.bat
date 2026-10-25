@echo off
setlocal
title Buscador de Pendones - mantener esta ventana abierta
pushd "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto python_command
py -3 "%~dp0abrir_buscador.py"
goto finished
:python_command
python "%~dp0abrir_buscador.py"
:finished
if errorlevel 1 (
  echo.
  echo No se pudo iniciar el buscador. Envia una captura del error sin mostrar el ticket.
  pause
)
popd
endlocal
