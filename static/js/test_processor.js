function getNextAction(action_list) {
    var action = action_list.splice(0, 1);
    // splice modifies the list in place and returns a new array containing elements removed
    action = action[0];

    // remove any comments by splitting "#"
    action = action.split("#")[0];

    var space_index = action.indexOf(" ");

    action = {
        type: action.substring(0, space_index === -1 ? action.length : space_index),
        // remember to convert from String to appropriate data type!
        data: space_index === -1 ? null : action.substring(space_index + 1).replace(/ /g, "")
    };

    return action;
}

var session_data = {
    session_id: null,
    auth_token: null
};

var processing = false;

var chart = null;

function processTests(action_list, delay) {
    window.setInterval(function () {
        // if currently performing an async operation, do not attempt to perform another one simultaneously
        if (processing) {
            return;
        }

        if (action_list.length === 0) {
            return;
        }

        var action = getNextAction(action_list);

        processing = true;

        switch (action.type) {
            case "init":
                // perform init
                console.log("Initializing...");

                init().then(function () {
                    setupWebSocket(session_data.session_id);
                    processing = false;
                });

                break;
            case "drafted":
            case "cards":
                // update drafted to action.data
                console.log("Performing update to " + action.type);

                action.data = action.data.split(",");
                updateServer(session_data.session_id, session_data.auth_token, action.data, action.type)
                    .then(() => processing = false);

                break;
            case "hero":
                console.log("Performing update to " + action.type);

                updateServer(session_data.session_id, session_data.auth_token, action.data, action.type)
                    .then(() => processing = false);

                break;
        }
    }, delay);
}

function initChart() {
    chart = new CanvasJS.Chart("chartContainer", {
        animationEnabled: true,
        backgroundColor: "#eee",
        title: {
            text: "Mana Breakdown"
        },
        axisY: {
            title: "# Cards",
            minimum: 0,
            maximum: 10
        },
        axisX: {
            title: "Mana Cost"
        },
        data: [
            {
                type: "column", //change type to bar, line, area, pie, etc
                color: "#000000",
                dataPoints: [
                    {label: "0", y: 0},
                    {label: "1", y: 0},
                    {label: "2", y: 0},
                    {label: "3", y: 0},
                    {label: "4", y: 0},
                    {label: "5", y: 0},
                    {label: "6", y: 0},
                    {label: "7+", y: 0},

                ]
            }
        ]
    });

    chart.render();
}

function init() {
    var get_session_endpoint = 'https://' + document.domain + ':' + location.port + '/session/new';
    return fetch(get_session_endpoint, {method: "GET"})
        .then(function (response) {
            return response.json();
        })
        .then(function (myJson) {
            session_data = myJson;

            var elem = document.getElementById("viewer_link");
            elem.href = 'https://' + document.domain + ':' + location.port + '/viewer/' + session_data.session_id;

            initChart();
        })
        .catch(function (err) {
            console.log(err);
        });
}

function updateServer(session_id, auth_token, data, endpoint) {
    var update_hero_endpoint =
        'https://' + document.domain + ':' + location.port + '/session/update/' + endpoint + '/' + session_id;

    var post_data = {
        session_id: session_id,
        auth_token: auth_token,
        [endpoint]: data
    };

    return fetch(update_hero_endpoint, {
        method: 'POST',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(post_data)
    })
        .then(function (response) {
            return response.json();
        })
        .then(function (myJson) {
            console.log(myJson);
        })
        .catch(function (err) {
            console.log(err);
        });
}

function setupWebSocket(session_id) {
    socket = io.connect('https://' + document.domain + ':' + location.port);

    socket.on('connect', function () {
        socket.emit('join', {id: session_id});
    });

    socket.on('cards_updated', function (data) {
        /*
         * data will be the three URLs to update our images to
         */

        // validate data
        if (false === ("cards") in data)
            return false;

        if (data["cards"].length != 3)
            return false;

        var card_element_ids = ["card_zero", "card_one", "card_two"];

        for (var i = 0; i < 3; i++) {
            updateImage(card_element_ids[i], data["cards"][i]);
        }

    });

    socket.on('hero_updated', function (data) {
        /*
         * data must include "hero" key, which is URL for new hero image
         */

        if (false === ("hero" in data))
            return false;

        updateImage("hero", data["hero"]);
    });

    socket.on('drafted_updated', function (data) {
        /*
         * data must include key "drafted", which is array of images to display vertically, sorted by mana
         * data must also include "manas" key, which is array of mana values of drafted cards.
         *
         * data will be of form:
         * {
         *  "drafted":
         * [
         *  {
         *    mana: url for mana image,
         *    card: url for card image,
         *    multiplicity: url for multiplicity image
         *   },
         *   ...
         *  ],
         *
         *  "manas": [
         *      0,
         *      0,
         *      1,
         *      5,
         *      3,
         *      ...
         *   ]
         *  }
         */
        if (false === ("drafted" in data))
            return false;

        // thanks to http://stackoverflow.com/questions/10750137/remove-all-li-from-ul
        // remove all <li> in our <ul> drafted
        var root = document.getElementById("drafted");
        while (root.firstChild) {
            root.removeChild(root.firstChild);
        }

        // decompose our input into a new list
        var index, li, element, keys = ["mana", "card", "multiplicity"];

        for (var i = 0; i < data["drafted"].length; i++) {
            li = document.createElement("li");

            li.setAttribute("data-toggle", "tooltip");
            li.setAttribute("data-placement", "left");
            li.setAttribute("data-html", "true");
            li.setAttribute("title", "<img src='" + data["drafted"][i]["full"] + "'>");

            for (index of keys) {
                element = document.createElement("img");
                element.setAttribute("src", data["drafted"][i][index]);

                li.appendChild(element);
            }

            root.appendChild(li);
        }

        // turn on the tooltips
        $(function () {
            $('[data-toggle="tooltip"]').tooltip()
        });

        // also process manas -- breakdown of drafted cards by mana value
        if (false === ("manas") in data)
            return false;

        updateChart(data["manas"]);

        // update the number drafted
        var num_drafted = data["manas"].length;

        var num_drafted_elem = document.getElementById("num_drafted");
        num_drafted_elem.innerHTML = "Number Drafted: " + num_drafted;
    });
}

function updateImage(elem_id, new_image_url) {
    var elem = document.getElementById(elem_id);
    elem.src = "/static/img/animate.svg";
    window.setTimeout(function () {
        elem.src = new_image_url;
    }, 1250);
}

function updateChart(manas) {
    // array of length 8 for storing number of cards matching that mana cost (0 thru 7+)
    var manas_combined = [
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0
    ];

    manas.forEach(function (d) {
        manas_combined[Math.min(d, 7)]++;
    });

    chart.options.data[0] = {
        type: "column", //change type to bar, line, area, pie, etc
        dataPoints: [
            {label: "0", y: manas_combined[0]},
            {label: "1", y: manas_combined[1]},
            {label: "2", y: manas_combined[2]},
            {label: "3", y: manas_combined[3]},
            {label: "4", y: manas_combined[4]},
            {label: "5", y: manas_combined[5]},
            {label: "6", y: manas_combined[6]},
            {label: "7+", y: manas_combined[7]},

        ]
    };

    chart.render();
}
