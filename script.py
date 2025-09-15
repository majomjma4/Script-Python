from mitmproxy import http
import sqlite3, json, os, time, threading, hashlib, binascii
from urllib.parse import parse_qs 
from io import BytesIO
import cgi
from datetime import datetime