$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

try {
    [Console]::InputEncoding = $utf8NoBom
} catch {
}

try {
    [Console]::OutputEncoding = $utf8NoBom
} catch {
}

$OutputEncoding = $utf8NoBom

# Ensure file writes from common cmdlets default to UTF-8.
$PSDefaultParameterValues["Out-File:Encoding"] = "utf8"
$PSDefaultParameterValues["Set-Content:Encoding"] = "utf8"
$PSDefaultParameterValues["Add-Content:Encoding"] = "utf8"

if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSDefaultParameterValues["Export-Csv:Encoding"] = "utf8"
}
