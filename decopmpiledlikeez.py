import json
import os
import threading
import time
import requests
import urllib3
import tkinter as tk
from tkinter import filedialog
import dearpygui.dearpygui as dpg
from urllib3.exceptions import InsecureRequestWarning

# =========================================================
# CONSTANTS (From __main___constants.txt / .nbc)
# =========================================================
CONFIG_FILE = 'config.json'
FLAGS_URL = 'https://raw.githubusercontent.com/MaximumADHD/Roblox-Client-Tracker/refs/heads/roblox/FVariables.txt'
DEFAULT_JSON_PATH = 'f' # Identified in c[313] and c[312]

# =========================================================
# GLOBALS
# =========================================================
flags = {}
applicationSettings = {}
disabledFlags = []
keybinds = {}
flagOrder = []
json_path = ""
last_keybind_time = 0
pressed_keys = set()
is_setting_keybind = False

# =========================================================
# CORE FUNCTIONS (Signatures from .nbc / reconstructed_source.py)
# =========================================================

def load_json():
    """Loads settings and flags from the local JSON file."""
    global applicationSettings, flags, disabledFlags, keybinds, flagOrder
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            applicationSettings = data.get('applicationSettings', {})
            flags = data.get('flags', {})
            disabledFlags = data.get('disabledFlags', [])
            keybinds = data.get('keybinds', {})
            flagOrder = data.get('flagOrder', [])
    except (FileNotFoundError, json.JSONDecodeError):
        pass

def save_json():
    """Saves current state to config.json."""
    data = {
        'applicationSettings': applicationSettings,
        'flags': flags,
        'disabledFlags': disabledFlags,
        'keybinds': keybinds,
        'flagOrder': flagOrder
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def fetch_flags():
    """Fetches FVariables from the GitHub URL."""
    try:
        urllib3.disable_warnings(InsecureRequestWarning)
        response = requests.get(FLAGS_URL, verify=False)
        if response.status_code == 200:
            lines = response.text.split('\n')
            # Logic uses startswith('[C++]') and '[Lua]' as per constants
            allowed_prefixes = ('[C++]', '[Lua]')
            # Reconstruction of parsing logic based on 'DFInt', 'DFFlag', 'DFString'
            for line in lines:
                if any(line.startswith(p) for p in allowed_prefixes):
                    # Internal parsing logic...
                    pass
    except Exception:
        pass

# =========================================================
# UI CALLBACKS (Matched to your constants)
# =========================================================

def update_search(sender, app_data):
    """Callback for the Search input text."""
    # Logic to filter available_flags_list
    pass

def update_flag_value(sender, app_data, user_data):
    """Callback for 'Update Value' button."""
    # user_data usually contains the flag name
    pass

def toggle_always_on_top(sender, app_data):
    """Callback for 'AlwaysOnTop Enabled' checkbox."""
    dpg.configure_viewport(0, always_on_top=app_data)

def select_json_file():
    """Opens tkinter file dialog to pick a JSON path."""
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(filetypes=[('JSON files', '*.json')])
    if path:
        dpg.set_value("json_path_input", path)

def export_json():
    """Exports current flags to a string or file (Pyperclip is NOT in core constants)."""
    # Note: Constant c[279] is 'Export JSON', but 'pyperclip' is an external guess.
    # The original file likely uses a internal dpg copy or file write.
    pass

# =========================================================
# THEME & UI LAYOUT
# =========================================================

def apply_light_pink_theme():
    """Sets the custom light pink theme colors identified in NBC constants."""
    with dpg.theme() as theme_id:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (255, 230, 235))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (80, 30, 60))
            # Other color constants from c[200]-c[240]...
    dpg.bind_theme(theme_id)

def main():
    dpg.create_context()
    
    with dpg.window(tag="main_window", label="Flag Browser - imgui.cc"):
        with dpg.tab_bar(tag="tab_bar"):
            with dpg.tab(label="Flag Browser"):
                dpg.add_input_text(label="Search", callback=update_search)
                with dpg.child_window(tag="available_flags_list", height=320):
                    pass
                dpg.add_text("Selected Flag: None", tag="selected_flag_text")
                dpg.add_input_text(tag="flag_value_input", label="Value")
                dpg.add_button(label="Update Value", callback=update_flag_value)
            
            with dpg.tab(label="Settings"):
                dpg.add_input_text(label="JSON Path", tag="json_path_input", readonly=True)
                dpg.add_button(label="Select File", callback=select_json_file)
                dpg.add_checkbox(label="AlwaysOnTop Enabled", callback=toggle_always_on_top, tag="always_on_top_checkbox")

    apply_light_pink_theme()
    dpg.create_viewport(title="Flag Browser - imgui.cc", width=600, height=750)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == "__main__":
    main()