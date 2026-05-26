from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector
import re
import os
import base64
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-later")


def get_db_connection():
    return mysql.connector.connect(
        host="warren.sewanee.edu",
        user="zhangz0_ADM",
        password="james",
        database="zhangz0"
    )


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
        LEFT JOIN descriptions d ON w.work_id = d.work_id
        ORDER BY w.work_id;
    """)

    recordings = cursor.fetchall()

    cursor.close()
    conn.close()

    return recordings


@app.route("/")
def index():
    current_user = get_current_user()
    return render_template("app.html", current_user=current_user)


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


@app.route("/user")
def user():
    current_user = get_current_user()

    return render_template(
        "user.html",
        current_user=current_user,
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
            message="Username and password cannot be empty."
        )

    if password != confirm_password:
        return render_template(
            "user.html",
            current_user=None,
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

        conn.commit()

        session["user_id"] = cursor.lastrowid

    except mysql.connector.Error:
        cursor.close()
        conn.close()

        return render_template(
            "user.html",
            current_user=None,
            message="This username already exists."
        )

    cursor.close()
    conn.close()

    return redirect(url_for("user"))


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
            message="Username not found."
        )

    if not check_password_hash(user["password_hash"], password):
        return render_template(
            "user.html",
            current_user=None,
            message="Incorrect password."
        )

    session["user_id"] = user["user_id"]

    return redirect(url_for("user"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("user"))


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
            message="Old password is incorrect."
        )

    if new_password == "" or len(new_password) < 4:
        cursor.close()
        conn.close()

        return render_template(
            "user.html",
            current_user=current_user,
            message="New password should be at least 4 characters."
        )

    if new_password != confirm_password:
        cursor.close()
        conn.close()

        return render_template(
            "user.html",
            current_user=current_user,
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
        LEFT JOIN places p ON w.place_id = p.place_id
        ORDER BY w.title;
    """)
    recordings = cursor.fetchall()

    cursor.execute("""
        SELECT
            playlist_id,
            playlist_name
        FROM playlists
        WHERE user_id = %s
        ORDER BY playlist_id;
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

    cursor.close()
    conn.close()

    return render_template(
        "playlist.html",
        current_user=current_user,
        recordings=recordings,
        playlists=playlists
    )


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

    if len(tracks) == 0:
        return jsonify({
            "success": False,
            "message": "Please add at least one recording."
        })

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if playlist_id:
        cursor.execute("""
            SELECT playlist_id
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
        SELECT playlist_id
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

    def get_op_number(title):
        match = re.search(r"Op\.?\s*(\d+)", title or "", re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 9999

    def get_no_number(title):
        match = re.search(r"No\.?\s*(\d+)", title or "", re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 0

    def normalize_text(text):
        if text is None:
            return ""

        text = text.lower()
        text = text.replace(",", " ")
        text = text.replace(".", " ")
        text = text.replace("-", " ")

        text = re.sub(r"\bno\s*\d+\b", " ", text)

        small_words = {"in", "the", "a", "an", "and", "for", "of"}
        words = text.split()
        words = [word for word in words if word not in small_words]

        return " ".join(words)

    def flexible_title_match(search_text, title):
        normalized_search = normalize_text(search_text)
        normalized_title = normalize_text(title)

        search_words = normalized_search.split()

        if not search_words:
            return False

        for word in search_words:
            if word not in normalized_title:
                return False

        return True

    if request.method == "POST":
        search_term = request.form.get("search_term", "").strip()
    else:
        search_term = request.args.get("q", "").strip()

    if search_term:
        lower_search = search_term.lower()

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
                work["score_path"] = "/static/score/score_" + str(work["work_id"]).zfill(3) + ".pdf"
            else:
                work["score_path"] = ""

        op_range_match = re.match(r"^op\.?\s*(\d+)\s*-\s*(\d+)$", lower_search)
        op_exact_match = re.match(r"^op\.?\s*(\d+)$", lower_search)
        year_range_match = re.match(r"^(\d{4})\s*-\s*(\d{4})$", lower_search)

        if op_range_match:
            start_op = int(op_range_match.group(1))
            end_op = int(op_range_match.group(2))

            if start_op > end_op:
                start_op, end_op = end_op, start_op

            results = [
                work for work in all_works
                if start_op <= get_op_number(work["title"]) <= end_op
            ]

            search_type = "opus range"

        elif op_exact_match:
            target_op = int(op_exact_match.group(1))

            results = [
                work for work in all_works
                if get_op_number(work["title"]) == target_op
            ]

            search_type = "opus number"

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
            for work in all_works:
                title = work["title"] or ""
                genre = work["genre"] or ""
                musical_key = work["musical_key"] or ""
                city = work["city"] or ""
                country = work["country"] or ""
                performer_name = work["performer_name"] or ""
                recording_title = work["recording_title"] or ""

                composition_year = str(work["composition_year"] or "")
                publication_year = str(work["publication_year"] or "")

                title_match = flexible_title_match(search_term, title)

                normal_match = (
                    lower_search in title.lower()
                    or lower_search in genre.lower()
                    or lower_search in musical_key.lower()
                    or lower_search in city.lower()
                    or lower_search in country.lower()
                    or lower_search in performer_name.lower()
                    or lower_search in recording_title.lower()
                    or lower_search in composition_year
                    or lower_search in publication_year
                )

                if title_match or normal_match:
                    results.append(work)

            if search_term.isdigit():
                search_type = "year"

            else:
                for work in results:
                    if work["genre"] and lower_search in work["genre"].lower():
                        search_type = "genre"
                        break

                if search_type == "":
                    for work in results:
                        if work["musical_key"] and lower_search in work["musical_key"].lower():
                            search_type = "key"
                            break

                if search_type == "":
                    for work in results:
                        city = work["city"] or ""
                        country = work["country"] or ""

                        if lower_search in city.lower() or lower_search in country.lower():
                            search_type = "place"
                            break

                if search_type == "":
                    for work in results:
                        performer_name = work["performer_name"] or ""
                        recording_title = work["recording_title"] or ""

                        if lower_search in performer_name.lower() or lower_search in recording_title.lower():
                            search_type = "recording"
                            break

                if search_type == "":
                    search_type = "title/general"

        if search_type == "genre":
            results.sort(
                key=lambda work: (
                    work["genre"] or "",
                    get_op_number(work["title"]),
                    get_no_number(work["title"]),
                    work["title"] or ""
                )
            )

        elif search_type == "key":
            results.sort(
                key=lambda work: (
                    work["genre"] or "",
                    get_op_number(work["title"]),
                    get_no_number(work["title"]),
                    work["title"] or ""
                )
            )

        elif search_type == "place":
            results.sort(
                key=lambda work: (
                    get_op_number(work["title"]),
                    get_no_number(work["title"]),
                    work["genre"] or "",
                    work["title"] or ""
                )
            )

        elif search_type == "year" or search_type == "year range":
            results.sort(
                key=lambda work: (
                    work["composition_year"] or 9999,
                    get_op_number(work["title"]),
                    get_no_number(work["title"]),
                    work["genre"] or "",
                    work["title"] or ""
                )
            )

        elif search_type == "opus number" or search_type == "opus range":
            results.sort(
                key=lambda work: (
                    get_op_number(work["title"]),
                    get_no_number(work["title"]),
                    work["genre"] or "",
                    work["title"] or ""
                )
            )

        else:
            results.sort(
                key=lambda work: (
                    get_op_number(work["title"]),
                    get_no_number(work["title"]),
                    work["genre"] or "",
                    work["title"] or ""
                )
            )

    return render_template(
        "search.html",
        results=results,
        search_term=search_term,
        search_type=search_type
    )


@app.route("/recordings")
def recordings():
    recordings = get_all_recordings()
    return render_template("recordings.html", recordings=recordings)


@app.route("/recording/<int:recording_id>")
def recording_detail(recording_id):
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
            score_path=""
        )

    recording = rows[0]

    descriptions = []

    for row in rows:
        if row["description_content"]:
            descriptions.append({
                "description_type": row["description_type"],
                "content": row["description_content"],
                "source": row["description_source"]
            })

    score_path = "/static/score/score_" + str(recording["work_id"]).zfill(3) + ".pdf"

    return render_template(
        "recording_detail.html",
        recording=recording,
        descriptions=descriptions,
        score_path=score_path
    )


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5210, debug=True)