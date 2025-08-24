IMAGE=192.168.33.204:8082/snapui:latest

build:
	podman build -t $(IMAGE) .

push:
	podman push $(IMAGE)

install: build push
	helm upgrade --install snapui ./charts/snapui -n snap 

clean:
	helm delete snapui -n snap

.PHONY: build push install clean