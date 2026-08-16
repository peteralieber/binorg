Get-PnpDevice -Class Bluetooth |
  Select-Object FriendlyName, InstanceId |
  Format-Table -AutoSize

$printer = Get-PnpDevice -Class Bluetooth |
  Where-Object { $_.FriendlyName -match 'B1|Nimot|Printer' } |
  Select-Object -First 1

if ($printer) {
    $rawId = $printer.InstanceId
    $hex = ($rawId -split 'DEV_' | Select-Object -Last 1) -replace '[^0-9A-Fa-f]', ''

    if ($hex.Length -gt 12) {
        $hex = $hex.Substring($hex.Length - 12)
    }

    if ($hex.Length -eq 12) {
        $formatted = (($hex -replace '(.{2})', '$1:').Trim(':')).ToUpper()
        "Printer found: $($printer.FriendlyName)"
        "InstanceId: $rawId"
        "Bluetooth MAC: $formatted"
    }
    else {
        "Printer found: $($printer.FriendlyName)"
        "InstanceId: $rawId"
        "Could not extract a valid Bluetooth MAC from this device ID."
    }
}
else {
    "No matching printer device found."
}