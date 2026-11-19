"""Test setup. pytest loads this file before any test.

It points the app at a throwaway database, so tests never touch makewell.db,
and switches tracking off, so tests never send anything to Amplitude.
This has to happen before `app` is imported, which is why it lives here.
"""
import os
import tempfile

os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["AMPLITUDE_API_KEY"] = ""
