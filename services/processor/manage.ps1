# Receive first positional argument
Param([Parameter(Position=0)]$FunctionName)
$current_dir = Get-Location
$script_dir_rel = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$script_dir = (Get-Item $script_dir_rel).FullName

$RESULT = Invoke-Expression -Command "python '$($script_dir)/helper.py' all"
$IMAGE_FULL_NAME, $BASE_NAME, $IMAGE_VERSION, $ADDON_VERSION = $RESULT.split("|")
$BASH_CONTAINER_NAME = "$($BASE_NAME)-bash-$($IMAGE_VERSION)"

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
  Write-Host "  bash     Run bash in docker image (for development purposes)"
}

function build {
  & docker build -t "$IMAGE_FULL_NAME" .
}

function clean {
  & docker rmi $(IMAGE_FULL_NAME)
}

function dist {
  build
  docker push "$IMAGE_FULL_NAME"
}

function load-env {
  $env_path = "$($script_dir)/.env"
  if (Test-Path $env_path) {
    Get-Content $env_path `
    | foreach {
      $name, $value = $_.split("=")
      if (-not([string]::IsNullOrWhiteSpace($name) -or $name.Contains("#"))) {
        Set-Content env:\$name $value
      }
    }
  }
}

function dev {
  load-env
  & docker run --rm -ti `
    -v "$($script_dir):/service" `
    --hostname syncsketch `
    --env AYON_API_KEY=$env:AYON_API_KEY `
    --env AYON_SERVER_URL=$env:AYON_SERVER_URL `
    --env AYON_ADDON_NAME=syncsketch `
    --env AYON_ADDON_VERSION=$ADDON_VERSION `
    --attach=stdin `
    --attach=stdout `
    --attach=stderr `
    --network=host `
    "$IMAGE_FULL_NAME" python -m processor
}

function bash {
  & docker run --name "$($BASH_CONTAINER_NAME)" --rm -it --entrypoint /bin/bash "$($IMAGE_FULL_NAME)"
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
  } elseif ($FunctionName -eq "bash") {
    bash
  } elseif ($null -eq $FunctionName) {
    defaultfunc
  } else {
    Write-Host "Unknown function ""$FunctionName"""
  }
}

main