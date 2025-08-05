import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTabWidget, QHBoxLayout, QPlainTextEdit, QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QIcon
from qt_material import apply_stylesheet
from bs_bot import BSBot
from pynput import keyboard
import json
import os
import platform



class SelectionOverlay(QWidget):
    region_selected = pyqtSignal()
    region = pyqtSignal(dict)
    cancelled = pyqtSignal()

    def __init__(self, is_screenshot=False, is_point=False):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowState.WindowFullScreen)

        self.start = None
        self.end = None
        self.setMouseTracking(True)
        self.is_screenshot = is_screenshot
        self.is_point = is_point

        self.show()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            print("Selection cancelled.")
            self.cancelled.emit()
            self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_point:
                point = event.globalPosition().toPoint()
                self.region.emit({"x": point.x(), "y": point.y()})
                self.region_selected.emit()
                self.close()
            else:
                self.start = event.globalPosition().toPoint()
                self.end = self.start
                self.update()

    def mouseMoveEvent(self, event):
        if self.start:
            self.end = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.is_point:
            self.end = event.globalPosition().toPoint()
            self.capture_rect()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dim the background
        painter.fillRect(self.rect(), QColor(50, 50, 50, 100))

        # Draw instruction text
        instruction = (
            "Click a point on the screen, or press Esc to cancel"
            if self.is_point else
            "Drag to select a region, or press Esc to cancel"
        )

        font = QFont("Segoe UI", 14)
        painter.setFont(font)
        painter.setPen(QPen(QColor(255, 255, 255)))
        text_rect = painter.boundingRect(self.rect(), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, instruction)
        text_rect.moveTop(20)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, instruction)

        # Draw selection rectangle if needed
        if self.start and self.end and not self.is_point:
            rect = QRect(self.start, self.end)
            painter.setPen(QPen(QColor(0, 255, 0), 2, Qt.PenStyle.SolidLine))
            painter.drawRect(rect)

    def capture_rect(self):
        x1, y1 = self.start.x(), self.start.y()
        x2, y2 = self.end.x(), self.end.y()
        left = min(x1, x2)
        top = min(y1, y2)
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        self.region.emit({"left": left, "top": top, "width": width, "height": height})
        self.region_selected.emit()
        self.close()

class BS_Farm(QWidget):
    bot_template_paths = {
        "player":    "img/player.png",
        "enemy":     "img/enemy.png",
        "enemy2":    "img/enemy2.png",
        "team":      "img/team.png"
    }

    ui_template_paths = {
        "connection_lost": "img/connection_lost.png",
        "red_x": "img/red_x.png",
        "retry_login": "img/retry_login.png",
        "play_button": "img/play_button.png",
        "proceed_button": "img/proceed_button.png",
        "im_ready_button": "img/im_ready_button.png",
        "exit_button": "img/exit_button.png",
        "current_game_mode": "img/current_game_mode.png",
        # "next_game_mode": "img/next_game_mode.png",
        # "next_brawler": "img/next_brawler.png",
    }
        
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoStarr")
        if platform.system() == "Windows":
            # if windows do ico, if not png
            self.setWindowIcon(QIcon("img/icon.ico"))
        else:
            # For non-Windows systems, use PNG icon
            self.setWindowIcon(QIcon("img/icon.png")) 
        self.setGeometry(200, 200, 800, 600)
        self.selected_region_temp = {}

        self.selected_region_temp = {"left": 0, "top": 0, "width": 1100, "height": 650}
        self.global_states = {
            # Attack Variables
            "attack_cooldown": 0.5,
            "attack_range": 400,
            "super_range": 600,
            "attack_always": False,

            # Movement Variables
            "movement_keys": {"w": False, "a": False, "s": False, "d": False},
            "joystick_x": 245,
            "joystick_y": 505,
            "joystick_radius": 75,
            "avoid_range": 250,
            "run_away_range": 150,
            "approach_range": 500,

            # Settings Variables
            "screenshot_region": [{"left": 0, "top": 0, "width": 1100, "height": 650}],
            "use_keyboard": True,
            "use_mouse_movement": True,
            "extra_scan_interval": 30,

            # Idle Variables
            "idle_timeout": 60,  # seconds
            }

        self.ui_locations = {
            # Main UI Elements
            "proceed_button": {"coords": (1100, 600), "key": "p"},
            "game_mode": {"coords": (1100, 600), "key": "g"},
            "retry_login": {"coords": (1100, 600), "key": "r"},
            "brawler_select": {"coords": (1100, 600), "key": "b"},
            "more_settings": {"coords": (1100, 600), "key": "m"},
            "switch_user": {"coords": (1100, 600), "key": "u"},

            # Game UI Elements
            "attack_button": {"coords": (1100, 600), "key": "space"},      
            "super_button": {"coords": (1225, 800), "key": "e"},       
            "gadget_button": {"coords": (1300, 880), "key": "f"},
            "hypercharge_button": {"coords": (1180, 900), "key": "q"},
            "idle_click_1": {"coords": (100, 200), "key": "i"},
            "idle_click_2": {"coords": (300, 400), "key": "o"},
        }

        # Console Output
        console_layout = QVBoxLayout()
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("""
            background-color: #1e1e1e;
            color: #dcdcdc;
            font-family: Consolas, monospace;
            font-size: 12px;
            padding: 10px;
        """)
        self.clear_button = QPushButton("Clear Console")
        self.clear_button.clicked.connect(lambda: self.console_output.clear())
        console_layout.addWidget(self.console_output)
        console_layout.addWidget(self.clear_button)

        # Tabs
        self.tabs = QTabWidget()
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tab3 = QWidget()
        self.tab4 = QWidget()
        self.tabs.addTab(self.tab1, "Main")
        self.tabs.addTab(self.tab2, "Variables")
        self.tabs.addTab(self.tab3, "UI Locations")
        self.tabs.addTab(self.tab4, "Screenshots")

        self.load_settings()  # Load settings before setting up the UI

        # Tab 1 Layout
        tab1_layout = QVBoxLayout()
        for key, value in self.ui_locations.items():
            row_layout = QHBoxLayout()
            # Element name
            row_layout.addWidget(QLabel(f"{key}:"))
            
            # Current hotkey display
            hotkey_label = QLabel(f"Current hotkey: {value.get('key', 'None')}")
            row_layout.addWidget(hotkey_label)

            # Button to change hotkey
            change_hotkey_btn = QPushButton("Change Hotkey")
            change_hotkey_btn.clicked.connect(
                lambda checked, k=key, lbl=hotkey_label: self.start_key_capture(lbl, k)
            )
            row_layout.addWidget(change_hotkey_btn)
            
            tab1_layout.addLayout(row_layout)

        self.screenshot_label = QLabel(f"Current Screenshot Region: {self.global_states['screenshot_region']}")
        self.screenshot_region_button = QPushButton("Select Region")
        self.screenshot_region_button.clicked.connect(self.capture_screenshot_region)
        # Don't overwrite the default screenshot region with an empty dict
        tab1_layout.addWidget(self.screenshot_label)
        tab1_layout.addWidget(self.screenshot_region_button)
        self.tab1.setLayout(tab1_layout)
        self.start_bot_button = QPushButton("Start Bot")
        self.start_bot_button.clicked.connect(self.start_bot)
        tab1_layout.addWidget(self.start_bot_button)

        # Tab 2 Layout
        tab2_layout = QVBoxLayout()
        self.tab2.setLayout(tab2_layout)
        
        for key, value in self.global_states.items():
            if isinstance(value, (dict, list)):
                continue  # Skip complex types
                
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(f"{key}:"))
            
            if isinstance(value, bool):
                dropdown = QComboBox()
                dropdown.addItem("True")
                dropdown.addItem("False")
                dropdown.setCurrentIndex(0 if value else 1)
                dropdown.currentTextChanged.connect(
                    lambda text, k=key: self.global_states.update({k: text == "True"})
                )
                dropdown.currentTextChanged.connect(
                    lambda text, k=key: self.console_output.appendPlainText(f"{k} updated to {text}")
                )
                row_layout.addWidget(dropdown)
            else:
                line_edit = QLineEdit(str(value))
                line_edit.textChanged.connect(
                    lambda text, k=key: self.update_numeric_value(text, k)
                )
                row_layout.addWidget(line_edit)
            tab2_layout.addLayout(row_layout)

        # Tab 3 Layout
        self.tab3.setLayout(QVBoxLayout())
        # Add each UI element to the settings with a button that can update the coordinates with SelectionOverlay
        for key, value in self.ui_locations.items():
            layout = QHBoxLayout()
            label = QLabel(f"{key}:")
            layout.addWidget(label)
            if isinstance(value, dict):
                coords = value.get("coords", (0, 0))
                coords_label = QLabel(f"Coords: {coords}")
                coords_button = QPushButton("Update Coords")
                coords_button.clicked.connect(lambda _, k=key, lbl=coords_label: self.capture_screenshot_region(is_point=True, target_key=k, label_to_update=lbl))

                layout.addWidget(coords_label)
                layout.addWidget(coords_button)
            else:
                coords_label = QLabel(f"Coords: {value}")
                layout.addWidget(coords_label)
            self.tab3.layout().addLayout(layout)

        # Tab 4 Layout
        self.tab4.setLayout(QVBoxLayout())

        for key in ["player", "enemy", "enemy2", "team", "connection_lost", "red_x", "retry_login", "play_button", "proceed_button", "im_ready_button", "exit_button", "current_game_mode", "next_game_mode", "next_brawler"]:
            layout = QHBoxLayout()
            label = QLabel(f"{key}:")
            layout.addWidget(label)
            button = QPushButton("Capture Screenshot")
            button.clicked.connect(lambda _, k=key: self.capture_screenshot_region(is_screenshot=True, target_key=k))
            layout.addWidget(button)
            self.tab4.layout().addLayout(layout)

        # Main Layout
        main_layout = QHBoxLayout()
        main_layout.addWidget(self.tabs, stretch=3)

       
        main_layout.addLayout(console_layout, stretch=2)

        self.setLayout(main_layout)
    
    def update_numeric_value(self, text, key):
        try:
            if text:  # Only try to convert if there's text
                value = int(text)
                self.global_states[key] = value
                self.console_output.appendPlainText(f"{key} updated to {value}")
        except ValueError:
            self.console_output.appendPlainText(f"Invalid input for {key}, must be a number")

    def start_key_capture(self, key_label, ui_element):
        """Start capturing the next keypress for hotkey assignment"""
        # Disable the button while capturing
        sender = self.sender()
        sender.setEnabled(False)
        sender.setText("Press any key...")
        
        def on_key_press(key):
            try:
                # Convert the key to a string representation
                if hasattr(key, 'char'):
                    key_str = key.char
                else:
                    key_str = str(key).replace('Key.', '')
                
                # Update the UI element's hotkey
                self.ui_locations[ui_element]["key"] = key_str
                # Update the label
                key_label.setText(f"Current hotkey: {key_str}")
                # Re-enable the button
                sender.setEnabled(True)
                sender.setText("Change Hotkey")
                # Log the change
                self.console_output.appendPlainText(f"Updated hotkey for {ui_element} to {key_str}")
                # Stop listening
                return False
            except Exception as e:
                self.console_output.appendPlainText(f"Error setting hotkey: {str(e)}")
                sender.setEnabled(True)
                sender.setText("Change Hotkey")
                return False

        # Start listening for a keypress
        listener = keyboard.Listener(on_press=on_key_press)
        listener.start()

    def capture_screenshot_region(self, is_screenshot=False, is_point=False, target_key=None, label_to_update=None):
        self.hide()
        self.overlay = SelectionOverlay(is_screenshot=is_screenshot, is_point=is_point)

        def handle_region(region_data):
            if is_point:
                self.ui_locations[target_key]["coords"] = (region_data["x"], region_data["y"])
                label_to_update.setText(f"Coords: {self.ui_locations[target_key]['coords']}")
                self.console_output.appendPlainText(f"{target_key} updated to {self.ui_locations[target_key]['coords']}")
            elif is_screenshot and target_key:
                def take_screenshot():
                    import mss
                    from PIL import Image
                    import os

                    try:
                        os.makedirs("img", exist_ok=True)
                        save_path = f"img/{target_key}.png"
                        with mss.mss() as sct:
                            monitor = {
                                "left": region_data["left"],
                                "top": region_data["top"],
                                "width": region_data["width"],
                                "height": region_data["height"],
                            }
                            sct_img = sct.grab(monitor)
                            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                            img.save(save_path)
                            self.console_output.appendPlainText(f"Saved screenshot to {save_path}")
                    except Exception as e:
                        self.console_output.appendPlainText(f"Failed to save screenshot: {e}")

                # Delay the screenshot slightly to let the overlay fully close
                QTimer.singleShot(100, take_screenshot)  # 100 ms is usually enough
            else:
                # Ensure region_data has all required keys
                validated_region = {
                    "left": region_data.get("left", 0),
                    "top": region_data.get("top", 0),
                    "width": region_data.get("width", 1100),
                    "height": region_data.get("height", 650)
                }
                self.global_states["screenshot_region"] = [validated_region]
                self.screenshot_label.setText(f"Region: {self.global_states['screenshot_region']}")
                self.console_output.appendPlainText(f"Screenshot region updated to {validated_region}")

        self.overlay.region.connect(handle_region)
        self.overlay.region_selected.connect(self.on_selection_complete)
        self.overlay.cancelled.connect(self.on_selection_cancelled)

    def on_selection_complete(self):
        self.show()
        self.screenshot_label.setText(f"Region: {self.global_states['screenshot_region']}")

    def on_selection_cancelled(self):
        self.show()
        self.screenshot_label.setText("Selection cancelled.")

    def start_bot(self):
        self.console_output.appendPlainText("Starting the bot")
        self.start_bot_button.setEnabled(False)
        self.thread = QThread()
        self.thread.setPriority(QThread.Priority.HighestPriority)  # Set thread to highest priority
        self.bot = BSBot(self.ui_locations, self.global_states, self.bot_template_paths, self.ui_template_paths)
        self.bot.moveToThread(self.thread)
        self.thread.started.connect(self.bot.check_state)
        self.bot.message.connect(lambda msg: self.console_output.appendPlainText(msg))
        self.bot.finished.connect(self.on_bot_stopped)
        self.thread.finished.connect(self.thread.deleteLater)

        self.console_output.appendPlainText("Bot started. Press ESC to stop.")
        self.thread.start()

    def on_bot_stopped(self):
        self.console_output.appendPlainText("Bot has stopped.")
        self.start_bot_button.setEnabled(True)
        # Properly clean up the thread
        if self.thread is not None:
            # Disconnect all signals
            self.bot.message.disconnect()
            self.bot.finished.disconnect()
            self.thread.started.disconnect()
            self.thread.finished.disconnect()
            self.thread.quit()
            self.thread.wait()
        self.bot = None
        self.thread = None
    
    SETTINGS_FILE = "bs_settings.json"

    def save_settings(self):
        data = {
            "global_states": self.global_states,
            "ui_locations": self.ui_locations
        }
        try:
            with open(self.SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=4)
            self.console_output.appendPlainText("Settings saved.")
        except Exception as e:
            self.console_output.appendPlainText(f"Failed to save settings: {e}")

    def load_settings(self):
        if not os.path.exists(self.SETTINGS_FILE):
            return  # Skip if no settings yet

        try:
            with open(self.SETTINGS_FILE, "r") as f:
                data = json.load(f)
                self.global_states.update(data.get("global_states", {}))
                self.ui_locations.update(data.get("ui_locations", {}))
                
                # Validate screenshot region format
                if not self.global_states.get("screenshot_region"):
                    self.global_states["screenshot_region"] = [{"left": 0, "top": 0, "width": 1100, "height": 650}]
                elif not isinstance(self.global_states["screenshot_region"], list):
                    self.global_states["screenshot_region"] = [self.global_states["screenshot_region"]]
                
                # Ensure each region has all required keys
                for i, region in enumerate(self.global_states["screenshot_region"]):
                    validated_region = {
                        "left": region.get("left", 0),
                        "top": region.get("top", 0),
                        "width": region.get("width", 1100),
                        "height": region.get("height", 650)
                    }
                    self.global_states["screenshot_region"][i] = validated_region
                    
            self.console_output.appendPlainText("Settings loaded.")
        except Exception as e:
            print(f"Failed to load settings: {e}")
            # Fallback to default region if there's an error
            self.global_states["screenshot_region"] = [{"left": 0, "top": 0, "width": 1100, "height": 650}]

    def closeEvent(self, event):
        # Stop the bot if it's running
        if hasattr(self, 'bot') and self.bot is not None:
            self.bot.state["stop_flag"] = True
            if self.thread is not None:
                # Give the bot time to clean up
                QTimer.singleShot(500, lambda: self.thread.quit())
                self.thread.wait()
        self.save_settings()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme='dark_teal.xml')
    window = BS_Farm()
    window.show()
    sys.exit(app.exec())
