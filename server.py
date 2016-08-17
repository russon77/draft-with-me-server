from flask import Flask, render_template, jsonify, abort, request, g
from flask_socketio import SocketIO, join_room
from uuid import uuid4
from pymongo import MongoClient
from flask_sslify import SSLify

import json
import os

###################################
####### Constants
###################################

MONGO_CONNECTION_URI = os.environ.get("MONGODB_URI")
MONGO_DATABASE_NAME = os.environ.get("MONGODB_DATABASE")
MONGO_COLLECTION_NAME = "DRAFTWITHMECOL"

VALID_HERO_IDS = {
        "no_hero",
        "druid", "hunter", "mage", "priest", "shaman", "thief", "paladin", "warlock", "warrior"
    }


###################################
####### Application Initialization
###################################

app = Flask(__name__, static_folder="static")

if 'DYNO' in os.environ:
    sslify = SSLify(app)

socketio = SocketIO(app, message_queue=os.environ.get("REDIS_URL"))

###################################
####### Database Access
###################################


def create_new_session_in_db(session_id):
    auth_token = uuid4().hex

    session = {
        "session_id": session_id,
        "current_cards": [0, 0, 0],
        "drafted": [],
        "num_drafted": 0,
        "hero": "no_hero",
        "auth_token": auth_token
    }

    g.collection.insert_one(session)

    return jsonify({
        "session_id": session_id,
        "auth_token": auth_token
    })


def update_session_cards_in_db(session_id, auth_token, new_cards):
    g.collection.find_and_modify(
        query={
            "session_id": session_id,
            "auth_token": auth_token,
            "num_drafted": {"$lt": 30}
        },
        update={
            "$set": {
                "current_cards": [card.upper() for card in new_cards]
            }
        }
    )


def update_session_drafted_in_db(session_id, auth_token, new_drafted):
    if len(new_drafted) > 30:
        raise ValueError

    g.collection.find_and_modify(
        query={
            "session_id": session_id,
            "auth_token": auth_token,
            "num_drafted": {"$lt": 30}
        },
        update={
            "$set": {
                "drafted": [drafted.upper() for drafted in new_drafted],
                "num_drafted": len(new_drafted)
            }
        }
    )


def update_session_hero_in_db(session_id, auth_token, new_hero):
    new_hero = new_hero.lower()

    if new_hero not in VALID_HERO_IDS:
        raise ValueError

    g.collection.find_and_modify(
        query={
            "session_id": session_id,
            "auth_token": auth_token,
        },
        update={
            "$set": {
                "hero": new_hero,
            }
        }
    )


def get_document_field_for_session(session_id, field):
    doc = g.collection.find_one({
        "session_id": session_id
    })

    return doc[field]


def get_document_for_session(session_id):
    return g.collection.find_one({
        "session_id": session_id
    })


def already_exists_in_db(session_id):
    """
    count the number of Documents whose session_id matches our session_key

    this value should be in (0, 1)... if everything goes right!
    """
    return g.collection.count({"session_id": session_id})

###################################
####### URL Helper Functions
###################################


def get_url_for_card_id(card_id):
    if card_id:
        return "https://s3.amazonaws.com/draftwithme/full_cards/%s.png" % card_id

    return "https://s3.amazonaws.com/draftwithme/full_cards/blank_card.png"


def get_url_for_hero(hero_id):
    if hero_id in VALID_HERO_IDS:
        return "https://s3.amazonaws.com/draftwithme/heroes/%s.png" % hero_id

    return "https://s3.amazonaws.com/draftwithme/heroes/no_hero.png"


def get_url_for_card_bar(card_id):
    return "https://s3.amazonaws.com/draftwithme/bar_cards/%s.png" % card_id


def get_url_for_mana(mana):
    if mana in range(0, 11) or mana in (12, 25):
        return "https://s3.amazonaws.com/draftwithme/mana/%d.png" % mana

    return "https://s3.amazonaws.com/draftwithme/mana/blank_mana.png"


def get_url_for_multiplicity(multiplicity):
    if multiplicity in range(0, 6):
        return "https://s3.amazonaws.com/draftwithme/multiplicity/%d.png" % multiplicity

    return "https://s3.amazonaws.com/draftwithme/multiplicity/blank_mult.png"


###################################
####### Card Helper Functions
###################################


def load_cards_db(filename="cards.collectible.json"):
    """
    load a dictionary of card id to {"mana": x, "name": y}
    :param filename: location of database to load
    :return:
    """
    with app.app_context():
        with open(filename, "r", encoding="utf-8") as handle:
            data = json.load(handle)

            cards_db = {}

            for card in data:
                if "cost" not in card:
                    continue

                card_id = card["id"]
                mana = card["cost"]
                name = card["name"]

                cards_db[card_id] = {
                    "mana": mana,
                    "name": name
                }

            return cards_db

####### load the cards db #######
GLOBAL_CARDS_DB = load_cards_db()


def sort_cards(cards):
    """
    :param cards: list of card ids to sort
    :return: list of card dictionaries of mana, card, and multiplicty, sorted by mana and subsorted by card text
    """
    multiplicity_dictionary = {}

    for card in cards:
        multiplicity_dictionary[card] = multiplicity_dictionary.get(card, 0) + 1

    unique = set()
    for card in cards:
        if card not in unique:
            unique.add(card)

    sorted_by_mana = {}
    for card in unique:
        # initialize list if not already initialized
        sorted_by_mana[get_mana_for_card(card)] = sorted_by_mana.get(get_mana_for_card(card), [])
        # append the card to its mana position
        sorted_by_mana[get_mana_for_card(card)].append(card)

    for mana_cost in sorted_by_mana:
        sorted_by_mana[mana_cost].sort(key=lambda x: get_name_for_card(card).lower())

    # finally, decompose our dictionary of lists into a single list of dictionaries of mana, card, and multiplicity
    final = []
    for i in range(0, 26):  # 25 is the highest mana val of any card in HearthStone
        if i in sorted_by_mana:
            final.extend(
                [
                    {
                        "mana": get_mana_for_card(card),
                        "card": card,
                        "multiplicity": multiplicity_dictionary[card]
                     }
                    for card in sorted_by_mana[i]
                ]
            )

    return final


def get_mana_for_card(card_id):
    return GLOBAL_CARDS_DB[card_id]["mana"]


def get_name_for_card(card_id):
    return GLOBAL_CARDS_DB[card_id]["name"]


###################################
####### Request Functions
###################################


@app.before_request
def before_request():
    conn = MongoClient(MONGO_CONNECTION_URI)
    db = conn[MONGO_DATABASE_NAME]
    g.collection = db[MONGO_COLLECTION_NAME]


###################################
####### View Functions
###################################


@app.route("/")
@app.route("/index")
@app.route("/landing")
def serve_landing_page():
    return render_template("landing.html")


@app.route("/download")
def serve_download_page():
    return render_template("download.html")


@app.route("/viewer_example")
def serve_example():
    return render_template("viewer_example_template.html",
                           cards=[get_url_for_card_id(None)] * 3,
                           hero=get_url_for_hero("none"),
                           drafted=[],
                           manas=[]
                           )


@app.route("/viewer/<_id>")
def serve_viewer(_id):
    try:
        doc = get_document_for_session(_id)
        cards = [get_url_for_card_id(card) for card in doc["current_cards"]]

        drafted = sort_cards(doc["drafted"])

        # front end expects a list of objects (already sorted by mana and name) comprised of three URLs each
        drafted_url_objects = []
        for card in drafted:
            drafted_url_objects.append({
                "mana": get_url_for_mana(card["mana"]),
                "card": get_url_for_card_bar(card["card"]),
                "multiplicity": get_url_for_multiplicity(card["multiplicity"]),
                "full": get_url_for_card_id(card["card"])
            })

        manas = [get_mana_for_card(c) for c in doc["drafted"]]

        # if there are 30 drafted cards, then the draft has finished. let the client know.
        message = ""
        finished = "false"
        if len(cards) == 30:
            message = "Draft has finished. Have a nice day!"
            finished = "true"

        return render_template("viewer_beta_template.html",
                               _id=_id,
                               hero=get_url_for_hero(doc["hero"]),
                               cards=cards,
                               drafted=drafted_url_objects,
                               message=message,
                               finished=finished,
                               manas=manas
                               )
    except TypeError:
        abort(404)


@app.route("/session/new")
def generate_session():
    """
    not the best way to go about things, i know.
    create a unique id, then check if it exists already -- if so, repeat until a unique, unused id is found,
     or fail after number of tries exceeds a hard limit

    upon success, return the session id to the client.
    upon failure, return a 500 HTTP status code
    """
    # todo there has to be a better way to generate an id without fail
    for i in range(0, 10):
        session_id = uuid4().hex
        if not already_exists_in_db(session_id):
            return create_new_session_in_db(session_id)

    abort(500)


@app.route("/session/update/cards/<_id>", methods=["POST"])
def update_session_cards(_id):
    """
    request must be accompanied with JSON array of three cards, like:
    {
        "auth_token": "authorization_token_here",
        "cards": ["ID-0", "ID-1", "ID-2"]
    }

    make sure to set the Content-Type: application/json
    """
    data = request.get_json()

    # perform data validation
    if len(data["cards"]) != 3:
        abort(400)

    # because we are otherwise plugging this string directly into the Mongo search query, we want to avoid a nasty
    # attack where the auth token is a special query (i.e. using wild cards)
    auth_token = "".join(ch for ch in data["auth_token"] if ch.isalnum())

    # update our db entry
    update_session_cards_in_db(_id, auth_token, data["cards"])

    # emit an update message to everyone in the room
    # we send an array of links to the images, so that the frontend does not have to be able to convert a card id
    # into a url. this allows us to change where the pictures are stored without having to modify the front-end
    socketio.emit("cards_updated",
                  {
                      "cards": [get_url_for_card_id(card) for card in data["cards"]]
                  },
                  room=_id)

    return jsonify({
        "success": True,
        "error": False
    })


@app.route("/session/update/hero/<_id>", methods=["POST"])
def update_session_hero(_id):
    """
    request must be accompanied with JSON array of three cards, like:
    {
        "auth_token": "authorization_token_here",
        "hero": "HERO_ID"
    }

    make sure to set the Content-Type: application/json
    """
    data = request.get_json()

    # perform data validation
    if data["hero"] not in VALID_HERO_IDS:
        abort(400)

    # because we are otherwise plugging this string directly into the Mongo search query, we want to avoid a nasty
    # attack where the auth token is a special query (i.e. using wild cards)
    auth_token = "".join(ch for ch in data["auth_token"] if ch.isalnum())

    # update our db entry
    update_session_hero_in_db(_id, auth_token, data["hero"])

    # emit an update message to everyone in the room
    # we send the link to the image, so that the frontend does not have to be able to convert a card id
    # into a url. this allows us to change where the pictures are stored without having to modify the front-end
    socketio.emit("hero_updated",
                  {
                      "hero": get_url_for_hero(data["hero"])
                  },
                  room=_id)

    return jsonify({
        "success": True,
        "error": False
    })


@app.route("/session/update/drafted/<_id>", methods=["POST"])
def update_session_drafted(_id):
    """
    request must be accompanied with JSON array of three cards, like:
    {
        "auth_token": "authorization_token_here",
        "drafted": ["CARD-ID", "CARD-ID", ...] (size <= 30)
    }

    make sure to set the Content-Type: application/json
    """
    data = request.get_json()

    # perform data validation
    if len(data["drafted"]) > 30:
        abort(400)

    # because we are otherwise plugging this string directly into the Mongo search query, we want to avoid a nasty
    # attack where the auth token is a special query (i.e. using wild cards)
    auth_token = "".join(ch for ch in data["auth_token"] if ch.isalnum())

    # update our db entry
    drafted = sort_cards(data["drafted"])
    drafted_as_list_of_card_ids = data["drafted"]
    update_session_drafted_in_db(_id, auth_token, drafted_as_list_of_card_ids)

    # front end expects a list of objects (already sorted by mana and name) comprised of three URLs each
    drafted_url_objects = []
    for card in drafted:
        drafted_url_objects.append({
            "mana": get_url_for_mana(card["mana"]),
            "card": get_url_for_card_bar(card["card"]),
            "multiplicity": get_url_for_multiplicity(card["multiplicity"]),
            "full": get_url_for_card_id(card["card"])
        })

    # manas is an array of mana costs used for updating the chart
    manas = [get_mana_for_card(c) for c in data["drafted"]]

    # emit an update message to everyone in the room
    # we send an array of links to the images, so that the frontend does not have to be able to convert a card id
    # into a url. this allows us to change where the pictures are stored without having to modify the front-end
    socketio.emit("drafted_updated",
                  {
                      "drafted": drafted_url_objects,
                      "manas": manas
                  },
                  room=_id)

    # if the length of drafted cards is 30, then drafting should have finished. let all the clients know to close
    # their connections.
    if len(data["drafted"]) == 30:
        socketio.emit("draft_finished",
                      room=_id)

    return jsonify({
        "success": True,
        "error": False
    })


@app.route("/json/<_id>")
def draftify_session(_id):
    """
    returns raw database Document object for this session.
    :param _id:
    :return:
    """
    if already_exists_in_db(_id):
        # for security purposes, do not return the document's auth_token field
        doc = get_document_for_session(_id)

        return jsonify({
            "session_id": doc["session_id"],
            "current_cards": doc["current_cards"],
            "drafted": doc["drafted"],
            "num_drafted": doc["num_drafted"],
            "hero": doc["hero"],
        })

    abort(404)


###################################
####### SocketIO Functions
###################################


@socketio.on("join")
def on_join(data):
    """
    due to the broadcast nature of our app (single drafter broadcasts to many viewers), we are utilizing rooms
    in our web sockets library. when emitting a message to a room, anyone who is a member of that room (someone who has
    explicitly joined the room) will receive the message.
    """
    room = data["id"]
    join_room(room)

    print("User has joined room " + room)


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
