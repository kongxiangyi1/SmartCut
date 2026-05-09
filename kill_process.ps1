$processId = 20388
$process = Get-Process -Id $processId -ErrorAction SilentlyContinue
if ($process) {
    Write-Host "Found process $processId, killing..."
    $process.Kill()
    Write-Host "Process killed"
} else {
    Write-Host "Process $processId not found"
}