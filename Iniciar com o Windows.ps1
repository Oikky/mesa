# Cria (ou remove, com -Remover) o atalho na pasta Inicializar que liga a Mesa sem janela no login.
param([switch]$Remover)

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Mesa (servidor).lnk'

if ($Remover) {
    Remove-Item $lnk -ErrorAction SilentlyContinue
    Write-Host 'A Mesa não liga mais sozinha.'
    return
}

$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = Join-Path $dir '.venv\Scripts\pythonw.exe'
$s.Arguments = '"' + (Join-Path $dir 'server\app.py') + '"'
$s.WorkingDirectory = $dir
$s.WindowStyle = 7
$s.IconLocation = Join-Path $dir '.venv\Scripts\pythonw.exe'
$s.Description = 'Mesa: controle de som pelo tablet'
$s.Save()
Write-Host "Pronto: a Mesa liga sozinha no login ($lnk)."
