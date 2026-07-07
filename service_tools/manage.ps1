# Receive first positional argument
$FunctionName=$ARGS[0]
$arguments=@()
if ($ARGS.Length -gt 1) {
    $arguments = $ARGS[1..($ARGS.Length - 1)]
}

$script_dir_rel = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$script_dir = (Get-Item $script_dir_rel).FullName

$ADDON_VERSION = Invoke-Expression -Command "python -c ""import os;import sys;content={};f=open(r'$($script_dir)/../package.py');exec(f.read(),content);f.close();print(content['version'])"""

function Default-Func {
  Write-Host ""
  Write-Host "*************************"
  Write-Host "AYON syncsketch services tool"
  Write-Host "   Run syncsketch services"
  Write-Host "*************************"
  Write-Host ""
  Write-Host "Run service processes from terminal. It is recommended to use docker images for production."
  Write-Host ""
  Write-Host "Usage: start [target]"
  Write-Host ""
  Write-Host "Optional arguments for service targets:"
  Write-Host "--variant [variant] (Define settings variant. default: 'production')"
  Write-Host ""
  Write-Host "Runtime targets:"
  Write-Host "  install      Install requirements"
  Write-Host "  processor    Main processing logic"
  Write-Host ""
}

function Install-Requirements {
  & uv sync
}

function Start-Processor {
  & uv run "$($script_dir)\main.py" --service processor @arguments
}

function Load-Env {
  $env_path = "$($script_dir)/.env"
  if (Test-Path $env_path) {
    Get-Content $env_path | foreach {
      $name, $value = $_.split("=")
      if (-not([string]::IsNullOrWhiteSpace($name) -or $name.Contains("#"))) {
        Set-Content env:\$name $value
      }
    }
  }
}
function main {
  if ($null -eq $FunctionName) {
    Default-Func
    return
  }
  $env:AYON_ADDON_NAME = "syncsketch"
  $env:AYON_ADDON_VERSION = $ADDON_VERSION
  Load-Env

  if ($FunctionName -eq "install") {
    Install-Requirements
  } elseif ($FunctionName -eq "processor") {
    Start-Processor
  } else {
    Write-Host "Unknown function ""$FunctionName"""
    Default-Func
  }
}

main