# Repository instructions

- PowerShell로 파일을 쓸 때는 BOM 없는 UTF-8(`New-Object System.Text.UTF8Encoding($false)`)을 사용한다. `[Text.Encoding]::UTF8`, `Set-Content -Encoding UTF8`, `Out-File` 기본값은 쓰지 않는다.
