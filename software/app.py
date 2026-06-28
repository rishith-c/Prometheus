"""
web server + camera loop for the fire detector.

laptop test:     python app.py
on the pi:       python app.py --host 0.0.0.0   (then open http://<pi-ip>:5000 from ur laptop)
test on a clip:  python app.py --source clip.mp4
"""

import argparse
import threading
import time
from collections import deque

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, request

from fire_detector import FireDetector

app = Flask(__name__)


class Worker:
    # camera + detector run on a bg thread, everything else just reads the shared state

    def __init__(self, source=0):
        self.source = source
        self.detector = FireDetector()
        self.lock = threading.Lock()
        self.jpeg = self._placeholder("STARTING")
        self.status = {"detected": False, "confidence": 0.0, "area_pct": 0.0,
                       "flicker": 0.0, "fps": 0.0, "source": str(source),
                       "online": False, "detections": 0, "last_detection": None,
                       "uptime": 0, "events": []}
        self.events = deque(maxlen=40)
        self.running = False
        self._fps = 0.0
        self._was = False
        self._count = 0
        self._last_det = None
        self._t0 = time.time()

    @staticmethod
    def _placeholder(text):
        # just a grey frame w some text for when theres no camera yet
        img = np.full((360, 640, 3), 16, np.uint8)
        cv2.putText(img, text, (200, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (120, 120, 120), 2, cv2.LINE_AA)
        ok, buf = cv2.imencode(".jpg", img)
        return buf.tobytes()

    def _log(self, kind):
        ts = time.strftime("%H:%M:%S")
        self.events.appendleft({"t": ts, "kind": kind})

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        cap = cv2.VideoCapture(self.source)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        last = time.time()
        miss = 0
        self._log("watch started")

        while self.running:
            ok, frame = cap.read()
            if not ok or frame is None:
                # video file just loops. camera: show NO SIGNAL + try reopening
                if isinstance(self.source, str):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                miss += 1
                with self.lock:
                    self.jpeg = self._placeholder("NO SIGNAL")
                    self.status["online"] = False
                    self.status["source"] = f"cam{self.source} offline"
                time.sleep(0.3)
                if miss % 10 == 0:
                    cap.release()
                    cap = cv2.VideoCapture(self.source)
                continue
            miss = 0

            annotated, det = self.detector.process(frame)

            now = time.time()
            dt = now - last
            last = now
            if dt > 0:
                self._fps = 0.9 * self._fps + 0.1 * (1.0 / dt)

            # only count + log on the edge (clear -> fire / fire -> clear)
            if det["detected"] and not self._was:
                self._count += 1
                self._last_det = time.strftime("%H:%M:%S")
                self._log("fire detected")
            elif not det["detected"] and self._was:
                self._log("cleared")
            self._was = det["detected"]

            ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            status = {
                **det,
                "fps": round(self._fps, 1),
                "source": str(self.source) if not isinstance(self.source, str)
                else self.source,
                "online": True,
                "detections": self._count,
                "last_detection": self._last_det,
                "uptime": int(now - self._t0),
                "events": list(self.events)[:12],
            }
            with self.lock:
                if ok:
                    self.jpeg = buf.tobytes()
                self.status = status

        cap.release()

    def get_jpeg(self):
        with self.lock:
            return self.jpeg

    def get_status(self):
        with self.lock:
            return dict(self.status)

    def configure(self, cfg):
        self.detector.update(**cfg)


worker = None  # set in main()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    # mjpeg stream, just keep yielding the latest jpeg
    def gen():
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        while True:
            jpeg = worker.get_jpeg()
            if jpeg:
                yield boundary + jpeg + b"\r\n"
            time.sleep(0.04)  # ~25fps to the browser is plenty
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/status")
def status():
    return jsonify(worker.get_status())


@app.route("/config", methods=["POST"])
def config():
    worker.configure(request.get_json(force=True) or {})
    return jsonify({"ok": True})


def parse_source(s):
    # "0"/"1" -> camera index, anything else -> treat as a file path
    return int(s) if s.isdigit() else s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0",
                    help="camera index (0,1,...) or path to a video file")
    ap.add_argument("--host", default="127.0.0.1",
                    help="use 0.0.0.0 on the pi so the laptop can reach it")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()

    worker = Worker(parse_source(args.source))
    worker.start()
    print(f"\n  Fire Watch -> http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, threaded=True)
