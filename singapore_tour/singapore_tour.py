from flask import render_template, request, redirect, url_for, session, send_from_directory, abort
import os
import uuid
import json
from jinja2 import ChoiceLoader, FileSystemLoader
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash

try:
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:
        pass
except ImportError:
    Image = None
    ImageOps = None
    UnidentifiedImageError = OSError

try:
    import rawpy
except ImportError:
    rawpy = None

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
SINGAPORE_STATIC_GALLERY_DIR = os.path.join(STATIC_DIR, "image", "gallery")
SINGAPORE_GALLERY_DIR = os.environ.get(
    "SINGAPORE_GALLERY_DIR",
    SINGAPORE_STATIC_GALLERY_DIR
)
SINGAPORE_GALLERY_BROWSER_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "avif"}
SINGAPORE_GALLERY_CONVERTIBLE_IMAGE_EXTENSIONS = {
    "jpg", "jpeg", "png", "webp", "heic", "heif", "tif", "tiff", "bmp", "avif"
}
SINGAPORE_GALLERY_RAW_EXTENSIONS = {"dng"}
SINGAPORE_GALLERY_IMAGE_EXTENSIONS = (
    SINGAPORE_GALLERY_BROWSER_IMAGE_EXTENSIONS |
    SINGAPORE_GALLERY_CONVERTIBLE_IMAGE_EXTENSIONS |
    SINGAPORE_GALLERY_RAW_EXTENSIONS
)
SINGAPORE_GALLERY_VIDEO_EXTENSIONS = {"mp4", "mov", "m4v", "webm"}
SINGAPORE_GALLERY_ALLOWED_EXTENSIONS = (
    SINGAPORE_GALLERY_IMAGE_EXTENSIONS | SINGAPORE_GALLERY_VIDEO_EXTENSIONS
)
SINGAPORE_GALLERY_PREVIEW_SUFFIX = ".preview.jpg"
SINGAPORE_GALLERY_ORDER_FILE = "gallery_order.json"
SINGAPORE_STATIC_MAX_AGE = 60 * 60 * 24 * 7
SINGAPORE_GALLERY_IMAGE_MAX_DIMENSION = 2200
SINGAPORE_GALLERY_IMAGE_QUALITY = 82
SINGAPORE_GALLERY_USER = "James"
SINGAPORE_GALLERY_PASSWORD_HASH = (
    "scrypt:32768:8:1$Md4O01kcXsqEB4kG$"
    "feb5ed4a67a6ffe64c2cb7537b9bb3f89504b413994356c5fb57abe00d19945494594d498f88044646d953aaba2130741de445662688914d1c84a818fc4e2911"
)


def is_singapore_gallery_logged_in():
    return session.get("singapore_gallery_user") == SINGAPORE_GALLERY_USER


def is_allowed_gallery_file(filename):
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in SINGAPORE_GALLERY_ALLOWED_EXTENSIONS


def get_singapore_gallery_media_type(filename):
    extension = filename.rsplit(".", 1)[1].lower()

    if extension in SINGAPORE_GALLERY_VIDEO_EXTENSIONS:
        return "video"

    if extension not in SINGAPORE_GALLERY_BROWSER_IMAGE_EXTENSIONS:
        return "file"

    return "image"


def save_dng_as_jpg(raw_path):
    if rawpy is None or Image is None:
        return None

    try:
        with rawpy.imread(raw_path) as raw:
            rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=False, output_bps=8)

        image = Image.fromarray(rgb)
        image.thumbnail(
            (
                SINGAPORE_GALLERY_IMAGE_MAX_DIMENSION,
                SINGAPORE_GALLERY_IMAGE_MAX_DIMENSION
            ),
            Image.Resampling.LANCZOS
        )
        saved_name = f"{uuid.uuid4().hex}.jpg"
        image.save(
            os.path.join(SINGAPORE_GALLERY_DIR, saved_name),
            "JPEG",
            quality=SINGAPORE_GALLERY_IMAGE_QUALITY,
            optimize=True,
            progressive=True
        )
        return saved_name
    except (OSError, ValueError):
        return None


def save_gallery_upload(file, extension):
    if extension in SINGAPORE_GALLERY_VIDEO_EXTENSIONS:
        saved_name = f"{uuid.uuid4().hex}.{extension}"
        file.save(os.path.join(SINGAPORE_GALLERY_DIR, saved_name))
        return saved_name

    if extension in SINGAPORE_GALLERY_RAW_EXTENSIONS:
        temp_name = f"{uuid.uuid4().hex}.{extension}"
        raw_path = os.path.join(SINGAPORE_GALLERY_DIR, temp_name)
        file.save(raw_path)
        saved_name = save_dng_as_jpg(raw_path)
        os.remove(raw_path)

        if saved_name:
            return saved_name

        file.stream.seek(0)
        fallback_name = f"{uuid.uuid4().hex}.{extension}"
        file.save(os.path.join(SINGAPORE_GALLERY_DIR, fallback_name))
        return fallback_name

    if Image is None or extension == "gif":
        saved_name = f"{uuid.uuid4().hex}.{extension}"
        file.save(os.path.join(SINGAPORE_GALLERY_DIR, saved_name))
        return saved_name

    try:
        image = Image.open(file.stream)
        image = ImageOps.exif_transpose(image)

        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            background = Image.new("RGB", image.size, (255, 255, 255))
            alpha = image.split()[-1] if image.mode in ("RGBA", "LA") else None
            background.paste(image, mask=alpha)
            image = background
        else:
            image = image.convert("RGB")

        image.thumbnail(
            (
                SINGAPORE_GALLERY_IMAGE_MAX_DIMENSION,
                SINGAPORE_GALLERY_IMAGE_MAX_DIMENSION
            ),
            Image.Resampling.LANCZOS
        )

        saved_name = f"{uuid.uuid4().hex}.jpg"
        image.save(
            os.path.join(SINGAPORE_GALLERY_DIR, saved_name),
            "JPEG",
            quality=SINGAPORE_GALLERY_IMAGE_QUALITY,
            optimize=True,
            progressive=True
        )
        return saved_name
    except (OSError, UnidentifiedImageError):
        file.stream.seek(0)
        saved_name = f"{uuid.uuid4().hex}.{extension}"
        file.save(os.path.join(SINGAPORE_GALLERY_DIR, saved_name))
        return saved_name


def get_gallery_order_path():
    return os.path.join(SINGAPORE_GALLERY_DIR, SINGAPORE_GALLERY_ORDER_FILE)


def load_gallery_order():
    try:
        with open(get_gallery_order_path(), "r", encoding="utf-8") as order_file:
            order = json.load(order_file)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(order, list):
        return []

    return [secure_filename(os.path.basename(filename)) for filename in order if filename]


def save_gallery_order(filenames):
    os.makedirs(SINGAPORE_GALLERY_DIR, exist_ok=True)

    with open(get_gallery_order_path(), "w", encoding="utf-8") as order_file:
        json.dump(filenames, order_file, ensure_ascii=True, indent=2)


def get_gallery_filenames():
    filenames = []

    for directory in (SINGAPORE_GALLERY_DIR, SINGAPORE_STATIC_GALLERY_DIR):
        if not os.path.isdir(directory):
            continue

        for filename in sorted(os.listdir(directory)):
            if filename == SINGAPORE_GALLERY_ORDER_FILE:
                continue

            if filename not in filenames:
                filenames.append(filename)

    valid_filenames = [
        filename
        for filename in filenames
        if is_allowed_gallery_file(filename)
    ]
    order = load_gallery_order()
    ordered = [filename for filename in order if filename in valid_filenames]
    unordered = [filename for filename in valid_filenames if filename not in ordered]

    return ordered + unordered


def get_singapore_gallery_images():
    images = []

    for filename in get_gallery_filenames():
        extension = filename.rsplit(".", 1)[1].lower()
        media_type = get_singapore_gallery_media_type(filename)
        src = url_for("singapore_tour_media", filename=filename)

        images.append({
            "filename": filename,
            "type": media_type,
            "title": filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " "),
            "extension": extension,
            "alt": "Singapore Tour gallery media",
            "src": src,
            "download_src": url_for("singapore_tour_media", filename=filename)
        })

    return images


def singapore_tour_static(filename):
    return send_from_directory(STATIC_DIR, filename, max_age=SINGAPORE_STATIC_MAX_AGE)


def singapore_tour_media(filename):
    safe_name = secure_filename(os.path.basename(filename))

    if not safe_name or (
        not is_allowed_gallery_file(safe_name) and
        not safe_name.endswith(SINGAPORE_GALLERY_PREVIEW_SUFFIX)
    ):
        abort(404)

    gallery_path = os.path.join(SINGAPORE_GALLERY_DIR, safe_name)

    if os.path.exists(gallery_path):
        return send_from_directory(SINGAPORE_GALLERY_DIR, safe_name, max_age=SINGAPORE_STATIC_MAX_AGE)

    return send_from_directory(SINGAPORE_STATIC_GALLERY_DIR, safe_name, max_age=SINGAPORE_STATIC_MAX_AGE)


def singapore_tour():
    return render_template(
        "singapore_tour.html",
        gallery_images=get_singapore_gallery_images(),
        gallery_logged_in=is_singapore_gallery_logged_in(),
        login_message=session.pop("singapore_gallery_login_message", ""),
        upload_message=session.pop("singapore_gallery_upload_message", "")
    )


def singapore_tour_login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if (
        username == SINGAPORE_GALLERY_USER and
        check_password_hash(SINGAPORE_GALLERY_PASSWORD_HASH, password)
    ):
        session.permanent = True
        session["singapore_gallery_user"] = SINGAPORE_GALLERY_USER
        return redirect(url_for("singapore_tour") + "#gallery")

    session["singapore_gallery_login_message"] = "用户名或密码不正确。"
    return redirect(url_for("singapore_tour") + "#gallery")


def singapore_tour_logout():
    session.pop("singapore_gallery_user", None)
    return redirect(url_for("singapore_tour") + "#gallery")


def singapore_tour_upload():
    if not is_singapore_gallery_logged_in():
        session["singapore_gallery_login_message"] = "请先登录再上传文件。"
        return redirect(url_for("singapore_tour") + "#gallery")

    files = request.files.getlist("photos")

    if not files:
        session["singapore_gallery_upload_message"] = "请选择至少一个文件。"
        return redirect(url_for("singapore_tour") + "#gallery")

    os.makedirs(SINGAPORE_GALLERY_DIR, exist_ok=True)
    uploaded_count = 0

    for file in files:
        if not file or not file.filename:
            continue

        if not is_allowed_gallery_file(file.filename):
            continue

        filename = secure_filename(file.filename)
        extension = filename.rsplit(".", 1)[1].lower()
        saved_name = save_gallery_upload(file, extension)

        if saved_name:
            order = load_gallery_order()
            order.append(saved_name)
            save_gallery_order(order)

        uploaded_count += 1

    if uploaded_count == 0:
        session["singapore_gallery_upload_message"] = "没有成功上传，请选择图片、DNG/HEIC，或 MP4、MOV、M4V、WEBM 视频。"
    else:
        session["singapore_gallery_upload_message"] = f"已上传 {uploaded_count} 个文件。"

    return redirect(url_for("singapore_tour") + "#gallery")


def singapore_tour_delete_photo():
    if not is_singapore_gallery_logged_in():
        session["singapore_gallery_login_message"] = "请先登录再删除文件。"
        return redirect(url_for("singapore_tour") + "#gallery")

    filename = secure_filename(os.path.basename(request.form.get("filename", "")))

    if not filename or not is_allowed_gallery_file(filename):
        session["singapore_gallery_upload_message"] = "没有找到要删除的文件。"
        return redirect(url_for("singapore_tour") + "#gallery")

    gallery_dir = os.path.abspath(SINGAPORE_GALLERY_DIR)
    static_gallery_dir = os.path.abspath(SINGAPORE_STATIC_GALLERY_DIR)
    photo_path = os.path.abspath(os.path.join(SINGAPORE_GALLERY_DIR, filename))

    if not os.path.exists(photo_path):
        photo_path = os.path.abspath(os.path.join(SINGAPORE_STATIC_GALLERY_DIR, filename))

    if not (
        photo_path.startswith(gallery_dir + os.sep) or
        photo_path.startswith(static_gallery_dir + os.sep)
    ):
        session["singapore_gallery_upload_message"] = "没有找到要删除的文件。"
        return redirect(url_for("singapore_tour") + "#gallery")

    if os.path.exists(photo_path):
        os.remove(photo_path)
        order = [item for item in load_gallery_order() if item != filename]
        save_gallery_order(order)
        session["singapore_gallery_upload_message"] = "已删除这个文件。"
    else:
        session["singapore_gallery_upload_message"] = "这个文件已经不存在。"

    return redirect(url_for("singapore_tour") + "#gallery")


def singapore_tour_reorder_photo():
    if not is_singapore_gallery_logged_in():
        session["singapore_gallery_login_message"] = "请先登录再调整顺序。"
        return redirect(url_for("singapore_tour") + "#gallery")

    filename = secure_filename(os.path.basename(request.form.get("filename", "")))
    direction = request.form.get("direction", "")
    filenames = get_gallery_filenames()

    if filename not in filenames:
        session["singapore_gallery_upload_message"] = "没有找到要调整的文件。"
        return redirect(url_for("singapore_tour") + "#gallery")

    index = filenames.index(filename)

    if direction == "target":
        try:
            target_index = int(request.form.get("target_position", "")) - 1
        except ValueError:
            session["singapore_gallery_upload_message"] = "请输入有效的位置编号。"
            return redirect(url_for("singapore_tour") + "#gallery")

        target_index = max(0, min(target_index, len(filenames) - 1))

        if target_index != index:
            filenames.pop(index)
            filenames.insert(target_index, filename)
            session["singapore_gallery_upload_message"] = f"已移动到第 {target_index + 1} 张。"
        else:
            session["singapore_gallery_upload_message"] = "已经在这个位置了。"
    elif direction == "earlier" and index > 0:
        filenames[index - 1], filenames[index] = filenames[index], filenames[index - 1]
        session["singapore_gallery_upload_message"] = "已向前移动。"
    elif direction == "later" and index < len(filenames) - 1:
        filenames[index + 1], filenames[index] = filenames[index], filenames[index + 1]
        session["singapore_gallery_upload_message"] = "已向后移动。"
    else:
        session["singapore_gallery_upload_message"] = "已经在这个位置了。"

    save_gallery_order(filenames)
    return redirect(url_for("singapore_tour") + "#gallery")


SINGAPORE_TOUR_DAYS = {
    "6-2": {
        "date": "6.2",
        "title": "雨后抵达 Sentosa",
        "weather": "清晨雷阵雨 / 抵达日",
        "base": "Outpost Sentosa",
        "summary": "不安排户外主项目。入住 Outpost Sentosa 后先休息；如果下午天气转好，就在酒店附近或海边短走一圈。",
        "map_title": "Outpost Sentosa and Siloso Beach",
        "map_src": "https://www.openstreetmap.org/export/embed.html?bbox=103.8135%2C1.2432%2C103.8405%2C1.2638&layer=mapnik&marker=1.2531%2C103.8202",
        "map_link": "https://www.openstreetmap.org/?mlat=1.2531&mlon=103.8202#map=15/1.2531/103.8202",
        "plans": [
            {
                "time": "下午",
                "title": "入住 Outpost Sentosa",
                "detail": "先办入住、放行李、熟悉酒店和泳池。第一天不排景点，把雨后湿热和飞行疲劳都算进去。"
            },
            {
                "time": "傍晚",
                "title": "Siloso Beach 短走",
                "detail": "天气转好再出门，从酒店附近走到 Siloso Beach 或海边步道，控制在 30-60 分钟。下雨就改成酒店休息。"
            },
            {
                "time": "晚餐",
                "title": "岛上简单吃饭",
                "detail": "就近解决，不折腾去主岛。可以看酒店附近餐厅或 RWS 方向。无需门票。"
            }
        ]
    },
    "6-3": {
        "date": "6.3",
        "title": "Sentosa 海边和缆车",
        "weather": "晴热 / 户外放早晚",
        "base": "Sentosa Island",
        "summary": "早上吃酒店自助早餐，趁上午或傍晚去海边、缆车或岛上散步。中午最热的时候回酒店休息，避免硬晒。",
        "map_title": "Sentosa beaches and cable car area",
        "map_src": "https://www.openstreetmap.org/export/embed.html?bbox=103.8078%2C1.2423%2C103.8482%2C1.2678&layer=mapnik&marker=1.2550%2C103.8238",
        "map_link": "https://www.openstreetmap.org/?mlat=1.2550&mlon=103.8238#map=14/1.2550/103.8238",
        "plans": [
            {
                "time": "早餐后",
                "title": "Siloso / Palawan 海边",
                "detail": "吃完自助早餐后出门，先走 Siloso Beach；如果体力好再往 Palawan 方向。热起来就立刻回酒店。"
            },
            {
                "time": "上午或傍晚",
                "title": "Singapore Cable Car",
                "detail": "天气清楚时坐更值得，避开正午暴晒。可选 Sentosa Line 小环线，或 SkyPass Round Trip 看完整海港视野。",
                "ticket": "Sentosa 官方订票",
                "price": "S$17 / S$35",
                "url": "https://www.sentosa.com.sg/en/things-to-do/attractions/singapore-cable-car/"
            },
            {
                "time": "中午",
                "title": "酒店休息和泳池",
                "detail": "12:00-15:30 尽量不户外硬晒。回酒店午休、游泳或喝东西，傍晚再出门。"
            },
            {
                "time": "晚上",
                "title": "RWS 附近轻松晚餐",
                "detail": "如果还想走动，可以去 Resorts World Sentosa 附近吃饭和散步；不进收费项目也可以。"
            }
        ]
    },
    "6-4": {
        "date": "6.4",
        "title": "Sentosa 收尾，晚上到 Hyatt",
        "weather": "晴热 / 室内备选",
        "base": "Sentosa and Grand Hyatt",
        "summary": "白天还是 Sentosa 慢慢收尾，中午可选水族馆、商店或酒店休息；晚上已经搬到 Grand Hyatt，后面几天从主岛出发。",
        "map_title": "Resorts World Sentosa",
        "map_src": "https://www.openstreetmap.org/export/embed.html?bbox=103.8145%2C1.2480%2C103.8345%2C1.2635&layer=mapnik&marker=1.2586%2C103.8206",
        "map_link": "https://www.openstreetmap.org/?mlat=1.2586&mlon=103.8206#map=16/1.2586/103.8206",
        "plans": [
            {
                "time": "上午",
                "title": "Resorts World Sentosa",
                "detail": "早餐后慢慢到 RWS。先看天气和体力：如果太阳很强，直接把重点放到室内。"
            },
            {
                "time": "中午室内",
                "title": "Singapore Oceanarium",
                "detail": "最适合热天中午或雨天。建议提前看入场时段，控制游览 1.5-2.5 小时，不要把下午排满。",
                "ticket": "Oceanarium 官方订票",
                "price": "From S$43",
                "url": "https://www.singaporeoceanarium.com/en/ticketing.html"
            },
            {
                "time": "可选",
                "title": "Universal Studios 外围或入园",
                "detail": "只在门口和 RWS 外围拍照不需要票；如果真的想入园，要单独留半天，不建议和水族馆硬塞同一天。",
                "ticket": "USS 官方订票",
                "price": "From S$76",
                "url": "https://www.rwsentosa.com/en/play/universal-studios-singapore/tickets"
            },
            {
                "time": "傍晚",
                "title": "Sentosa 收尾，晚上去 Grand Hyatt",
                "detail": "如果中午进了室内项目，傍晚只安排轻松散步或回酒店收拾。晚上搬到 Grand Hyatt 后就不要再加行程。"
            }
        ]
    },
    "6-5": {
        "date": "6.5",
        "title": "Hyatt 出发，傍晚鱼尾狮",
        "weather": "室内下午 / 傍晚海湾",
        "base": "Grand Hyatt, National Museum and Merlion Park",
        "summary": "已经住在 Grand Hyatt，白天不要赶。下午可去 National Museum of Singapore，傍晚去 Marina Bay 和 Merlion Park 看鱼尾狮、海湾和夜景。",
        "map_title": "National Museum and Merlion Park",
        "map_src": "https://www.openstreetmap.org/export/embed.html?bbox=103.8280%2C1.2780%2C103.8625%2C1.3105&layer=mapnik&marker=1.2868%2C103.8545",
        "map_link": "https://www.openstreetmap.org/?mlat=1.2868&mlon=103.8545#map=15/1.2868/103.8545",
        "plans": [
            {
                "time": "上午",
                "title": "Grand Hyatt 慢慢开始",
                "detail": "上午不硬排。可以在 Orchard 附近吃早午饭、补休息，或者只处理一些轻松的小事。"
            },
            {
                "time": "下午",
                "title": "National Museum of Singapore",
                "detail": "适合热天或阵雨的室内安排。开放时间一般为 10:00-19:00，成人游客票 S$20；如果体力一般，控制在 1.5-2 小时就好。",
                "ticket": "National Museum 官方信息",
                "price": "Adult tourist S$20",
                "url": "https://www.nhb.gov.sg/nationalmuseum/"
            },
            {
                "time": "傍晚",
                "title": "Marina Bay / Merlion Park",
                "detail": "傍晚从 City Hall、Raffles Place 或 Esplanade 过去都方便。先看鱼尾狮，再沿海湾短走一段；天黑后看 skyline，走累就停。",
                "ticket": "公共区域",
                "price": "Free",
                "url": "https://www.visitsingapore.com/see-do-singapore/recreation-leisure/viewpoints/merlion-park/"
            },
            {
                "time": "晚餐",
                "title": "海湾附近简单吃",
                "detail": "不想绕路就选 Makansutra Gluttons Bay、Suntec 或 Marina Square；想吃 hawker 氛围再去 Lau Pa Sat。"
            }
        ]
    },
    "6-6": {
        "date": "6.6",
        "title": "博物馆和美术馆",
        "weather": "室内文化日 / 热天友好",
        "base": "National Gallery, Singapore Art Museum and Civic District",
        "summary": "把这天留给博物馆、美术馆和咖啡。上午可去 National Gallery Singapore，下午去 Singapore Art Museum；如果前一天错过 National Museum，也可以挪到这天。",
        "map_title": "Civic District and art museums",
        "map_src": "https://www.openstreetmap.org/export/embed.html?bbox=103.8390%2C1.2760%2C103.8595%2C1.3005&layer=mapnik&marker=1.2907%2C103.8515",
        "map_link": "https://www.openstreetmap.org/?mlat=1.2907&mlon=103.8515#map=15/1.2907/103.8515",
        "plans": [
            {
                "time": "上午",
                "title": "National Gallery Singapore",
                "detail": "从 Hyatt 出发到 Civic District。适合慢慢看建筑、展厅和城市视角；开放时间一般为 10:00-19:00，标准成人票 S$20。",
                "ticket": "National Gallery 官方订票",
                "price": "Adult S$20",
                "url": "https://www.nationalgallery.sg/visit/admissions/"
            },
            {
                "time": "中午",
                "title": "Civic District 午餐或咖啡",
                "detail": "不要急着转场。可以在 City Hall、Raffles City、CHIJMES 或 National Gallery 附近吃饭，顺便避开最热的时段。"
            },
            {
                "time": "下午",
                "title": "Singapore Art Museum",
                "detail": "如果还想看当代艺术，下午去 SAM。开放时间一般为 10:00-19:00，成人游客票 S$10；如果累了，就只保留一个美术馆。",
                "ticket": "SAM 官方订票",
                "price": "Adult tourist S$10",
                "url": "https://www.singaporeartmuseum.sg/visit"
            },
            {
                "time": "傍晚",
                "title": "一个本地街区收尾",
                "detail": "只选一个：Kampong Glam 看街景，Tiong Bahru 更安静，Chinatown 吃东西方便。当天重点是舒服，不是打卡数量。"
            }
        ]
    },
    "6-7": {
        "date": "6.7",
        "title": "Bird Paradise",
        "weather": "晴天上午户外 / 中午休息",
        "base": "Bird Paradise, Mandai Wildlife Reserve",
        "summary": "把裕廊鸟动物园安排成 Bird Paradise（原裕廊鸟园，现在在 Mandai）。最好上午去，天气热时坐园内交通、找室内/遮阴区域休息。",
        "map_title": "Bird Paradise",
        "map_src": "https://www.openstreetmap.org/export/embed.html?bbox=103.7820%2C1.3935%2C103.8035%2C1.4108&layer=mapnik&marker=1.4030%2C103.7907",
        "map_link": "https://www.openstreetmap.org/?mlat=1.4030&mlon=103.7907#map=16/1.4030/103.7907",
        "plans": [
            {
                "time": "上午",
                "title": "Bird Paradise 入园",
                "detail": "从 Grand Hyatt 出发去 Mandai，尽量上午到。Bird Paradise 是原裕廊鸟园的新园区，户外多，晴天上午最舒服。"
            },
            {
                "time": "中午",
                "title": "园内慢慢看，不赶场",
                "detail": "看鸟舍、表演和步道，中午热的时候多用 tram / shuttle，找餐厅或遮阴处休息。官方非居民成人票 S$49，儿童 S$34。",
                "ticket": "Bird Paradise 官方订票",
                "price": "Adult S$49 / Child S$34",
                "url": "https://www.mandai.com/en/tickets-and-passes/single-attractions/bird-paradise.html"
            },
            {
                "time": "下午",
                "title": "回市区休息",
                "detail": "Bird Paradise 不要排到太晚。下午回酒店或 Orchard 附近休息，晚上再轻松吃饭。"
            },
            {
                "time": "雨天备选",
                "title": "改成室内日",
                "detail": "如果上午大雨，就不要硬去动物园；改成 National Gallery、ArtScience Museum 或商场，Bird Paradise 可视体力挪到另一个晴天上午。"
            }
        ]
    },
    "6-8": {
        "date": "6.8",
        "title": "Gardens by the Bay",
        "weather": "花园 / 6.8 更合适",
        "base": "Gardens by the Bay and Marina Bay",
        "summary": "把 Gardens by the Bay 放到 6.8：Floral Fantasy 6.1-6.7 关闭，6.8 再去更合适。上午或傍晚看户外，中午进冷室。",
        "map_title": "Gardens by the Bay and Marina Bay",
        "map_src": "https://www.openstreetmap.org/export/embed.html?bbox=103.8493%2C1.2738%2C103.8738%2C1.2928&layer=mapnik&marker=1.2816%2C103.8636",
        "map_link": "https://www.openstreetmap.org/?mlat=1.2816&mlon=103.8636#map=15/1.2816/103.8636",
        "plans": [
            {
                "time": "上午或傍晚",
                "title": "Gardens by the Bay 户外区",
                "detail": "先走 Supertree Grove 和户外花园，免费区域就够好看。太阳强就把户外挪到傍晚。"
            },
            {
                "time": "中午室内",
                "title": "Cloud Forest / Flower Dome / Floral Fantasy",
                "detail": "热的时候进冷室最舒服。Floral Fantasy 6.1-6.7 关闭，6.8 开始再安排。官方价格按组合不同变化，建议出发前看官网。",
                "ticket": "Gardens 官方订票",
                "price": "按场馆组合为准",
                "url": "https://www.gardensbythebay.com.sg/en/tickets-and-promotions/tickets.html"
            },
            {
                "time": "下午雨天备选",
                "title": "ArtScience Museum",
                "detail": "如果下雨、太热或 haze，就把 Marina Bay 户外减少，改去 ArtScience。官方票务按展览变化。",
                "ticket": "ArtScience 官方订票",
                "price": "按展览为准",
                "url": "https://www.marinabaysands.com/museum/ticket/search.html"
            },
            {
                "time": "傍晚",
                "title": "Marina Bay 夜景",
                "detail": "天气和能见度可以的话，傍晚走 Marina Bay；如果状态不好，就改成室内晚餐。"
            }
        ]
    },
    "6-9": {
        "date": "6.9",
        "title": "最后一个早晨",
        "weather": "离开日 / 不赶路",
        "base": "Grand Hyatt to Changi Airport",
        "summary": "在 Grand Hyatt 慢慢退房，补几张照片，需要的话买一点纪念品。天气不好也不影响，重点是从容去机场，搭乘 SQ838。",
        "map_title": "Changi Airport",
        "map_src": "https://www.openstreetmap.org/export/embed.html?bbox=103.9735%2C1.3415%2C104.0105%2C1.3740&layer=mapnik&marker=1.3644%2C103.9915",
        "map_link": "https://www.openstreetmap.org/?mlat=1.3644&mlon=103.9915#map=15/1.3644/103.9915",
        "plans": [
            {
                "time": "上午",
                "title": "Grand Hyatt 慢慢退房",
                "detail": "整理行李、补几张照片，别安排需要排队或跨城的项目。离开日只做低风险安排。"
            },
            {
                "time": "去机场前",
                "title": "最后购物或咖啡",
                "detail": "如果时间够，在 Orchard 附近买一点东西；时间不够就直接去机场。"
            },
            {
                "time": "机场",
                "title": "Changi Airport / Jewel",
                "detail": "可以看 Rain Vortex、吃饭或逛 Jewel。大部分区域无需门票，重点是留足值机和安检时间，准备搭乘 SQ838。"
            }
        ]
    }
}


def singapore_tour_day(day):
    tour_day = SINGAPORE_TOUR_DAYS.get(day)

    if not tour_day:
        return redirect(url_for("singapore_tour"))

    day_keys = list(SINGAPORE_TOUR_DAYS.keys())
    day_index = day_keys.index(day)
    previous_key = day_keys[day_index - 1] if day_index > 0 else None
    next_key = day_keys[day_index + 1] if day_index < len(day_keys) - 1 else None

    previous_day = None
    next_day = None

    if previous_key:
        previous_day = {
            "key": previous_key,
            "date": SINGAPORE_TOUR_DAYS[previous_key]["date"],
            "title": SINGAPORE_TOUR_DAYS[previous_key]["title"]
        }

    if next_key:
        next_day = {
            "key": next_key,
            "date": SINGAPORE_TOUR_DAYS[next_key]["date"],
            "title": SINGAPORE_TOUR_DAYS[next_key]["title"]
        }

    return render_template(
        "singapore_tour_day.html",
        day=tour_day,
        previous_day=previous_day,
        next_day=next_day
    )


def register_singapore_tour(app):
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(TEMPLATE_DIR),
        app.jinja_loader
    ])

    app.add_url_rule(
        "/project/singapore-tour/static/<path:filename>",
        "singapore_tour_static",
        singapore_tour_static
    )
    app.add_url_rule(
        "/project/singapore-tour/media/<path:filename>",
        "singapore_tour_media",
        singapore_tour_media
    )
    app.add_url_rule("/project/singapore-tour", "singapore_tour", singapore_tour)
    app.add_url_rule(
        "/project/singapore-tour/login",
        "singapore_tour_login",
        singapore_tour_login,
        methods=["POST"]
    )
    app.add_url_rule(
        "/project/singapore-tour/logout",
        "singapore_tour_logout",
        singapore_tour_logout,
        methods=["POST"]
    )
    app.add_url_rule(
        "/project/singapore-tour/upload",
        "singapore_tour_upload",
        singapore_tour_upload,
        methods=["POST"]
    )
    app.add_url_rule(
        "/project/singapore-tour/delete",
        "singapore_tour_delete_photo",
        singapore_tour_delete_photo,
        methods=["POST"]
    )
    app.add_url_rule(
        "/project/singapore-tour/reorder",
        "singapore_tour_reorder_photo",
        singapore_tour_reorder_photo,
        methods=["POST"]
    )
    app.add_url_rule(
        "/project/singapore-tour/<day>",
        "singapore_tour_day",
        singapore_tour_day
    )
