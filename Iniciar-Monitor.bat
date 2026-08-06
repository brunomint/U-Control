@echo off
REM ============================================================
REM  U-Control - Iniciar Monitor (Telao)
REM  Abre o Chrome em modo app, com autoplay liberado (audio+video)
REM ============================================================

REM >>> CONFIGURE AQUI O IP DO RASPBERRY PI NA REDE <<<
set SERVER_IP=192.168.1.10
set SERVER_PORT=8585

REM Tenta encontrar o Chrome em locais padroes do Windows
set CHROME=
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe

if "%CHROME%"=="" (
    echo Chrome nao encontrado. Instale o Google Chrome.
    pause
    exit /b 1
)

REM Abre em modo app, tela cheia, com autoplay liberado
start "" "%CHROME%" --autoplay-policy=no-user-gesture-required --app=http://%SERVER_IP%:%SERVER_PORT%/img --start-fullscreen --disable-features=TranslateUI
