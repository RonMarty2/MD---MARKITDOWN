Option Explicit

Dim shell, fso, root, script, command, exitCode

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
script = root & "\scripts\actualizar-sin-consola.ps1"
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & script & Chr(34)

shell.Popup "Actualizando GitHub en segundo plano. Si Git pide credenciales, puede abrirse una ventana de autenticacion.", 4, "Markitdown", 64
exitCode = shell.Run(command, 0, True)

If exitCode = 0 Then
  shell.Popup "Actualizacion terminada. Revisa GitHub si quieres confirmar el push.", 6, "Markitdown", 64
Else
  shell.Popup "La actualizacion fallo. Revisa logs\updater.log dentro de la carpeta del proyecto.", 10, "Markitdown", 16
End If
