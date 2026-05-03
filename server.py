from flask import Flask, request, jsonify
import time, json, os

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
    return jsonify({"status": "ok", "configs": sorted(configs.get(key, {}).keys())})

@app.route("/configs/save", methods=["POST"])
def configs_save():
    data = request.json or {}
    key, error = auth_user(data)
    if error:
        return error
    name = "".join(ch for ch in str(data.get("name", "default")).lower() if ch.isalnum() or ch in "._-").strip(".-_") or "default"
    configs.setdefault(key, {})[name] = data.get("data", {})
    save_configs()
    return jsonify({"status": "ok"})

@app.route("/configs/load", methods=["POST"])
def configs_load():
    data = request.json or {}
    key, error = auth_user(data)
    if error:
        return error
    name = "".join(ch for ch in str(data.get("name", "default")).lower() if ch.isalnum() or ch in "._-").strip(".-_") or "default"
    user_configs = configs.get(key, {})
    if name not in user_configs:
        return jsonify({"status": "not_found", "message": "config not found"})
    return jsonify({"status": "ok", "data": user_configs[name]})

@app.route("/configs/delete", methods=["POST"])
def configs_delete():
    data = request.json or {}
    key, error = auth_user(data)
    if error:
        return error
    name = "".join(ch for ch in str(data.get("name", "default")).lower() if ch.isalnum() or ch in "._-").strip(".-_") or "default"
    configs.setdefault(key, {}).pop(name, None)
    save_configs()
    return jsonify({"status": "ok"})

# ===== RUN =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
