# Analyze release package
$folder = "d:\Download\autoclip-main1\autoclip-main\releases\AutoClip-1.0.0"

# Check backend folder size
$backendFiles = Get-ChildItem -Path "$folder\backend" -Recurse -Force | Where-Object { !$_.PSIsContainer }
$backendSize = ($backendFiles | Measure-Object -Property Length -Sum).Sum
$backendMB = [math]::Round($backendSize/1MB, 2)

# Check frontend folder size
$frontendFiles = Get-ChildItem -Path "$folder\frontend" -Recurse -Force | Where-Object { !$_.PSIsContainer }
$frontendSize = ($frontendFiles | Measure-Object -Property Length -Sum).Sum
$frontendMB = [math]::Round($frontendSize/1MB, 2)

# Check models folder size
$modelsFiles = Get-ChildItem -Path "$folder\offline_packages" -Recurse -Force | Where-Object { !$_.PSIsContainer } -ErrorAction SilentlyContinue
$modelsSize = ($modelsFiles | Measure-Object -Property Length -Sum).Sum
$modelsMB = [math]::Round($modelsSize/1MB, 2)

Write-Host "Backend: $backendMB MB"
Write-Host "Frontend: $frontendMB MB"
Write-Host "Models: $modelsMB MB"
Write-Host ""

$total = $backendSize + $frontendSize + $modelsSize
$totalMB = [math]::Round($total/1MB, 2)
Write-Host "Total (without venv): $totalMB MB"