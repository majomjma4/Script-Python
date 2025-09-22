from flask import Flask, request 
import sqlite3, os, json 
from datetime import datetime 
import threading 

BD_PATH = os.path.join(os.path.dirname(__file__), "captura_formularios.db") 
BLOQUEO_BD = threading.Lock() 

def ahora_iso():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S") 


def iniciar_db():
    try:
        with BLOQUEO_BD:
            conn = sqlite3.connect(BD_PATH, check_same_thread=False)
            cursor = conn.cursor()
            conn.execute("""CREATE TABLE IF NOT EXISTS envios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ruta TEXT,
                metodo TEXT,
                campos_json TEXT,
                ip_cliente TEXT,
                agente_usuario TEXT,
                recibido_en TEXT
            )""")
            conn.commit()
            cursor.close()
            print(f"[INFO] Base de datos lista en {BD_PATH}")
            return conn
    except Exception as e:
        print(f"[ERROR] No se pudo crear la base de datos: ", e)
        raise
    
app = Flask(__name__)
conexion = iniciar_db()

def guardar_envio(ruta, metodo, campos, ip_cliente, agente_usuario):
    try:
        with BLOQUEO_BD:
            conexion.execute(
                "INSERT INTO envios (ruta,metodo,campos_json,ip_cliente,agente_usuario,recibido_en) VALUES (?,?,?,?,?,?)",
                ( ruta, metodo, json.dumps(campos, ensure_ascii=False), ip_cliente, agente_usuario, ahora_iso())
            )
            conexion.commit()
            print(f"\n[CAPTURA] {ruta} desde {ip_cliente} - campos: {list(campos.keys())} - {ahora_iso()}\n")
    except Exception as e:
        print("[ERROR] No se pudo guardar el envío", e)
        
@app.route("/", defaults ={"path": ""}, methods =["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def capturar(path):
    campos = {}
    if request.method == "POST":
        campos.update(request.form.to_dict())
        if request.is_json:
            try:
                j = request.get_json()
                if isinstance(j, dict):
                    campos.update(j)
                    
            except:
                pass
            
    ip_cliente = request.remote_addr
    agente_usuario = request.headers.get("User-Agent", "")
    if campos:
        guardar_envio(f"/{path}", request.method, campos, ip_cliente, agente_usuario)
    return "Formulario recibido!!", 200

def iniciar_app():
    print("\n[INFO] Captura de formularios iniciada...")
    print("[INFO] Esperando envíos de formularios...\n")
    app.run(host="0.0.0.0", port=5000)
    print("\n[INFO] Captura de formularios finalizada. \n")
    
if __name__ == "__main__":
    try:
        iniciar_app()
    except KeyboardInterrupt:
        print("\n[INFO] Captura detenida por el usuario. \n") 