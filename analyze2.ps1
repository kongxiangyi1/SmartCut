$folder = "d:\Download\autoclip-main1\autoclip-main\releases\AutoClip-1.0.0"
$items = Get-ChildItem -Path $folder -Recurse -Force | Where-Object { !$_.PSIsContainer }
$sorted = $items | Sort-Object Length -Descending | Select-Object -First 15

Write-Host "=== 发布包最大文件 TOP 15 ==="
Write-Host ""

foreach ($item in $sorted) {
    $sizeMB = [math]::Round($item.Length/1MB, 2)
    $relPath = $item.FullName.Replace($folder + "\", "")
    Write-Host "$($sizeMB) MB - $relPath"
}

Write-Host ""
Write-Host "=== 各目录大小 ==="
Write-Host ""

$dirs = @(
    "$folder\backend",
    "$folder\frontend",
    "$folder\offline_packages"
)

foreach ($dir in $dirs) {
    if (Test-Path $dir) {
        $files = Get-ChildItem -Path $dir -Recurse -Force | Where-Object { !$_.PSIsContainer }
        $total = ($files | Measure-Object -Property Length -Sum).Sum
        $sizeMB = [math]::Round($total/1MB, 2)
        $sizeGB = [math]::Round($total/1GB, 2)
        Write-Host "$dir : $sizeMB MB ($sizeGB GB)"
    } else {
        Write-Host "$dir : 不存在"
    }
}