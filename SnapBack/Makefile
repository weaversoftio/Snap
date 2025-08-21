IMAGE=192.168.33.204:8082/snapback:latest

certs:
	@if [ ! -f tls.crt ] || [ ! -f tls.key ]; then \
		echo "Generating TLS certificates..."; \
		openssl req -x509 -newkey rsa:2048 -keyout tls.key -out tls.crt -days 365 -nodes -config csr.conf -extensions req_ext; \
	else \
		echo "TLS certificates already exist."; \
	fi

build:
	podman build -t $(IMAGE) .

push:
	podman push $(IMAGE)

install: certs build push
	helm upgrade --install snapback ./charts/snapback -n snap \
	--set webhook.tlsCrt="$$(cat tls.crt | base64 -w0)" \
	--set webhook.tlsKey="$$(cat tls.key | base64 -w0)" \
	--set webhook.caBundle="$$(cat tls.crt | base64 -w0)"

clean:
	helm delete snapback -n snap || true
	rm -f tls.crt tls.key tls.csr

.PHONY: certs build push install clean