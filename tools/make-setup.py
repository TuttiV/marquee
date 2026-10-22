#!/usr/bin/env python3
"""Build the Windows Setup wizard: "Syncplay Marquee Setup.exe".

A normal Windows installer (NSIS with the Modern UI): Welcome, then the install folder, then the shortcuts (Start menu
and desktop, each on its own), then installing, then Finish with "Start Syncplay Marquee now". It installs just for the
person running it (by default in %LOCALAPPDATA%\\Programs\\Syncplay Marquee, like most apps that update themselves), so it
never needs administrator rights and the app's own updates can write to its folder. It adds an uninstaller and an entry
under Settings > Apps, and tidies away the copy that the older single-file .exe unpacked.

The installed folder holds the same pieces the single-file .exe unpacks (a private Python runtime, the app) plus the
same launcher, built without anything packed into it: it then simply starts the app in its own folder.

Usage:
    python tools/make-setup.py --build N [--defaults path/to/syncplay-defaults.json] [--out dist]

Needs what tools/make-exe.py needs, plus NSIS 3 (apt install nsis) and ImageMagick (for the wizard artwork).
Downloads are shared with make-exe.py in <out>/cache."""
import argparse
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = "Syncplay Marquee"
EXE = "Syncplay Marquee.exe"
UNINSTALLER = "Uninstall Syncplay Marquee.exe"           # syncplay/install.py SETUP_UNINSTALLER
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SyncplayMarquee"  # install.SETUP_UNINSTALL_KEY
APP_KEY = r"Software\Syncplay Marquee"                    # install.REG_KEY (the launcher reads InstallDir from it too)
LINK_KEY = r"Software\Classes\syncplay-marquee"           # Invite links (syncplay/invite.py)
SETTINGS_FILES = ("syncplay-secrets.json", "syncplay.ini", ".syncplay", "instance.json", "invite-inbox.txt",
                  "resume-positions.json")                # install.SETTINGS_FILES, in %APPDATA%


def loadMakeExe():
    spec = importlib.util.spec_from_file_location("make_exe", os.path.join(ROOT, "tools", "make-exe.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def artwork(work):
    """The wizard's pictures: a tall dark panel with the logo for the Welcome and Finish pages, and a small logo for the
    header of the other pages. NSIS wants 24-bit BMP files."""
    logo = os.path.join(ROOT, "syncplay", "resources", "syncplay.png")
    side = os.path.join(work, "wizard-side.bmp")
    header = os.path.join(work, "wizard-header.bmp")
    subprocess.run(["convert", "-size", "164x314", "gradient:#262a36-#14161c",
                    "(", logo, "-resize", "84x84", ")", "-gravity", "north", "-geometry", "+0+56", "-composite",
                    "-fill", "#2b62d6", "-draw", "rectangle 0,310 164,314",
                    "-type", "TrueColor", "BMP3:" + side], check=True)
    subprocess.run(["convert", "-size", "150x57", "xc:#ffffff",
                    "(", logo, "-resize", "40x40", ")", "-gravity", "east", "-geometry", "+10+0", "-composite",
                    "-type", "TrueColor", "BMP3:" + header], check=True)
    return side, header


SCRIPT = r'''
Target amd64-unicode   ; A 64-bit installer, like the app it installs
ManifestDPIAware true
SetCompressor /SOLID lzma
SetCompressorDictSize 64
RequestExecutionLevel user

!define APP "@APP@"
!define EXE "@EXE@"
!define UNINSTALLER "@UNINSTALLER@"
!define UNINSTALL_KEY "@UNINSTALL_KEY@"
!define APP_KEY "@APP_KEY@"
!define LINK_KEY "@LINK_KEY@"
!define BUILD "@BUILD@"
!define STAMP "@STAMP@"

Name "${APP}"
Caption "${APP} Setup"
OutFile "@OUTFILE@"
InstallDir "$LOCALAPPDATA\Programs\${APP}"
InstallDirRegKey HKCU "${APP_KEY}" "InstallDir"
BrandingText "${APP} - build ${BUILD}"
VIProductVersion "@BUILD@.0.0.0"
VIAddVersionKey "ProductName" "${APP}"
VIAddVersionKey "FileDescription" "${APP} Setup"
VIAddVersionKey "FileVersion" "Build ${BUILD}"
VIAddVersionKey "ProductVersion" "Build ${BUILD}"
VIAddVersionKey "LegalCopyright" "Apache License 2.0"

!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!define MUI_ICON "@ICON@"
!define MUI_UNICON "@ICON@"
!define MUI_WELCOMEFINISHPAGE_BITMAP "@SIDE@"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "@SIDE@"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_HEADERIMAGE_BITMAP "@HEADER@"
!define MUI_HEADERIMAGE_UNBITMAP "@HEADER@"
!define MUI_ABORTWARNING

Var WantMenu       ; ${BST_CHECKED} or ${BST_UNCHECKED}
Var WantDesktop
Var MenuBox
Var DesktopBox
Var OldRoot        ; Where the older single-file .exe unpacked itself (tidied away after installing)

; ---------------------------------------------------------------------------------------------------------- pages
!define MUI_WELCOMEPAGE_TITLE "Install ${APP}"
!define MUI_WELCOMEPAGE_TEXT "Watch videos in sync with your friends.$\r$\n$\r$\nThis installs ${APP} (build ${BUILD}) just for you: it doesn't need administrator rights, and the app keeps itself up to date.$\r$\n$\r$\nTo play videos you also need VLC or mpv.$\r$\n$\r$\nClick Next to continue."
!insertmacro MUI_PAGE_WELCOME

!define MUI_DIRECTORYPAGE_TEXT_TOP "Choose the folder to install ${APP} in. Everything it needs goes in this one folder.$\r$\n$\r$\nIf ${APP} is already installed, choose the same folder to update it; your settings are kept."
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE DirectoryLeave
!insertmacro MUI_PAGE_DIRECTORY

Page custom ShortcutsShow ShortcutsLeave

!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_TITLE "${APP} is installed"
!define MUI_FINISHPAGE_TEXT "Open it from the shortcuts you chose, or search for ${APP} in Windows.$\r$\n$\r$\nTo remove it later, use Settings > Apps, or Help > Uninstall in the app."
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Start ${APP} now"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ------------------------------------------------------------------------------------------------------- helpers
; The install folder is always called "${APP}" (the app relies on it), so a chosen folder gets that name added
!macro NormaliseInstDir
  ${GetFileName} "$INSTDIR" $0
  ${If} $0 != "${APP}"
    StrCpy $INSTDIR "$INSTDIR\${APP}"
  ${EndIf}
!macroend

; Windows won't rename a folder that a running program has open, so a failed rename means the app is open
!macro WaitUntilClosed DIR
  ${If} ${FileExists} "${DIR}\app\*.*"
    ${Do}
      ClearErrors
      Rename "${DIR}\app" "${DIR}\app.check"
      ${IfNot} ${Errors}
        Rename "${DIR}\app.check" "${DIR}\app"
        ${Break}
      ${EndIf}
      MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "${APP} is still open. Close it (also from the system tray), then click Retry." /SD IDCANCEL IDRETRY +2
      Abort "${APP} is still open."
    ${Loop}
  ${EndIf}
!macroend

; Every python-* runtime folder in DIR except KEEP (an empty KEEP removes them all)
!macro RemoveRuntimes DIR KEEP
  FindFirst $R0 $R1 "${DIR}\python-*"
  ${DoWhile} $R1 != ""
    ${If} $R1 != "${KEEP}"
      RMDir /r "${DIR}\$R1"
    ${EndIf}
    FindNext $R0 $R1
  ${Loop}
  FindClose $R0
!macroend

Function .onInit
  ; An earlier install's shortcut choices; otherwise the Start menu on and the desktop off
  StrCpy $WantMenu ${BST_CHECKED}
  StrCpy $WantDesktop ${BST_UNCHECKED}
  ReadRegStr $0 HKCU "${UNINSTALL_KEY}" "InstallLocation"
  ${If} $0 != ""
    ${IfNot} ${FileExists} "$SMPROGRAMS\${APP}.lnk"
      StrCpy $WantMenu ${BST_UNCHECKED}
    ${EndIf}
  ${EndIf}
  ${If} ${FileExists} "$DESKTOP\${APP}.lnk"
    StrCpy $WantDesktop ${BST_CHECKED}
  ${EndIf}
  ; The single-file .exe unpacked into the folder picked in its install window, or by default into %LOCALAPPDATA%\${APP}
  ReadRegStr $OldRoot HKCU "${APP_KEY}" "InstallDir"
  ${If} $OldRoot == ""
    StrCpy $OldRoot "$LOCALAPPDATA\${APP}"
  ${EndIf}
FunctionEnd

Function DirectoryLeave
  !insertmacro NormaliseInstDir
  ; Not into a folder that already holds something else
  ${If} ${FileExists} "$INSTDIR\*.*"
  ${AndIfNot} ${FileExists} "$INSTDIR\app\program\launch-syncplay.pyw"
    FindFirst $R0 $R1 "$INSTDIR\*.*"
    StrCpy $R2 0
    ${DoWhile} $R1 != ""
      ${If} $R1 != "."
      ${AndIf} $R1 != ".."
        StrCpy $R2 1
      ${EndIf}
      FindNext $R0 $R1
    ${Loop}
    FindClose $R0
    ${If} $R2 == 1
      MessageBox MB_OK|MB_ICONEXCLAMATION "$INSTDIR already has other files in it. Please choose an empty folder or a new one."
      Abort
    ${EndIf}
  ${EndIf}
FunctionEnd

Function ShortcutsShow
  !insertmacro MUI_HEADER_TEXT "Shortcuts" "Choose where you want to open ${APP} from."
  nsDialogs::Create 1018
  Pop $0
  ${NSD_CreateLabel} 0 0 100% 20u "Tick the shortcuts you want. You can change them later in the app, under Help > Install and shortcuts."
  Pop $0
  ${NSD_CreateCheckbox} 0 30u 100% 12u "Add to the Start menu"
  Pop $MenuBox
  ${NSD_SetState} $MenuBox $WantMenu
  ${NSD_CreateCheckbox} 0 48u 100% 12u "Add a shortcut on the desktop"
  Pop $DesktopBox
  ${NSD_SetState} $DesktopBox $WantDesktop
  nsDialogs::Show
FunctionEnd

Function ShortcutsLeave
  ${NSD_GetState} $MenuBox $WantMenu
  ${NSD_GetState} $DesktopBox $WantDesktop
FunctionEnd

; ------------------------------------------------------------------------------------------------------- install
Section "Install"
  !insertmacro NormaliseInstDir   ; Silent installs (/D=...) skip the folder page
  !insertmacro WaitUntilClosed "$INSTDIR"
  ; A fresh app folder: no half-applied in-app update or old rollback copy can come back over the new version
  RMDir /r "$INSTDIR\app"
  SetOutPath "$INSTDIR"
  File /r "@STAGE@/*"
  !insertmacro RemoveRuntimes "$INSTDIR" "python-${STAMP}"
  WriteUninstaller "$INSTDIR\${UNINSTALLER}"

  ; Shortcuts, exactly as chosen (an unticked one from an earlier install goes)
  ${If} $WantMenu == ${BST_CHECKED}
    CreateShortcut "$SMPROGRAMS\${APP}.lnk" "$INSTDIR\${EXE}" "" "$INSTDIR\${EXE}" 0
  ${Else}
    Delete "$SMPROGRAMS\${APP}.lnk"
  ${EndIf}
  ${If} $WantDesktop == ${BST_CHECKED}
    CreateShortcut "$DESKTOP\${APP}.lnk" "$INSTDIR\${EXE}" "" "$INSTDIR\${EXE}" 0
  ${Else}
    Delete "$DESKTOP\${APP}.lnk"
  ${EndIf}

  ; Where the app lives (read by the launcher too), and the entry in Settings > Apps
  WriteRegStr HKCU "${APP_KEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${APP}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${EXE},0"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "Build ${BUILD}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\${UNINSTALLER}"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\${UNINSTALLER}" /S'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "EstimatedSize" "$0"

  ; The copy the older single-file .exe unpacked: only ever a folder that really holds that layout, and not while open
  ${If} $OldRoot != $INSTDIR
  ${AndIf} ${FileExists} "$OldRoot\app\program\launch-syncplay.pyw"
  ${AndIfNot} ${FileExists} "$OldRoot\${UNINSTALLER}"
    ClearErrors
    Rename "$OldRoot" "$OldRoot.old"
    ${IfNot} ${Errors}
      RMDir /r "$OldRoot.old"
      DetailPrint "Removed the copy unpacked by the older download: $OldRoot"
    ${Else}
      DetailPrint "Left the older copy in $OldRoot (it is open); it can be deleted by hand."
    ${EndIf}
  ${EndIf}
SectionEnd

; ----------------------------------------------------------------------------------------------------- uninstall
Section "Uninstall"
  !insertmacro WaitUntilClosed "$INSTDIR"
  Delete "$SMPROGRAMS\${APP}.lnk"
  Delete "$DESKTOP\${APP}.lnk"
  RMDir /r "$INSTDIR\app"
  !insertmacro RemoveRuntimes "$INSTDIR" ""
  Delete "$INSTDIR\${EXE}"
  Delete "$INSTDIR\${UNINSTALLER}"
  RMDir "$INSTDIR"   ; Only if nothing else is left in it
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  DeleteRegKey HKCU "${APP_KEY}"
  DeleteRegKey HKCU "${LINK_KEY}"
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "Also remove your ${APP} settings (your name, rooms, server and saved keys)?" /SD IDNO IDNO keepSettings
@DELETE_SETTINGS@
    DeleteRegKey HKCU "Software\Syncplay"
  keepSettings:
SectionEnd
'''


def nsisScript(**values):
    text = SCRIPT
    deletes = "\n".join('    Delete "$APPDATA\\{}"'.format(name) for name in SETTINGS_FILES)
    for key, value in dict(values, DELETE_SETTINGS=deletes, APP=APP, EXE=EXE, UNINSTALLER=UNINSTALLER,
                           UNINSTALL_KEY=UNINSTALL_KEY, APP_KEY=APP_KEY, LINK_KEY=LINK_KEY).items():
        text = text.replace("@{}@".format(key), str(value))
    left = re.findall(r"@[A-Z_]+@", text)
    if left:
        raise ValueError("Unfilled placeholders in the NSIS script: {}".format(", ".join(sorted(set(left)))))
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build", type=int, required=True)
    parser.add_argument("--defaults", help="syncplay-defaults.json to ship inside (your API key / update repo)")
    parser.add_argument("--out", default=os.path.join(ROOT, "dist"))
    args = parser.parse_args()
    if not shutil.which("makensis"):
        sys.exit("NSIS is needed: apt install nsis")
    args.out = os.path.abspath(args.out)
    makeExe = loadMakeExe()
    cache = os.path.join(args.out, "cache")
    work = os.path.join(args.out, "work-setup")
    os.makedirs(cache, exist_ok=True)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)

    runtime = makeExe.assembleRuntime(cache, work)
    runtimeZip = os.path.join(work, "runtime.zip")
    makeExe.zipTree(runtime, runtimeZip)  # Only for its fingerprint, which names the runtime folder as the .exe does
    stamp = hashlib.sha256(open(runtimeZip, "rb").read()).hexdigest()[:16]
    os.remove(runtimeZip)
    app = makeExe.buildApp(work, args.build, args.defaults)
    makeExe.verifyBundle(runtime, app)
    launcher = makeExe.compileStub(work)

    # The installed layout: the launcher, python-<stamp>\ and app\ (with the markers the single-file .exe leaves, so an
    # older copy of that .exe opened later finds everything already in place)
    stage = os.path.join(work, "stage")
    os.makedirs(stage)
    runtimeFolder = "python-" + stamp
    shutil.move(runtime, os.path.join(stage, runtimeFolder))
    with open(os.path.join(stage, runtimeFolder, ".unpacked"), "w") as f:
        f.write("ok")
    shutil.move(app, os.path.join(stage, "app"))
    with open(os.path.join(stage, "app", ".marquee-build"), "w") as f:
        f.write(str(args.build))
    shutil.copyfile(launcher, os.path.join(stage, EXE))

    side, header = artwork(work)
    outFile = os.path.join(args.out, "{} Setup.exe".format(APP))
    script = os.path.join(work, "setup.nsi")
    with open(script, "w", encoding="utf-8-sig") as f:
        f.write(nsisScript(BUILD=args.build, STAMP=stamp, OUTFILE=outFile, STAGE=stage, SIDE=side, HEADER=header,
                           ICON=os.path.join(ROOT, "syncplay", "resources", "icon.ico")))
    subprocess.run(["makensis", "-V2", "-INPUTCHARSET", "UTF8", script], check=True)
    print("Built {} - {:.1f} MB, build {}".format(outFile, os.path.getsize(outFile) / 1e6, args.build))


if __name__ == "__main__":
    main()
