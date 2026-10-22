@echo off
rem Para a Mesa que roda escondida (iniciada com o Windows ou pelo "Iniciar Mesa (sem janela)").
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" | Where-Object { $_.CommandLine -like '*server\app.py*' }; if ($p) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Host 'Mesa parada.' } else { Write-Host 'A Mesa nao estava rodando.' }"
ping -n 3 127.0.0.1 >nul
