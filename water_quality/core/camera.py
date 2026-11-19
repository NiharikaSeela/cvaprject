"""
Webcam helpers. DirectShow is used on Windows because it opens and releases
cameras more reliably than the default backend.
"""
import platform

import cv2

import config


def open_camera(index: int = config.CAMERA_INDEX):
    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
    return cap


def release_camera(cap) -> None:
    if cap is not None and cap.isOpened():
        cap.release()
