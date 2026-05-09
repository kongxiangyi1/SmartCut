$folder = "d:\Download\autoclip-main1\autoclip-main\releases\AutoClip-1.0.0\backend"
$files = Get-ChildItem -Path $folder -Recurse -Force | Where-Object { !$_.PSIsContainer }
$sorted = $files | Sort-Object Length -Descending | Select-Object -First 20

Write-Host "=== Backend TOP 20 大文件 ==="
Write-Host ""

foreach ($f in $sorted) {
    $sizeMB = [math]::Round($f.Length/1MB, 2)
    $relPath = $f.FullName.Replace($folder + "\", "")
    Write-Host "$($sizeMB) MB - $relPath"
}