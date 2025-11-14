param(
    [string]$Source,
    [string]$Target,
    [string]$Executable,
    [int]$TargetProcessId,
    [string]$LogFile
)

$ErrorActionPreference = "Stop"

function Write-Log($Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "$stamp`t$Message"
}

function Wait-ForProcess($ProcessId) {
    if ($ProcessId -le 0) { return }
    while (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        Start-Sleep -Seconds 1
    }
}

function Resolve-PayloadPath([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Source path '$Path' does not exist."
    }
    $p = $Path
    while (Test-Path -LiteralPath $p -PathType Container) {
        $entries = Get-ChildItem -LiteralPath $p
        if ($entries.Count -eq 1 -and $entries[0].PSIsContainer) {
            $p = $entries[0].FullName
        } else {
            break
        }
    }
    return $p
}

function Invoke-WithRetry {
    param(
        [scriptblock]$Action,
        [string]$Description,
        [int]$Retries = 30,
        [int]$DelaySeconds = 1
    )

    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        try {
            & $Action
            return
        } catch {
            if ($attempt -ge $Retries) {
                throw
            }
            Write-Log ("$Description failed (attempt $attempt of $Retries): " + $_.Exception.Message)
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

function Mirror-Directory {
    param(
        [string]$Source,
        [string]$Target
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Mirror source '$Source' does not exist."
    }
    if (-not (Test-Path -LiteralPath $Target)) {
        New-Item -ItemType Directory -Path $Target -Force | Out-Null
    }

    # Use direct robocopy invocation to avoid fragile string-quoting
    $robocopyArgs = @(
        $Source
        $Target
        "/MIR","/R:5","/W:2","/NFL","/NDL","/NJH","/NJS","/NP"
    )
    & robocopy @robocopyArgs | Out-Null
    $code = $LASTEXITCODE
    if ($code -ge 8) {
        throw "Robocopy failed with exit code $code."
    }
}

function Stop-ProcessesInPath {
    param(
        [string]$Path,
        [int]$ExcludePid
    )

    try {
        $normalized = [System.IO.Path]::GetFullPath($Path).TrimEnd('\').ToLowerInvariant()
    } catch {
        Write-Log ("Unable to normalize path $($Path): " + $_.Exception.Message)
        return
    }

    try {
        $processes = Get-CimInstance Win32_Process | Where-Object {
            $_.ExecutablePath -and $_.ExecutablePath.ToLowerInvariant().StartsWith($normalized)
        }
    } catch {
        Write-Log ("Failed to list processes for $($Path): " + $_.Exception.Message)
        return
    }

    foreach ($proc in $processes) {
        if ($proc.ProcessId -eq $ExcludePid) { continue }
        Write-Log ("Stopping process {0} (PID {1}) still using target" -f $proc.Name, $proc.ProcessId)
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            Wait-ForProcess $proc.ProcessId
        } catch {
            Write-Log ("Failed to stop process {0}: {1}" -f $proc.ProcessId, $_.Exception.Message)
        }
    }
}

$sourceRoot = $Source
$installSucceeded = $false

try {
    $payloadSource = Resolve-PayloadPath -Path $sourceRoot

    Write-Log "Waiting for process $TargetProcessId to exit"
    Wait-ForProcess $TargetProcessId
    Stop-ProcessesInPath -Path $Target -ExcludePid $TargetProcessId
    Write-Log "Copying update files"

    $targetParent = Split-Path -Parent $Target
    $targetName = Split-Path -Leaf $Target
    $backup = Join-Path $targetParent ($targetName + ".bak")
    $rotated = $false

    Invoke-WithRetry -Description "Remove old backup" -Action {
        if (Test-Path -LiteralPath $backup) {
            Remove-Item -LiteralPath $backup -Recurse -Force
        }
    }

    if (Test-Path -LiteralPath $Target) {
        try {
            Invoke-WithRetry -Description "Rotate existing installation" -Action {
                Rename-Item -LiteralPath $Target -NewName ($targetName + ".bak")
            }
            $rotated = $true
            Write-Log "Existing installation moved to $backup"
        } catch {
            Write-Log ("Rotate existing installation failed after retries: " + $_.Exception.Message + ". Falling back to in-place copy.")
        }
    }

    Invoke-WithRetry -Description "Ensure target directory" -Action {
        if ($rotated) {
            New-Item -ItemType Directory -Path $Target -Force | Out-Null
        } elseif (-not (Test-Path -LiteralPath $Target)) {
            New-Item -ItemType Directory -Path $Target -Force | Out-Null
        }
    }

    Invoke-WithRetry -Description "Mirror payload into target" -Action {
        Mirror-Directory -Source $payloadSource -Target $Target
    }

    if ($rotated) {
        Invoke-WithRetry -Description "Remove backup" -Action {
            if (Test-Path -LiteralPath $backup) {
                Remove-Item -LiteralPath $backup -Recurse -Force
            }
        }
    }

    $exeName = Split-Path -Leaf $Executable
    $exePathInTarget = Join-Path $Target $exeName

    Write-Log "Launching updated client: $exePathInTarget"
    Start-Process -FilePath $exePathInTarget -WorkingDirectory $Target
    $installSucceeded = $true
} catch {
    Write-Log ("Update failed: " + $_.Exception.Message)
    throw
} finally {
    if ($installSucceeded) {
        try {
            if (Test-Path -LiteralPath $sourceRoot) {
                Remove-Item -LiteralPath $sourceRoot -Recurse -Force
            }
        } catch {
            Write-Log ("Cleanup failed: " + $_.Exception.Message)
        }
    } else {
        Write-Log "Staging directory preserved for retry."
    }
}