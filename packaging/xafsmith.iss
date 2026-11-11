; Inno Setup 6 脚本：把 PyInstaller 的 dist\XAFSmith 打成 Windows 安装程序（无需管理员权限，装到当前用户）
; 构建：iscc /DAppVersion=1.0.0 packaging\xafsmith.iss        输出：dist\XAFSmith-<版本>-Setup.exe
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8D3B6C9E-5A47-4E0B-9C1F-7A2E4D6B1C30}
AppName=XAFSmith
AppVersion={#AppVersion}
AppVerName=XAFSmith {#AppVersion}
AppPublisher=Eggy & Claude
AppPublisherURL=https://github.com/Wiolic/XAFSmith
AppSupportURL=https://github.com/Wiolic/XAFSmith/issues
AppUpdatesURL=https://github.com/Wiolic/XAFSmith/releases
AppCopyright=Copyright (C) 2026 Eggy & Claude. PolyForm Noncommercial License 1.0.0
; 安装程序文件属性（资源管理器 → 属性 → 详细信息）
VersionInfoVersion={#AppVersion}
VersionInfoProductName=XAFSmith
VersionInfoProductVersion={#AppVersion}
VersionInfoCompany=Eggy & Claude
VersionInfoDescription=XAFSmith Setup - XAFS processing and fitting software
VersionInfoCopyright=Copyright (C) 2026 Eggy & Claude
DefaultDirName={autopf}\XAFSmith
DefaultGroupName=XAFSmith
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=XAFSmith-{#AppVersion}-Setup
SetupIconFile=..\src\xafsmith\assets\xafsmith.ico
UninstallDisplayIcon={app}\XAFSmith.exe
Compression=lzma2/ultra64
LZMAUseSeparateProcess=yes
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; 欢迎页与完成页：署名、许可、免责声明、引用（文字与 src/xafsmith/about.py 一致）。Inno 6 无官方简体中文语言文件，界面保持英文，这里中英双语。
[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%nDeveloped by Eggy & Claude Opus 5.5 (Anthropic).%nLicense: PolyForm Noncommercial 1.0.0 (noncommercial use only).%n%nXAFSmith is provided "as is", without warranty of any kind. Please validate your results, e.g. against Athena / Artemis.%n%n本软件由 Eggy 与 Claude Opus 5.5（Anthropic）开发，仅限非商业用途。软件按“现状”提供，不附带任何保证，请自行核验结果。
FinishedLabel=Setup has finished installing [name] on your computer.%n%nA demo project built from public data is in the "examples\demo_project" folder of the installation; copy it to your own folder before opening it.%n%nIf you use XAFSmith in a publication, please cite it (and Larch and FEFF): Eggy & Claude. XAFSmith, version {#AppVersion}. https://github.com/Wiolic/XAFSmith%n%n论文中使用请引用本软件及 Larch、FEFF。

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\XAFSmith\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs
; 公开数据演示项目（只读示例；使用前请复制到自己的文件夹再打开）。不含 output/ notes/ models/ structures/（可重新生成）
Source: "..\tests\data\demo_project\*"; DestDir: "{app}\examples\demo_project"; Excludes: "output\*,notes\*,models\*,structures\*"; Flags: recursesubdirs ignoreversion createallsubdirs

[Icons]
Name: "{group}\XAFSmith"; Filename: "{app}\XAFSmith.exe"
Name: "{group}\Uninstall XAFSmith"; Filename: "{uninstallexe}"
Name: "{autodesktop}\XAFSmith"; Filename: "{app}\XAFSmith.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\XAFSmith.exe"; Description: "{cm:LaunchProgram,XAFSmith}"; Flags: nowait postinstall skipifsilent
