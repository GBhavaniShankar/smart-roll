# Makefile

PORT ?= 8000
CERT = cert.pem
KEY  = key.pem

# Detect local IP (non-loopback)
IP := $(shell hostname -I | awk '{print $$1}')

# Target to generate self-signed SSL certs
certs:
	@if [ ! -f "$(CERT)" ] || [ ! -f "$(KEY)" ]; then \
		echo "Generating SSL certificates for $(IP)..."; \
		openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
			-keyout $(KEY) \
			-out $(CERT) \
			-subj "/C=US/ST=State/L=City/O=Org/OU=Unit/CN=$(IP)"; \
	else \
		echo "Certificates already exist, skipping generation."; \
	fi

# Target to run Uvicorn with SSL
run: certs
	@echo "Starting Uvicorn on https://$(IP):$(PORT)"
	uvicorn main:app --reload --host $(IP) --port $(PORT) --ssl-keyfile=$(KEY) --ssl-certfile=$(CERT)
