====================
Draft With Me Server
====================

Todo
^^^^
- Integration with arena draft services, i.e. ones that provide deck building assistance.
- Perfect the card identification.

What?
^^^^^
Draft With Me is a method for "streaming" your arena drafts to friends, without the use of screen sharing. Simply
share the link that the app provides, and go! You can have as many people as you want view your draft.

Why?
^^^^
Having enjoyed playing arena runs together with a friend, drafting was the only piece that required extraneous effort
to do together. Screen sharing apps work for this, but I consider them overkill for what should really be built into
the game anyway. Thus was born Draft With Me!

How?
^^^^
- MongoDB (database): Easy to setup, Heroku support, good Python support, and no need for a relational database.
- Flask (HTTP): Easy to use, intuitive, no unneeded batteries included, templating.
- Flask-SocketIO: Websocket support :-)
- Gunicorn / Eventlet: HTTP server
- Redis (message queue): Needed by Flask-SocketIO for multiplexing websocket connections.
- Amazon S3: static content hosting.
- Heroku: Hosting made simple for small hobby projects.

API
^^^
Session id should be replaced with session id given by ``/session/new``.

+-----------------------------------------+------+---------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------------------------------+----------------------------------------------------------------------------------------------------+
| Endpoint                                | Type | Parameters (JSON)                                                         | Success                                                                                                                                                      | Failure                                     | Example                                                                                            |
+=========================================+======+===========================================================================+==============================================================================================================================================================+=============================================+====================================================================================================+
| ``/session/new``                        | GET  | None                                                                      | {"session_id": "42", "auth_token": "42"}                                                                                                                     | 500 if cannot generate id                   | GET /session/new                                                                                   |
+-----------------------------------------+------+---------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------------------------------+----------------------------------------------------------------------------------------------------+
| ``/session/update/cards/session_id``    | POST | {"auth_token": "42", "cards": ["Card Id 1", "Card Id 2", "Card Id 3"]}    | {"success": True, "error": False}                                                                                                                            | 400 if length of cards is not 3             | POST /session/update/cards/42 {"auth_token": "42", "cards": ["42", "42", "42"]}                    |
+-----------------------------------------+------+---------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------------------------------+----------------------------------------------------------------------------------------------------+
| ``/session/update/hero/session_id``     | POST | {"auth_token": "42", "hero": "mage"}                                      | {"success": True, "error": False}                                                                                                                            | 400 if hero is not valid                    | POST /session/update/hero/42 {"auth_token": "42", "hero": "mage"}                                  |
+-----------------------------------------+------+---------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------------------------------+----------------------------------------------------------------------------------------------------+
| ``/session/update/drafted/session_id``  | POST | {"auth_token": "42", "drafted": ["Card Id 1", ...]}                       | {"success": True, "error": False}                                                                                                                            | 400 if length of drafted is greater than 30 | POST /session/update/drafted/42 {"auth_token": "42", "drafted": ["42", "42", "42", "42", "42"]}    |
+-----------------------------------------+------+---------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------------------------------+----------------------------------------------------------------------------------------------------+
| ``/json/session_id``                    | GET  | None                                                                      | {"session_id": session_id, "current_cards": ["Card Id 1", "Card Id 2", "Card Id 3"], "drafted": ["Card Id 1", ...], "num_drafted": 0, "hero": "mage",}       | 404 if not found                            | GET /json/42                                                                                       |
+-----------------------------------------+------+---------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------------------------------+----------------------------------------------------------------------------------------------------+


WebSockets API
^^^^^^^^^^^^^^

+-------------------+------------------------------------------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------------------------+
|  Event Name       | Payload                                                                                                                            | Notes                                                                                                                |
+===================+====================================================================================================================================+======================================================================================================================+
| connect           | None                                                                                                                               | will respond with join                                                                                               |
+-------------------+------------------------------------------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------------------------+
| cards_updated     | {"cards": [CARD_ONE_ID, CARD_TWO_ID, CARD_THREE_ID]}                                                                               |                                                                                                                      |
+-------------------+------------------------------------------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------------------------+
| hero_updated      | {"hero": HERO_IMAGE_ID}                                                                                                            |                                                                                                                      |
+-------------------+------------------------------------------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------------------------+
| drafted_updated   | {"drafted": [{"mana": CARD_MANA, "card": CARD_ID,  "multiplicity": NUM_CARDS,}, ...], "manas":  [MANA0, MANA1, MANA2, ...]}        | drafted array is already sorted by mana, then by name; manas is array of integers representing mana values of cards. |
+-------------------+------------------------------------------------------------------------------------------------------------------------------------+----------------------------------------------------------------------------------------------------------------------+

Examples
^^^^^^^^
Check out /viewer_example for a demo of the service. The demo runs using Javascript to simulate a draft -- the
simulator processes a simple drafting language. Commands are:

- init: get a new session id / auth token from the server. also starts the websocket connection.
- hero <hero_id>: plain text hero name, i.e. "hero mage" ("druid", "hunter", "mage", "priest", "shaman", "thief", "paladin", "warlock", "warrior").
- cards <CARD_ID1,CARD_ID2,CARD_ID3>: 3 cards separated by comma, i.e. "cards CS2_032,EX1_277,CS2_029"
- drafted <Array of card ids>: same format as above, card ids separated by comma (no space!). up to 30

Timeout is the time between commands, in milliseconds.

Store the commands as an array of Strings, and run them with ``processTests(commands, timeout)``.

Thanks to
^^^^^^^^^
- HearthSim team for cards.collectible.json
- All the developers of the open source projects used here!
- Blizzard for making wonderful games!
- Jake for always saving your gold to play arena runs with me as co-pilot!

License
^^^^^^^
This project is licensed MIT. Please see LICENSE for more information.

Notice / Copyrighted Materials
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Hearthstone text, image and other contents are copyright of Blizzard Entertainment. Copyright © 2016 Blizzard Entertainment.