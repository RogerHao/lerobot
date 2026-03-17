#!/usr/bin/env python3
"""Minimal SO-101 web controller for lerobot 0.4.4 API."""

import json
import logging
import threading
import time
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorNormMode, MotorCalibration

logger = logging.getLogger(__name__)

MOTORS = {
    "shoulder_pan": Motor(1, "sts3215", MotorNormMode.DEGREES),
    "shoulder_lift": Motor(2, "sts3215", MotorNormMode.DEGREES),
    "elbow_flex": Motor(3, "sts3215", MotorNormMode.DEGREES),
    "wrist_flex": Motor(4, "sts3215", MotorNormMode.DEGREES),
    "wrist_roll": Motor(5, "sts3215", MotorNormMode.DEGREES),
    "gripper": Motor(6, "sts3215", MotorNormMode.DEGREES),
}

CALIBRATION_PATH = Path.home() / ".cache/huggingface/lerobot/calibration/robots/so101_follower/None.json"


def load_calibration(path: Path) -> dict[str, MotorCalibration]:
    with open(path) as f:
        raw = json.load(f)
    return {
        name: MotorCalibration(
            id=data["id"],
            drive_mode=data["drive_mode"],
            homing_offset=data["homing_offset"],
            range_min=data["range_min"],
            range_max=data["range_max"],
        )
        for name, data in raw.items()
    }


class ArmController:
    def __init__(self, port: str):
        self.port = port
        self.bus: FeetechMotorsBus | None = None
        self.calibration: dict[str, MotorCalibration] | None = None
        self.lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self.bus is not None

    def connect(self):
        if self.bus is not None:
            return
        self.calibration = load_calibration(CALIBRATION_PATH)
        self.bus = FeetechMotorsBus(
            port=self.port, motors=MOTORS, calibration=self.calibration
        )
        self.bus.connect()
        # Enable torque on all motors
        for name in MOTORS:
            self.bus.write("Torque_Enable", name, 1, normalize=False)
        logger.info("Arm connected on %s", self.port)

    def disconnect(self):
        if self.bus is None:
            return
        with self.lock:
            for name in MOTORS:
                try:
                    self.bus.write("Torque_Enable", name, 0, normalize=False)
                except Exception:
                    pass
            self.bus.disconnect()
            self.bus = None
        logger.info("Arm disconnected")

    def read_positions(self) -> dict[str, float]:
        if self.bus is None:
            return {}
        with self.lock:
            return {
                name: round(float(self.bus.read("Present_Position", name)), 1)
                for name in MOTORS
            }

    def write_position(self, motor: str, degrees: float):
        if self.bus is None:
            return
        with self.lock:
            self.bus.write("Goal_Position", motor, degrees)


def create_app(port: str, host: str = "0.0.0.0", web_port: int = 8080):
    template_folder = Path(__file__).parent / "templates"
    static_folder = Path(__file__).parent / "static"

    app = Flask(
        __name__,
        template_folder=str(template_folder),
        static_folder=str(static_folder),
    )
    app.config["SECRET_KEY"] = "so101"
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
    arm = ArmController(port)

    # --- Status monitor thread ---
    status_running = threading.Event()

    def status_loop():
        while status_running.is_set():
            if arm.connected:
                try:
                    pos = arm.read_positions()
                    socketio.emit("robot_status", {
                        "positions": pos,
                        "connected": True,
                        "timestamp": time.time(),
                    })
                except Exception as e:
                    logger.warning("Status read error: %s", e)
            time.sleep(0.1)

    # --- Routes ---
    @app.route("/")
    def index():
        return render_template("robot_control.html")

    @app.route("/api/status")
    def api_status():
        if not arm.connected:
            return jsonify(connected=False, joints=[], current_positions={}, joint_ranges={})
        pos = arm.read_positions()
        joints = [f"{name}.pos" for name in MOTORS]
        # Ranges in degrees — these are the calibrated degree limits
        degree_ranges = {
            "shoulder_pan": (-150, 150),
            "shoulder_lift": (-150, 150),
            "elbow_flex": (-150, 150),
            "wrist_flex": (-150, 150),
            "wrist_roll": (-150, 150),
            "gripper": (-100, 100),
        }
        ranges = {}
        for name in MOTORS:
            lo, hi = degree_ranges.get(name, (-150, 150))
            ranges[f"{name}.pos"] = {"min": lo, "max": hi, "center": 0}
        current = {f"{name}.pos": val for name, val in pos.items()}
        return jsonify(connected=True, joints=joints, current_positions=current, joint_ranges=ranges)

    @app.route("/api/connect", methods=["POST"])
    def api_connect():
        if arm.connected:
            return jsonify(status="info", message="Already connected", connected=True)
        try:
            arm.connect()
            status_running.set()
            threading.Thread(target=status_loop, daemon=True).start()
            return jsonify(status="success", message="Connected", connected=True, robot_type="SO-101")
        except Exception as e:
            return jsonify(status="error", message=str(e), connected=False)

    @app.route("/api/disconnect", methods=["POST"])
    def api_disconnect():
        status_running.clear()
        arm.disconnect()
        return jsonify(status="success", message="Disconnected", connected=False)

    @app.route("/api/control", methods=["POST"])
    def api_control():
        if not arm.connected:
            return jsonify(status="error", message="Not connected")
        data = request.get_json()
        if not data:
            return jsonify(status="error", message="No data")
        try:
            for joint_key, value in data.items():
                motor_name = joint_key.replace(".pos", "")
                if motor_name in MOTORS:
                    arm.write_position(motor_name, float(value))
            return jsonify(status="success", message="OK")
        except Exception as e:
            return jsonify(status="error", message=str(e))

    @socketio.on("request_status")
    def on_request_status():
        if arm.connected:
            pos = arm.read_positions()
            emit("robot_status", {"positions": pos, "connected": True, "timestamp": time.time()})

    def run():
        logger.info("Starting on http://%s:%d", host, web_port)
        try:
            socketio.run(app, host=host, port=web_port, use_reloader=False, allow_unsafe_werkzeug=True)
        finally:
            status_running.clear()
            arm.disconnect()

    return app, socketio, run


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(description="SO-101 Web Controller")
    parser.add_argument("--port", required=True, help="Serial port (e.g. /dev/ttyACM0)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--web-port", type=int, default=8080)
    args = parser.parse_args()

    _, _, run = create_app(args.port, args.host, args.web_port)
    run()
