include .env
VERSION=$(shell python -c "import os;import sys;content={};f=open('$(CURDIR)/../../version.py');exec(f.read(),content);f.close();print(content['__version__'])")
IMAGE := ynput/ayon-syncsketch-processor:$(VERSION)

build:
	cp -r ../../syncsketch_common .
	docker build -t $(IMAGE) .
	rm -rf syncsketch_common

clean:
	if docker images | grep $(IMAGE); then \
		docker rmi $(IMAGE); \
	fi

clean-build: clean
	docker build --no-cache -t $(IMAGE) .

dev:
	cp -r ../../ftrack_common .
	docker run --rm -u ayonuser -ti \
		-v $(CURDIR):/service:Z \
		--env-file .env \
		--attach=stdin \
		--attach=stdout \
		--attach=stderr \
		--network=host \
		$(IMAGE) python -m processor


shell:
	docker run --rm -u ayonuser -ti --env-file .env --network=host -v $(CURDIR):/service:Z $(IMAGE) /bin/sh
