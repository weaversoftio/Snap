import os, subprocess

CERT_DIR = "/certs"
CERT_FILE = os.path.join(CERT_DIR, "tls.crt")
KEY_FILE = os.path.join(CERT_DIR, "tls.key")

def ensure_certs():
    if not os.path.exists(CERT_FILE) or not os.path.exists(KEY_FILE):
        os.makedirs(CERT_DIR, exist_ok=True)
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", KEY_FILE, "-out", CERT_FILE,
            "-days", "365", "-nodes", "-subj", "/CN=snaphook-webhook"
        ])