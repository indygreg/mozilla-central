'This Source Code Form is subject to the terms of the Mozilla Public
'License, v. 2.0. If a copy of the MPL was not distributed with this
'file, You can obtain one at http://mozilla.org/MPL/2.0/.

'This script is used to download and install Python on Windows. Once Python
'is installed, we download the regular Python bootstrap script and run it.

Sub Download(uri, path)
    Dim httpRequest, stream

    Set httpRequest = CreateObject("Microsoft.XMLHTTP")
    Set stream = CreateObject("Adodb.Stream")

    httpRequest.Open "GET", uri, False
    httpRequest.Send

    With stream
        .type = 1
        .open
        .write httpRequest.responseBody
        .savetofile path, 2
    End With
End Sub

Function DownloadToTempFile(uri)
    Dim fso, tempFolder, tempName

    Set fso = CreateObject("Scripting.FileSystemObject")
    tempFolder = fso.GetSpecialFolder(2)
    tempName = fso.GetTempName
    tempName = fso.BuildPath(tempFolder, tempName)

    Download uri, tempName
    DownloadToTempFile = tempName
End Function

Function GetInstallPath()
    Dim message, prompt

    message = "Installation Path:"
    title = "Select Installation Location"
    GetInstallPath = InputBox(message, title, "c:\mozilla-build")
end Function

Dim pythonURI, mbPath, pythonInstaller, shell, fso, pythonInstallPath
Dim pythonExe, mozbootPyURI, mozbootPy

pythonURI = "http://www.python.org/ftp/python/2.7.3/python-2.7.3.msi"
mozbootPyURI = "https://hg.mozilla.org/mozilla-central/raw-file/default/python/mozboot/bin/bootstrap.py"

'Where MozillaBuild will be installed to.
mbPath = GetInstallPath()
pythonInstallPath = mbPath & "\python"

'Download the Python installer MSI.
pythonInstaller = DownloadToTempFile(pythonURI)

Set fso = CreateObject("Scripting.FileSystemObject")

'It needs to have an .msi extension for the installer to be happy.
fso.MoveFile pythonInstaller, "python-installer.msi"

Set shell = CreateObject("WScript.Shell")

'Install Python and delete the installer.
shell.run "msiexec /i python-installer.msi /qb TARGETDIR=" & pythonInstallPath, 1, True
fso.DeleteFile("python-installer.msi")

pythonExe = pythonInstallPath & "\python.exe"

'Download and run the mozboot bootstrapper.
mozbootPy = DownloadToTempFile(mozbootPyURI)
shell.run pythonExe & " " & mozbootPy, 1, True
fso.DeleteFile(mozbootPy)