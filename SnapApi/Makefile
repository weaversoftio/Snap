IMAGE=192.168.33.204:8082/snapapi:latest

build:
	podman build -t $(IMAGE) .

push:
	podman push $(IMAGE)

install: build push
	helm upgrade --install snapapi ./charts/snapapi -n snap 

clean:
	helm delete snapapi -n snap

.PHONY: build push install clean