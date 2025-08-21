IMAGE=192.168.33.204:8082/snapwatch:latest

build:
	podman build -t $(IMAGE) .

push:
	podman push $(IMAGE)

install: build push
	helm upgrade --install snapwatch ./charts/snapwatch -n snap 

clean:
	helm delete snapwatch -n snap || true

.PHONY: build push install clean