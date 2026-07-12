import dearpygui.dearpygui as dpg
import win32gui
import win32con
import keyboard
import time
import json
import os
import requests
import threading
import re
from tkinter import Tk, filedialog
import pyperclip
import dearpygui.demo as demo
import traceback
import queue
from collections import deque

class FlagBrowserOverlay:
    def __init__(self):
        self.dpg_job_queue = queue.Queue()

        # Initialize Tkinter for screen dimensions (and file dialogs)
        root = Tk()
        root.withdraw()
        self.screen_width = root.winfo_screenwidth()
        self.screen_height = root.winfo_screenheight()
        root.destroy()

        # Overlay and application settings
        self.overlay_visible = True
        self.overlay_title = "Flag Browser - imgui.cc"
        self.always_on_top = True
        self.transparency = 230 # Opaque: 255, Fully Transparent: 0
        self.config_file = "flag_browser_config.json"
        self.hotkey = "F6" # Hotkey to toggle overlay visibility
        
        self.active_hotkey_ids = {}
        self.last_flag_toggle_times = {} # To prevent hotkey spamming
        
        # Default settings, will be overwritten by loaded config
        self.settings = {
            "json_path": "flags.json", # Path to save/load flag data
            "always_on_top": True,
            "window_pos": [0, 0], # Will be updated to full screen initially
            "window_size": [self.screen_width, self.screen_height], # Full screen
            "auto_save_flags": True,
            "roblox_log_path": "" # Path to Roblox log file for chat monitoring
        }
        
        # Flag data management
        self.flags_list = [] # List of all available flags fetched from GitHub
        self.settings_data = { # Data structure for user's flag settings, keybinds etc.
            "applicationSettings": {}, # Flags that are enabled/applied
            "disabledFlags": {}, # Flags that are disabled/commented out
            "keybinds": {}, # Hotkeys for flags
            "flagOrder": [] # Order of flags in the modified flags list
        }
        self.selected_flag = None # Currently selected flag in the browser
        self.is_setting_keybind = False # Flag to manage keybind capture state

        # Preset management
        self.presets_dir = "presets"
        os.makedirs(self.presets_dir, exist_ok=True)

        # Log management for application itself
        self.max_log_messages = 100 
        self.chat_logs = deque(maxlen=self.max_log_messages) 

        # Roblox Chat Log storage and monitoring
        self.roblox_chat_logs = deque(maxlen=self.max_log_messages)
        self.roblox_log_monitor_thread = None
        self.stop_log_monitor_event = threading.Event()
        self.roblox_chat_log_pattern = re.compile(r"Incoming MessageReceived Status: Success Text: (.*)")
        self.roblox_player_log_filename_pattern = re.compile(r"^\d+\.\d+\.\d+\.\d+_\d{8}T\d{6}Z_Player_.*\.log$")

        # --- Initialization Order ---
        # 1. Load configuration first to get user's saved settings (including json_path and roblox_log_path)
        self.load_config() 
        
        # 2. Set up Dear PyGui GUI elements
        self.setup_gui() 

        # 3. Load flag data from the determined JSON path
        self.load_flag_data() 
        
        # 4. Update the modified flags list display
        self.update_modified_flags_list() 
        
        # 5. Log application start
        self.log_message("Application started.") 

        # 6. Start the main hotkey listener for the overlay toggle
        self.start_key_listener()
        
        # 7. Fetch flags from GitHub in a separate thread to avoid blocking UI
        threading.Thread(target=self.fetch_flags, daemon=True).start()

        # 8. Auto-detect and start Roblox log monitoring based on loaded config or detection
        self.auto_detect_and_start_roblox_log_monitor()

    # --- DPG Job Queue Management ---
    # This mechanism ensures that GUI updates are performed on the main DPG thread
    # preventing common Dear PyGui threading issues.
    def queue_dpg_job(self, job_func):
        self.dpg_job_queue.put(job_func)

    def process_dpg_jobs(self):
        while not self.dpg_job_queue.empty():
            job_func = self.dpg_job_queue.get()
            try:
                job_func()
            except Exception as e:
                # Log any errors that occur during DPG job execution
                print(f"Error executing queued DPG job: {e}")
                self.log_message(f"[DPG Job Error] {e}", level="error")
                traceback.print_exc()

    # --- Configuration Loading and Saving ---
    def load_config(self):
        """Loads application settings from the config file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    loaded_settings = json.load(f)
                    # Update settings while preserving defaults if a key is missing
                    for key in self.settings:
                        if key in loaded_settings:
                            self.settings[key] = loaded_settings[key]
                self.log_message(f"Config loaded from {self.config_file}.")
            except Exception as e:
                self.log_message(f"Error loading config: {e}", level="error")
        else:
            self.log_message(f"Config file not found: {self.config_file}. Using default settings.", level="warning")

    def save_config(self):
        """Saves current application settings to the config file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.settings, f, indent=4)
            self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", "Settings saved successfully!"))
            self.log_message("Settings saved successfully.")
        except Exception as e:
            self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", f"Error saving settings: {e}"))
            self.log_message(f"Error saving settings: {e}", level="error")

    # --- Application Log Functions ---
    def log_message(self, message, level="info"):
        """Adds a message to the application's internal log and updates the UI."""
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        colored_message = ""
        
        # Apply color coding based on log level
        if level == "info":
            colored_message = f"{timestamp} {message}"
        elif level == "warning":
            colored_message = f"|WARN| {timestamp} {message}"
        elif level == "error":
            colored_message = f"|ERR!| {timestamp} {message}"
        elif level == "debug":
            colored_message = f"|DBG| {timestamp} {message}"
        else:
            colored_message = f"{timestamp} {message}"
            
        self.chat_logs.append(colored_message)
        # Queue DPG job to update the display safely
        self.queue_dpg_job(self.update_chat_log_display)

    def update_chat_log_display(self):
        """Refreshes the application log display in the GUI."""
        if dpg.does_item_exist("chat_log_child_window"):
            dpg.delete_item("chat_log_child_window", children_only=True)
            for msg in self.chat_logs:
                color = [255, 255, 255] # Default white
                if "|WARN|" in msg:
                    color = [255, 255, 0] # Yellow
                elif "|ERR!|" in msg:
                    color = [255, 0, 0] # Red
                elif "|DBG|" in msg:
                    color = [100, 100, 255] # Light blue
                dpg.add_text(msg, parent="chat_log_child_window", color=color)
            dpg.set_y_scroll("chat_log_child_window", dpg.get_y_scroll_max("chat_log_child_window"))
            
    def clear_chat_log(self):
        """Clears the application log."""
        self.chat_logs.clear()
        self.update_chat_log_display()
        self.log_message("Application log cleared.")

    # --- Roblox Chat Log Functions ---
    def log_roblox_chat_message(self, message):
        """Adds a message to the Roblox chat log and updates the UI."""
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        self.roblox_chat_logs.append(f"{timestamp} {message}")
        self.queue_dpg_job(self.update_roblox_chat_log_display)

    def update_roblox_chat_log_display(self):
        """Refreshes the Roblox chat log display in the GUI."""
        if dpg.does_item_exist("roblox_chat_log_child_window"):
            dpg.delete_item("roblox_chat_log_child_window", children_only=True)
            for msg in self.roblox_chat_logs:
                dpg.add_text(msg, parent="roblox_chat_log_child_window")
            dpg.set_y_scroll("roblox_chat_log_child_window", dpg.get_y_scroll_max("roblox_chat_log_child_window"))

    def clear_roblox_chat_log(self):
        """Clears the Roblox chat log."""
        self.roblox_chat_logs.clear()
        self.update_roblox_chat_log_display()
        self.log_message("Roblox chat log cleared.")

    def start_roblox_log_monitor(self):
        """Starts the thread that monitors the Roblox log file."""
        if self.roblox_log_monitor_thread and self.roblox_log_monitor_thread.is_alive():
            self.log_message("Roblox log monitor is already running.", level="warning")
            return
        
        if not self.settings["roblox_log_path"] or not os.path.exists(self.settings["roblox_log_path"]):
            self.log_message("Roblox log path is not set or file does not exist. Cannot start monitoring.", level="error")
            self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "Invalid path or file not found. Monitoring off."))
            return

        self.stop_log_monitor_event.clear() # Clear the stop event for a new run
        self.roblox_log_monitor_thread = threading.Thread(target=self.monitor_roblox_log_file, daemon=True)
        self.roblox_log_monitor_thread.start()
        self.log_message(f"Started monitoring Roblox log file: {self.settings['roblox_log_path']}.")
        # Update UI feedback
        self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", f"Monitoring: {os.path.basename(self.settings['roblox_log_path'])}"))


    def stop_roblox_log_monitor(self):
        """Stops the Roblox log monitoring thread."""
        if self.roblox_log_monitor_thread and self.roblox_log_monitor_thread.is_alive():
            self.stop_log_monitor_event.set() # Signal the thread to stop
            self.roblox_log_monitor_thread.join(timeout=2) # Wait for thread to finish
            if self.roblox_log_monitor_thread.is_alive():
                self.log_message("Roblox log monitor thread did not stop gracefully.", level="warning")
            else:
                self.log_message("Roblox log monitor stopped.")
            self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "Monitoring stopped."))


    def monitor_roblox_log_file(self):
        """Thread function to continuously read and parse the Roblox log file."""
        try:
            # Open in 'r' mode and seek to end to only read new lines
            # 'utf-8' with 'errors="ignore"' to handle potential encoding issues in logs
            with open(self.settings["roblox_log_path"], "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, os.SEEK_END) # Start reading from the end of the file
                self.log_message(f"Monitoring Roblox log file from current end: {self.settings['roblox_log_path']}", level="debug")

                while not self.stop_log_monitor_event.is_set():
                    line = f.readline()
                    if line:
                        match = self.roblox_chat_log_pattern.search(line)
                        if match:
                            chat_text = match.groups()[0].strip()
                            self.log_roblox_chat_message(f"[Roblox Chat] {chat_text}")
                            self.log_message(f"[Roblox Log Match] '{chat_text}'", level="debug")
                    else:
                        time.sleep(0.1) # Wait a bit before checking for new lines
        except FileNotFoundError:
            self.log_message(f"Roblox log file not found: {self.settings['roblox_log_path']}", level="error")
            self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", f"File not found: {self.settings['roblox_log_path']}"))
        except Exception as e:
            self.log_message(f"Error reading Roblox log file: {e}", level="error")
            self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", f"Error reading log: {e}"))
        self.log_message("Roblox log monitoring thread terminated.", level="debug")

    # --- Auto-detection and Validation for Roblox Logs ---
    def _find_latest_roblox_log(self):
        """
        Attempts to find the latest Roblox Player log file in common directories.
        Returns the full path to the latest log file or None if not found.
        """
        # Common Roblox log directories
        candidate_dirs = [
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Roblox', 'logs'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Packages', 'ROBLOXCorporation.ROBLOX_55nm5eh3cm0pr', 'LocalState', 'logs')
        ]
        
        latest_log_file = None
        latest_mod_time = 0

        for log_dir in candidate_dirs:
            if os.path.isdir(log_dir):
                self.log_message(f"Searching for Roblox logs in: {log_dir}", level="debug")
                for filename in os.listdir(log_dir):
                    # Check if the filename matches the Roblox Player log pattern
                    if self.roblox_player_log_filename_pattern.match(filename):
                        file_path = os.path.join(log_dir, filename)
                        try:
                            mod_time = os.path.getmtime(file_path) # Get last modification time
                            if mod_time > latest_mod_time:
                                latest_mod_time = mod_time
                                latest_log_file = file_path
                        except Exception as e:
                            self.log_message(f"Could not get modification time for {file_path}: {e}", level="warning")
        
        if latest_log_file:
            self.log_message(f"Found latest Roblox log candidate: {latest_log_file}", level="debug")
        else:
            self.log_message("No Roblox log files found in common directories.", level="debug")
        return latest_log_file

    def _validate_roblox_log_for_chat(self, log_path, num_lines_to_check=50):
        """
        Checks if the given log file contains the chat message pattern.
        Reads only the last `num_lines_to_check` lines for efficiency.
        Returns True if pattern is found, False otherwise.
        """
        if not os.path.exists(log_path):
            return False
        
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                # Seek to end and then back a bit (e.g., last 10KB) to read recent lines
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                seek_pos = max(0, file_size - 1024 * 10) # Seek back 10KB (adjust as needed)
                f.seek(seek_pos)
                
                lines = f.readlines()
                # Check the last few lines for the pattern
                for line in reversed(lines[-num_lines_to_check:]):
                    if self.roblox_chat_log_pattern.search(line):
                        self.log_message(f"Roblox log '{os.path.basename(log_path)}' validated for chat pattern.", level="debug")
                        return True
            self.log_message(f"Roblox log '{os.path.basename(log_path)}' does not contain chat pattern in last {num_lines_to_check} lines.", level="debug")
            return False
        except Exception as e:
            self.log_message(f"Error validating Roblox log '{log_path}': {e}", level="error")
            return False

    def auto_detect_and_start_roblox_log_monitor(self):
        """
        Attempts to auto-detect the Roblox log path and start monitoring.
        This is called once on application startup.
        """
        self.log_message("Attempting to auto-detect Roblox log path...")
        
        # 1. If a path is already configured (from saved settings) and exists, try to use it first
        if self.settings["roblox_log_path"] and os.path.exists(self.settings["roblox_log_path"]):
            self.log_message(f"Using configured Roblox log path: {self.settings['roblox_log_path']}", level="info")
            if self._validate_roblox_log_for_chat(self.settings["roblox_log_path"]):
                self.start_roblox_log_monitor()
                self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "Auto-detected & monitoring (chat enabled)."))
            else:
                self.log_message("Configured Roblox log does not contain chat pattern. Monitoring will not start.", level="warning")
                self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "Configured log found, but no chat detected. Monitoring off."))
            return

        # 2. Otherwise, try to find the latest log file automatically
        latest_log = self._find_latest_roblox_log()
        if latest_log:
            self.settings["roblox_log_path"] = latest_log
            self.queue_dpg_job(lambda: dpg.set_value("roblox_log_path_input", latest_log)) # Update UI field
            
            if self._validate_roblox_log_for_chat(latest_log):
                self.start_roblox_log_monitor()
                self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "Auto-detected & monitoring (chat enabled)."))
                self.log_message("Auto-detected Roblox log with chat pattern. Monitoring started.")
            else:
                self.log_message("Auto-detected Roblox log, but no chat pattern found. Monitoring will not start.", level="warning")
                self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "Auto-detected log found, but no chat detected. Monitoring off."))
        else:
            self.log_message("Could not auto-detect Roblox log path.", level="warning")
            self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "No Roblox log file found automatically."))

    # --- GUI Setup ---
    def setup_gui(self):
        """Initializes Dear PyGui context and sets up all GUI windows and themes."""
        dpg.create_context()
        self.create_transparent_theme()
        
        # Set initial viewport size/position based on loaded settings
        dpg.create_viewport(
            title=self.overlay_title,
            width=self.settings["window_size"][0],
            height=self.settings["window_size"][1],
            x_pos=self.settings["window_pos"][0],
            y_pos=self.settings["window_pos"][1],
            resizable=True,
            always_on_top=self.always_on_top,
            clear_color=[0, 0, 0, 0], # Transparent background
            decorated=False # No window borders/title bar
        )
        
        # Create all individual GUI windows
        self.create_main_window()
        self.create_flag_browser_window()
        self.create_settings_window()
        self.create_create_preset_window()
        self.create_presets_window()
        self.create_chat_log_window()
        self.create_roblox_chat_log_window()

    def create_transparent_theme(self):
        """Creates a custom Dear PyGui theme for a semi-transparent look."""
        with dpg.theme() as self.transparent_theme:
            with dpg.theme_component(dpg.mvAll):
                colors = {
                    dpg.mvThemeCol_WindowBg: [30, 30, 30, 240], # Dark gray, slightly transparent
                    dpg.mvThemeCol_ChildBg: [30, 30, 30, 240],
                    dpg.mvThemeCol_PopupBg: [40, 40, 40, 240],
                    dpg.mvThemeCol_FrameBg: [50, 50, 50, 200],
                    dpg.mvThemeCol_FrameBgHovered: [60, 60, 60, 200],
                    dpg.mvThemeCol_FrameBgActive: [80, 80, 80, 200],
                    dpg.mvThemeCol_Button: [70, 70, 70, 200],
                    dpg.mvThemeCol_ButtonHovered: [90, 90, 90, 200],
                    dpg.mvThemeCol_ButtonActive: [110, 110, 110, 200],
                    dpg.mvThemeCol_Text: [255, 255, 255, 255], # White text
                    dpg.mvThemeCol_Border: [60, 60, 60, 200],
                    dpg.mvThemeCol_Header: [80, 80, 80, 200],
                    dpg.mvThemeCol_HeaderHovered: [100, 100, 100, 200],
                    dpg.mvThemeCol_HeaderActive: [120, 120, 120, 200],
                    dpg.mvThemeCol_CheckMark: [255, 255, 255, 255]
                }
                
                for color, value in colors.items():
                    dpg.add_theme_color(color, value)

    def create_main_window(self):
        """Creates the main, invisible window that hosts the menu bar."""
        with dpg.window(
            label="Main",
            tag="main_window",
            no_title_bar=True,
            no_background=True,
            no_move=True,
            no_resize=True,
            no_scrollbar=True,
            no_collapse=True,
            no_close=True
        ):
            dpg.bind_theme(self.transparent_theme)
            
            with dpg.menu_bar():
                with dpg.menu(label="Menu"):
                    dpg.add_menu_item(label="Flag Browser", callback=lambda: dpg.configure_item("flag_browser_window", show=not dpg.is_item_shown("flag_browser_window")))
                    dpg.add_menu_item(label="Settings", callback=lambda: dpg.configure_item("settings_window", show=not dpg.is_item_shown("settings_window")))
                    dpg.add_menu_item(label="Presets", callback=lambda: dpg.configure_item("presets_window", show=not dpg.is_item_shown("presets_window")))
                    dpg.add_menu_item(label="Application Log", callback=lambda: dpg.configure_item("chat_log_window", show=not dpg.is_item_shown("chat_log_window")))
                    dpg.add_menu_item(label="Roblox Chat Log", callback=lambda: dpg.configure_item("roblox_chat_log_window", show=not dpg.is_item_shown("roblox_chat_log_window")))
                    dpg.add_menu_item(label="DearPyGui Demo", callback=demo.show_demo) 
                    dpg.add_menu_item(label=f"Toggle Overlay ({self.hotkey})", callback=self.toggle_overlay)
                    dpg.add_menu_item(label="Exit", callback=self.clean_exit)


    def create_flag_browser_window(self):
        """Creates the window for Browse and managing Roblox flags."""
        with dpg.window(
            label="Flag Browser",
            tag="flag_browser_window",
            width=600,
            height=600,
            pos=[100, 100],
            show=False,
            no_collapse=False 
        ):
            dpg.bind_theme(self.transparent_theme)
            
            dpg.add_text("Available Flags")
            dpg.add_input_text(label="Search", callback=self.update_search, tag="flag_search_input")
            with dpg.child_window(height=200, tag="available_flags_list"):
                pass
            
            dpg.add_text("Selected Flag: None", tag="selected_flag_text")
            dpg.add_input_text(label="Value", tag="flag_value_input")
            dpg.add_button(label="Set Value", callback=self.set_flag_value)
            
            dpg.add_separator()
            dpg.add_button(label="Create Preset", callback=lambda: dpg.configure_item("create_preset_window", show=True))
            dpg.add_separator()

            with dpg.group(horizontal=True):
                dpg.add_text("Modified Flags")
                dpg.add_input_text(width=200, hint="Search modified flags...", callback=self.update_modified_flags_search, tag="modified_flag_search_input")
                dpg.add_button(label="Toggle All", callback=self.toggle_all_flags, width=100)
            
            with dpg.child_window(height=250, tag="enabled_flags_list"):
                pass

    def create_settings_window(self):
        """Creates the settings configuration window."""
        with dpg.window(
            label="Settings",
            tag="settings_window",
            width=400,
            height=380,
            pos=[750, 100],
            show=False,
            no_collapse=False 
        ):
            dpg.bind_theme(self.transparent_theme)
            
            dpg.add_input_text(label="JSON Path", default_value=self.settings["json_path"], callback=self.update_json_path, tag="json_path_input")
            dpg.add_button(label="Select JSON File", callback=self.select_json_file)
            dpg.add_separator()

            dpg.add_input_text(label="Roblox Log Path", default_value=self.settings["roblox_log_path"], callback=self.update_roblox_log_path, tag="roblox_log_path_input")
            dpg.add_button(label="Select Roblox Log File", callback=self.select_roblox_log_file)
            dpg.add_text("Auto-detecting...", tag="roblox_log_feedback", color=[255, 255, 0]) # Feedback for log path issues/status
            dpg.add_separator()
            
            dpg.add_checkbox(
                label="Always On Top", 
                default_value=self.always_on_top, 
                callback=lambda sender, app_data: self.update_setting("always_on_top", dpg.get_value(sender)),
                tag="always_on_top_checkbox"
            )

            dpg.add_checkbox(
                label="Auto-save Modified Flags",
                default_value=self.settings["auto_save_flags"],
                callback=lambda sender, app_data: self.update_setting("auto_save_flags", dpg.get_value(sender)),
                tag="auto_save_flags_checkbox"
            )
            
            dpg.add_button(label="Save Settings", callback=self.save_config)
            dpg.add_text("", tag="settings_feedback")

    def create_create_preset_window(self):
        """Creates the modal window for creating new flag presets."""
        with dpg.window(
            label="Create New Preset",
            tag="create_preset_window",
            width=300,
            height=150,
            modal=True,
            show=False,
            no_collapse=True,
            no_resize=True,
            pos=[(self.screen_width - 300) // 2, (self.screen_height - 150) // 2]
        ):
            dpg.bind_theme(self.transparent_theme)
            dpg.add_input_text(label="Preset Name", tag="new_preset_name_input")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Create", callback=self.create_preset)
                dpg.add_button(label="Cancel", callback=lambda: dpg.configure_item("create_preset_window", show=False))
            dpg.add_text("", tag="create_preset_feedback")


    def create_presets_window(self):
        """Creates the window for managing (loading/deleting) saved presets."""
        with dpg.window(
            label="Presets",
            tag="presets_window",
            width=400,
            height=500,
            pos=[750, 450],
            show=False,
            no_collapse=False
        ):
            dpg.bind_theme(self.transparent_theme)
            dpg.add_text("Saved Presets")
            with dpg.child_window(height=-1, tag="presets_list_child_window"):
                pass
            self.refresh_presets_list() # Populate list on creation

    def create_chat_log_window(self):
        """Creates the window for displaying application-level logs."""
        with dpg.window(
            label="Application Log",
            tag="chat_log_window",
            width=600,
            height=400,
            pos=[(self.screen_width - 600) // 2, (self.screen_height - 400) // 2],
            show=False,
            no_collapse=False
        ):
            dpg.bind_theme(self.transparent_theme)
            dpg.add_text("Application Log Messages")
            with dpg.child_window(height=-1, tag="chat_log_child_window", border=True):
                pass
            dpg.add_button(label="Clear Log", callback=self.clear_chat_log)

    def create_roblox_chat_log_window(self):
        """Creates the window for displaying captured Roblox chat messages."""
        with dpg.window(
            label="Roblox Chat Log",
            tag="roblox_chat_log_window",
            width=700,
            height=400,
            pos=[(self.screen_width - 700) // 2, (self.screen_height - 400) // 2 + 100],
            show=False,
            no_collapse=False
        ):
            dpg.bind_theme(self.transparent_theme)
            dpg.add_text("Roblox Chat Messages (requires verbose logging in Roblox)")
            with dpg.child_window(height=-1, tag="roblox_chat_log_child_window", border=True):
                pass
            dpg.add_button(label="Clear Roblox Chat Log", callback=self.clear_roblox_chat_log)

    # --- Flag Data Fetching and Management ---
    def fetch_flags(self):
        """Fetches the latest Roblox flags from a GitHub repository."""
        self.log_message("Attempting to fetch flags from GitHub...")
        try:
            url = "https://raw.githubusercontent.com/MaximumADHD/Roblox-Client-Tracker/roblox/FVariables.txt"
            response = requests.get(url)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            lines = response.text.split("\n")
            allowed_prefixes = ("DFInt", "DFFlag", "DFString")

            self.flags_list = []
            for line in lines:
                line = line.strip()
                if line and (line.startswith('[C++]') or line.startswith('[Lua]')):
                    parts = line.split(None, 1) # Split only on first space
                    if len(parts) > 1:
                        flag_name = parts[1].strip()
                        if flag_name.startswith(allowed_prefixes):
                            self.flags_list.append(flag_name)

            self.update_flag_list() # Update the GUI list of available flags
            self.log_message(f"Successfully fetched {len(self.flags_list)} flags.")

            if not self.flags_list:
                error_msg = "No flags were fetched. The file format may have changed or no matching flags were found."
                self.log_message(error_msg, level="warning")
                self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", error_msg))

        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch flags: {str(e)}"
            self.log_message(error_msg, level="error")
            self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", error_msg))
        except Exception as e:
            error_msg = f"Error processing flags: {str(e)}"
            self.log_message(error_msg, level="error")
            self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", error_msg))

    def load_flag_data(self):
        """Loads user's saved flag settings, keybinds, and order from JSON file."""
        self.log_message(f"Attempting to load flag data from: {self.settings['json_path']}")
        try:
            with open(self.settings["json_path"], "r") as f:
                data = json.load(f)
                self.settings_data["applicationSettings"] = data.get("applicationSettings", {})
                self.settings_data["disabledFlags"] = data.get("disabledFlags", {})
                self.settings_data["keybinds"] = data.get("keybinds", {})
                self.settings_data["flagOrder"] = data.get("flagOrder", [])
                self.log_message("Successfully loaded flag data.")
        except FileNotFoundError:
            # If file doesn't exist, initialize with empty data
            self.settings_data = {
                "applicationSettings": {},
                "disabledFlags": {},
                "keybinds": {},
                "flagOrder": []
            }
            self.log_message(f"flags.json not found at {self.settings['json_path']}. Initializing with empty data.", level="warning")
        except json.JSONDecodeError as e:
            # If JSON is invalid, initialize with empty data
            self.settings_data = {
                "applicationSettings": {},
                "disabledFlags": {},
                "keybinds": {},
                "flagOrder": []
            }
            self.log_message(f"Error decoding flags.json at {self.settings['json_path']}: {e}. Initializing with empty data.", level="error")
        except Exception as e:
            # Catch any other unexpected errors
            self.settings_data = {
                "applicationSettings": {},
                "disabledFlags": {},
                "keybinds": {},
                "flagOrder": []
            }
            self.log_message(f"An unexpected error occurred while loading flags.json: {e}. Initializing with empty data.", level="error")
        finally:
            # Re-register hotkeys after loading data
            for flag in list(self.active_hotkey_ids.keys()): # Unregister all existing hotkeys
                self.unregister_flag_keybind_hotkey(flag)
            
            for flag_name in self.settings_data["keybinds"]: # Register hotkeys from loaded data
                self.register_flag_keybind_hotkey(flag_name)
            self.update_modified_flags_list()


    def save_flag_data(self, force_save=False):
        """Saves current flag settings to the JSON file."""
        if not self.settings["auto_save_flags"] and not force_save:
            self.log_message("Auto-save is off, flag data not saved.", level="info")
            self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", "Auto-save is off for flag data. Not saved."))
            self.queue_dpg_job(lambda: dpg.configure_item("settings_feedback", color=[255, 255, 0]))
            threading.Timer(3, lambda: self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", ""))).start()
            return

        try:
            with open(self.settings["json_path"], "w") as f:
                json.dump(self.settings_data, f, indent=4)
            self.log_message("Flag data saved successfully.")
            self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", "Flag data saved successfully!"))
            self.queue_dpg_job(lambda: dpg.configure_item("settings_feedback", color=[0, 255, 0]))
            threading.Timer(3, lambda: self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", ""))).start()
        except Exception as e:
            error_msg = f"Failed to save flag data: {e}"
            self.log_message(error_msg, level="error")
            self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", error_msg))
            self.queue_dpg_job(lambda: dpg.configure_item("settings_feedback", color=[255, 0, 0]))
            threading.Timer(5, lambda: self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", "")).start())

    def update_flag_list(self, search_query=""):
        """Updates the list of available flags based on search query."""
        if not dpg.does_item_exist("available_flags_list"):
            return
            
        dpg.delete_item("available_flags_list", children_only=True)
        for flag in self.flags_list:
            if search_query.lower() in flag.lower():
                dpg.add_button(
                    label=flag,
                    parent="available_flags_list",
                    callback=self.select_flag,
                    user_data=flag
                )
        self.log_message(f"Available flags list updated with search query: '{search_query}'.")

    def update_modified_flags_list(self, search_query=""):
        """Updates the list of modified/enabled flags in the UI."""
        if not dpg.does_item_exist("enabled_flags_list"):
            return
            
        dpg.delete_item("enabled_flags_list", children_only=True)
        # Store current input values to reapply after refresh (prevents losing unsaved text)
        existing_inputs = {}
        for flag in self.settings_data["flagOrder"]:
            if dpg.does_item_exist(f"edit_value_{flag}"):
                existing_inputs[flag] = dpg.get_value(f"edit_value_{flag}")
        
        # Filter flags based on search query
        filtered_flags = [
            flag for flag in self.settings_data["flagOrder"] 
            if (flag in self.settings_data["applicationSettings"] or flag in self.settings_data["disabledFlags"]) and
            search_query.lower() in flag.lower()
        ]
        
        for index, flag in enumerate(filtered_flags):
            is_enabled = flag in self.settings_data["applicationSettings"]
            value = self.settings_data["applicationSettings"].get(flag, self.settings_data["disabledFlags"].get(flag, ""))
            keybind_label = f"Keybind: {self.settings_data['keybinds'].get(flag, 'none')}"
            
            with dpg.group(parent="enabled_flags_list"):
                dpg.add_input_text(
                    tag=f"display_value_{flag}",
                    default_value=f"{flag}: {value}",
                    width=500,
                    readonly=True
                )
                with dpg.group(horizontal=True):
                    dpg.add_input_text(
                        tag=f"edit_value_{flag}",
                        width=300,
                        hint="Enter new value or toggle (true/false, 1/0)..."
                    )
                    dpg.add_button(
                        label="Update",
                        callback=lambda sender, app_data, flag=flag: self.update_flag_value(sender, app_data, flag),
                        user_data=flag
                    )
                with dpg.group(horizontal=True):
                    dpg.add_checkbox(label="Enabled", default_value=is_enabled, callback=self.toggle_flag_visibility, user_data=flag, tag=f"enabled_checkbox_{flag}")
                    dpg.add_button(
                        label="Remove",
                        callback=lambda sender, app_data, flag=flag: self.remove_flag(sender, app_data, flag),
                        user_data=flag
                    )
                    with dpg.group(horizontal=True):
                        dpg.add_button(label=keybind_label, callback=self.set_keybind, user_data=flag, tag=f"keybind_button_{flag}")
                        x_button_visibility = flag in self.settings_data["keybinds"]
                        dpg.add_button(label="X", callback=self.clear_keybind, user_data=flag, width=25, tag=f"clear_keybind_button_{flag}", show=x_button_visibility)
                if index < len(filtered_flags) - 1:
                    dpg.add_spacer(height=10)
        
        # Reapply input values
        for flag, value in existing_inputs.items():
            if dpg.does_item_exist(f"edit_value_{flag}"):
                dpg.set_value(f"edit_value_{flag}", value)
        self.log_message(f"Modified flags list updated with search query: '{search_query}'.")

    def select_flag(self, sender, app_data, user_data):
        """Selects a flag from the available flags list."""
        flag = user_data
        self.selected_flag = flag
        self.queue_dpg_job(lambda: dpg.set_value("selected_flag_text", f"Selected Flag: {flag}"))
        value = self.settings_data["applicationSettings"].get(flag, self.settings_data["disabledFlags"].get(flag, ""))
        self.queue_dpg_job(lambda: dpg.set_value("flag_value_input", value))
        self.log_message(f"Selected flag: '{flag}', Value: '{value}'.")

    def set_flag_value(self, sender, app_data):
        """Sets the value for the currently selected flag."""
        if self.selected_flag and dpg.does_item_exist("flag_value_input"):
            value = dpg.get_value("flag_value_input").strip()
            if value:
                self.save_flag(self.selected_flag, value)
                self.queue_dpg_job(lambda: dpg.set_value("flag_value_input", ""))
                self.queue_dpg_job(lambda: dpg.set_value("selected_flag_text", "Selected Flag: None"))
                self.selected_flag = None
                self.log_message(f"Set value for flag '{self.selected_flag}' to '{value}'.")

    def update_flag_value(self, sender, app_data, flag):
        """Updates the value of a flag directly from the modified flags list."""
        if dpg.does_item_exist(f"edit_value_{flag}"):
            new_value = dpg.get_value(f"edit_value_{flag}").strip()
            
            # If input is empty, attempt to toggle boolean-like values
            if not new_value:
                current_value = self.settings_data["applicationSettings"].get(flag, self.settings_data["disabledFlags"].get(flag, "")).lower()
                if current_value == "true":
                    new_value = "false"
                elif current_value == "false":
                    new_value = "true"
                elif current_value == "1":
                    new_value = "0"
                elif current_value == "0":
                    new_value = "1"
                else: # If not boolean-like, just keep current value
                    new_value = current_value

            if flag in self.settings_data["applicationSettings"]:
                self.settings_data["applicationSettings"][flag] = new_value
            elif flag in self.settings_data["disabledFlags"]:
                self.settings_data["disabledFlags"][flag] = new_value
            
            self.save_flag_data() 
            self.queue_dpg_job(lambda: dpg.set_value(f"display_value_{flag}", f"{flag}: {new_value}"))
            self.queue_dpg_job(lambda: dpg.set_value(f"edit_value_{flag}", ""))
            self.update_modified_flags_list()
            self.log_message(f"Updated flag '{flag}' value to '{new_value}'.")

    def remove_flag(self, sender, app_data, flag):
        """Removes a flag from the modified flags list."""
        self.unregister_flag_keybind_hotkey(flag) # Unregister hotkey first

        if flag in self.settings_data["applicationSettings"]:
            del self.settings_data["applicationSettings"][flag]
        if flag in self.settings_data["disabledFlags"]:
            del self.settings_data["disabledFlags"][flag]
        if flag in self.settings_data["flagOrder"]:
            self.settings_data["flagOrder"].remove(flag)
        
        if flag in self.settings_data["keybinds"]:
            del self.settings_data["keybinds"][flag]
            
        self.save_flag_data()
        self.update_modified_flags_list() 
        if self.selected_flag == flag: # If the removed flag was selected, clear selection
            self.queue_dpg_job(lambda: dpg.set_value("selected_flag_text", "Selected Flag: None"))
            self.queue_dpg_job(lambda: dpg.set_value("flag_value_input", ""))
            self.selected_flag = None
        self.log_message(f"Removed flag '{flag}'.")

    def toggle_all_flags(self, sender, app_data):
        """Toggles the enabled/disabled state of all modified flags."""
        any_enabled = len(self.settings_data["applicationSettings"]) > 0
        
        if any_enabled:
            # Move all flags from applicationSettings to disabledFlags
            for flag in list(self.settings_data["applicationSettings"].keys()):
                self.settings_data["disabledFlags"][flag] = self.settings_data["applicationSettings"].pop(flag)
            message = "All flags have been disabled."
        else:
            # Move all flags from disabledFlags to applicationSettings
            for flag in list(self.settings_data["disabledFlags"].keys()):
                self.settings_data["applicationSettings"][flag] = self.settings_data["disabledFlags"].pop(flag)
            message = "All flags have been enabled."
        
        self.save_flag_data()
        self.update_modified_flags_list()
        self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", message))
        self.queue_dpg_job(lambda: dpg.configure_item("settings_feedback", color=[0, 255, 0]))
        threading.Timer(5, lambda: self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", ""))).start()
        self.log_message(message)

    def toggle_flag_visibility(self, sender, app_data, flag):
        """Toggles a single flag between enabled and disabled."""
        if flag in self.settings_data["applicationSettings"]:
            # Move from enabled to disabled
            self.settings_data["disabledFlags"][flag] = self.settings_data["applicationSettings"].pop(flag)
            self.log_message(f"Disabled flag '{flag}'.")
        elif flag in self.settings_data["disabledFlags"]:
            # Move from disabled to enabled
            self.settings_data["applicationSettings"][flag] = self.settings_data["disabledFlags"].pop(flag)
            self.log_message(f"Enabled flag '{flag}'.")
        self.save_flag_data()
        self.update_modified_flags_list()

    def save_flag(self, name, value):
        """Saves a new flag or updates an existing one."""
        if name not in self.settings_data["flagOrder"]:
            self.settings_data["flagOrder"].append(name)
        
        # If it was disabled, move it to enabled (by setting a new value)
        if name in self.settings_data["disabledFlags"]:
            self.settings_data["disabledFlags"][name] = value
        else:
            self.settings_data["applicationSettings"][name] = value
        
        self.save_flag_data()
        self.update_modified_flags_list()
        self.log_message(f"Saved flag '{name}' with value '{value}'.")

    # --- Keybind Management ---
    def unregister_flag_keybind_hotkey(self, flag):
        """Unhooks a keyboard hotkey associated with a flag."""
        hotkey_id = self.active_hotkey_ids.get(flag) 
        if hotkey_id is not None:
            try:
                keyboard.unhook(hotkey_id)
                self.log_message(f"Unhooked hotkey ID {hotkey_id} for flag '{flag}'.", level="debug")
            except KeyError:
                self.log_message(f"Hotkey ID {hotkey_id} for flag '{flag}' was already unhooked or not found.", level="warning")
            except Exception as e:
                self.log_message(f"Error unhooking hotkey ID {hotkey_id} for flag '{flag}': {e}", level="error")
                traceback.print_exc()
            finally:
                self.active_hotkey_ids.pop(flag, None) 

    def register_flag_keybind_hotkey(self, flag):
        """Registers a keyboard hotkey for a flag to toggle its state."""
        self.unregister_flag_keybind_hotkey(flag) # Ensure no duplicate hotkeys

        keybind_string = self.settings_data["keybinds"].get(flag)
        if not keybind_string:
            return

        def hotkey_callback():
            """Callback function executed when a flag hotkey is pressed."""
            current_time = time.time()
            last_toggle = self.last_flag_toggle_times.get(flag, 0.0)
            # Debounce: prevent rapid toggles if key is held down
            if (current_time - last_toggle < 0.2): 
                return
            self.last_flag_toggle_times[flag] = current_time

            # Queue DPG job to safely toggle flag visibility on main thread
            self.queue_dpg_job(lambda: self.toggle_flag_visibility(None, None, flag))
            self.log_message(f"Hotkey '{keybind_string}' triggered for flag '{flag}'.")

        try:
            hotkey_id = keyboard.add_hotkey(keybind_string, hotkey_callback)
            self.active_hotkey_ids[flag] = hotkey_id
            self.log_message(f"Registered hotkey '{keybind_string}' for flag '{flag}' with ID {hotkey_id}.", level="debug")
        except Exception as e:
            self.log_message(f"Error registering hotkey '{keybind_string}' for flag '{flag}': {e}", level="error")
            traceback.print_exc()
            # If hotkey registration fails, remove it from settings
            if flag in self.settings_data["keybinds"]:
                del self.settings_data["keybinds"][flag]
            self.save_flag_data()
            self.update_modified_flags_list()

    def set_keybind(self, sender, app_data, flag):
        """Initiates the process of capturing a new keybind for a flag."""
        if self.is_setting_keybind:
            return
        self.is_setting_keybind = True
        self.log_message(f"Setting keybind for flag '{flag}'. Waiting for input...")
        
        # Update UI button to indicate waiting for input
        keybind_button_tag = f"keybind_button_{flag}"
        if dpg.does_item_exist(keybind_button_tag):
            self.queue_dpg_job(lambda: dpg.configure_item(keybind_button_tag, label="Keybind: waiting for input..."))
        dpg.split_frame() # Ensure UI updates immediately

        def capture_key():
            """Thread function to capture the next keypress as a hotkey."""
            try:
                while self.is_setting_keybind:
                    event = keyboard.read_event()
                    if event.event_type == keyboard.KEY_DOWN:
                        pressed_key = event.name.upper()

                        # Handle modifier-only keybinds (e.g., "CTRL")
                        if pressed_key in ["CTRL", "SHIFT", "ALT"]:
                            is_only_modifier = True
                            for k in keyboard.all_keys:
                                if k != event.name and k.lower() not in ["ctrl", "shift", "alt"] and keyboard.is_pressed(k):
                                    is_only_modifier = False
                                    break
                            
                            if is_only_modifier:
                                modifier_state = pressed_key
                                self.settings_data["keybinds"][flag] = modifier_state
                                self.save_flag_data()
                                self.register_flag_keybind_hotkey(flag)
                                self.is_setting_keybind = False
                                self.log_message(f"Keybind for '{flag}' set to '{modifier_state}'.")
                                break

                        # Construct keybind string with modifiers
                        modifier = ""
                        if keyboard.is_pressed("ctrl"):
                            modifier += "CTRL+"
                        if keyboard.is_pressed("shift"):
                            modifier += "SHIFT+"
                        if keyboard.is_pressed("alt"):
                            modifier += "ALT+"

                        # If a non-modifier key is pressed, or a modifier is pressed with other keys
                        if pressed_key not in ["CTRL", "SHIFT", "ALT"] or \
                           (pressed_key in ["CTRL", "SHIFT", "ALT"] and (len(modifier) > 0 or any(keyboard.is_pressed(k) for k in keyboard.all_keys if k not in ["ctrl", "shift", "alt", pressed_key.lower()]))):
                            
                            keybind_str = f"{modifier}{pressed_key}"
                            self.settings_data["keybinds"][flag] = keybind_str
                            self.save_flag_data()
                            self.register_flag_keybind_hotkey(flag)
                            self.is_setting_keybind = False
                            self.log_message(f"Keybind for '{flag}' set to '{keybind_str}'.")
                            break
            except Exception as e:
                self.log_message(f"Error capturing keybind for flag '{flag}': {e}", level="error")
                traceback.print_exc()
            finally:
                self.is_setting_keybind = False
                # Update UI on main thread after keybind is set or capture fails
                self.queue_dpg_job(self.update_modified_flags_list)

        threading.Thread(target=capture_key, daemon=True).start()

    def clear_keybind(self, sender, app_data, flag):
        """Clears the keybind for a specific flag."""
        self.unregister_flag_keybind_hotkey(flag) 
        
        if flag in self.settings_data["keybinds"]:
            del self.settings_data["keybinds"][flag]
        self.save_flag_data()
        self.update_modified_flags_list()
        self.log_message(f"Cleared keybind for flag '{flag}'.")

    # --- UI Callbacks for Inputs and Selections ---
    def update_search(self, sender, data):
        """Callback for the 'Available Flags' search input."""
        self.update_flag_list(data)

    def update_modified_flags_search(self, sender, data):
        """Callback for the 'Modified Flags' search input."""
        self.update_modified_flags_list(data)

    def update_json_path(self, sender, data):
        """Callback for the 'JSON Path' input in settings."""
        self.settings["json_path"] = data
        self.load_flag_data() # Reload flag data from new path
        self.update_modified_flags_list()
        self.log_message(f"JSON path updated to: {data}. Re-loaded flag data.")

    def select_json_file(self):
        """Opens a file dialog to select the JSON file for flag data."""
        root = Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            self.settings["json_path"] = file_path
            self.queue_dpg_job(lambda: dpg.set_value("json_path_input", file_path))
            self.load_flag_data()
            self.update_modified_flags_list()
            self.log_message(f"JSON file selected: {file_path}. Re-loaded flag data.")

    def update_roblox_log_path(self, sender, data):
        """Callback for the 'Roblox Log Path' input in settings."""
        old_path = self.settings["roblox_log_path"]
        self.settings["roblox_log_path"] = data
        self.log_message(f"Roblox log path manually updated to: {data}.")
        if old_path != data: # Only restart if path actually changed
            self.stop_roblox_log_monitor() 
            if data and os.path.exists(data):
                if self._validate_roblox_log_for_chat(data):
                    self.start_roblox_log_monitor()
                    self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "Manually set & monitoring (chat enabled)."))
                else:
                    self.log_message("Manually set Roblox log does not contain chat pattern. Monitoring will not start.", level="warning")
                    self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "Manually set log found, but no chat detected. Monitoring off."))
            else:
                self.log_message("Roblox log path is invalid or file does not exist. Monitoring stopped.", level="warning")
                self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "Invalid path or file not found. Monitoring off."))


    def select_roblox_log_file(self):
        """Opens a file dialog to select the Roblox log file."""
        root = Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(filetypes=[("Log Files", "*.log"), ("All Files", "*.*")])
        if file_path:
            self.settings["roblox_log_path"] = file_path
            self.queue_dpg_job(lambda: dpg.set_value("roblox_log_path_input", file_path))
            self.log_message(f"Roblox log file manually selected: {file_path}.")
            self.stop_roblox_log_monitor() 
            if self._validate_roblox_log_for_chat(file_path):
                self.start_roblox_log_monitor()
                self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "Manually selected & monitoring (chat enabled)."))
            else:
                self.log_message("Manually selected Roblox log does not contain chat pattern. Monitoring will not start.", level="warning")
                self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "Selected log found, but no chat detected. Monitoring off."))
        else:
            self.log_message("No Roblox log file selected.", level="info")
            self.queue_dpg_job(lambda: dpg.set_value("roblox_log_feedback", "No file selected."))

    def update_setting(self, key, value):
        """Updates a general application setting."""
        self.settings[key] = value
        if key == "always_on_top":
            self.queue_dpg_job(lambda: dpg.configure_viewport(0, always_on_top=value))
            self.log_message(f"Setting '{key}' updated to '{value}'.")

    # --- Overlay Control ---
    def toggle_overlay(self):
        """Toggles the visibility of the main overlay window."""
        self.overlay_visible = not self.overlay_visible
        hwnd = win32gui.FindWindow(None, self.overlay_title)
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW if self.overlay_visible else win32con.SW_HIDE)
            self.log_message(f"Overlay visibility toggled to: {self.overlay_visible}.")

    def make_window_clickable(self):
        """Makes the DPG viewport clickable and sets transparency."""
        hwnd = win32gui.FindWindow(None, self.overlay_title)
        if hwnd:
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                hwnd, 
                win32con.GWL_EXSTYLE, 
                (style | win32con.WS_EX_LAYERED) & ~win32con.WS_EX_TRANSPARENT # Enable layered window, disable transparent click-through
            )
            win32gui.SetLayeredWindowAttributes(
                hwnd, 
                0, # Color key (not used here)
                self.transparency, # Alpha value
                win32con.LWA_ALPHA # Use alpha
            )
            self.log_message("Overlay window made clickable (set transparency).")


    def start_key_listener(self):
        """Starts a background thread to listen for the main overlay hotkey (F6)."""
        def f6_listener():
            while True:
                if keyboard.is_pressed(self.hotkey):
                    self.toggle_overlay() 
                    time.sleep(0.2) # Debounce for hotkey
                time.sleep(0.01) # Small delay to prevent high CPU usage
        threading.Thread(target=f6_listener, daemon=True).start()
        self.log_message(f"Main hotkey listener for '{self.hotkey}' started.")

    def clean_exit(self):
        """Performs cleanup before exiting the application."""
        self.log_message("Application exiting. Saving data...")
        self.save_config() # Save general settings
        self.save_flag_data(force_save=True) # Force save flag data
        self.stop_roblox_log_monitor() # Ensure log monitor thread is stopped
        keyboard.unhook_all() # Unhook all keyboard listeners
        dpg.stop_dearpygui() # Stop the DPG rendering loop
        self.log_message("Application exited cleanly.")

    # --- Preset Management ---
    def _get_preset_path(self, preset_name):
        """Generates a safe file path for a preset."""
        safe_name = "".join(c for c in preset_name if c.isalnum() or c in (' ', '.', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_').lower()
        if not safe_name:
            safe_name = "untitled_preset_" + str(int(time.time()))
        return os.path.join(self.presets_dir, f"{safe_name}.json")

    def create_preset(self, sender, app_data):
        """Creates a new flag preset from current settings."""
        preset_name = dpg.get_value("new_preset_name_input").strip()
        if not preset_name:
            self.queue_dpg_job(lambda: dpg.set_value("create_preset_feedback", "Preset name cannot be empty!"))
            self.queue_dpg_job(lambda: dpg.configure_item("create_preset_feedback", color=[255, 0, 0]))
            self.log_message("Attempted to create preset with empty name.", level="warning")
            return

        preset_path = self._get_preset_path(preset_name)

        # Copy current flag settings and keybinds
        preset_data = {
            "applicationSettings": self.settings_data["applicationSettings"].copy(),
            "disabledFlags": self.settings_data["disabledFlags"].copy(),
            "keybinds": self.settings_data["keybinds"].copy(),
            "flagOrder": self.settings_data["flagOrder"].copy()
        }

        try:
            with open(preset_path, "w") as f:
                json.dump(preset_data, f, indent=4)
            self.queue_dpg_job(lambda: dpg.set_value("create_preset_feedback", f"Preset '{preset_name}' created successfully!"))
            self.queue_dpg_job(lambda: dpg.configure_item("create_preset_feedback", color=[0, 255, 0]))
            self.queue_dpg_job(lambda: dpg.configure_item("create_preset_window", show=False))
            self.queue_dpg_job(self.refresh_presets_list) # Refresh presets display
            self.log_message(f"Preset '{preset_name}' created and saved to {preset_path}.")
        except Exception as e:
            self.queue_dpg_job(lambda: dpg.set_value("create_preset_feedback", f"Error creating preset: {e}"))
            self.queue_dpg_job(lambda: dpg.configure_item("create_preset_feedback", color=[255, 0, 0]))
            self.log_message(f"Error saving preset '{preset_name}': {e}", level="error")
        
        threading.Timer(3, lambda: self.queue_dpg_job(lambda: dpg.set_value("create_preset_feedback", ""))).start()


    def load_preset(self, sender, app_data, preset_name):
        """Loads a flag preset, applying its settings to the current application state."""
        preset_path = self._get_preset_path(preset_name)
        self.log_message(f"Attempting to load preset '{preset_name}' from {preset_path}...")
        try:
            with open(preset_path, "r") as f:
                preset_data = json.load(f)
            
            # Unregister all active hotkeys before loading new ones
            for flag in list(self.active_hotkey_ids.keys()):
                self.unregister_flag_keybind_hotkey(flag)

            # Apply preset data
            self.settings_data["applicationSettings"] = preset_data.get("applicationSettings", {})
            self.settings_data["disabledFlags"] = preset_data.get("disabledFlags", {})
            self.settings_data["keybinds"] = preset_data.get("keybinds", {})
            self.settings_data["flagOrder"] = preset_data.get("flagOrder", [])
            
            self.save_flag_data() # Save the newly loaded data
            self.update_modified_flags_list() # Update GUI
            
            # Register new hotkeys from the loaded preset
            for flag_name in self.settings_data["keybinds"]:
                self.register_flag_keybind_hotkey(flag_name)

            self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", f"Preset '{preset_name}' loaded successfully!"))
            self.queue_dpg_job(lambda: dpg.configure_item("settings_feedback", color=[0, 255, 0]))
            self.log_message(f"Preset '{preset_name}' loaded successfully.")
        except FileNotFoundError:
            self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", f"Preset '{preset_name}' not found."))
            self.queue_dpg_job(lambda: dpg.configure_item("settings_feedback", color=[255, 0, 0]))
            self.log_message(f"Preset '{preset_name}' not found at {preset_path}.", level="error")
        except json.JSONDecodeError as e:
            self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", f"Error decoding preset '{preset_name}': {e}"))
            self.queue_dpg_job(lambda: dpg.configure_item("settings_feedback", color=[255, 0, 0]))
            self.log_message(f"Error decoding preset '{preset_name}' from {preset_path}: {e}", level="error")
        except Exception as e:
            self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", f"Error loading preset '{preset_name}': {e}"))
            self.queue_dpg_job(lambda: dpg.configure_item("settings_feedback", color=[255, 0, 0]))
            self.log_message(f"An unexpected error occurred loading preset '{preset_name}': {e}", level="error")
        
        threading.Timer(3, lambda: self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", ""))).start()

    def delete_preset(self, sender, app_data, preset_name):
        """Deletes a saved flag preset."""
        preset_path = self._get_preset_path(preset_name)
        self.log_message(f"Attempting to delete preset '{preset_name}' from {preset_path}...")
        try:
            if os.path.exists(preset_path):
                os.remove(preset_path)
                self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", f"Preset '{preset_name}' deleted."))
                self.queue_dpg_job(lambda: dpg.configure_item("settings_feedback", color=[0, 255, 0]))
                self.queue_dpg_job(self.refresh_presets_list) # Refresh presets display
                self.log_message(f"Preset '{preset_name}' deleted.")
            else:
                self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", f"Preset '{preset_name}' not found."))
                self.queue_dpg_job(lambda: dpg.configure_item("settings_feedback", color=[255, 255, 0]))
                self.log_message(f"Preset '{preset_name}' not found for deletion.", level="warning")
        except Exception as e:
            self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", f"Error deleting preset '{preset_name}': {e}"))
            self.queue_dpg_job(lambda: dpg.configure_item("settings_feedback", color=[255, 0, 0]))
            self.log_message(f"Error deleting preset '{preset_name}': {e}", level="error")
        
        threading.Timer(3, lambda: self.queue_dpg_job(lambda: dpg.set_value("settings_feedback", ""))).start()

    def refresh_presets_list(self):
        """Refreshes the display of available presets in the GUI."""
        if not dpg.does_item_exist("presets_list_child_window"):
            return

        self.queue_dpg_job(lambda: dpg.delete_item("presets_list_child_window", children_only=True))
        
        preset_files = [f for f in os.listdir(self.presets_dir) if f.endswith('.json')]
        
        if not preset_files:
            self.queue_dpg_job(lambda: dpg.add_text("No presets found.", parent="presets_list_child_window"))
            self.log_message("No presets found in the presets directory.")
            return

        for filename in preset_files:
            preset_name = os.path.splitext(filename)[0].replace('_', ' ').title() # Format filename to readable name
            
            # Queue multiple DPG commands for each preset to build its UI elements
            self.queue_dpg_job(
                lambda preset_name=preset_name:
                (
                    dpg.add_group(horizontal=True, parent="presets_list_child_window", tag=f"preset_group_{preset_name}"),
                    dpg.add_text(preset_name, parent=f"preset_group_{preset_name}"),
                    dpg.add_button(label="Load", callback=self.load_preset, user_data=preset_name, parent=f"preset_group_{preset_name}"),
                    dpg.add_button(label="Delete", callback=self.delete_preset, user_data=preset_name, parent=f"preset_group_{preset_name}"),
                    dpg.add_separator(parent="presets_list_child_window")
                )
            )
        self.log_message(f"Presets list UI refreshed. Found {len(preset_files)} presets.")


    def run(self):
        """Starts the Dear PyGui application."""
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)
        self.make_window_clickable() # Ensure overlay is clickable and has transparency
        
        # Main Dear PyGui rendering loop
        while dpg.is_dearpygui_running():
            self.process_dpg_jobs() # Process any queued GUI updates
            dpg.render_dearpygui_frame() # Render the next frame
        
        dpg.destroy_context() # Clean up DPG context on exit

if __name__ == "__main__":
    overlay = FlagBrowserOverlay()
    overlay.run()
