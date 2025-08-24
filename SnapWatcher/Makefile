IMAGE=192.168.33.204:8082/snapwatcher:latest

build:
	podman build -t $(IMAGE) .

push:
	podman push $(IMAGE)

install: build push
	helm upgrade --install snapwatcher ./charts/snapwatcher -n snap 

clean:
	helm delete snapwatcher -n snap

.PHONY: build push install clean