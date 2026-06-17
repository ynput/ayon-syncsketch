include .env
VERSION=$(shell python -c "import os;import sys;content={};f=open('$(CURDIR)/../../package.py');exec(f.read(),content);f.close();print(content['version'])")
IMAGE := ynput/ayon-syncsketch-processor:$(VERSION)

build:
	cp -r ../syncsketch_common $(CURDIR)/processor/common
	docker build -t $(IMAGE) .
	rm -rf $(CURDIR)/processor/common

clean:
	if docker images | grep $(IMAGE); then \
		docker rmi $(IMAGE); \
	fi

clean-build: clean
	docker build --no-cache -t $(IMAGE) .

dev:
	cp -r ../syncsketch_common $(CURDIR)/processor/common
	docker run --rm -u ayonuser -ti \
		-v $(CURDIR):/service:Z \
		--env-file .env \
		--attach=stdin \
		--attach=stdout \
		--attach=stderr \
		--network=host \
		$(IMAGE) python -m processor
	rm -rf $(CURDIR)/processor/common


shell:
	docker run --rm -u ayonuser -ti --env-file .env --network=host -v $(CURDIR):/service:Z $(IMAGE) /bin/sh
