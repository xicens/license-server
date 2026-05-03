from flask import Flask, request, jsonify
import time, json, os
import secrets

app = Flask(__name__)

DB_FILE = "keys.json"
CONFIG_FILE = "configs.json"

# ===== ЗАГРУЗКА =====
if os.path.exists(DB_FILE):
    with open(DB_FILE) as f:
        keys = json.load(f)
else:
    keys = {}

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE) as f:
        configs = json.load(f)
else:
    configs = {}

def save():
    with open(DB_FILE, "w") as f:
        json.dump(keys, f, indent=4)

def save_configs():
    with open(CONFIG_FILE, "w") as f:
        json.dump(configs, f, indent=4)

def clean_name(value):
    return "".join(ch for ch in str(value or "default").lower() if ch.isalnum() or ch in "._-").strip(".-_") or "default"

def make_code(key, name):
    code = name
    used = {
        cfg.get("code", cfg_name)
        for user_cfgs in configs.values()
        for cfg_name, cfg in user_cfgs.items()
        if isinstance(cfg, dict)
    }
    if code not in used:
        return code
    while True:
        code = secrets.token_urlsafe(4).replace("-", "").replace("_", "")[:6].lower()
        if code and code not in used:
            return code

def config_data(entry):
    if isinstance(entry, dict) and "data" in entry:
        return entry.get("data", {})
    return entry

def auth_user(data):
    key = data.get("key")
    hwid = data.get("hwid")
    if key not in keys:
        return None, jsonify({"status": "invalid", "message": "invalid key"})
    user = keys[key]
    if user["banned"]:
        return None, jsonify({"status": "banned", "message": "banned"})
    if user["hwid"] != hwid:
        return None, jsonify({"status": "hwid_error", "message": "hwid error"})
    now = int(time.time())
    end = user["start"] + user["days"] * 86400
    if now > end:
        return None, jsonify({"status": "expired", "message": "expired"})
    configs.setdefault(key, {})
    return key, None

# ===== CHECK =====
@app.route("/check", methods=["POST"])
def check():
    data = request.json
    key = data.get("key")
    hwid = data.get("hwid")

    if key not in keys:
        return jsonify({"status": "invalid"})

    user = keys[key]

    if user["banned"]:
        return jsonify({"status": "banned"})

    if user["hwid"] is None:
        user["hwid"] = hwid
        user["start"] = int(time.time())
        save()
        return jsonify({
            "status": "ok",
            "start": user["start"],
            "days": user["days"]
        })

    if user["hwid"] != hwid:
        return jsonify({"status": "hwid_error"})

    now = int(time.time())
    end = user["start"] + user["days"] * 86400

    if now > end:
        return jsonify({"status": "expired"})

    return jsonify({
        "status": "ok",
        "start": user["start"],
        "days": user["days"]
    })

# ===== ADD KEY =====
@app.route("/add", methods=["GET"])
def add():
    key = request.args.get("key")
    days = request.args.get("days")

    if not key or not days:
        return "Используй: /add?key=XXX&days=30"

    if key in keys:
        return "KEY EXISTS"

    keys[key] = {
        "hwid": None,
        "banned": False,
        "days": int(days),
        "start": None
    }

    save()
    return f"OK: {key}"

# ===== BAN =====
@app.route("/ban", methods=["GET"])
def ban():
    key = request.args.get("key")

    if key in keys:
        keys[key]["banned"] = True
        save()
        return "BANNED"

    return "NOT FOUND"

# ===== LIST =====
@app.route("/list", methods=["GET"])
def list_keys():
    return jsonify(keys)

@app.route("/configs/list", methods=["POST"])
def configs_list():
    key, error = auth_user(request.json or {})
    if error:
        return error
    items = []
    for name, entry in sorted(configs.get(key, {}).items()):
        if isinstance(entry, dict):
            items.append({"name": name, "code": entry.get("code", name)})
        else:
            items.append({"name": name, "code": name})
    return jsonify({"status": "ok", "configs": items})

@app.route("/configs/save", methods=["POST"])
def configs_save():
    data = request.json or {}
    key, error = auth_user(data)
    if error:
        return error
    name = clean_name(data.get("name", "default"))
    overwrite = bool(data.get("overwrite", False))
    user_configs = configs.setdefault(key, {})
    if name in user_configs and not overwrite:
        return jsonify({"status": "exists", "message": "name is busy"})
    code = user_configs.get(name, {}).get("code", make_code(key, name)) if isinstance(user_configs.get(name), dict) else make_code(key, name)
    user_configs[name] = {"code": code, "data": data.get("data", {})}
    save_configs()
    return jsonify({"status": "ok", "code": code})

@app.route("/configs/load", methods=["POST"])
def configs_load():
    data = request.json or {}
    key, error = auth_user(data)
    if error:
        return error
    name = clean_name(data.get("name", "default"))
    user_configs = configs.get(key, {})
    if name not in user_configs:
        return jsonify({"status": "not_found", "message": "config not found"})
    entry = user_configs[name]
    return jsonify({"status": "ok", "data": config_data(entry), "code": entry.get("code", name) if isinstance(entry, dict) else name})

@app.route("/configs/code", methods=["POST"])
def configs_code():
    data = request.json or {}
    key, error = auth_user(data)
    if error:
        return error
    code = clean_name(data.get("code", ""))
    for owner_key, user_configs in configs.items():
        for name, entry in user_configs.items():
            entry_code = entry.get("code", name) if isinstance(entry, dict) else name
            if entry_code == code:
                return jsonify({"status": "ok", "name": name, "data": config_data(entry)})
    return jsonify({"status": "not_found", "message": "config code not found"})

@app.route("/configs/delete", methods=["POST"])
def configs_delete():
    data = request.json or {}
    key, error = auth_user(data)
    if error:
        return error
    name = clean_name(data.get("name", "default"))
    configs.setdefault(key, {}).pop(name, None)
    save_configs()
    return jsonify({"status": "ok"})

# ===== RUN =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
