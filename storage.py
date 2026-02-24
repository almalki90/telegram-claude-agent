import sqlite3, os, base64, logging
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)
DB_PATH = Path(__file__).parent / 'bot_data.db'
SALT_PATH = Path(__file__).parent / '.salt'

def _fernet():
    token = os.getenv('TELEGRAM_TOKEN','default')
    if SALT_PATH.exists(): salt = SALT_PATH.read_bytes()
    else:
        salt = os.urandom(16); SALT_PATH.write_bytes(salt); os.chmod(SALT_PATH,0o600)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=100000)
    key = base64.urlsafe_b64encode(kdf.derive(token.encode()))
    return Fernet(key)

def _enc(text): return _fernet().encrypt(text.encode()).decode()
def _dec(text): return _fernet().decrypt(text.encode()).decode()

def init_db():
    c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute('''CREATE TABLE IF NOT EXISTS api_keys(user_id INTEGER, provider TEXT, enc_key TEXT, model TEXT, PRIMARY KEY(user_id,provider))''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_cfg(user_id INTEGER PRIMARY KEY, active_provider TEXT, active_model TEXT, waiting_key TEXT, updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ctx(user_id INTEGER, role TEXT, content TEXT, id INTEGER PRIMARY KEY AUTOINCREMENT)''')
    c.commit(); c.close(); logger.info('DB ready')

def save_api_key(uid, provider, key, model=None):
    enc = _enc(key)
    c = sqlite3.connect(DB_PATH)
    c.execute("INSERT OR REPLACE INTO api_keys VALUES(?,?,?,?)",(uid,provider,enc,model))
    c.execute("INSERT INTO user_cfg(user_id,active_provider,active_model) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET active_provider=?,active_model=?,updated=CURRENT_TIMESTAMP",(uid,provider,model,provider,model))
    c.commit(); c.close()

def get_api_key(uid, provider):
    c = sqlite3.connect(DB_PATH)
    r = c.execute("SELECT enc_key FROM api_keys WHERE user_id=? AND provider=?",(uid,provider)).fetchone()
    c.close()
    if r:
        try: return _dec(r[0])
        except: return None
    return None

def get_active_provider(uid):
    c = sqlite3.connect(DB_PATH)
    r = c.execute("SELECT active_provider FROM user_cfg WHERE user_id=?",(uid,)).fetchone()
    c.close(); return r[0] if r else None

def get_active_model(uid):
    c = sqlite3.connect(DB_PATH)
    r = c.execute("SELECT active_model FROM user_cfg WHERE user_id=?",(uid,)).fetchone()
    c.close(); return r[0] if r else None

def set_active_provider(uid, provider, model=None):
    c = sqlite3.connect(DB_PATH)
    c.execute("INSERT INTO user_cfg(user_id,active_provider,active_model) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET active_provider=?,active_model=COALESCE(?,active_model),updated=CURRENT_TIMESTAMP",(uid,provider,model,provider,model))
    c.commit(); c.close()

def set_waiting_for_key(uid, provider):
    c = sqlite3.connect(DB_PATH)
    c.execute("INSERT INTO user_cfg(user_id,waiting_key) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET waiting_key=?,updated=CURRENT_TIMESTAMP",(uid,provider,provider))
    c.commit(); c.close()

def get_waiting_for_key(uid):
    c = sqlite3.connect(DB_PATH)
    r = c.execute("SELECT waiting_key FROM user_cfg WHERE user_id=?",(uid,)).fetchone()
    c.close(); return r[0] if r else None

def clear_waiting_for_key(uid):
    c = sqlite3.connect(DB_PATH)
    c.execute("UPDATE user_cfg SET waiting_key=NULL WHERE user_id=?",(uid,))
    c.commit(); c.close()

def save_context(uid, role, content):
    c = sqlite3.connect(DB_PATH)
    c.execute("INSERT INTO ctx(user_id,role,content) VALUES(?,?,?)",(uid,role,content))
    c.execute("DELETE FROM ctx WHERE user_id=? AND id NOT IN (SELECT id FROM ctx WHERE user_id=? ORDER BY id DESC LIMIT 20)",(uid,uid))
    c.commit(); c.close()

def get_context(uid):
    c = sqlite3.connect(DB_PATH)
    rows = c.execute("SELECT role,content FROM ctx WHERE user_id=? ORDER BY id",(uid,)).fetchall()
    c.close(); return [{"role":r[0],"content":r[1]} for r in rows]

def clear_context(uid):
    c = sqlite3.connect(DB_PATH)
    c.execute("DELETE FROM ctx WHERE user_id=?",(uid,))
    c.commit(); c.close()

def get_all_providers(uid):
    c = sqlite3.connect(DB_PATH)
    rows = c.execute("SELECT provider,model FROM api_keys WHERE user_id=?",(uid,)).fetchall()
    c.close(); return {r[0]:{"model":r[1]} for r in rows}

def delete_provider(uid, provider):
    c = sqlite3.connect(DB_PATH)
    c.execute("DELETE FROM api_keys WHERE user_id=? AND provider=?",(uid,provider))
    c.execute("UPDATE user_cfg SET active_provider=NULL,active_model=NULL WHERE user_id=? AND active_provider=?",(uid,provider))
    c.commit(); c.close()
