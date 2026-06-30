import json
import os
import random
import sqlite3
import time
import hashlib

from flask import jsonify, render_template, request, send_from_directory, session
from jinja2 import ChoiceLoader, FileSystemLoader
from werkzeug.security import check_password_hash, generate_password_hash


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(MODULE_DIR, "templates")
STATIC_DIR = os.path.join(MODULE_DIR, "static")
DATA_DIR = os.path.join(MODULE_DIR, "data")
DATABASE_PATH = os.environ.get(
    "MY_FOOTPRINT_DB_PATH",
    os.path.join(DATA_DIR, "my_footprint.db"),
)
SESSION_USER_KEY = "my_footprint_user_id"
CAPTCHA_SESSION_KEY = "my_footprint_captcha_answer"
REGISTER_COOLDOWN_SECONDS = 45


def get_footprint_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_footprint_db():
    with get_footprint_db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS maps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS maps_user_id_idx ON maps(user_id, updated_at);

            CREATE TABLE IF NOT EXISTS routes (
                route_pk INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                map_id INTEGER,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                start_lat REAL NOT NULL,
                start_lng REAL NOT NULL,
                end_lat REAL NOT NULL,
                end_lng REAL NOT NULL,
                color TEXT NOT NULL DEFAULT '#ff6a3d',
                trip_date TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE,
                UNIQUE (user_id, id)
            );

            CREATE INDEX IF NOT EXISTS routes_user_id_idx ON routes(user_id);

            CREATE TABLE IF NOT EXISTS friend_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_id INTEGER NOT NULL,
                addressee_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (addressee_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE (requester_id, addressee_id),
                CHECK (requester_id <> addressee_id),
                CHECK (status IN ('pending', 'accepted', 'declined'))
            );

            CREATE TABLE IF NOT EXISTS friendships (
                user_id INTEGER NOT NULL,
                friend_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (friend_id) REFERENCES users(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, friend_id),
                CHECK (user_id <> friend_id)
            );

            CREATE INDEX IF NOT EXISTS friend_requests_addressee_idx
                ON friend_requests(addressee_id, status);
            CREATE INDEX IF NOT EXISTS friendships_friend_id_idx
                ON friendships(friend_id);

            CREATE TABLE IF NOT EXISTS registration_cooldowns (
                client_key TEXT PRIMARY KEY,
                last_registered_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS social_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                actor_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                read_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE CASCADE,
                CHECK (user_id <> actor_id),
                CHECK (type IN ('friend_accepted'))
            );

            CREATE INDEX IF NOT EXISTS social_notifications_user_idx
                ON social_notifications(user_id, read_at, created_at);

            CREATE TABLE IF NOT EXISTS username_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                old_username TEXT NOT NULL,
                new_username TEXT NOT NULL,
                changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS username_changes_user_month_idx
                ON username_changes(user_id, changed_at);
            """
        )
        user_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        if "avatar_data_url" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN avatar_data_url TEXT")
        if "is_private" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN is_private INTEGER NOT NULL DEFAULT 0")
        route_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(routes)").fetchall()
        }
        if "map_id" not in route_columns:
            connection.execute("ALTER TABLE routes ADD COLUMN map_id INTEGER")


def my_footprint_v0():
    return render_template("my_footprint_v0.html")


def my_footprint_static(filename):
    return send_from_directory(STATIC_DIR, filename)


def current_footprint_user(connection):
    user_id = session.get(SESSION_USER_KEY)
    if not user_id:
        return None

    return connection.execute(
        "SELECT id, username, avatar_data_url, is_private FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def require_footprint_user(connection):
    user = current_footprint_user(connection)
    if not user:
        return None, (jsonify({"error": "Sign in first."}), 401)
    return user, None


def client_cooldown_key():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    client_ip = forwarded_for.split(",", 1)[0].strip() or request.remote_addr or "local"
    return f"register:{client_ip}"


def registration_cooldown_remaining(connection):
    row = connection.execute(
        "SELECT last_registered_at FROM registration_cooldowns WHERE client_key = ?",
        (client_cooldown_key(),),
    ).fetchone()
    if not row:
        return 0

    elapsed = time.time() - float(row["last_registered_at"])
    return max(0, int(REGISTER_COOLDOWN_SECONDS - elapsed))


def mark_registration_cooldown(connection):
    connection.execute(
        """
        INSERT INTO registration_cooldowns (client_key, last_registered_at)
        VALUES (?, ?)
        ON CONFLICT(client_key) DO UPDATE SET last_registered_at = excluded.last_registered_at
        """,
        (client_cooldown_key(), time.time()),
    )


def make_captcha_challenge():
    first = random.SystemRandom().randint(2, 12)
    second = random.SystemRandom().randint(2, 12)
    session[CAPTCHA_SESSION_KEY] = str(first + second)
    return {"question": f"{first} + {second} = ?", "cooldownSeconds": 0}


def footprint_captcha():
    with get_footprint_db() as connection:
        challenge = make_captcha_challenge()
        challenge["cooldownSeconds"] = registration_cooldown_remaining(connection)
    return jsonify(challenge)


def footprint_session():
    with get_footprint_db() as connection:
        user = current_footprint_user(connection)

        return jsonify({
            "authenticated": user is not None,
            "user": serialize_public_user(connection, user) if user else None,
        })


def footprint_register():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    password_confirm = str(payload.get("passwordConfirm", ""))
    captcha_answer = str(payload.get("captchaAnswer", "")).strip()

    with get_footprint_db() as connection:
        cooldown_seconds = registration_cooldown_remaining(connection)
        if cooldown_seconds > 0:
            return jsonify({
                "error": f"Please wait {cooldown_seconds} seconds before creating another account.",
                "cooldownSeconds": cooldown_seconds,
            }), 429

    expected_answer = session.get(CAPTCHA_SESSION_KEY)
    if not expected_answer or captcha_answer != expected_answer:
        make_captcha_challenge()
        return jsonify({"error": "Human check failed. Try the new question."}), 400

    username_error = validate_username(username)
    if username_error:
        return jsonify({"error": username_error}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must contain at least 8 characters."}), 400
    if password != password_confirm:
        return jsonify({"error": "Passwords do not match."}), 400

    try:
        with get_footprint_db() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            mark_registration_cooldown(connection)
            session[SESSION_USER_KEY] = cursor.lastrowid
            session.permanent = True
            session.pop(CAPTCHA_SESSION_KEY, None)
    except sqlite3.IntegrityError:
        make_captcha_challenge()
        return jsonify({"error": "That username is already in use."}), 409

    with get_footprint_db() as connection:
        user = connection.execute(
            "SELECT id, username, avatar_data_url, is_private FROM users WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return jsonify({"user": serialize_public_user(connection, user)}), 201


def footprint_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    with get_footprint_db() as connection:
        user = connection.execute(
            "SELECT id, username, password_hash, avatar_data_url, is_private FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Incorrect username or password."}), 401

    session[SESSION_USER_KEY] = user["id"]
    session.permanent = True
    return jsonify({"user": serialize_public_user(connection, user)})


def footprint_logout():
    session.pop(SESSION_USER_KEY, None)
    return jsonify({"ok": True})


def validate_username(username):
    if not 3 <= len(username) <= 32:
        return "Username must be 3 to 32 characters."
    if not username.replace("_", "").replace("-", "").isalnum():
        return "Username may only contain letters, numbers, _ and -."
    return None


def validate_route(route):
    required_text = ("id", "origin", "destination")
    required_number = ("startLat", "startLng", "endLat", "endLng")

    if not isinstance(route, dict):
        raise ValueError("Each route must be an object.")
    if any(not str(route.get(field, "")).strip() for field in required_text):
        raise ValueError("Each route needs an id, origin and destination.")

    normalized = {
        "id": str(route["id"])[:120],
        "origin": str(route["origin"])[:180],
        "destination": str(route["destination"])[:180],
        "color": str(route.get("color", "#ff6a3d"))[:32],
        "trip_date": route.get("tripDate") or None,
        "metadata_json": json.dumps(route.get("metadata", {}), ensure_ascii=False),
    }

    for field in required_number:
        try:
            normalized[field] = float(route[field])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid route coordinate: {field}.") from error

    return normalized


def serialize_route(row):
    return {
        "id": row["id"],
        "origin": row["origin"],
        "destination": row["destination"],
        "startLat": row["start_lat"],
        "startLng": row["start_lng"],
        "endLat": row["end_lat"],
        "endLng": row["end_lng"],
        "color": row["color"],
        "tripDate": row["trip_date"],
        "metadata": json.loads(row["metadata_json"] or "{}"),
    }


def validate_map_name(name):
    name = str(name or "").strip()
    if not name:
        return None, "Map name is required."
    if len(name) > 80:
        return None, "Map name must be 80 characters or fewer."
    return name, None


def ensure_default_map(connection, user_id):
    row = connection.execute(
        "SELECT * FROM maps WHERE user_id = ? ORDER BY created_at, id LIMIT 1",
        (user_id,),
    ).fetchone()
    if not row:
        cursor = connection.execute(
            "INSERT INTO maps (user_id, name) VALUES (?, ?)",
            (user_id, "My Footprint"),
        )
        map_id = cursor.lastrowid
        row = connection.execute("SELECT * FROM maps WHERE id = ?", (map_id,)).fetchone()

    connection.execute(
        "UPDATE routes SET map_id = ? WHERE user_id = ? AND map_id IS NULL",
        (row["id"], user_id),
    )
    return row


def serialize_map(connection, row, include_routes=False):
    route_count = connection.execute(
        "SELECT COUNT(*) AS route_count FROM routes WHERE user_id = ? AND map_id = ?",
        (row["user_id"], row["id"]),
    ).fetchone()["route_count"]
    payload = {
        "id": row["id"],
        "name": row["name"],
        "routeCount": route_count,
    }
    if include_routes:
        payload["routes"] = get_user_routes(connection, row["user_id"], row["id"])
    return payload


def get_user_maps(connection, user_id, include_routes=False):
    ensure_default_map(connection, user_id)
    rows = connection.execute(
        "SELECT * FROM maps WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [serialize_map(connection, row, include_routes) for row in rows]


def get_user_routes(connection, user_id, map_id=None):
    if map_id is None:
        default_map = ensure_default_map(connection, user_id)
        map_id = default_map["id"]
    rows = connection.execute(
        "SELECT * FROM routes WHERE user_id = ? AND map_id = ? ORDER BY created_at, rowid",
        (user_id, map_id),
    ).fetchall()
    return [serialize_route(row) for row in rows]


def get_owned_map(connection, user_id, map_id):
    try:
        map_id = int(map_id)
    except (TypeError, ValueError):
        return None
    return connection.execute(
        "SELECT * FROM maps WHERE id = ? AND user_id = ?",
        (map_id, user_id),
    ).fetchone()


def serialize_user(row):
    return {"id": row["id"], "username": row["username"]}


def row_value(row, key, default=None):
    if row is None:
        return default
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def avatar_for_username(username):
    digest = hashlib.sha1(username.encode("utf-8")).hexdigest()
    hue = int(digest[:2], 16) % 360
    initial = next(iter(username.strip()), "?").upper()
    return {
        "initial": initial,
        "color": f"hsl({hue}, 72%, 58%)",
    }


def avatar_for_user(row):
    avatar_data_url = row_value(row, "avatar_data_url")
    if avatar_data_url:
        return {"imageUrl": avatar_data_url}
    return avatar_for_username(row_value(row, "username", "?"))


def country_from_place(place):
    parts = [part.strip() for part in str(place or "").split(",") if part.strip()]
    return parts[-1] if len(parts) > 1 else None


def get_user_stats(connection, user_id):
    rows = connection.execute(
        "SELECT origin, destination FROM routes WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    countries = set()
    for row in rows:
        for field in ("origin", "destination"):
            country = country_from_place(row[field])
            if country:
                countries.add(country)
    return {
        "journeyCount": len(rows),
        "countryCount": len(countries),
    }


def serialize_public_user(connection, row, viewer_id=None):
    user = serialize_user(row)
    user["avatar"] = avatar_for_user(row)
    user["isPrivate"] = bool(row_value(row, "is_private", 0))
    user["stats"] = get_user_stats(connection, user["id"])
    if viewer_id is not None:
        user["state"] = get_friendship_state(connection, viewer_id, user["id"])
    return user


def serialize_notification(connection, row, viewer_id):
    actor = {
        "id": row["actor_id"],
        "username": row["actor_username"],
        "avatar_data_url": row["actor_avatar_data_url"],
    }
    return {
        "id": row["id"],
        "type": row["type"],
        "read": row["read_at"] is not None,
        "createdAt": row["created_at"],
        "actor": serialize_public_user(connection, actor, viewer_id),
    }


def are_friends(connection, user_id, friend_id):
    return connection.execute(
        "SELECT 1 FROM friendships WHERE user_id = ? AND friend_id = ?",
        (user_id, friend_id),
    ).fetchone() is not None


def get_friendship_state(connection, user_id, other_id):
    if user_id == other_id:
        return "self"
    if are_friends(connection, user_id, other_id):
        return "friends"

    outgoing = connection.execute(
        """
        SELECT status FROM friend_requests
        WHERE requester_id = ? AND addressee_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (user_id, other_id),
    ).fetchone()
    if outgoing and outgoing["status"] == "pending":
        return "outgoing"

    incoming = connection.execute(
        """
        SELECT status FROM friend_requests
        WHERE requester_id = ? AND addressee_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (other_id, user_id),
    ).fetchone()
    if incoming and incoming["status"] == "pending":
        return "incoming"

    return "none"


def footprint_social_overview():
    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        friends = connection.execute(
            """
            SELECT users.id, users.username, users.avatar_data_url, users.is_private
            FROM friendships
            JOIN users ON users.id = friendships.friend_id
            WHERE friendships.user_id = ?
            """,
            (user["id"],),
        ).fetchall()
        incoming = connection.execute(
            """
            SELECT
                friend_requests.id,
                users.id AS user_id,
                users.username,
                users.avatar_data_url,
                users.is_private,
                friend_requests.created_at
            FROM friend_requests
            JOIN users ON users.id = friend_requests.requester_id
            WHERE friend_requests.addressee_id = ? AND friend_requests.status = 'pending'
            ORDER BY friend_requests.created_at DESC
            """,
            (user["id"],),
        ).fetchall()
        outgoing = connection.execute(
            """
            SELECT
                friend_requests.id,
                users.id AS user_id,
                users.username,
                users.avatar_data_url,
                users.is_private,
                friend_requests.created_at
            FROM friend_requests
            JOIN users ON users.id = friend_requests.addressee_id
            WHERE friend_requests.requester_id = ? AND friend_requests.status = 'pending'
            ORDER BY friend_requests.created_at DESC
            """,
            (user["id"],),
        ).fetchall()
        notifications = connection.execute(
            """
            SELECT
                social_notifications.id,
                social_notifications.type,
                social_notifications.read_at,
                social_notifications.created_at,
                users.id AS actor_id,
                users.username AS actor_username,
                users.avatar_data_url AS actor_avatar_data_url
            FROM social_notifications
            JOIN users ON users.id = social_notifications.actor_id
            WHERE social_notifications.user_id = ?
            ORDER BY social_notifications.created_at DESC, social_notifications.id DESC
            LIMIT 30
            """,
            (user["id"],),
        ).fetchall()

        return jsonify({
            "friends": [serialize_public_user(connection, friend, user["id"]) for friend in friends],
            "incoming": [
                {"id": row["id"], "user": serialize_public_user(
                    connection,
                    {
                        "id": row["user_id"],
                        "username": row["username"],
                        "avatar_data_url": row["avatar_data_url"],
                        "is_private": row["is_private"],
                    },
                    user["id"],
                )}
                for row in incoming
            ],
            "outgoing": [
                {"id": row["id"], "user": serialize_public_user(
                    connection,
                    {
                        "id": row["user_id"],
                        "username": row["username"],
                        "avatar_data_url": row["avatar_data_url"],
                        "is_private": row["is_private"],
                    },
                    user["id"],
                )}
                for row in outgoing
            ],
            "notifications": [
                serialize_notification(connection, row, user["id"])
                for row in notifications
            ],
        })


def footprint_search_users():
    query = str(request.args.get("q", "")).strip()
    if len(query) < 1:
        return jsonify({"users": []})

    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        rows = connection.execute(
            """
            SELECT id, username, avatar_data_url, is_private FROM users
            WHERE username LIKE ? COLLATE NOCASE AND id <> ?
            ORDER BY username COLLATE NOCASE
            LIMIT 12
            """,
            (f"%{query}%", user["id"]),
        ).fetchall()

        users = [serialize_public_user(connection, row, user["id"]) for row in rows]

    return jsonify({"users": users})


def footprint_send_friend_request():
    payload = request.get_json(silent=True) or {}
    addressee_id = payload.get("userId")

    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        try:
            addressee_id = int(addressee_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Choose a valid user."}), 400

        if addressee_id == user["id"]:
            return jsonify({"error": "You cannot add yourself."}), 400
        if are_friends(connection, user["id"], addressee_id):
            return jsonify({"error": "You are already friends."}), 409

        addressee = connection.execute(
            "SELECT id FROM users WHERE id = ?",
            (addressee_id,),
        ).fetchone()
        if not addressee:
            return jsonify({"error": "User not found."}), 404

        incoming = connection.execute(
            """
            SELECT id FROM friend_requests
            WHERE requester_id = ? AND addressee_id = ? AND status = 'pending'
            """,
            (addressee_id, user["id"]),
        ).fetchone()
        if incoming:
            return accept_friend_request_by_id(connection, user["id"], incoming["id"])

        try:
            connection.execute(
                """
                INSERT INTO friend_requests (requester_id, addressee_id, status)
                VALUES (?, ?, 'pending')
                ON CONFLICT(requester_id, addressee_id) DO UPDATE SET
                    status = 'pending',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user["id"], addressee_id),
            )
        except sqlite3.IntegrityError:
            return jsonify({"error": "Could not send that request."}), 400

    return jsonify({"ok": True})


def accept_friend_request_by_id(connection, user_id, request_id):
    row = connection.execute(
        """
        SELECT * FROM friend_requests
        WHERE id = ? AND addressee_id = ? AND status = 'pending'
        """,
        (request_id, user_id),
    ).fetchone()
    if not row:
        return jsonify({"error": "Friend request not found."}), 404

    connection.execute(
        "UPDATE friend_requests SET status = 'accepted', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (request_id,),
    )
    connection.execute(
        "INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)",
        (row["requester_id"], row["addressee_id"]),
    )
    connection.execute(
        "INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)",
        (row["addressee_id"], row["requester_id"]),
    )
    connection.execute(
        """
        INSERT INTO social_notifications (user_id, actor_id, type)
        SELECT ?, ?, 'friend_accepted'
        WHERE NOT EXISTS (
            SELECT 1 FROM social_notifications
            WHERE user_id = ?
                AND actor_id = ?
                AND type = 'friend_accepted'
                AND created_at >= datetime('now', '-1 day')
        )
        """,
        (
            row["requester_id"],
            row["addressee_id"],
            row["requester_id"],
            row["addressee_id"],
        ),
    )
    return jsonify({"ok": True})


def footprint_accept_friend_request(request_id):
    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        return accept_friend_request_by_id(connection, user["id"], request_id)


def footprint_decline_friend_request(request_id):
    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        row = connection.execute(
            """
            SELECT id FROM friend_requests
            WHERE id = ? AND addressee_id = ? AND status = 'pending'
            """,
            (request_id, user["id"]),
        ).fetchone()
        if not row:
            return jsonify({"error": "Friend request not found."}), 404

        connection.execute(
            "UPDATE friend_requests SET status = 'declined', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (request_id,),
        )

    return jsonify({"ok": True})


def footprint_cancel_friend_request(request_id):
    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        cursor = connection.execute(
            """
            DELETE FROM friend_requests
            WHERE id = ? AND requester_id = ? AND status = 'pending'
            """,
            (request_id, user["id"]),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Friend request not found."}), 404

    return jsonify({"ok": True})


def footprint_unfollow_friend(friend_id):
    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        try:
            friend_id = int(friend_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Friend not found."}), 404

        if not are_friends(connection, user["id"], friend_id):
            return jsonify({"error": "That user is not in your friend list."}), 404

        connection.execute(
            """
            DELETE FROM friendships
            WHERE (user_id = ? AND friend_id = ?)
                OR (user_id = ? AND friend_id = ?)
            """,
            (user["id"], friend_id, friend_id, user["id"]),
        )
        connection.execute(
            """
            UPDATE friend_requests
            SET status = 'declined', updated_at = CURRENT_TIMESTAMP
            WHERE (
                    requester_id = ? AND addressee_id = ?
                ) OR (
                    requester_id = ? AND addressee_id = ?
                )
            """,
            (user["id"], friend_id, friend_id, user["id"]),
        )

    return jsonify({"ok": True})


def footprint_friend_routes(friend_id):
    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        try:
            friend_id = int(friend_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Friend not found."}), 404

        friend = connection.execute(
            "SELECT id, username, avatar_data_url, is_private FROM users WHERE id = ?",
            (friend_id,),
        ).fetchone()
        if not friend or not are_friends(connection, user["id"], friend_id):
            return jsonify({"error": "Only accepted friends can share footprints."}), 403

        return jsonify({
            "friend": serialize_public_user(connection, friend, user["id"]),
            "routes": get_user_routes(connection, friend_id),
        })


def footprint_public_routes(username):
    username = str(username or "").strip()
    if not username:
        return jsonify({"error": "Footprint not found."}), 404

    with get_footprint_db() as connection:
        viewer = current_footprint_user(connection)
        user = connection.execute(
            "SELECT id, username, avatar_data_url, is_private FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()

        if not user:
            return jsonify({"error": "Footprint not found."}), 404

        viewer_id = viewer["id"] if viewer else None
        is_own_footprint = viewer_id == user["id"]
        can_view_private = (
            not bool(row_value(user, "is_private", 0))
            or is_own_footprint
            or (viewer_id is not None and are_friends(connection, viewer_id, user["id"]))
        )
        if not can_view_private:
            return jsonify({
                "error": "This account is private. Send a friend request first.",
                "user": serialize_public_user(connection, user, viewer_id),
            }), 403

        return jsonify({
            "user": serialize_public_user(connection, user, viewer_id),
            "routes": get_user_routes(connection, user["id"]),
        })


def username_change_used_this_month(connection, user_id):
    row = connection.execute(
        """
        SELECT 1 FROM username_changes
        WHERE user_id = ?
            AND strftime('%Y-%m', changed_at) = strftime('%Y-%m', 'now')
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    return row is not None


def footprint_profile_username():
    payload = request.get_json(silent=True) or {}
    new_username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    username_error = validate_username(new_username)
    if username_error:
        return jsonify({"error": username_error}), 400

    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        current = connection.execute(
            "SELECT id, username, password_hash, avatar_data_url, is_private FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()
        if not current or not check_password_hash(current["password_hash"], password):
            return jsonify({"error": "Incorrect password."}), 401
        if current["username"].lower() == new_username.lower():
            return jsonify({"error": "That is already your username."}), 400
        if username_change_used_this_month(connection, current["id"]):
            return jsonify({"error": "You can change your username once per month."}), 429

        try:
            connection.execute(
                "UPDATE users SET username = ? WHERE id = ?",
                (new_username, current["id"]),
            )
            connection.execute(
                """
                INSERT INTO username_changes (user_id, old_username, new_username)
                VALUES (?, ?, ?)
                """,
                (current["id"], current["username"], new_username),
            )
        except sqlite3.IntegrityError:
            return jsonify({"error": "That username is already in use."}), 409

        updated_user = connection.execute(
            "SELECT id, username, avatar_data_url, is_private FROM users WHERE id = ?",
            (current["id"],),
        ).fetchone()
        return jsonify({"user": serialize_public_user(connection, updated_user)})


def footprint_profile_avatar():
    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        if request.method == "DELETE":
            connection.execute(
                "UPDATE users SET avatar_data_url = NULL WHERE id = ?",
                (user["id"],),
            )
        else:
            payload = request.get_json(silent=True) or {}
            avatar_data_url = str(payload.get("avatarDataUrl", "")).strip()
            if not avatar_data_url.startswith("data:image/"):
                return jsonify({"error": "Upload an image file."}), 400
            if avatar_data_url.startswith("data:image/svg"):
                return jsonify({"error": "SVG avatars are not supported."}), 400
            if len(avatar_data_url) > 750000:
                return jsonify({"error": "Avatar image is too large. Try a smaller image."}), 400
            connection.execute(
                "UPDATE users SET avatar_data_url = ? WHERE id = ?",
                (avatar_data_url, user["id"]),
            )

        updated_user = connection.execute(
            "SELECT id, username, avatar_data_url, is_private FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()
        return jsonify({"user": serialize_public_user(connection, updated_user)})


def footprint_profile_privacy():
    payload = request.get_json(silent=True) or {}
    is_private = bool(payload.get("isPrivate"))

    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        connection.execute(
            "UPDATE users SET is_private = ? WHERE id = ?",
            (1 if is_private else 0, user["id"]),
        )
        updated_user = connection.execute(
            "SELECT id, username, avatar_data_url, is_private FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()
        return jsonify({"user": serialize_public_user(connection, updated_user)})


def footprint_mark_notifications_read():
    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        connection.execute(
            """
            UPDATE social_notifications
            SET read_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND read_at IS NULL
            """,
            (user["id"],),
        )

    return jsonify({"ok": True})


def upsert_route(connection, user_id, route, map_id=None):
    if map_id is None:
        map_id = ensure_default_map(connection, user_id)["id"]
    connection.execute(
        """
        INSERT INTO routes (
            id, user_id, map_id, origin, destination, start_lat, start_lng,
            end_lat, end_lng, color, trip_date, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, id) DO UPDATE SET
            map_id = excluded.map_id,
            origin = excluded.origin,
            destination = excluded.destination,
            start_lat = excluded.start_lat,
            start_lng = excluded.start_lng,
            end_lat = excluded.end_lat,
            end_lng = excluded.end_lng,
            color = excluded.color,
            trip_date = excluded.trip_date,
            metadata_json = excluded.metadata_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            route["id"], user_id, map_id, route["origin"], route["destination"],
            route["startLat"], route["startLng"], route["endLat"],
            route["endLng"], route["color"], route["trip_date"],
            route["metadata_json"],
        ),
    )


def footprint_routes():
    with get_footprint_db() as connection:
        user = current_footprint_user(connection)
        if not user:
            return jsonify({"error": "Sign in to sync routes."}), 401
        default_map = ensure_default_map(connection, user["id"])

        if request.method == "GET":
            return jsonify({"routes": get_user_routes(connection, user["id"], default_map["id"])})

        payload = request.get_json(silent=True) or {}
        incoming_routes = payload.get("routes", [])
        if not isinstance(incoming_routes, list) or len(incoming_routes) > 5000:
            return jsonify({"error": "Invalid route list."}), 400

        try:
            normalized_routes = [validate_route(route) for route in incoming_routes]
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        for route in normalized_routes:
            upsert_route(connection, user["id"], route, default_map["id"])

        incoming_ids = [route["id"] for route in normalized_routes]
        if incoming_ids:
            placeholders = ",".join("?" for _ in incoming_ids)
            connection.execute(
                f"DELETE FROM routes WHERE user_id = ? AND map_id = ? AND id NOT IN ({placeholders})",
                [user["id"], default_map["id"], *incoming_ids],
            )
        else:
            connection.execute(
                "DELETE FROM routes WHERE user_id = ? AND map_id = ?",
                (user["id"], default_map["id"]),
            )

        return jsonify({"routes": get_user_routes(connection, user["id"], default_map["id"])})


def footprint_maps():
    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        if request.method == "GET":
            return jsonify({"maps": get_user_maps(connection, user["id"], include_routes=True)})

        payload = request.get_json(silent=True) or {}
        name, name_error = validate_map_name(payload.get("name"))
        if name_error:
            return jsonify({"error": name_error}), 400

        incoming_routes = payload.get("routes", [])
        if not isinstance(incoming_routes, list) or len(incoming_routes) > 5000:
            return jsonify({"error": "Invalid route list."}), 400
        try:
            normalized_routes = [validate_route(route) for route in incoming_routes]
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        cursor = connection.execute(
            "INSERT INTO maps (user_id, name) VALUES (?, ?)",
            (user["id"], name),
        )
        map_id = cursor.lastrowid
        for route in normalized_routes:
            upsert_route(connection, user["id"], route, map_id)
        row = get_owned_map(connection, user["id"], map_id)
        return jsonify({"map": serialize_map(connection, row, include_routes=True)}), 201


def footprint_map_detail(map_id):
    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error

        row = get_owned_map(connection, user["id"], map_id)
        if not row:
            return jsonify({"error": "Map not found."}), 404

        if request.method == "DELETE":
            connection.execute(
                "DELETE FROM routes WHERE user_id = ? AND map_id = ?",
                (user["id"], row["id"]),
            )
            connection.execute("DELETE FROM maps WHERE id = ?", (row["id"],))
            ensure_default_map(connection, user["id"])
            return jsonify({"maps": get_user_maps(connection, user["id"], include_routes=True)})

        payload = request.get_json(silent=True) or {}
        name, name_error = validate_map_name(payload.get("name"))
        if name_error:
            return jsonify({"error": name_error}), 400
        connection.execute(
            "UPDATE maps SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (name, row["id"]),
        )
        updated = get_owned_map(connection, user["id"], row["id"])
        return jsonify({"map": serialize_map(connection, updated, include_routes=True)})


def footprint_map_routes(map_id):
    payload = request.get_json(silent=True) or {}
    incoming_routes = payload.get("routes", [])
    if not isinstance(incoming_routes, list) or len(incoming_routes) > 5000:
        return jsonify({"error": "Invalid route list."}), 400
    try:
        normalized_routes = [validate_route(route) for route in incoming_routes]
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    with get_footprint_db() as connection:
        user, error = require_footprint_user(connection)
        if error:
            return error
        row = get_owned_map(connection, user["id"], map_id)
        if not row:
            return jsonify({"error": "Map not found."}), 404

        for route in normalized_routes:
            upsert_route(connection, user["id"], route, row["id"])
        incoming_ids = [route["id"] for route in normalized_routes]
        if incoming_ids:
            placeholders = ",".join("?" for _ in incoming_ids)
            connection.execute(
                f"DELETE FROM routes WHERE user_id = ? AND map_id = ? AND id NOT IN ({placeholders})",
                [user["id"], row["id"], *incoming_ids],
            )
        else:
            connection.execute(
                "DELETE FROM routes WHERE user_id = ? AND map_id = ?",
                (user["id"], row["id"]),
            )
        connection.execute("UPDATE maps SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
        updated = get_owned_map(connection, user["id"], row["id"])
        return jsonify({"map": serialize_map(connection, updated, include_routes=True)})


def footprint_import_routes():
    payload = request.get_json(silent=True) or {}
    incoming_routes = payload.get("routes", [])
    if not isinstance(incoming_routes, list) or len(incoming_routes) > 5000:
        return jsonify({"error": "Invalid route list."}), 400

    try:
        normalized_routes = [validate_route(route) for route in incoming_routes]
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    with get_footprint_db() as connection:
        user = current_footprint_user(connection)
        if not user:
            return jsonify({"error": "Sign in to import routes."}), 401

        existing_ids = {
            row["id"] for row in connection.execute(
                "SELECT id FROM routes WHERE user_id = ?",
                (user["id"],),
            ).fetchall()
        }
        for route in normalized_routes:
            if route["id"] not in existing_ids:
                upsert_route(connection, user["id"], route)

        return jsonify({"routes": get_user_routes(connection, user["id"])})


def register_my_footprint_v0(app):
    initialize_footprint_db()
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(TEMPLATE_DIR),
        app.jinja_loader,
    ])

    app.add_url_rule("/project/my-footprint-v0", "my_footprint_v0", my_footprint_v0, strict_slashes=False)

    def add_footprint_routes(prefix, endpoint_prefix):
        app.add_url_rule(f"{prefix}/static/<path:filename>", f"{endpoint_prefix}_static", my_footprint_static)
        app.add_url_rule(f"{prefix}/api/session", f"{endpoint_prefix}_session", footprint_session)
        app.add_url_rule(f"{prefix}/api/register", f"{endpoint_prefix}_register", footprint_register, methods=["POST"])
        app.add_url_rule(f"{prefix}/api/captcha", f"{endpoint_prefix}_captcha", footprint_captcha)
        app.add_url_rule(f"{prefix}/api/login", f"{endpoint_prefix}_login", footprint_login, methods=["POST"])
        app.add_url_rule(f"{prefix}/api/logout", f"{endpoint_prefix}_logout", footprint_logout, methods=["POST"])
        app.add_url_rule(
            f"{prefix}/api/profile/avatar",
            f"{endpoint_prefix}_profile_avatar",
            footprint_profile_avatar,
            methods=["PUT", "DELETE"],
        )
        app.add_url_rule(
            f"{prefix}/api/profile/username",
            f"{endpoint_prefix}_profile_username",
            footprint_profile_username,
            methods=["PUT"],
        )
        app.add_url_rule(
            f"{prefix}/api/profile/privacy",
            f"{endpoint_prefix}_profile_privacy",
            footprint_profile_privacy,
            methods=["PUT"],
        )
        app.add_url_rule(
            f"{prefix}/api/notifications/read",
            f"{endpoint_prefix}_notifications_read",
            footprint_mark_notifications_read,
            methods=["POST"],
        )
        app.add_url_rule(f"{prefix}/api/routes", f"{endpoint_prefix}_routes", footprint_routes, methods=["GET", "PUT"])
        app.add_url_rule(
            f"{prefix}/api/routes/import",
            f"{endpoint_prefix}_import_routes",
            footprint_import_routes,
            methods=["POST"],
        )
        app.add_url_rule(f"{prefix}/api/maps", f"{endpoint_prefix}_maps", footprint_maps, methods=["GET", "POST"])
        app.add_url_rule(
            f"{prefix}/api/maps/<int:map_id>",
            f"{endpoint_prefix}_map_detail",
            footprint_map_detail,
            methods=["PUT", "DELETE"],
        )
        app.add_url_rule(
            f"{prefix}/api/maps/<int:map_id>/routes",
            f"{endpoint_prefix}_map_routes",
            footprint_map_routes,
            methods=["PUT"],
        )
        app.add_url_rule(f"{prefix}/api/social", f"{endpoint_prefix}_social", footprint_social_overview)
        app.add_url_rule(f"{prefix}/api/users/search", f"{endpoint_prefix}_search_users", footprint_search_users)
        app.add_url_rule(
            f"{prefix}/api/friend-requests",
            f"{endpoint_prefix}_send_friend_request",
            footprint_send_friend_request,
            methods=["POST"],
        )
        app.add_url_rule(
            f"{prefix}/api/friend-requests/<int:request_id>/accept",
            f"{endpoint_prefix}_accept_friend_request",
            footprint_accept_friend_request,
            methods=["POST"],
        )
        app.add_url_rule(
            f"{prefix}/api/friend-requests/<int:request_id>/decline",
            f"{endpoint_prefix}_decline_friend_request",
            footprint_decline_friend_request,
            methods=["POST"],
        )
        app.add_url_rule(
            f"{prefix}/api/friend-requests/<int:request_id>",
            f"{endpoint_prefix}_cancel_friend_request",
            footprint_cancel_friend_request,
            methods=["DELETE"],
        )
        app.add_url_rule(
            f"{prefix}/api/friends/<int:friend_id>",
            f"{endpoint_prefix}_unfollow_friend",
            footprint_unfollow_friend,
            methods=["DELETE"],
        )
        app.add_url_rule(
            f"{prefix}/api/friends/<int:friend_id>/routes",
            f"{endpoint_prefix}_friend_routes",
            footprint_friend_routes,
        )
        app.add_url_rule(
            f"{prefix}/api/public-footprint/<username>",
            f"{endpoint_prefix}_public_routes",
            footprint_public_routes,
        )

    add_footprint_routes("/project/my-footprint-v0", "my_footprint_v0")
