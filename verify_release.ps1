$folder = "d:\Download\autoclip-main1\autoclip-main\releases\AutoClip-1.0.0"

Write-Host "=== 发布包内容验证 ==="
Write-Host ""

# Check backend folder
$backendFiles = Get-ChildItem -Path "$folder\backend" -Recurse -Force | Where-Object { !$_.PSIsContainer }
$backendSize = ($backendFiles | Measure-Object -Property Length -Sum).Sum
$backendMB = [math]::Round($backendSize/1MB, 2)
Write-Host "Backend: $backendMB MB"

# Check frontend folder
$frontendFiles = Get-ChildItem -Path "$folder\frontend" -Recurse -Force | Where-Object { !$_.PSIsContainer } -ErrorAction SilentlyContinue
$frontendSize = ($frontendFiles | Measure-Object -Property Length -Sum).Sum
$frontendMB = [math]::Round($frontendSize/1MB, 2)
Write-Host "Frontend: $frontendMB MB"

# Check models folder
$modelsFiles = Get-ChildItem -Path "$folder\offline_packages" -Recurse -Force | Where-Object { !$_.PSIsContainer } -ErrorAction SilentlyContinue
$modelsSize = ($modelsFiles | Measure-Object -Property Length -Sum).Sum
$modelsMB = [math]::Round($modelsSize/1MB, 2)
Write-Host "Models: $modelsMB MB"

# Check batch files
$batchFiles = Get-ChildItem -Path $folder -Filter "*.bat" -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "Batch files:"
foreach ($f in $batchFiles) {
    Write-Host "  - $($f.Name)"
}

# Check if venv exists
$venvExists = Test-Path "$folder\backend\venv"
Write-Host ""
Write-Host "venv excluded: $(-not $venvExists)"

# Check total
$totalMB = [math]::Round(($backendSize + $frontendSize + $modelsSize)/1MB, 2)
Write-Host ""
Write-Host "Total (without venv): $totalMB MB"

# Check zip size
$zipPath = "d:\Download\autoclip-main1\autoclip-main\releases\AutoClip-1.0.0.zip"
if (Test-Path $zipPath) {
    $zipSize = (Get-Item $zipPath).Length
    $zipMB = [math]::Round($zipSize/1MB, 2)
    Write-Host ""
    Write-Host "ZIP file: $zipMB MB"
}