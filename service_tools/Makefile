ifneq (,$(wildcard ./.env))
		include .env
		export
endif

VERSION=$(shell python -c "import os;import sys;content={};f=open('$(CURDIR)/../../package.py');exec(f.read(),content);f.close();print(content['version'])")

define HELP_INFO

*************************
AYON syncsketch services tool
	 Run syncsketch services
*************************

Run service processes from terminal. It is recommended to use docker images for production.

Usage: make [target]

Optional arguments for service targets:
--variant [variant] (Define settings variant. default: 'production')

Runtime targets:
	install    Install requirements
	processor  Main processing logic

endef
export HELP_INFO

help:
	@echo "$$HELP_INFO"

install:
		uv sync

processor:
		export AYON_ADDON_NAME="syncsketch" && \
		export AYON_ADDON_VERSION=$(VERSION) && \
		uv run "$(CURDIR)/main.py" --service processor $@

info: help
default: help
