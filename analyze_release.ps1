$folder = "d:\Download\autoclip-main1\autoclip-main\releases\AutoClip-1.0.0"
$files = Get-ChildItem -Path $folder -Recurse -Force -File | Where-Object { $_.FullName -notmatch "venv" }
$total = ($files | Measure-Object -Property Length -Sum).Sum

Write-Host "=== 发布包文件分析 ==="
Write-Host ""

# 按大小排序显示前15个文件
$topFiles = $files | Sort-Object Length -Descending | Select-Object -First 15

foreach ($f in $topFiles) {
    $sizeMB = [math]::Round($f.Length/1MB, 2)
    $relPath = $f.FullName.Replace($folder + "\", "")
    Write-Host "$($sizeMB) MB - $relPath"
}

Write-Host ""
$totalMB = [math]::Round($total/1MB, 2)
$totalGB = [math]::Round($total/1GB, 2)
Write-Host "总文件大小: $totalMB MB ($totalGB GB)"