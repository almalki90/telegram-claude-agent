import subprocess, logging, json, os
logger = logging.getLogger(__name__)

TOOLS_SCHEMA = [
    {"name":"ssh_execute","description":"SSH command on remote server","parameters":{"type":"object","properties":{"host":{"type":"string"},"username":{"type":"string"},"password":{"type":"string"},"command":{"type":"string"},"port":{"type":"integer","default":22}},"required":["host","username","password","command"]}},
    {"name":"http_request","description":"HTTP request to any URL","parameters":{"type":"object","properties":{"url":{"type":"string"},"method":{"type":"string","enum":["GET","POST","PUT","DELETE"],"default":"GET"},"headers":{"type":"object"},"body":{"type":"object"},"timeout":{"type":"integer","default":30}},"required":["url"]}},
    {"name":"execute_shell","description":"Execute local shell command","parameters":{"type":"object","properties":{"command":{"type":"string"},"timeout":{"type":"integer","default":30}},"required":["command"]}},
    {"name":"read_file","description":"Read a local file","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
    {"name":"write_file","description":"Write a local file","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}},
    {"name":"database_query","description":"Execute SQL query on MySQL/PostgreSQL","parameters":{"type":"object","properties":{"db_type":{"type":"string","enum":["mysql","postgresql"]},"host":{"type":"string"},"port":{"type":"integer"},"database":{"type":"string"},"username":{"type":"string"},"password":{"type":"string"},"query":{"type":"string"}},"required":["db_type","host","database","username","password","query"]}},
    {"name":"get_system_info","description":"Get system info (CPU/RAM/disk)","parameters":{"type":"object","properties":{"info_type":{"type":"string","enum":["all","cpu","memory","disk","network","processes"],"default":"all"}},"required":[]}}
]

def execute_tool(name, inp):
    try:
        fns = {
            "ssh_execute": _ssh,
            "http_request": _http,
            "execute_shell": _shell,
            "read_file": _rfile,
            "write_file": _wfile,
            "database_query": _db,
            "get_system_info": _sysinfo
        }
        fn = fns.get(name)
        if fn:
            return fn(**inp)
        return "unknown tool: " + name
    except Exception as e:
        return "tool error " + name + ": " + str(e)

def _ssh(host, username, password, command, port=22):
    try:
        import paramiko
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(host, port=int(port), username=username, password=password, timeout=30)
        _, o, e = c.exec_command(command, timeout=30)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        code = o.channel.recv_exit_status()
        c.close()
        r = "SSH " + str(username) + "@" + str(host) + "\n"
        r += "Cmd: " + str(command) + "\nExit: " + str(code) + "\n"
        if out:
            r += "\nOutput:\n" + out[:2000]
        if err:
            r += "\nErrors:\n" + err[:500]
        return r
    except Exception as ex:
        return "SSH failed: " + str(ex)

def _http(url, method="GET", headers=None, body=None, timeout=30):
    try:
        import requests as rq
        h = headers or {}
        if method == "GET":
            r = rq.get(url, headers=h, timeout=timeout)
        elif method == "POST":
            r = rq.post(url, headers=h, json=body, timeout=timeout)
        elif method == "PUT":
            r = rq.put(url, headers=h, json=body, timeout=timeout)
        else:
            r = rq.delete(url, headers=h, timeout=timeout)
        res = "HTTP " + method + " " + url + "\nStatus: " + str(r.status_code) + "\n"
        try:
            res += json.dumps(r.json(), ensure_ascii=False, indent=2)[:2000]
        except Exception:
            res += r.text[:2000]
        return res
    except Exception as ex:
        return "HTTP failed: " + str(ex)

def _shell(command, timeout=30):
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=int(timeout))
        res = "Cmd: " + str(command) + "\nExit: " + str(r.returncode) + "\n"
        if r.stdout:
            res += r.stdout[:2000]
        if r.stderr:
            res += "\nErr: " + r.stderr[:500]
        return res
    except subprocess.TimeoutExpired:
        return "Timeout after " + str(timeout) + "s"
    except Exception as ex:
        return "Shell failed: " + str(ex)

def _rfile(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            c = f.read()
        return "File: " + str(path) + "\n\n" + c[:3000]
    except FileNotFoundError:
        return "File not found: " + str(path)
    except Exception as ex:
        return "Read error: " + str(ex)

def _wfile(path, content):
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return "Saved: " + str(path)
    except Exception as ex:
        return "Write error: " + str(ex)

def _db(db_type, host, database, username, password, query, port=None):
    try:
        if db_type == "mysql":
            import pymysql
            conn = pymysql.connect(host=host, port=int(port or 3306), user=username,
                                   password=password, database=database, charset="utf8mb4")
        else:
            import psycopg2
            conn = psycopg2.connect(host=host, port=int(port or 5432), user=username,
                                    password=password, dbname=database)
        cur = conn.cursor()
        cur.execute(query)
        if query.strip().upper().startswith("SELECT"):
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            conn.close()
            r = str(db_type) + ": " + str(database) + "@" + str(host) + " - " + str(len(rows)) + " rows\n"
            if cols and rows:
                r += " | ".join(str(c) for c in cols) + "\n" + "-" * 40 + "\n"
                for row in rows[:20]:
                    r += " | ".join(str(v) if v is not None else "NULL" for v in row) + "\n"
            return r
        else:
            conn.commit()
            aff = cur.rowcount
            conn.close()
            return "Done. Affected: " + str(aff)
    except Exception as ex:
        return "DB error: " + str(ex)

def _sysinfo(info_type="all"):
    try:
        cmds = {
            "memory": "free -h",
            "disk": "df -h",
            "cpu": "top -bn1 | head -5",
            "processes": "ps aux --sort=-%mem | head -10",
            "network": "ip addr show 2>/dev/null | head -20"
        }
        if info_type == "all":
            result = ""
            for k in ["memory", "disk"]:
                p = subprocess.run(cmds[k], shell=True, capture_output=True, text=True, timeout=10)
                result += "=== " + k + " ===\n" + p.stdout[:400] + "\n"
            return result
        cmd = cmds.get(info_type, "echo unknown")
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return p.stdout[:1500]
    except Exception as ex:
        return "Sysinfo error: " + str(ex)
