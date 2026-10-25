Option Explicit
Dim shell, files, folder, target, desktop, shortcutPath, shortcut
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
target = files.BuildPath(folder, "Iniciar buscador.bat")
If Not files.FileExists(target) Then
    MsgBox "No se encuentra Iniciar buscador.bat. Mantenga este archivo dentro de la carpeta buscador-pendones.", vbExclamation, "Buscador de Pendones"
    WScript.Quit 1
End If
desktop = shell.SpecialFolders("Desktop")
shortcutPath = files.BuildPath(desktop, "Buscador de Pendones.lnk")
If files.FileExists(shortcutPath) Then
    If MsgBox("Ya existe un acceso directo con este nombre. Desea reemplazarlo?", vbYesNo + vbQuestion, "Buscador de Pendones") <> vbYes Then
        WScript.Quit 0
    End If
End If
Set shortcut = shell.CreateShortcut(shortcutPath)
shortcut.TargetPath = target
shortcut.WorkingDirectory = folder
shortcut.Description = "Abrir Buscador de Pendones"
shortcut.IconLocation = shell.ExpandEnvironmentStrings("%SystemRoot%\System32\shell32.dll") & ",22"
shortcut.Save
MsgBox "Acceso creado en el escritorio: Buscador de Pendones. Abra ese icono con doble clic. Mantenga la ventana del programa abierta mientras lo utiliza.", vbInformation, "Buscador de Pendones"
