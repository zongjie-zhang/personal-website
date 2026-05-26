from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
import mysql.connector
import re
import os
import base64
import difflib
import unicodedata
import urllib.request
import urllib.error
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-later")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
app.permanent_session_lifetime = timedelta(days=365)

ADMIN_USER_IDS = {1}


def normalize_url_prefix(prefix):
    prefix = (prefix or "").strip()

    if prefix in {"", "/"}:
        return ""

    if not prefix.startswith("/"):
        prefix = "/" + prefix

    return prefix.rstrip("/")


def normalize_external_base_url(url):
    url = (url or "").strip()

    if url == "":
        return ""

    return url.rstrip("/")


APP_URL_PREFIX = normalize_url_prefix(os.environ.get("APP_URL_PREFIX", ""))
SUPPORTED_PATH_PREFIXES = ["/project/chopin"]


def get_env_bool(name, default=False):
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_production():
    return os.environ.get("FLASK_ENV") == "production" or get_env_bool("PRODUCTION", False)


def get_env_value(*names, default=None):
    for name in names:
        value = os.environ.get(name)

        if value not in {None, ""}:
            return value

    return default


ASSET_BASE_URL = normalize_external_base_url(
    get_env_value("ASSET_BASE_URL", "R2_PUBLIC_BASE_URL", default="")
)
SCORE_BASE_URL = normalize_external_base_url(
    get_env_value("SCORE_BASE_URL", default=ASSET_BASE_URL)
)
AUDIO_BASE_URL = normalize_external_base_url(
    get_env_value("AUDIO_BASE_URL", default=ASSET_BASE_URL)
)
SCORE_URL_VERSION = get_env_value("SCORE_URL_VERSION", default="2")


app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = is_production()


class PathPrefixMiddleware:
    def __init__(self, wsgi_app, prefix=""):
        self.wsgi_app = wsgi_app
        self.prefix = normalize_url_prefix(prefix)

    def __call__(self, environ, start_response):
        path_info = environ.get("PATH_INFO", "") or "/"
        active_prefix = self.prefix

        if active_prefix == "":
            forwarded_prefix = normalize_url_prefix(
                environ.get("HTTP_X_FORWARDED_PREFIX", "")
            )

            if forwarded_prefix:
                active_prefix = forwarded_prefix

        if active_prefix == "":
            for supported_prefix in SUPPORTED_PATH_PREFIXES:
                if (
                    path_info == supported_prefix or
                    path_info.startswith(supported_prefix + "/")
                ):
                    active_prefix = supported_prefix
                    break

        if active_prefix and (
            path_info == active_prefix or path_info.startswith(active_prefix + "/")
        ):
            environ["SCRIPT_NAME"] = active_prefix
            trimmed_path = path_info[len(active_prefix):]
            environ["PATH_INFO"] = trimmed_path if trimmed_path else "/"

        return self.wsgi_app(environ, start_response)


app.wsgi_app = PathPrefixMiddleware(app.wsgi_app, APP_URL_PREFIX)


@app.context_processor
def inject_path_helpers():
    chopin_site_root = request.script_root or "/project/chopin"

    return {
        "app_root": request.script_root or "",
        "static_base_url": url_for("static", filename=""),
        "audio_base_url": AUDIO_BASE_URL,
        "chopin_site_root": chopin_site_root
    }


def get_db_connection():
    return mysql.connector.connect(
        host=get_env_value("DB_HOST", "MYSQLHOST", default="127.0.0.1"),
        user=get_env_value("DB_USER", "MYSQLUSER", default="root"),
        password=get_env_value("DB_PASSWORD", "MYSQLPASSWORD", default="00000000"),
        database=get_env_value("DB_NAME", "MYSQLDATABASE", default="chopin_db"),
        port=int(get_env_value("DB_PORT", "MYSQLPORT", default="3306")),
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci"
    )


def build_asset_url(folder_name, file_name):
    if not file_name:
        return ""

    base_url = ""

    if folder_name == "audio":
        base_url = AUDIO_BASE_URL
    elif folder_name == "score":
        base_url = SCORE_BASE_URL

    if base_url:
        return f"{base_url}/{file_name}"

    return url_for("static", filename=f"{folder_name}/{file_name}")


def build_audio_url(link):
    if not link:
        return ""

    return build_asset_url("audio", os.path.basename(link))


def build_score_url(work_id):
    if work_id is None:
        return ""

    score_source_url = build_score_source_url(work_id)

    if not score_source_url:
        return ""

    separator = "&" if "?" in score_source_url else "?"
    return score_source_url + separator + "v=" + SCORE_URL_VERSION


def build_score_source_url(work_id):
    if work_id is None:
        return ""

    return build_asset_url(
        "score",
        "score_" + str(work_id).zfill(3) + ".pdf"
    )


def get_op_number_from_title(title):
    match = re.search(r"Op\.?\s*(\d+)", title or "", re.IGNORECASE)

    if match:
        return int(match.group(1))

    return 9999


def get_b_number_from_title(title):
    match = re.search(r"\bB\.?\s*(\d+)", title or "", re.IGNORECASE)

    if match:
        return int(match.group(1))

    return 9999


def get_no_number_from_title(title):
    match = re.search(r"No\.?\s*(\d+)", title or "", re.IGNORECASE)

    if match:
        return int(match.group(1))

    return 0


def get_catalog_sort_group_from_title(title):
    title = title or ""

    if re.search(r"Op\.?\s*\d+", title, re.IGNORECASE):
        return 0

    if re.search(r"\bB\.?\s*\d+", title, re.IGNORECASE):
        return 1

    return 2


def catalog_title_sort_key(title):
    return (
        get_catalog_sort_group_from_title(title),
        get_op_number_from_title(title),
        get_b_number_from_title(title),
        get_no_number_from_title(title),
        title or ""
    )


def normalize_search_text(text):
    text = text or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.lower()
    text = re.sub(r"\b(op|b|no)(\d+)\b", r"\1 \2", text)

    replacements = {
        "&": " and ",
        "opus": "op",
        "number": "no",
        "num": "no",
    }

    for old_text, new_text in replacements.items():
        text = re.sub(r"\b" + re.escape(old_text) + r"\b", new_text, text)

    text = re.sub(r"\b(op|b|no)\s*(\d+)\b", r"\1 \2", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def get_search_tokens(text):
    stop_words = {"in", "the", "a", "an", "and", "for", "of"}
    tokens = []

    for token in normalize_search_text(text).split():
        if token in stop_words:
            continue

        if len(token) > 3 and token.endswith("s"):
            token = token[:-1]

        tokens.append(token)

    return tokens


def get_descriptive_search_tokens(text):
    descriptive_tokens = []

    for token in get_search_tokens(text):
        if token in {"op", "b", "no"}:
            continue

        if token.isdigit():
            continue

        descriptive_tokens.append(token)

    return descriptive_tokens


def fuzzy_token_match(token, target_tokens):
    for target_token in target_tokens:
        if token == target_token:
            return True

        if len(token) >= 4 and token in target_token:
            return True

        if len(target_token) >= 4 and target_token in token:
            return True

        if len(token) >= 4 and len(target_token) >= 4:
            ratio = difflib.SequenceMatcher(None, token, target_token).ratio()

            if ratio >= 0.78:
                return True

    return False


def work_matches_descriptive_tokens(work, query_tokens):
    if not query_tokens:
        return True

    fields = [
        work.get("title", ""),
        work.get("genre", ""),
        work.get("musical_key", ""),
        work.get("city", ""),
        work.get("country", ""),
        work.get("performer_name", ""),
        work.get("recording_title", "")
    ]

    target_tokens = []

    for field_text in fields:
        target_tokens.extend(get_search_tokens(field_text))

    for query_token in query_tokens:
        if not fuzzy_token_match(query_token, target_tokens):
            return False

    return True


def get_catalog_query(search_text):
    normalized = normalize_search_text(search_text)

    op_range_match = re.search(r"\bop\s+(\d+)\s+(\d+)\b", normalized)
    op_exact_match = re.search(r"\bop\s+(\d+)\b", normalized)
    b_range_match = re.search(r"\bb\s+(\d+)\s+(\d+)\b", normalized)
    b_exact_match = re.search(r"\bb\s+(\d+)\b", normalized)
    no_match = re.search(r"\bno\s+(\d+)\b", normalized)

    if op_range_match:
        return {
            "type": "opus range",
            "start": int(op_range_match.group(1)),
            "end": int(op_range_match.group(2)),
            "no": int(no_match.group(1)) if no_match else None
        }

    if op_exact_match:
        return {
            "type": "opus number",
            "value": int(op_exact_match.group(1)),
            "no": int(no_match.group(1)) if no_match else None
        }

    if b_range_match:
        return {
            "type": "brown catalogue range",
            "start": int(b_range_match.group(1)),
            "end": int(b_range_match.group(2)),
            "no": int(no_match.group(1)) if no_match else None
        }

    if b_exact_match:
        return {
            "type": "brown catalogue number",
            "value": int(b_exact_match.group(1)),
            "no": int(no_match.group(1)) if no_match else None
        }

    return None


def score_search_result(search_text, work):
    query_tokens = get_search_tokens(search_text)

    if not query_tokens:
        return 0

    title = work["title"] or ""
    genre = work["genre"] or ""
    musical_key = work["musical_key"] or ""
    city = work["city"] or ""
    country = work["country"] or ""
    performer_name = work["performer_name"] or ""
    recording_title = work["recording_title"] or ""
    composition_year = str(work["composition_year"] or "")
    publication_year = str(work["publication_year"] or "")

    fields = {
        "title": title,
        "genre": genre,
        "key": musical_key,
        "place": city + " " + country,
        "recording": performer_name + " " + recording_title,
        "year": composition_year + " " + publication_year
    }

    normalized_fields = {
        field_name: normalize_search_text(field_text)
        for field_name, field_text in fields.items()
    }

    field_tokens = {
        field_name: get_search_tokens(field_text)
        for field_name, field_text in fields.items()
    }

    normalized_query = normalize_search_text(search_text)
    score = 0

    if normalized_query and normalized_query in normalized_fields["title"]:
        score += 120

    exact_field_weights = {
        "title": 36,
        "genre": 28,
        "key": 24,
        "place": 18,
        "recording": 18,
        "year": 16
    }

    fuzzy_field_weights = {
        "title": 22,
        "genre": 16,
        "key": 14,
        "place": 10,
        "recording": 10,
        "year": 8
    }

    for query_token in query_tokens:
        token_matched = False

        for field_name, tokens in field_tokens.items():
            if query_token in tokens:
                score += exact_field_weights[field_name]
                token_matched = True
            elif fuzzy_token_match(query_token, tokens):
                score += fuzzy_field_weights[field_name]
                token_matched = True

        if not token_matched:
            return 0

    if (genre or "").lower() == (search_text or "").strip().lower():
        score += 80

    return score


def get_current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            user_id,
            username,
            avatar_data
        FROM users
        WHERE user_id = %s;
    """, (user_id,))

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    return user


def is_admin_user(user):
    return bool(user and user.get("user_id") in ADMIN_USER_IDS)


def get_favorites_playlist_id(cursor, user_id):
    cursor.execute("""
        SELECT playlist_id
        FROM playlists
        WHERE user_id = %s
        AND playlist_name = 'Favorites'
        LIMIT 1;
    """, (user_id,))

    playlist = cursor.fetchone()

    if playlist:
        return playlist["playlist_id"]

    cursor.execute("""
        INSERT INTO playlists (user_id, playlist_name)
        VALUES (%s, 'Favorites');
    """, (user_id,))

    return cursor.lastrowid


def get_favorite_recording_ids(user_id):
    if not user_id:
        return []

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT pt.recording_id
        FROM playlists p
        JOIN playlist_tracks pt ON p.playlist_id = pt.playlist_id
        WHERE p.user_id = %s
        AND p.playlist_name = 'Favorites';
    """, (user_id,))

    favorite_ids = [row["recording_id"] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return favorite_ids


def get_favorites_playlist(user_id):
    if not user_id:
        return None

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    favorites_playlist_id = get_favorites_playlist_id(cursor, user_id)

    cursor.execute("""
        SELECT
            pt.playlist_track_id,
            pt.track_order,
            r.recording_id,
            r.recording_title,
            r.performer_name,
            r.link,
            w.title AS work_title,
            w.genre,
            w.composition_year
        FROM playlist_tracks pt
        JOIN recordings r ON pt.recording_id = r.recording_id
        JOIN works w ON r.work_id = w.work_id
        WHERE pt.playlist_id = %s
        ORDER BY pt.track_order, pt.playlist_track_id;
    """, (favorites_playlist_id,))

    favorites_tracks = cursor.fetchall()

    for track in favorites_tracks:
        track["audio_url"] = build_audio_url(track.get("link"))

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "playlist_id": favorites_playlist_id,
        "playlist_name": "Favorites",
        "tracks": favorites_tracks
    }


def get_all_recordings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            r.recording_id,
            r.recording_title,
            r.performer_name,
            r.link,
            w.work_id,
            w.title AS work_title,
            w.genre,
            w.composition_year,
            p.place_name,
            p.city,
            p.country,
            d.description_type,
            d.content AS description_content,
            d.source AS description_source
        FROM recordings r
        JOIN works w ON r.work_id = w.work_id
        LEFT JOIN places p ON w.place_id = p.place_id
        LEFT JOIN descriptions d ON w.work_id = d.work_id;
    """)

    recordings = cursor.fetchall()

    for recording in recordings:
        recording["audio_url"] = build_audio_url(recording.get("link"))
        recording["score_path"] = build_score_url(recording.get("work_id"))

    cursor.close()
    conn.close()

    recordings.sort(
        key=lambda recording: catalog_title_sort_key(recording["work_title"])
    )

    return recordings


def get_recording_cover(recording):
    if not recording:
        return ""

    performer = normalize_search_text(recording.get("performer_name", ""))
    title = normalize_search_text(
        recording.get("work_title", "") or recording.get("title", "")
    )
    genre = normalize_search_text(recording.get("genre", ""))
    combined_work_text = title + " " + genre
    cover_folder = url_for("static", filename="image/cover/")

    def cover(file_name):
        return cover_folder + file_name

    if "rubinstein" in performer:
        if "mazurka" in combined_work_text:
            return cover("IMG_9554.JPG")

        if "nocturne" in combined_work_text:
            return cover("IMG_9550.JPG")

        if "waltz" in combined_work_text:
            return cover("IMG_9556.JPG")

    if "pollini" in performer:
        if "etude" in combined_work_text:
            return cover("IMG_9544.JPG")

        if "sonata" in combined_work_text:
            return cover("IMG_9553.JPG")

        if (
            "berceuse" in combined_work_text
            or "scherzo" in combined_work_text
            or "barcarolle" in combined_work_text
        ):
            return cover("IMG_9548.JPG")

    if "zimerman" in performer:
        if "concerto" in combined_work_text:
            return cover("IMG_9547.JPG")

        if (
            "ballade" in combined_work_text
            or "barcarolle" in combined_work_text
            or "fantasy" in combined_work_text
            or "fantaisie" in combined_work_text
        ):
            return cover("IMG_9552.JPG")

    if "argerich" in performer:
        if "prelude" in combined_work_text or "sonata" in combined_work_text:
            return cover("IMG_9555.JPG")

    if ("blechaz" in performer or "blechacz" in performer) and "polonaise" in combined_work_text:
        return cover("IMG_9545.JPG")

    if "bruce" in performer and "liu" in performer:
        return cover("IMG_9546.JPG")

    if "yundi" in performer:
        return cover("IMG_9551.JPG")

    if "sokolov" in performer and "prelude" in combined_work_text:
        return cover("IMG_9543.JPG")

    if "david" in performer and "fray" in performer:
        return cover("IMG_9542.JPG")

    if "laplante" in performer:
        return cover("IMG_9541.JPG")

    if "tianyao" in performer or "lvy" in performer or "lyu" in performer:
        return cover("IMG_9540.JPG")

    return cover("IMG_9549.JPG")


@app.route("/")
def index():
    if request.script_root == "/project/chopin":
        current_user = get_current_user()
        return render_template("app.html", current_user=current_user)

    return render_template("index.html")


@app.route("/project")
def projects():
    return render_template("projects.html")


@app.route("/game")
def games():
    return render_template("games.html")


@app.route("/app")
def app_shell():
    current_user = get_current_user()
    return render_template("app.html", current_user=current_user)


@app.route("/home")
def home():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/test-db")
def test_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                work_id,
                title
            FROM works
            ORDER BY work_id
            LIMIT 10;
        """)

        works = cursor.fetchall()

        cursor.close()
        conn.close()

        output = "<h1>Local MySQL connection works</h1>"
        output += "<p>First 10 works:</p>"

        for work in works:
            output += f"<p>{work['work_id']} - {work['title']}</p>"

        return output

    except mysql.connector.Error as err:
        return (
            "<h1>Database connection error</h1>"
            "<p>" + str(err) + "</p>"
            "<p>Check your local MySQL password, database name, and table names.</p>"
        )


@app.route("/user")
def user():
    current_user = get_current_user()
    favorites_playlist = None

    if current_user:
        favorites_playlist = get_favorites_playlist(current_user["user_id"])

    return render_template(
        "user.html",
        current_user=current_user,
        favorites_playlist=favorites_playlist,
        message=""
    )


@app.route("/register", methods=["POST"])
def register():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if username == "" or password == "":
        return render_template(
            "user.html",
            current_user=None,
            favorites_playlist=None,
            message="Username and password cannot be empty."
        )

    if password != confirm_password:
        return render_template(
            "user.html",
            current_user=None,
            favorites_playlist=None,
            message="Passwords do not match."
        )

    password_hash = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            INSERT INTO users (username, password_hash)
            VALUES (%s, %s);
        """, (username, password_hash))

        session.permanent = True
        session["user_id"] = cursor.lastrowid
        get_favorites_playlist_id(cursor, session["user_id"])

        conn.commit()

    except mysql.connector.Error:
        cursor.close()
        conn.close()

        return render_template(
            "user.html",
            current_user=None,
            favorites_playlist=None,
            message="This username already exists."
        )

    cursor.close()
    conn.close()

    return redirect(url_for("app_shell"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return redirect(url_for("user"))

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            user_id,
            username,
            password_hash,
            avatar_data
        FROM users
        WHERE username = %s;
    """, (username,))

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        return render_template(
            "user.html",
            current_user=None,
            favorites_playlist=None,
            message="Username not found."
        )

    if not check_password_hash(user["password_hash"], password):
        return render_template(
            "user.html",
            current_user=None,
            favorites_playlist=None,
            message="Incorrect password."
        )

    session.permanent = True
    session["user_id"] = user["user_id"]

    return redirect(url_for("app_shell"))


@app.route("/logout")
def logout():
    next_path = request.args.get("next", "/app")

    if not next_path.startswith("/"):
        next_path = "/app"

    session.clear()
    return redirect(next_path)


@app.route("/update_user", methods=["POST"])
def update_user():
    current_user = get_current_user()

    if not current_user:
        return redirect(url_for("user"))

    new_username = request.form.get("username", "").strip()
    avatar_file = request.files.get("avatar")

    if new_username == "":
        return render_template(
            "user.html",
            current_user=current_user,
            favorites_playlist=get_favorites_playlist(current_user["user_id"]),
            message="Username cannot be empty."
        )

    avatar_data = current_user["avatar_data"]

    if avatar_file and avatar_file.filename != "":
        file_bytes = avatar_file.read()
        mime_type = avatar_file.mimetype
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        avatar_data = "data:" + mime_type + ";base64," + encoded

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            UPDATE users
            SET username = %s,
                avatar_data = %s
            WHERE user_id = %s;
        """, (new_username, avatar_data, current_user["user_id"]))

        conn.commit()

    except mysql.connector.Error:
        cursor.close()
        conn.close()

        return render_template(
            "user.html",
            current_user=current_user,
            favorites_playlist=get_favorites_playlist(current_user["user_id"]),
            message="That username is already taken."
        )

    cursor.close()
    conn.close()

    return redirect(url_for("user"))


@app.route("/change_password", methods=["POST"])
def change_password():
    current_user = get_current_user()

    if not current_user:
        return redirect(url_for("user"))

    old_password = request.form.get("old_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT password_hash
        FROM users
        WHERE user_id = %s;
    """, (current_user["user_id"],))

    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()

        session.clear()
        return redirect(url_for("user"))

    if not check_password_hash(user["password_hash"], old_password):
        cursor.close()
        conn.close()

        return render_template(
            "user.html",
            current_user=current_user,
            favorites_playlist=get_favorites_playlist(current_user["user_id"]),
            message="Old password is incorrect."
        )

    if new_password == "" or len(new_password) < 4:
        cursor.close()
        conn.close()

        return render_template(
            "user.html",
            current_user=current_user,
            favorites_playlist=get_favorites_playlist(current_user["user_id"]),
            message="New password should be at least 4 characters."
        )

    if new_password != confirm_password:
        cursor.close()
        conn.close()

        return render_template(
            "user.html",
            current_user=current_user,
            favorites_playlist=get_favorites_playlist(current_user["user_id"]),
            message="New passwords do not match."
        )

    new_hash = generate_password_hash(new_password)

    cursor.execute("""
        UPDATE users
        SET password_hash = %s
        WHERE user_id = %s;
    """, (new_hash, current_user["user_id"]))

    conn.commit()

    cursor.close()
    conn.close()

    return render_template(
        "user.html",
        current_user=get_current_user(),
        favorites_playlist=get_favorites_playlist(current_user["user_id"]),
        message="Password changed."
    )


@app.route("/playlist")
def playlist():
    current_user = get_current_user()

    if not current_user:
        return render_template(
            "playlist.html",
            current_user=None,
            recordings=[],
            playlists=[]
        )

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            r.recording_id,
            r.recording_title,
            r.performer_name,
            r.link,
            w.title AS work_title,
            w.genre,
            w.composition_year,
            p.place_name,
            p.city,
            p.country
        FROM recordings r
        JOIN works w ON r.work_id = w.work_id
        LEFT JOIN places p ON w.place_id = p.place_id;
    """)

    recordings = cursor.fetchall()

    for recording in recordings:
        recording["audio_url"] = build_audio_url(recording.get("link"))

    recordings.sort(
        key=lambda recording: catalog_title_sort_key(recording["work_title"])
    )

    cursor.execute("""
        SELECT
            playlist_id,
            playlist_name
        FROM playlists
        WHERE user_id = %s
        AND playlist_name != 'Favorites'
        ORDER BY
            playlist_id;
    """, (current_user["user_id"],))

    playlists = cursor.fetchall()

    for playlist_item in playlists:
        cursor.execute("""
            SELECT
                pt.playlist_track_id,
                pt.track_order,
                r.recording_id,
                r.recording_title,
                r.performer_name,
                r.link,
                w.title AS work_title,
                w.genre,
                w.composition_year
            FROM playlist_tracks pt
            JOIN recordings r ON pt.recording_id = r.recording_id
            JOIN works w ON r.work_id = w.work_id
            WHERE pt.playlist_id = %s
            ORDER BY pt.track_order, pt.playlist_track_id;
        """, (playlist_item["playlist_id"],))

        playlist_item["tracks"] = cursor.fetchall()

        for track in playlist_item["tracks"]:
            track["audio_url"] = build_audio_url(track.get("link"))

    cursor.close()
    conn.close()

    return render_template(
        "playlist.html",
        current_user=current_user,
        recordings=recordings,
        playlists=playlists
    )


@app.route("/admin")
def admin():
    current_user = get_current_user()
    message = request.args.get("message")

    if not is_admin_user(current_user):
        return render_template(
            "admin.html",
            current_user=current_user,
            is_admin=False,
            users=[],
            total_playlists=0,
            total_tracks=0,
            message=None
        ), 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            user_id,
            username,
            avatar_data
        FROM users
        WHERE user_id != %s
        ORDER BY user_id;
    """, (current_user["user_id"],))

    users = cursor.fetchall()
    total_playlists = 0
    total_tracks = 0

    for user_item in users:
        cursor.execute("""
            SELECT
                playlist_id,
                playlist_name
            FROM playlists
            WHERE user_id = %s
            ORDER BY
                playlist_name = 'Favorites' DESC,
                playlist_id;
        """, (user_item["user_id"],))

        playlists = cursor.fetchall()
        total_playlists += len(playlists)

        for playlist_item in playlists:
            cursor.execute("""
                SELECT
                    pt.playlist_track_id,
                    pt.track_order,
                    r.recording_id,
                    r.recording_title,
                    r.performer_name,
                    w.title AS work_title,
                    w.genre,
                    w.composition_year
                FROM playlist_tracks pt
                JOIN recordings r ON pt.recording_id = r.recording_id
                JOIN works w ON r.work_id = w.work_id
                WHERE pt.playlist_id = %s
                ORDER BY pt.track_order, pt.playlist_track_id;
            """, (playlist_item["playlist_id"],))

            tracks = cursor.fetchall()
            playlist_item["tracks"] = tracks
            total_tracks += len(tracks)

        user_item["playlists"] = playlists
        user_item["playlist_count"] = len(playlists)
        user_item["track_count"] = sum(
            len(playlist_item["tracks"]) for playlist_item in playlists
        )

    cursor.close()
    conn.close()

    return render_template(
        "admin.html",
        current_user=current_user,
        is_admin=True,
        users=users,
        total_playlists=total_playlists,
        total_tracks=total_tracks,
        message=message
    )


@app.route("/admin/delete_user", methods=["POST"])
def admin_delete_user():
    current_user = get_current_user()

    if not is_admin_user(current_user):
        return redirect(url_for("user"))

    user_id = request.form.get("user_id", type=int)

    if not user_id or user_id in ADMIN_USER_IDS:
        return redirect(url_for("admin", message="Admin account cannot be deleted."))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT username
        FROM users
        WHERE user_id = %s;
    """, (user_id,))

    user_to_delete = cursor.fetchone()

    if not user_to_delete:
        cursor.close()
        conn.close()
        return redirect(url_for("admin", message="User not found."))

    cursor.execute("""
        DELETE pt
        FROM playlist_tracks pt
        JOIN playlists p ON pt.playlist_id = p.playlist_id
        WHERE p.user_id = %s;
    """, (user_id,))

    cursor.execute("""
        DELETE FROM playlists
        WHERE user_id = %s;
    """, (user_id,))

    cursor.execute("""
        DELETE FROM users
        WHERE user_id = %s;
    """, (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for(
        "admin",
        message=user_to_delete["username"] + " has been deleted."
    ))


@app.route("/save_playlist", methods=["POST"])
def save_playlist():
    current_user = get_current_user()

    if not current_user:
        return jsonify({
            "success": False,
            "message": "Please log in first."
        })

    data = request.get_json()

    playlist_id = data.get("playlist_id")
    playlist_name = data.get("playlist_name", "").strip()
    tracks = data.get("tracks", [])

    if playlist_name == "":
        return jsonify({
            "success": False,
            "message": "Playlist name cannot be empty."
        })

    if playlist_name.lower() == "favorites":
        return jsonify({
            "success": False,
            "message": "Favorites is reserved for your favorite recordings."
        })

    if len(tracks) == 0:
        return jsonify({
            "success": False,
            "message": "Please add at least one recording."
        })

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if playlist_id:
        cursor.execute("""
            SELECT playlist_id, playlist_name
            FROM playlists
            WHERE playlist_id = %s
            AND user_id = %s;
        """, (playlist_id, current_user["user_id"]))

        existing_playlist = cursor.fetchone()

        if not existing_playlist:
            cursor.close()
            conn.close()

            return jsonify({
                "success": False,
                "message": "Playlist not found."
            })

        if existing_playlist["playlist_name"] == "Favorites":
            cursor.close()
            conn.close()

            return jsonify({
                "success": False,
                "message": "Favorites cannot be edited here."
            })

        cursor.execute("""
            SELECT playlist_id
            FROM playlists
            WHERE user_id = %s
            AND LOWER(playlist_name) = LOWER(%s)
            AND playlist_id != %s;
        """, (current_user["user_id"], playlist_name, playlist_id))

        duplicate_playlist = cursor.fetchone()

        if duplicate_playlist:
            cursor.close()
            conn.close()

            return jsonify({
                "success": False,
                "message": "A playlist with this name already exists. Please choose another name."
            })

        cursor.execute("""
            UPDATE playlists
            SET playlist_name = %s
            WHERE playlist_id = %s
            AND user_id = %s;
        """, (playlist_name, playlist_id, current_user["user_id"]))

        cursor.execute("""
            DELETE FROM playlist_tracks
            WHERE playlist_id = %s;
        """, (playlist_id,))

    else:
        cursor.execute("""
            SELECT playlist_id
            FROM playlists
            WHERE user_id = %s
            AND LOWER(playlist_name) = LOWER(%s);
        """, (current_user["user_id"], playlist_name))

        duplicate_playlist = cursor.fetchone()

        if duplicate_playlist:
            cursor.close()
            conn.close()

            return jsonify({
                "success": False,
                "message": "A playlist with this name already exists. Please choose another name."
            })

        cursor.execute("""
            INSERT INTO playlists (user_id, playlist_name)
            VALUES (%s, %s);
        """, (current_user["user_id"], playlist_name))

        playlist_id = cursor.lastrowid

    for index, recording_id in enumerate(tracks):
        cursor.execute("""
            INSERT INTO playlist_tracks
                (playlist_id, recording_id, track_order)
            VALUES
                (%s, %s, %s);
        """, (playlist_id, recording_id, index))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Playlist saved."
    })


@app.route("/delete_playlist", methods=["POST"])
def delete_playlist():
    current_user = get_current_user()

    if not current_user:
        return jsonify({
            "success": False,
            "message": "Please log in first."
        })

    data = request.get_json()
    playlist_id = data.get("playlist_id")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT playlist_id, playlist_name
        FROM playlists
        WHERE playlist_id = %s
        AND user_id = %s;
    """, (playlist_id, current_user["user_id"]))

    playlist_item = cursor.fetchone()

    if not playlist_item:
        cursor.close()
        conn.close()

        return jsonify({
            "success": False,
            "message": "Playlist not found."
        })

    if playlist_item["playlist_name"] == "Favorites":
        cursor.close()
        conn.close()

        return jsonify({
            "success": False,
            "message": "Favorites cannot be deleted."
        })

    cursor.execute("""
        DELETE FROM playlist_tracks
        WHERE playlist_id = %s;
    """, (playlist_id,))

    cursor.execute("""
        DELETE FROM playlists
        WHERE playlist_id = %s
        AND user_id = %s;
    """, (playlist_id, current_user["user_id"]))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Playlist deleted."
    })


@app.route("/toggle_favorite", methods=["POST"])
def toggle_favorite():
    current_user = get_current_user()

    if not current_user:
        return jsonify({
            "success": False,
            "message": "Please log in first."
        })

    data = request.get_json()
    recording_id = data.get("recording_id")

    if not recording_id:
        return jsonify({
            "success": False,
            "message": "Recording not found."
        })

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT recording_id
        FROM recordings
        WHERE recording_id = %s;
    """, (recording_id,))

    recording = cursor.fetchone()

    if not recording:
        cursor.close()
        conn.close()

        return jsonify({
            "success": False,
            "message": "Recording not found."
        })

    favorites_playlist_id = get_favorites_playlist_id(
        cursor,
        current_user["user_id"]
    )

    cursor.execute("""
        SELECT playlist_track_id
        FROM playlist_tracks
        WHERE playlist_id = %s
        AND recording_id = %s
        LIMIT 1;
    """, (favorites_playlist_id, recording_id))

    favorite_track = cursor.fetchone()

    if favorite_track:
        cursor.execute("""
            DELETE FROM playlist_tracks
            WHERE playlist_track_id = %s;
        """, (favorite_track["playlist_track_id"],))

        favorited = False
    else:
        cursor.execute("""
            SELECT COALESCE(MAX(track_order), -1) + 1 AS next_order
            FROM playlist_tracks
            WHERE playlist_id = %s;
        """, (favorites_playlist_id,))

        next_order = cursor.fetchone()["next_order"]

        cursor.execute("""
            INSERT INTO playlist_tracks
                (playlist_id, recording_id, track_order)
            VALUES
                (%s, %s, %s);
        """, (favorites_playlist_id, recording_id, next_order))

        favorited = True

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "favorited": favorited
    })


@app.route("/works")
def works():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            w.work_id,
            w.title,
            w.genre,
            w.musical_key,
            w.instrument,
            w.composition_year,
            w.publication_year,
            w.duration,
            w.dedicatee,
            p.place_name,
            p.city,
            p.country
        FROM works w
        LEFT JOIN places p ON w.place_id = p.place_id
        ORDER BY w.work_id;
    """)

    works = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("works.html", works=works)


@app.route("/analysis")
def analysis():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            genre,
            COUNT(*) AS count
        FROM works
        GROUP BY genre
        ORDER BY count DESC;
    """)

    genre_counts = cursor.fetchall()

    cursor.execute("""
        SELECT
            p.city,
            p.country,
            COUNT(*) AS count
        FROM works w
        LEFT JOIN places p ON w.place_id = p.place_id
        GROUP BY p.city, p.country
        ORDER BY count DESC;
    """)

    place_counts = cursor.fetchall()

    cursor.execute("""
        SELECT
            MIN(composition_year) AS earliest_year,
            MAX(composition_year) AS latest_year
        FROM works;
    """)

    summary = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "analysis.html",
        genre_counts=genre_counts,
        place_counts=place_counts,
        summary=summary
    )


@app.route("/search", methods=["GET", "POST"])
def search():
    results = []
    search_term = ""
    search_type = ""

    if request.method == "POST":
        search_term = request.form.get("search_term", "").strip()
    else:
        search_term = request.args.get("q", "").strip()

    current_user = get_current_user()
    favorite_recording_ids = []

    if current_user:
        favorite_recording_ids = get_favorite_recording_ids(
            current_user["user_id"]
        )

    if search_term:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                w.work_id,
                w.title,
                w.genre,
                w.musical_key,
                w.instrument,
                w.composition_year,
                w.publication_year,
                w.duration,
                w.dedicatee,
                p.place_name,
                p.city,
                p.country,
                r.recording_id,
                r.recording_title,
                r.performer_name,
                r.link AS recording_link,
                d.description_type,
                d.content AS description_content,
                d.source AS description_source
            FROM works w
            LEFT JOIN places p ON w.place_id = p.place_id
            LEFT JOIN recordings r ON w.work_id = r.work_id
            LEFT JOIN descriptions d ON w.work_id = d.work_id;
        """)

        all_works = cursor.fetchall()

        cursor.close()
        conn.close()

        for work in all_works:
            if work["work_id"] is not None:
                work["score_path"] = build_score_url(work["work_id"])
            else:
                work["score_path"] = ""

            work["audio_url"] = build_audio_url(work.get("recording_link"))
            work["cover_path"] = get_recording_cover(work)

        catalog_query = get_catalog_query(search_term)
        descriptive_tokens = get_descriptive_search_tokens(search_term)
        brown_catalog_only = re.match(
            r"^b\.$",
            (search_term or "").strip(),
            re.IGNORECASE
        )
        year_range_match = re.match(
            r"^(\d{4})\s*-\s*(\d{4})$",
            normalize_search_text(search_term)
        )

        if brown_catalog_only:
            results = [
                work for work in all_works
                if get_b_number_from_title(work["title"]) != 9999
            ]

            search_type = "brown catalogue"

        elif catalog_query and catalog_query["type"] == "opus range":
            start_op = catalog_query["start"]
            end_op = catalog_query["end"]

            if start_op > end_op:
                start_op, end_op = end_op, start_op

            results = [
                work for work in all_works
                if start_op <= get_op_number_from_title(work["title"]) <= end_op
                and (
                    catalog_query["no"] is None
                    or get_no_number_from_title(work["title"]) == catalog_query["no"]
                )
                and work_matches_descriptive_tokens(work, descriptive_tokens)
            ]

            search_type = "opus range"

        elif catalog_query and catalog_query["type"] == "opus number":
            target_op = catalog_query["value"]

            results = [
                work for work in all_works
                if get_op_number_from_title(work["title"]) == target_op
                and (
                    catalog_query["no"] is None
                    or get_no_number_from_title(work["title"]) == catalog_query["no"]
                )
                and work_matches_descriptive_tokens(work, descriptive_tokens)
            ]

            search_type = "opus number"

        elif catalog_query and catalog_query["type"] == "brown catalogue range":
            start_b = catalog_query["start"]
            end_b = catalog_query["end"]

            if start_b > end_b:
                start_b, end_b = end_b, start_b

            results = [
                work for work in all_works
                if start_b <= get_b_number_from_title(work["title"]) <= end_b
                and work_matches_descriptive_tokens(work, descriptive_tokens)
            ]

            search_type = "brown catalogue range"

        elif catalog_query and catalog_query["type"] == "brown catalogue number":
            target_b = catalog_query["value"]

            results = [
                work for work in all_works
                if get_b_number_from_title(work["title"]) == target_b
                and work_matches_descriptive_tokens(work, descriptive_tokens)
            ]

            search_type = "brown catalogue number"

        elif year_range_match:
            start_year = int(year_range_match.group(1))
            end_year = int(year_range_match.group(2))

            if start_year > end_year:
                start_year, end_year = end_year, start_year

            results = [
                work for work in all_works
                if work["composition_year"] is not None
                and start_year <= work["composition_year"] <= end_year
            ]

            search_type = "year range"

        else:
            scored_results = []

            for work in all_works:
                relevance_score = score_search_result(search_term, work)

                if relevance_score > 0:
                    work["_search_score"] = relevance_score
                    scored_results.append(work)

            scored_results.sort(
                key=lambda work: (
                    -work["_search_score"],
                    catalog_title_sort_key(work["title"]),
                    work["genre"] or ""
                )
            )

            results = scored_results
            search_type = "flexible match"

        if search_type == "genre":
            results.sort(
                key=lambda work: catalog_title_sort_key(work["title"])
            )

        elif search_type == "key":
            results.sort(
                key=lambda work: (
                    work["genre"] or "",
                    catalog_title_sort_key(work["title"])
                )
            )

        elif search_type == "place":
            results.sort(
                key=lambda work: (
                    catalog_title_sort_key(work["title"]),
                    work["genre"] or ""
                )
            )

        elif search_type == "year" or search_type == "year range":
            results.sort(
                key=lambda work: (
                    work["composition_year"] or 9999,
                    catalog_title_sort_key(work["title"]),
                    work["genre"] or ""
                )
            )

        elif search_type == "opus number" or search_type == "opus range":
            results.sort(
                key=lambda work: (
                    get_op_number_from_title(work["title"]),
                    get_no_number_from_title(work["title"]),
                    work["genre"] or "",
                    work["title"] or ""
                )
            )

        elif (
            search_type == "brown catalogue"
            or search_type == "brown catalogue number"
            or search_type == "brown catalogue range"
        ):
            results.sort(
                key=lambda work: (
                    get_b_number_from_title(work["title"]),
                    get_no_number_from_title(work["title"]),
                    work["genre"] or "",
                    work["title"] or ""
                )
            )

        elif search_type == "flexible match":
            pass

        else:
            results.sort(
                key=lambda work: (
                    catalog_title_sort_key(work["title"]),
                    work["genre"] or ""
                )
            )

    return render_template(
        "search.html",
        results=results,
        search_term=search_term,
        search_type=search_type,
        current_user=current_user,
        favorite_recording_ids=favorite_recording_ids
    )


@app.route("/recordings")
def recordings():
    recordings = get_all_recordings()
    current_user = get_current_user()
    favorite_recording_ids = []

    for recording in recordings:
        recording["cover_path"] = get_recording_cover(recording)

    if current_user:
        favorite_recording_ids = get_favorite_recording_ids(
            current_user["user_id"]
        )

    return render_template(
        "recordings.html",
        recordings=recordings,
        current_user=current_user,
        favorite_recording_ids=favorite_recording_ids
    )


@app.route("/recording/<int:recording_id>")
def recording_detail(recording_id):
    return_q = request.args.get("return_q", "").strip()
    return_to_search_url = url_for("search", q=return_q) if return_q else url_for("search")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            r.recording_id,
            r.recording_title,
            r.performer_name,
            r.link,
            w.work_id,
            w.title AS work_title,
            w.genre,
            w.musical_key,
            w.instrument,
            w.composition_year,
            w.publication_year,
            w.duration,
            w.dedicatee,
            p.place_name,
            p.city,
            p.country,
            d.description_type,
            d.content AS description_content,
            d.source AS description_source
        FROM recordings r
        JOIN works w ON r.work_id = w.work_id
        LEFT JOIN places p ON w.place_id = p.place_id
        LEFT JOIN descriptions d ON w.work_id = d.work_id
        WHERE r.recording_id = %s;
    """, (recording_id,))

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    if not rows:
        return render_template(
            "recording_detail.html",
            recording=None,
            descriptions=[],
            score_path="",
            cover_path="",
            favorite_recording_ids=[],
            return_to_search_url=return_to_search_url
        )

    recording = rows[0]
    recording["audio_url"] = build_audio_url(recording.get("link"))

    descriptions = []

    for row in rows:
        if row["description_content"]:
            descriptions.append({
                "description_type": row["description_type"],
                "content": row["description_content"],
                "source": row["description_source"]
            })

    score_path = build_score_url(recording["work_id"])
    cover_path = get_recording_cover(recording)
    current_user = get_current_user()
    favorite_recording_ids = []

    if current_user:
        favorite_recording_ids = get_favorite_recording_ids(
            current_user["user_id"]
        )

    return render_template(
        "recording_detail.html",
        recording=recording,
        descriptions=descriptions,
        score_path=score_path,
        cover_path=cover_path,
        favorite_recording_ids=favorite_recording_ids,
        return_to_search_url=return_to_search_url
    )


@app.route("/score/<int:work_id>")
def score_file(work_id):
    score_source_url = build_score_source_url(work_id)

    if score_source_url == "":
        return "Score not found.", 404

    try:
        request_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            )
        }
        score_request = urllib.request.Request(
            score_source_url,
            headers=request_headers
        )

        with urllib.request.urlopen(score_request) as response:
            pdf_bytes = response.read()

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=score_" + str(work_id).zfill(3) + ".pdf"
            }
        )
    except urllib.error.HTTPError as err:
        return f"Score not found. ({err.code})", 404
    except urllib.error.URLError:
        return "Unable to load score.", 502


@app.route("/friends")
def friends():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            f.friend_id,
            f.friend_name,
            f.birth_year,
            f.death_year,
            f.occupation,
            f.relationship_notes,
            f.image_link,
            p.place_name,
            p.city,
            p.country
        FROM friends f
        LEFT JOIN places p ON f.place_id = p.place_id
        ORDER BY f.friend_id;
    """)

    friends = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("friends.html", friends=friends)


@app.route("/performers")
def performers():
    return render_template("performer.html")


@app.route("/healthz")
def healthz():
    return jsonify({
        "ok": True,
        "app": "chopin-app"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5210")),
        debug=get_env_bool("FLASK_DEBUG", True)
    )
