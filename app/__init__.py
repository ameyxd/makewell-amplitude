"""Makewell: a small workshop booking site."""
from dotenv import load_dotenv

# Read settings from the .env file, if there is one, into os.environ.
# Python runs this file before any other file in app/, so every file can
# read its settings from os.environ without worrying about import order.
load_dotenv()
