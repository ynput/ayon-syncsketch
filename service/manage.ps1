# Receive first positional argument
Param([Parameter(Position=0)]$FunctionName)
$current_dir = Get-Location
$script_dir_rel = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$script_dir = (Get-Item $script_dir_rel).FullName

$IMAGE_NAME = "ynput/ayon-syncsketch-processor"
$ADDON_VERSION = Invoke-Expression -Command "python -c ""import os;import sys;content={};f=open(os.path.normpath(r'$($script_dir)/../package.py'));exec(f.read(),content);f.close();print(content['version'])"""
$IMAGE_FULL_NAME = "$($IMAGE_NAME):$($ADDON_VERSION)"

function defaultfunc {
  Write-Host ""
  Write-Host "*************************"
  Write-Host "AYON syncsketch processor service"
  Write-Host "   Run event processing service"
  Write-Host "   Docker image name: $($IMAGE_FULL_NAME)"
  Write-Host "*************************"
  Write-Host ""
  Write-Host "Run event processor as a service."
  Write-Host ""
  Write-Host "Usage: manage [target]"
  Write-Host ""
  Write-Host "Runtime targets:"
  Write-Host "  build    Build docker image"
  Write-Host "  clean    Remove docker image"
  Write-Host "  dist     Publish docker image to docker hub"
  Write-Host "  dev      Run docker (for development purposes)"
}

function build {
  & Copy-Item -r "$current_dir/../syncsketch_common" "$current_dir/processor/common"
  try {
    & docker build -t "$IMAGE_FULL_NAME" .
  } finally {
    & Remove-Item -Recurse -Force "$current_dir/processor/common"
  }
}

function clean {
  & docker rmi $(IMAGE_FULL_NAME)
}

function dist {
  build
  # Publish the docker image to the registry
  docker push "$IMAGE_FULL_NAME"
}

function dev {
  & Copy-Item -r "$current_dir/../syncsketch_common" "$current_dir/processor/common"
  try {
    & docker run --rm -u ayonuser -ti `
      -v "$($current_dir):/service:Z"`
      --env-file "$($current_dir)/.env" `
      --attach=stdin `
      --attach=stdout `
      --attach=stderr `
      --network=host `
      "$($IMAGE_FULL_NAME)" python -m processor
  } finally {
    & Remove-Item -Recurse -Force "$current_dir/processor/common"
  }
}

function main {
  if ($FunctionName -eq "build") {
    build
  } elseif ($FunctionName -eq "clean") {
    clean
  } elseif ($FunctionName -eq "dev") {
    dev
  } elseif ($FunctionName -eq "dist") {
    dist
  } elseif ($null -eq $FunctionName) {
    defaultfunc
  } else {
    Write-Host "Unknown function ""$FunctionName"""
  }
}

main