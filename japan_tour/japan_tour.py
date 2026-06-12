from flask import abort, render_template, send_from_directory
from jinja2 import ChoiceLoader, FileSystemLoader
import os

from itinerary_data import BUDGET_CARDS, HOTELS, STOP_DETAILS, STOPS


BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
JAPAN_STATIC_MAX_AGE = 60 * 60 * 24 * 7


def japan_tour():
    return render_template(
        "japan_tour.html",
        stops=STOPS,
        hotels=HOTELS,
        budget_cards=BUDGET_CARDS
    )


def japan_tour_stop(stop):
    detail = STOP_DETAILS.get(stop)

    if detail is None:
        abort(404)

    stop_keys = [item["slug"] for item in STOPS]
    stop_index = stop_keys.index(stop)
    summary = STOPS[stop_index]
    previous_stop = STOPS[stop_index - 1] if stop_index > 0 else None
    next_stop = STOPS[stop_index + 1] if stop_index < len(STOPS) - 1 else None

    return render_template(
        "japan_tour_stop.html",
        stop=summary,
        detail=detail,
        previous_stop=previous_stop,
        next_stop=next_stop
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
    app.add_url_rule("/project/japan/<stop>", "japan_tour_stop", japan_tour_stop)
