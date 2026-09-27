param(
    [string]$ApiUrl = "http://localhost:8000",
    [string]$UiUrl = "http://localhost:8501"
)

$ErrorActionPreference = "Stop"

$health = Invoke-RestMethod -Uri "$ApiUrl/health" -Method Get
if ($health.status -ne "ok") {
    throw "API health check did not report status=ok."
}

$readiness = Invoke-RestMethod -Uri "$ApiUrl/system/readiness" -Method Get
if ($readiness.external_actions_enabled) {
    throw "Release boundary violation: external actions must remain disabled."
}
if ($readiness.specialist_agent_count -ne 8) {
    throw "Expected eight registered specialist agents."
}

$ui = Invoke-WebRequest -Uri $UiUrl -UseBasicParsing
if ($ui.StatusCode -ne 200) {
    throw "Streamlit UI did not return HTTP 200."
}

Write-Output "PASS: API, readiness boundary, and Streamlit UI smoke checks succeeded."
