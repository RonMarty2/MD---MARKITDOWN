Option Explicit

Dim shell, fso, root, script, command, exitCode

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
script = root & "\scripts\iniciar-sin-consola.ps1"
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & script & Chr(34)

shell.Popup "Preparando Markitdown. La primera vez puede tardar varios minutos. El navegador se abrira cuando este listo.", 4, "Markitdown", 64
exitCode = shell.Run(command, 0, True)

If exitCode = 0 Then
  shell.Popup "Markitdown esta iniciado en http://127.0.0.1:8000", 4, "Markitdown", 64
Else
  shell.Popup "No pude iniciar Markitdown. Revisa logs\launcher.log dentro de la carpeta del proyecto.", 10, "Markitdown", 16
End If
