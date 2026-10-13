import os

# Test-only signing material; production configuration fails closed when absent.
os.environ.setdefault("API_KEY", "unit-test-api-key")
os.environ.setdefault("HMAC_SECRET", "unit-test-hmac-secret-with-sufficient-length")
