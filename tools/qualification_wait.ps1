# Pure polling boundary shared by opt-in installation probes and background tests.
function Wait-QualificationCondition {
    param(
        [Parameter(Mandatory)][scriptblock]$Condition,
        [ValidateRange(0.01, 120)][double]$TimeoutSeconds = 30,
        [ValidateRange(1, 1000)][int]$IntervalMilliseconds = 100,
        [string]$Label = 'Qualification condition'
    )
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        if (& $Condition) { return }
        if ($timer.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
            throw "$Label did not complete within $TimeoutSeconds seconds"
        }
        Start-Sleep -Milliseconds $IntervalMilliseconds
    }
}
