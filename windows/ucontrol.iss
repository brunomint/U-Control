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
; PowerPoint -> slides precisa do LibreOffice (blueprints/gallery.py). Não
; vem dentro do instalador: seriam +350 MB em cada atualização. Baixa o
; oficial na hora (versão e SHA-256 fixos em [Code]); some se já houver um.
Name: "libreoffice"; Description: "Converter PowerPoint em slides (baixa e instala o LibreOffice, ~360 MB)"; GroupDescription: "Opcional:"; Check: not LibreOfficeInstalled

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
const
  // Atualizar: versão "still" de https://download.documentfoundation.org/libreoffice/stable/
  // e o SHA-256 do .mirrorlist do mesmo arquivo
  LO_URL = 'https://download.documentfoundation.org/libreoffice/stable/26.2.6/win/x86_64/LibreOffice_26.2.6_Win_x86-64.msi';
  LO_SHA256 = 'f9877032fd908beb9c0ddf06df4af5c2e85f419c42e14876c4cce5aae5fb2660';

var
  DownloadPage: TDownloadWizardPage;
  LibreOfficeBaixado: Boolean;

function RelaunchRequested: Boolean;
begin
  Result := Pos('/RELAUNCH', UpperCase(GetCmdTail)) > 0;
end;

function LibreOfficeInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{commonpf64}\LibreOffice\program\soffice.exe'))
    or FileExists(ExpandConstant('{commonpf32}\LibreOffice\program\soffice.exe'));
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage('Baixando o LibreOffice', 'Para converter PowerPoint em slides. Pode levar alguns minutos.', nil);
end;

// Baixa antes de copiar os arquivos (vale também no modo silencioso). Falhar
// aqui nunca impede de instalar o U-Control: só fica sem converter PowerPoint.
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not WizardIsTaskSelected('libreoffice') then
    Exit;
  DownloadPage.Clear;
  DownloadPage.Add(LO_URL, 'LibreOffice.msi', LO_SHA256);
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
      LibreOfficeBaixado := True;
    except
      Log('LibreOffice: download falhou: ' + GetExceptionMessage);
      if not DownloadPage.AbortedByUser then
        SuppressibleMsgBox('Não deu para baixar o LibreOffice (' + GetExceptionMessage + ').' + #13#10 +
          'O U-Control será instalado mesmo assim; para converter PowerPoint depois, rode este instalador de novo ou instale o LibreOffice.',
          mbError, MB_OK, IDOK);
    end;
  finally
    DownloadPage.Hide;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if (CurStep <> ssPostInstall) or not LibreOfficeBaixado then
    Exit;
  WizardForm.StatusLabel.Caption := 'Instalando o LibreOffice (pode levar alguns minutos)...';
  // REGISTER_NO_MSO_TYPES: não vira o programa padrão de .pptx/.docx de
  // quem já usa o Office
  if not Exec(ExpandConstant('{sys}\msiexec.exe'),
      '/i "' + ExpandConstant('{tmp}\LibreOffice.msi') + '" /qn /norestart REGISTER_NO_MSO_TYPES=1 CREATEDESKTOPLINK=0 ISCHECKFORPRODUCTUPDATES=0 RebootYesNo=No',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or ((ResultCode <> 0) and (ResultCode <> 3010)) then
  begin
    Log(Format('LibreOffice: msiexec terminou com %d', [ResultCode]));
    SuppressibleMsgBox(Format('O LibreOffice não foi instalado (código %d). O U-Control funciona normalmente; só a conversão de PowerPoint fica de fora.', [ResultCode]),
      mbError, MB_OK, IDOK);
  end;
end;
