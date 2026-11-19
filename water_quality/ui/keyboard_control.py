"""
Python side of the keyboard component (ui/keyboard/index.html).

Returns the latest key event as {"id", "key", "cm"} or None.
Each event has a unique id, so the same key press is never handled twice.
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import config

_component = components.declare_component(
    "drone_keyboard", path=str(Path(__file__).resolve().parent / "keyboard")
)


def keyboard_control(connected: bool, flying: bool, busy: bool, detecting: bool,
                     move_cm: int, forward_cm: int) -> dict | None:
    event = _component(
        connected=connected,
        flying=flying,
        busy=busy,
        detecting=detecting,
        move_cm=int(move_cm),
        forward_cm=int(forward_cm),
        min_cm=config.DRONE_MIN_MOVE_CM,
        max_cm=config.DRONE_MAX_MOVE_CM,
        test_mode=config.DRONE_TEST_MODE,
        key="drone_keyboard",
        default=None,
    )
    if not event or event.get("id") == st.session_state.get("last_drone_key_id"):
        return None
    st.session_state.last_drone_key_id = event["id"]
    return event
