"""
fire detector. no ML model, just opencv (color + flicker).
runs fully offline which is kinda the whole point on a drone.

per frame: grab the warm/bright fire-colored pixels, check they actually flicker
(static orange stuff doesnt move), debounce over a few frames, spit out a confidence.
its classical CV so it WILL false trigger in harsh light. treat it as a hint not proof.
"""

from collections import deque
import time
import cv2
import numpy as np


class FireDetector:
    # everything gets resized to this width. keeps it fast on the pi and the
    # thresholds behave the same no matter which camera im on
    PROC_WIDTH = 640

    def __init__(
        self,
        min_area=500,          # smallest blob (px) that counts as fire
        sat_min=110,           # min saturation for a warm/fire color
        val_min=150,           # min brightness
        flicker_filter=0.5,    # 0 = ignore flicker (loose), 1 = demand loads (strict)
        persistence=5,         # how many frames the debounce looks at
        history=14,            # frames of mask history kept for the flicker calc
        show_overlay=True,     # tint the detected fire pixels on the output frame
    ):
        self.min_area = int(min_area)
        self.sat_min = int(sat_min)
        self.val_min = int(val_min)
        self.flicker_filter = float(flicker_filter)
        self.persistence = int(persistence)
        self.show_overlay = bool(show_overlay)

        self._mask_hist = deque(maxlen=int(history))
        self._hits = deque(maxlen=self.persistence)   # was-it-fire per frame
        self._conf_ema = 0.0                           # smoothed conf so it doesnt jump around
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    # live tuning from the dashboard sliders
    def update(self, **cfg):
        for k in ("min_area", "sat_min", "val_min", "persistence"):
            if k in cfg and cfg[k] is not None:
                setattr(self, k, int(cfg[k]))
        if cfg.get("flicker_filter") is not None:
            self.flicker_filter = float(cfg["flicker_filter"])
        if cfg.get("show_overlay") is not None:
            self.show_overlay = bool(cfg["show_overlay"])
        if "persistence" in cfg and cfg["persistence"]:
            self._hits = deque(self._hits, maxlen=self.persistence)

    # build the fire-pixel mask
    def _fire_mask(self, bgr):
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        # warm + bright + saturated colors (the orange/red/yellow flame body)
        warm = cv2.inRange(hsv, (0, self.sat_min, self.val_min), (35, 255, 255))
        warm |= cv2.inRange(hsv, (170, self.sat_min, self.val_min), (179, 255, 255))

        # fire skews R>=G>=B with a real red lead, not just any bright pixel
        b, g, r = cv2.split(bgr.astype(np.int16))
        order = ((r >= g) & (g >= b) & (r > 150) & ((r - b) > 28)).astype(np.uint8) * 255
        warm = cv2.bitwise_and(warm, order)

        # bright near-white core, but ONLY where its touching warm pixels.
        # otherwise lamps / white walls light up the whole mask
        core = cv2.inRange(hsv, (0, 0, 245), (179, 70, 255))
        warm_dil = cv2.dilate(warm, self._kernel, iterations=2)
        core = cv2.bitwise_and(core, warm_dil)

        mask = cv2.bitwise_or(warm, core)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel)   # kill specks
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel, iterations=2)
        return mask

    def _flicker_score(self, mask, fire_area):
        # how much of the fire area changed since last frame. flame shimmers,
        # a static orange thing doesnt. ts is the bit that kills false positives
        if not self._mask_hist:
            return 0.0
        diff = cv2.absdiff(mask, self._mask_hist[-1])
        changed = int(np.count_nonzero(diff))
        return changed / float(max(fire_area, 1))

    # the main one. takes a BGR frame, returns (annotated frame, status dict)
    def process(self, frame_bgr):
        # resize to PROC_WIDTH so its fast + thresholds stay consistent
        h, w = frame_bgr.shape[:2]
        if w != self.PROC_WIDTH:
            scale = self.PROC_WIDTH / float(w)
            frame_bgr = cv2.resize(frame_bgr, (self.PROC_WIDTH, int(h * scale)))
        H, W = frame_bgr.shape[:2]
        frame_px = float(H * W)

        mask = self._fire_mask(frame_bgr)

        cnts = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]   # opencv 3 vs 4 return different stuff

        boxes, fire_area = [], 0
        for c in cnts:
            a = cv2.contourArea(c)
            if a >= self.min_area:
                fire_area += a
                boxes.append([int(v) for v in cv2.boundingRect(c)])

        flicker = self._flicker_score(mask, fire_area)
        self._mask_hist.append(mask)

        area_frac = fire_area / frame_px
        raw = len(boxes) > 0

        # flicker gate. required flicker scales w the slider (0..~0.22)
        flick_req = (1.0 - self.flicker_filter) * 0.22
        flicker_ok = flicker >= flick_req or area_frac > 0.06  # big steady blaze still counts

        self._hits.append(bool(raw and flicker_ok))
        votes = sum(self._hits)
        detected = votes >= max(2, int(np.ceil(self.persistence * 0.6)))

        # confidence = area + flicker + how many recent frames hit, then smoothed
        area_score = min(area_frac / 0.05, 1.0)
        flick_score = min(flicker / 0.20, 1.0)
        persist_score = votes / float(self.persistence)
        target = 100.0 * (0.50 * area_score + 0.20 * flick_score + 0.30 * persist_score)
        if not raw:
            target *= 0.25  # nothing warm on screen, drop it fast
        self._conf_ema = 0.7 * self._conf_ema + 0.3 * target
        confidence = round(self._conf_ema, 1)

        annotated = self._annotate(frame_bgr, mask, boxes, detected, confidence)

        status = {
            "detected": bool(detected),
            "confidence": confidence,
            "area_pct": round(area_frac * 100.0, 2),
            "flicker": round(flicker, 3),
            "boxes": boxes,
            "proc_size": [W, H],
        }
        return annotated, status

    # draw the boxes + corner ticks on the frame (just looks better imo)
    def _annotate(self, frame, mask, boxes, detected, confidence):
        out = frame
        if self.show_overlay and boxes:
            tint = np.zeros_like(frame)
            tint[mask > 0] = (30, 110, 255)  # orange in BGR
            out = cv2.addWeighted(frame, 1.0, tint, 0.30, 0)

        colour = (40, 60, 255) if detected else (230, 200, 60)  # red if fire else cyan (BGR)
        for (x, y, w, h) in boxes:
            cv2.rectangle(out, (x, y), (x + w, y + h), colour, 2)
            # corner ticks
            t = max(8, w // 8)
            for (cx, cy, dx, dy) in (
                (x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)
            ):
                cv2.line(out, (cx, cy), (cx + dx * t, cy), colour, 2)
                cv2.line(out, (cx, cy), (cx, cy + dy * t), colour, 2)

        if detected and boxes:
            bx = max(boxes, key=lambda b: b[2] * b[3])
            cv2.putText(out, f"FIRE {confidence:.0f}%", (bx[0], max(18, bx[1] - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 60, 255), 2, cv2.LINE_AA)
        return out
