; Before replacing the sidecar runtime, ask Windows Restart Manager to close
; the previous app binary and any orphaned process holding this exact DLL.
; The first check also handles upgrades from an older executable name.
!macro NSIS_HOOK_PREINSTALL
  ReadRegStr $R9 SHCTX "${UNINSTKEY}" "MainBinaryName"
  ${If} $R9 == ""
    StrCpy $R9 "${MAINBINARYNAME}.exe"
  ${EndIf}
  !insertmacro CheckIfAppIsRunning "$INSTDIR\$R9" "${PRODUCTNAME}"
  !insertmacro CheckIfAppIsRunning "$INSTDIR\_internal\VCRUNTIME140.dll" "${PRODUCTNAME}"
!macroend
