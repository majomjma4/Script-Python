from mitmproxy import http
import sqlite3, json, os, threading, hashlib, binascii
from urllib.parse import parse_qs
from io import BytesIO
import cgi
from datetime import datetime

BD = os.path.join(os.path.expanduser("~"), "mitm_envios.db")
BLOQUEO_DB = threading.Lock()

def ahora_iso():
    return datetime.utcnow().isoformat() + "Z"

def hash_seguro(password: str, iteraciones=100_000):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iteraciones)
    return f"pbkdf2_sha256${iteraciones}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

def iniciar_db():
    with BLOQUEO_DB:
        conexion = sqlite3.connect(BD, check_same_thread=False)
        conexion.execute("PRAGMA journal_mode=WAL;")
        conexion.execute("""CREATE TABLE IF NOT EXISTS envios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servidor TEXT,
            ruta TEXT,
            metodo TEXT,
            campos_json TEXT,
            ip_cliente TEXT,
            agente_usuario TEXT,
            recibido_en TEXT
        )""")
        conexion.commit()
        return conexion
    
print("[INFO] Iniciando captura de formularios...")

class CapturadorFormularios:
    def __init__(self):
        self.conexion = iniciar_db()

    def guardar_envio(self, servidor, ruta, metodo, campos, ip_cliente, agente_usuario):
        with BLOQUEO_DB:
            self.conexion.execute(
                "INSERT INTO envios (servidor,ruta,metodo,campos_json,ip_cliente,agente_usuario,recibido_en) VALUES (?,?,?,?,?,?,?)",
                (servidor, ruta, metodo, json.dumps(campos, ensure_ascii=False), ip_cliente, agente_usuario, ahora_iso())
            )
            self.conexion.commit()
        print(f"[{ahora_iso()}] Nuevo envío {servidor}{ruta} desde {ip_cliente} - campos: {list(campos.keys())}")

    def _parsear_multipart(self, flujo):
        campos = {}
        fp = BytesIO(flujo.request.raw_content or b"")
        env = {"REQUEST_METHOD": flujo.request.method}
        headers = {k.lower(): v for k, v in flujo.request.headers.items()}
        if "content-type" in headers:
            env['CONTENT_TYPE'] = headers['content-type']
        fs = cgi.FieldStorage(fp=fp, environ=env, keep_blank_values=True)
        for key in fs.keys():
            item = fs[key]
            if isinstance(item, list):
                val = [p.filename or p.value for p in item]
            else:
                val = item.filename or item.value
            campos[key] = val
        return campos

    def request(self, flujo: http.HTTPFlow):
        try:
            print("[INFO] Capturando nueva petición...")
            metodo = flujo.request.method.upper()
            servidor = flujo.request.host or ""
            ruta = flujo.request.path or ""
            agente_usuario = flujo.request.headers.get("user-agent", "")
            ip_cliente = flujo.client_conn.address[0] if getattr(flujo, "client_conn", None) else "desconocida"
            campos = {}

            if flujo.request.query:
                campos.update({k: v for k, v in flujo.request.query.items()})

            tipo_contenido = flujo.request.headers.get("content-type", "").lower()
            if "application/x-www-form-urlencoded" in tipo_contenido:
                texto = flujo.request.get_text() or ""
                parseados = parse_qs(texto, keep_blank_values=True)
                for k, v in parseados.items():
                    campos[k] = v[0] if v else ""
            elif "multipart/form-data" in tipo_contenido:
                try:
                    campos.update(self._parsear_multipart(flujo))
                except:
                    pass
            elif "application/json" in tipo_contenido:
                try:
                    j = json.loads(flujo.request.get_text() or "{}")
                    if isinstance(j, dict):
                        campos.update(j)
                    else:
                        campos["__json"] = j
                except:
                    pass

            if "password" in campos:
                pw = campos.pop("password")
                try:
                    campos["password_hash"] = hash_seguro(pw)
                except:
                    campos["password_hash"] = "error_hashing"

            if campos:
                self.guardar_envio(servidor, ruta, metodo, campos, ip_cliente, agente_usuario)

        except Exception as e:
            print("Error en mitm_addon:", e)

addons = [CapturadorFormularios()]

print("[INFO] Capturador lissto. Esprando formularios...")

import atexit
atexit.register(lambda: print("[INFO] Finalización de captura de datos. "))

                
                