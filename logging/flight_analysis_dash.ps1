# PowerShell script for running flight_analysis_dash.py with appropriate CSV arguments

param(
    [Parameter(Position=0, Mandatory=$false)]
    [string]$LogId
)

# Set up directory path (no date)
$CsvDir = "CSV_OUTPUT"

# If no specific LogId is provided, look for available log files
if (-not $LogId) {
    $AttFiles = Get-ChildItem -Path $CsvDir -Filter '*.ATT.csv' -File | Sort-Object Name
    if (-not $AttFiles) {
        Write-Error "No ATT.csv files found in $CsvDir. Please ensure logs have been extracted and converted to CSV."
        exit 1
    }
    $FirstAtt = $AttFiles[0].Name
    $LogId = $FirstAtt -replace '\.ATT\.csv$',''
    Write-Host "Found log ID: $LogId"
}

# Construct the python command for the Dash app
$PythonCmd = "python flight_analysis_dash.py"

# Add required arguments - check if they exist
$AttCsv = "$CsvDir/$LogId.ATT.csv"
$ImuCsv = "$CsvDir/$LogId.IMU.csv"

if (!(Test-Path $AttCsv)) {
    Write-Error "Required file '$AttCsv' not found."
    exit 1
}
$PythonCmd += " --att-csv `"$AttCsv`""

if (!(Test-Path $ImuCsv)) {
    Write-Error "Required file '$ImuCsv' not found."
    exit 1
}
$PythonCmd += " --imu-csv `"$ImuCsv`""

# Add optional arguments if files exist
$optionalFiles = @(
    @{Name='RCIN'; Arg='--rcin-csv'},
    @{Name='POS';  Arg='--pos-csv'},
    @{Name='GPS';  Arg='--gps-csv'},
    @{Name='ARSP'; Arg='--arsp-csv'},
    @{Name='XKF5'; Arg='--xkf5-csv'},
    @{Name='RFND'; Arg='--rfnd-csv'},
    @{Name='BARO'; Arg='--baro-csv'},
    @{Name='TERR'; Arg='--terr-csv'},
    @{Name='BAT';  Arg='--bat-csv'}
)
foreach ($file in $optionalFiles) {
    $csvPath = "$CsvDir/$LogId.$($file.Name).csv"
    if (Test-Path $csvPath) {
        $PythonCmd += " $($file.Arg) `"$csvPath`""
    }
}

# Echo the command being run
Write-Host "Running analysis with command:"
Write-Host $PythonCmd
Write-Host ""

# Execute the command
# Use Start-Process with -Wait to allow CTRL+C to stop the Python server
try {
    $PythonArgs = @("flight_analysis_dash.py", "--att-csv", $AttCsv, "--imu-csv", $ImuCsv)
    # Add optional arguments as needed
    # ...
    & python @PythonArgs
} catch {
    Write-Host "\nFailed to execute the Python script."
    exit 1
} 