import datetime
import functools
import logging
import threading
import time
from contextlib import contextmanager
from typing import Iterable, Optional

import serial
from flask import Flask, abort, jsonify, request

from bravia_serial_control.display import BraviaDisplay, InputMode, PictureMode
from bravia_serial_control.serial_protocol import BraviaDisplaySerialPort


COMMAND_INTERVAL_SECS = 0.5

app = Flask(__name__)
lock = threading.Lock()
last_request_time: Optional[datetime.datetime] = None


def throttled_request(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        global last_request_time
        with lock:
            if last_request_time is not None:
                secs_since_last_request = (
                    datetime.datetime.now() - last_request_time
                ).total_seconds()

                if secs_since_last_request < COMMAND_INTERVAL_SECS:
                    secs_to_wait = COMMAND_INTERVAL_SECS - secs_since_last_request
                    logging.info("Throttling for %.3f seconds", secs_to_wait)
                    time.sleep(secs_to_wait)

            return_value = f(*args, **kwargs)

            last_request_time = datetime.datetime.now()
            return return_value

    return wrapper


@app.route("/power", methods=["GET", "POST"])
@throttled_request
def power():
    if request.method == "GET":
        with open_bravia() as bravia:
            return jsonify({"power": "on" if bravia.get_power_mode() else "off"})

    if request.method == "POST":
        raw_requested_mode = request.json.get("power").lower()
        if raw_requested_mode == "off":
            requested_mode = False
        elif raw_requested_mode == "on":
            requested_mode = True
        else:
            abort(400)

        with open_bravia() as bravia:
            bravia.set_power_mode(requested_mode)
            return jsonify({"power": "on" if requested_mode else "off"})

    abort(405)


@app.route("/picture_mode", methods=["POST"])
@throttled_request
def picture_mode():
    raw_requested_mode = request.json.get("picture_mode").upper()

    try:
        requested_mode = PictureMode[raw_requested_mode]
    except ValueError:
        abort(400)

    with open_bravia() as bravia:
        bravia.set_picture_mode(requested_mode)
        return jsonify({"picture_mode": requested_mode.name.lower()})


@app.route("/input_mode", methods=["GET", "POST"])
@throttled_request
def input_mode():
    if request.method == "GET":
        with open_bravia() as bravia:
            return jsonify({"input_mode": bravia.get_input_mode().name.lower()})

    if request.method == "POST":
        raw_requested_mode = request.json.get("input_mode").lower()

        try:
            requested_mode = InputMode[raw_requested_mode]
        except ValueError:
            abort(400)

        with open_bravia() as bravia:
            bravia.set_input_mode(requested_mode)
            return jsonify({"input_mode": requested_mode.name.lower()})

    abort(405)


@contextmanager
def open_bravia() -> Iterable[BraviaDisplay]:
    with serial.Serial(port="/dev/ttyUSB0", baudrate=9600, timeout=5) as raw_serial:
        bravia_serial = BraviaDisplaySerialPort(raw_serial)
        yield BraviaDisplay(bravia_serial)


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(asctime)s] [%(levelname)s] %(message)s", level=logging.DEBUG
    )

    app.run(host="0.0.0.0", port=5000, debug=True)
