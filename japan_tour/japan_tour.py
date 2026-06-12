from flask import render_template, send_from_directory
from jinja2 import ChoiceLoader, FileSystemLoader
import os


BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
JAPAN_STATIC_MAX_AGE = 60 * 60 * 24 * 7


def japan_tour():
    stops = [
        {
            "city": "Tokyo",
            "city_zh": "东京",
            "dates": "7.20-7.23",
            "nights": "3 nights",
            "nights_zh": "3晚",
            "note": "Grand Bach Hotel, first Tokyo base before flying north.",
            "note_zh": "东京第一站，住 Grand Bach Hotel，之后飞往北海道。"
        },
        {
            "city": "Sapporo",
            "city_zh": "札幌",
            "dates": "7.23-7.25",
            "nights": "2 nights",
            "nights_zh": "2晚",
            "note": "Onsen Ryokan Yuen and the start of the Hokkaido leg.",
            "note_zh": "住 Onsen Ryokan Yuen，北海道段从这里开始。"
        },
        {
            "city": "Lake Toya",
            "city_zh": "洞爷湖",
            "dates": "7.25-7.27",
            "nights": "2 nights",
            "nights_zh": "2晚",
            "note": "Activate the rail pass, then transfer by local bus to Toyako Onsen.",
            "note_zh": "这天启用铁路周游券，洞爷站到洞爷湖温泉巴士另付。"
        },
        {
            "city": "Furano",
            "city_zh": "富良野",
            "dates": "7.27-7.29",
            "nights": "2 nights",
            "nights_zh": "2晚",
            "note": "Lavender fields, Biei day options, and slower Hokkaido mornings.",
            "note_zh": "薰衣草、美瑛备选，节奏放慢一点。"
        },
        {
            "city": "Osaka",
            "city_zh": "大阪",
            "dates": "7.29-7.31",
            "nights": "2 nights",
            "nights_zh": "2晚",
            "note": "Fly from New Chitose and settle into the Kansai section.",
            "note_zh": "从新千岁飞往大阪，进入关西段。"
        },
        {
            "city": "Kyoto",
            "city_zh": "京都",
            "dates": "7.31-8.3",
            "nights": "3 nights",
            "nights_zh": "3晚",
            "note": "Three-night Kyoto base, hotel still to be finalized.",
            "note_zh": "京都住三晚，酒店暂定。"
        },
        {
            "city": "Narita",
            "city_zh": "成田",
            "dates": "8.3-8.4",
            "nights": "1 night",
            "nights_zh": "1晚",
            "note": "Kyoto to Tokyo, stay near Narita before the Hangzhou flight.",
            "note_zh": "京都回东京，成田机场附近住一晚，第二天飞杭州。"
        }
    ]

    hotels = [
        {"city": "Tokyo", "hotel": "Grand Bach Hotel", "nights": "3", "price": "¥4110", "note": "First Tokyo stay"},
        {"city": "Sapporo", "hotel": "Onsen Ryokan Yuen", "nights": "2", "price": "¥4104", "note": "City onsen ryokan"},
        {"city": "Lake Toya", "hotel": "Toya Kohan Tei", "nights": "2", "price": "¥3853", "note": "Lake Toya Onsen"},
        {"city": "Furano", "hotel": "Nozo Hotel", "nights": "2", "price": "¥3747", "note": "Furano base"},
        {"city": "Osaka", "hotel": "Sugata Hotel Osaka", "nights": "2", "price": "¥825", "note": "Kansai arrival"},
        {"city": "Kyoto", "hotel": "TBD", "nights": "3", "price": "¥3000", "note": "Pending"},
        {"city": "Narita", "hotel": "Narita Tobu Hotel", "nights": "1", "price": "¥415", "note": "Airport night"}
    ]

    budget_cards = [
        {"label": "Flights", "label_zh": "机票", "value": "¥3709", "detail": "Hangzhou-Tokyo round trip + Japan domestic legs", "detail_zh": "杭州往返东京 + 日本国内段"},
        {"label": "Hokkaido Pass", "label_zh": "北海道周游券", "value": "¥930", "detail": "5-day JR Hokkaido rail pass", "detail_zh": "5日 JR 北海道铁路周游券"},
        {"label": "Hotels per person", "label_zh": "酒店人均", "value": "¥10027", "detail": "¥20054 total, about ¥668 / person / night", "detail_zh": "酒店合计 ¥20054，人均约 ¥668 / 晚"},
        {"label": "Visa", "label_zh": "签证", "value": "¥210", "detail": "Japan visa fee", "detail_zh": "日本签证费用"},
        {"label": "Current total", "label_zh": "目前单人花费", "value": "¥14876", "detail": "Current single-person spend", "detail_zh": "已确认的单人花费"},
        {"label": "Estimated total", "label_zh": "预计单人总花费", "value": "¥22000", "detail": "Expected single-person total", "detail_zh": "预计完整行程总预算"}
    ]

    return render_template(
        "japan_tour.html",
        stops=stops,
        hotels=hotels,
        budget_cards=budget_cards
    )


def japan_tour_static(filename):
    return send_from_directory(STATIC_DIR, filename, max_age=JAPAN_STATIC_MAX_AGE)


def register_japan_tour(app):
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(TEMPLATE_DIR),
        app.jinja_loader
    ])

    app.add_url_rule(
        "/project/japan/static/<path:filename>",
        "japan_tour_static",
        japan_tour_static
    )
    app.add_url_rule("/project/japan", "japan_tour", japan_tour)
    app.add_url_rule("/project/japan-tour", "japan_tour_alias", japan_tour)
