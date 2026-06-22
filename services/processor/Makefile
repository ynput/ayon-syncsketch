ENVFILE = .env
ENVFILE_EXAMPLE = example_env

# Create the .env file if not exit.
ifeq ("$(wildcard $(ENVFILE))","")
   $(shell cp $(ENVFILE_EXAMPLE) $(ENVFILE))
endif

ADDON_VERSION=$(shell python "$(CURDIR)/helper.py" addon-version)
IMAGE=$(shell python "$(CURDIR)/helper.py" image)
BASE_NAME := $(shell python "$(CURDIR)/helper.py" image-base)
IMAGE_VERSION := $(shell python "$(CURDIR)/helper.py" image-version)
BASH_CONTAINER_NAME := $(BASE_NAME)-bash-$(IMAGE_VERSION)

build:
	docker build -t $(IMAGE) .

dist:
	docker push $(IMAGE)

clean:
	docker rmi $(IMAGE)

dev:
	docker run --rm -ti \
		-v $(CURDIR):/service \
		--hostname syncsketch \
		--env AYON_API_KEY=${AYON_API_KEY} \
		--env AYON_SERVER_URL=${AYON_SERVER_URL} \
		--env AYON_ADDON_NAME=syncsketch \
		--env AYON_ADDON_VERSION=$(ADDON_VERSION) \
		$(IMAGE) python -m processor

bash:
	docker run --name $(BASH_CONTAINER_NAME) --rm -it --entrypoint /bin/bash $(IMAGE)
