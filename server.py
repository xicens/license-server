from flask import Flask, request, jsonify
import time, json, os

app = Flask(__name__)

DB_FILE = "keys.json"

# ===== ЗАГРУЗКА =====
if os.path.exists(DB_FILE):
    with open(DB_FILE) as f:
        keys = json.load(f)
else:
    keys = {}

def save():
    with open(DB_FILE, "w") as f:
        json.dump(keys, f, indent=4)

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

# ===== RUN =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)