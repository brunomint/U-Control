; Instalador do U-Control pra Windows (Inno Setup 6). Monta a partir de
; dist\U-Control\ (PyInstaller, ucontrol.spec) e windows\bin\ (ffmpeg).
; Roda no GitHub Actions: iscc /DAppVersion=1.2.3 windows\ucontrol.iss
;
; Os dados (banco, fotos, áudios) ficam em %APPDATA%\U-Control (ver
; paths.py/desktop.py), fora da pasta do programa: instalar uma versão
; nova por cima ou desinstalar não mexe neles.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; AppId fixo: é por ele que o Windows reconhece a atualização como o mesmo programa
AppId={{DDA62849-38AF-4250-A8E0-5F67EA74144B}
AppName=U-Control
AppVersion={#AppVersion}
AppVerName=U-Control {#AppVersion}
AppPublisher=U-Control
DefaultDirName={autopf}\U-Control
DefaultGroupName=U-Control
DisableProgramGroupPage=yes
; Administrador: a regra do firewall (celulares da rede acessarem) exige
PrivilegesRequired=admin
OutputDir=..\dist
OutputBaseFilename=U-Control-Setup-{#AppVersion}
SetupIconFile=..\static\U-Control-ico.ico
UninstallDisplayIcon={app}\U-Control.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Atualização com o programa aberto: fecha ele antes de trocar os arquivos
CloseApplications=force
RestartApplications=no

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar ícone na área de trabalho"; GroupDescription: "Atalhos:"
Name: "startup"; Description: "Abrir o U-Control junto com o Windows"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "..\dist\U-Control\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "bin\*"; DestDir: "{app}\bin"; Flags: ignoreversion recursesubdirs

[InstallDelete]
; Versão nova pode ter removido arquivos — não deixa sobra da anterior
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\U-Control"; Filename: "{app}\U-Control.exe"
Name: "{group}\Desinstalar U-Control"; Filename: "{uninstallexe}"
Name: "{autodesktop}\U-Control"; Filename: "{app}\U-Control.exe"; Tasks: desktopicon
Name: "{userstartup}\U-Control"; Filename: "{app}\U-Control.exe"; Tasks: startup

[Run]
; Libera a porta pros celulares/PCs da rede (perfil any: rede da igreja
; costuma ficar como "Pública" no Windows). Apaga antes pra não duplicar.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""U-Control"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""U-Control"" dir=in action=allow program=""{app}\U-Control.exe"" enable=yes profile=any"; Flags: runhidden
Filename: "{app}\U-Control.exe"; Description: "Abrir o U-Control agora"; Flags: nowait postinstall skipifsilent
; Atualização pelo próprio programa (updates.py roda o Setup com /SILENT
; /RELAUNCH): abre de novo sozinho. Como o usuário, não como admin — os
; dados ficam no %APPDATA% de quem usa.
Filename: "{app}\U-Control.exe"; Flags: nowait runasoriginaluser; Check: RelaunchRequested

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""U-Control"""; Flags: runhidden; RunOnceId: "FirewallRule"

[Code]
function RelaunchRequested: Boolean;
begin
  Result := Pos('/RELAUNCH', UpperCase(GetCmdTail)) > 0;
end;
