$folder = "d:\Download\autoclip-main1\autoclip-main\releases\AutoClip-1.0.0\backend\venv"
if (Test-Path $folder) {
    $size = (Get-ChildItem -Path $folder -Recurse -Force -File | Measure-Object -Property Length -Sum).Sum
    $sizeInMB = [math]::Round($size / 1MB, 2)
    $sizeInGB = [math]::Round($size / 1GB, 2)
    Write-Host "venv 文件夹大小: $sizeInMB MB ($sizeInGB GB)"
} else {
    Write-Host "venv 文件夹不存在"
}