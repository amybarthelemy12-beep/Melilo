param([string]$Model = 'olmo2:7b')
$ErrorActionPreference = 'Stop'
$prompt = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'prompt.txt') -Encoding UTF8 -Raw
$body = @{
    model = $Model
    prompt = $prompt
    stream = $false
    options = @{ temperature = 0; num_ctx = 2048; num_predict = 600 }
} | ConvertTo-Json -Depth 4 -Compress
try {
    $result = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/generate' -Method Post -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 300
} catch {
    throw "Local Ollama request failed. Open Ollama and run 'ollama pull $Model', then try again. Details: $_"
}
if (-not $result.done -or [string]::IsNullOrWhiteSpace($result.response)) {
    throw 'Ollama did not return a completed answer.'
}
if ($result.done_reason -eq 'length') {
    Write-Warning 'Ollama hit its output limit. Review the response for missing citations.'
}
$result.response
