import os

# Keep pytest independent from a real .env file. Several tests import modules
# that import config.py during collection, and config.py requires Azure keys at
# import time. Dummy values are enough because unit tests mock external calls.
os.environ.setdefault("AZURE_SPEECH_KEY", "test-key")
os.environ.setdefault("AZURE_SPEECH_REGION", "japaneast")
