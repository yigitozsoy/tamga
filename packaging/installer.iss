; tamga — Inno Setup 6 kurulum betiği (tamga ailesi)
; Doğrudan değil, packaging\build.ps1 üzerinden derleyin (önce PyInstaller çıktısı ve version.iss gerekir).
; Yönetici izni istemez: varsayılan olarak %LOCALAPPDATA%\Programs\tamga klasörüne kurulur.
; tamga'nın kendi verisi (%LOCALAPPDATA%\tamga) kaldırmada SİLİNMEZ; ailenin uygulamalarına dokunulmaz.

#include "version.iss"
#define AppName "tamga"
#define AppExe "tamga.exe"
#define AppUserModelID "tamga.launcher"

[Setup]
; AppId sonraki sürümlerde aynı kalmalı (yerinde güncelleme). DEĞİŞTİRME.
AppId={{FB53E9DE-E7AE-4660-8910-541D2D3F23BF}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=tamga
AppPublisherURL=https://github.com/yigitozsoy/tamga
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UsePreviousAppDir=no
UsePreviousGroup=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\build\installer
OutputBaseFilename=tamga-setup-{#AppVersion}
SetupIconFile=..\tamga\assets\logo.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} {#AppVersion}
VersionInfoDescription={#AppName} kurulumu
VersionInfoProductName={#AppName}
VersionInfoVersion={#AppVersion}
; Lisans sayfası yok; LICENSE.txt (GPL-3.0) kurulum klasörüne konur.
Compression=lzma2/ultra64
SolidCompression=yes
; Görünüm (Inno Setup 6.7+, ailenin diğer kurulumlarıyla aynı): Windows 11 stili, Windows'un açık/koyu temasını izler, ayırıcı çizgi yok.
; Renkler ailenin temalarıyla aynı (koyu: siyah, açık: beyaz); görseller make_meta.py'de üretilir.
WizardStyle=modern dynamic windows11 hidebevels
WizardBackColor=#ffffff
WizardBackColorDynamicDark=#0f0f0f
WizardImageBackColor=#ffffff
WizardImageBackColorDynamicDark=#0f0f0f
WizardSmallImageBackColor=#ffffff
WizardSmallImageBackColorDynamicDark=#0f0f0f
WizardSmallImageFile={#WizSmall}
WizardSmallImageFileDynamicDark={#WizSmallDark}
WizardImageFile={#WizLarge}
WizardImageFileDynamicDark={#WizLargeDark}
; Güncellemede açık tamga kapatılsın
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\build\dist\tamga\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; eski sürümden kalan PyInstaller dosyaları karışmasın
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "{#AppUserModelID}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "{#AppUserModelID}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; tamga kendini güncelleyince (/SILENT /relaunch=1) kurulum bitince yeniden açılsın
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: Relaunch

[Code]
function Relaunch: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:relaunch|0}') = '1');
end;
