Option Explicit

Dim shell, fso, root, script, command, exitCode

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
script = root & "\scripts\detener-sin-consola.ps1"
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & script & Chr(34)

exitCode = shell.Run(command, 0, True)

If exitCode = 0 Then
  shell.Popup "Markitdown se detuvo.", 4, "Markitdown", 64
Else
  shell.Popup "No pude detener Markitdown. Revisa logs\launcher.log dentro de la carpeta del proyecto.", 8, "Markitdown", 16
End If
