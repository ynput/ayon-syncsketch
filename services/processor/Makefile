include .env
VERSION=$(shell python -c "import os;import sys;content={};f=open('$(CURDIR)/../../../package.py');exec(f.read(),content);f.close();print(content['version'])")
IMAGE := ynput/ayon-syncsketch-processor:$(VERSION)

build:
	docker build -t $(IMAGE) .

clean:
	if docker images | grep $(IMAGE); then \
		docker rmi $(IMAGE); \
	fi

clean-build: clean
	docker build --no-cache -t $(IMAGE) .

dev:
	docker run --rm -ti \
		-v $(CURDIR):/service:Z \
		--env-file .env \
		--attach=stdin \
		--attach=stdout \
		--attach=stderr \
		--network=host \
		$(IMAGE) python -m processor


shell:
	docker run --rm -ti --env-file .env --network=host -v $(CURDIR):/service:Z $(IMAGE) /bin/sh
