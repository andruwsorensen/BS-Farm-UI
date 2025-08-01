import pydirectinput as pyautogui
import time
import random
import keyboard 
import threading
from pynput import keyboard
from fastScanner import FastTemplateScanner
import numpy as np
from PyQt6.QtCore import pyqtSignal, QObject, QTimer

class BSBot(QObject):
    finished = pyqtSignal()
    message = pyqtSignal(str)

    def __init__(self, ui_locations, global_states, BOT_TEMPLATE_PATHS, UI_TEMPLATE_PATHS):
        super().__init__()
        self.bot_scanner = FastTemplateScanner(BOT_TEMPLATE_PATHS, confidence_threshold=0.75)
        self.ui_locations = ui_locations
        self.ui_scanner = FastTemplateScanner(UI_TEMPLATE_PATHS, confidence_threshold=0.85)
        self.global_states = global_states
        self.idle_time = time.time()
        self.idle_count = 0
        self.state = {
            "stop_flag": False
        }
        self.movement_lock = threading.Lock()
        self.joystick_active = False  # Move this to instance variable
        

    def on_press(self, key):
        if key == keyboard.Key.esc:
            print("Stopping...")
            self.state["stop_flag"] = True
            self.cleanup()  # Clean up when stopping with ESC
            return False  # Stop listening for keys

    def cleanup(self):
        """Clean up all resources and release controls"""
        if self.global_states["use_mouse_movement"] and self.joystick_active:
            pyautogui.mouseUp()
            self.joystick_active = False
        # Release any held keyboard keys
        for key in self.global_states["movement_keys"]:
            if self.global_states["movement_keys"][key]:
                pyautogui.keyUp(key)
                self.global_states["movement_keys"][key] = False

    def check_state(self):
        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()
        last_scan_time = 0
        last_game_element_time = 0
        last_ui_scan_time = 0
        in_game_mode = False
        GAME_TIMEOUT = 5.0  # Time in seconds before switching back to UI mode if no game elements found
        SCAN_INTERVAL = 0.05  # Reduced minimum time between scans
        MIN_SLEEP = 0.001  # Minimum sleep time to prevent CPU thrashing
        FORCE_UI_SCAN_INTERVAL = 60.0  # Force UI scan every 60 seconds
        
        try:
            while not self.state["stop_flag"]:
                try:
                    current_time = time.time()
                    time_since_last_scan = current_time - last_scan_time
                    
                    # More responsive scan interval
                    if time_since_last_scan < SCAN_INTERVAL:
                        sleep_time = min(max(MIN_SLEEP, (SCAN_INTERVAL - time_since_last_scan) / 4), 0.01)
                        time.sleep(sleep_time)
                        continue
                    
                    last_scan_time = time.time()  # Update after sleep to ensure accurate timing
                    
                    # Check if we need to force a UI scan
                    if current_time - last_ui_scan_time > FORCE_UI_SCAN_INTERVAL:
                        self.message.emit("Performing periodic UI scan...")
                        try:
                            other_icons = self.ui_scanner.scan_screen(max_workers=2)
                            if other_icons:
                                self.ui_loop(other_icons)
                            last_ui_scan_time = current_time
                        except Exception as ui_error:
                            self.message.emit(f"Periodic UI scan error: {str(ui_error)}")

                    # Game scan with timeout
                    try:
                        found_icons = self.bot_scanner.scan_roi_regions(self.global_states["screenshot_region"], max_workers=2)
                        
                        if found_icons:
                            # Game elements found, process them
                            in_game_mode = True
                            last_game_element_time = last_scan_time
                            self.idle_time = last_scan_time
                            self.bot_loop(found_icons)
                            continue  # Skip regular UI scan if game elements found
                    except Exception as scan_error:
                        self.message.emit(f"Game scan error: {str(scan_error)}")
                        time.sleep(0.05)  # Brief pause on scan error
                    
                    # Handle UI mode transition
                    if in_game_mode and last_scan_time - last_game_element_time > GAME_TIMEOUT:
                        in_game_mode = False
                        self.message.emit("Switching to UI scan mode...")
                        self.joystick_active = False  # Release joystick if switching modes
                        pyautogui.mouseUp()
                    
                    # UI scan if needed
                    if not in_game_mode:
                        try:
                            self.message.emit("Scanning for UI elements...")
                            other_icons = self.ui_scanner.scan_screen(max_workers=2)
                            if other_icons:
                                self.idle_time = last_scan_time
                                self.ui_loop(other_icons)
                            elif last_scan_time - self.idle_time > int(self.global_states["idle_timeout"]):
                                self.message.emit("No elements found, performing idle clicks...")
                                x, y = self.ui_locations["idle_click_1"]["coords"]
                                pyautogui.click(x, y)
                                time.sleep(3)
                                x, y = self.ui_locations["idle_click_2"]["coords"]
                                pyautogui.click(x, y)
                                last_scan_time = time.time()  # Reset last scan time after idle clicks
                        except Exception as ui_error:
                            self.message.emit(f"UI scan error: {str(ui_error)}")
                            time.sleep(0.05)  # Brief pause on scan error
                    
                    # CPU load management
                    time.sleep(0.02)
                    
                except Exception as e:
                    self.message.emit(f"Error in main loop: {str(e)}")
                    time.sleep(0.1)  # Brief pause on error, but don't cleanup
                    
        finally:
            self.cleanup()  # Single cleanup when stopping
            self.finished.emit()


    def bot_loop(self, found_icons):
        if self.state["stop_flag"]:
            return
        if found_icons:
            player_pos = None
            enemy_pos = None
            
            if "player" in found_icons and ("enemy" in found_icons or "enemy2" in found_icons):
                # Get player_pos with highest confidence
                player_matches = found_icons["player"]
                if not isinstance(player_matches, list):
                    player_matches = [player_matches]
                player_pos = player_matches[0]['location']

                all_enemies = []
                if "enemy" in found_icons:
                    enemies = found_icons["enemy"]
                    if not isinstance(enemies, list):
                        enemies = [enemies]
                    all_enemies.extend(enemies)
                if "enemy2" in found_icons:
                    enemies2 = found_icons["enemy2"]
                    if not isinstance(enemies2, list):
                        enemies2 = [enemies2]
                    all_enemies.extend(enemies2)
                
                closest_enemy = min(
                    all_enemies, 
                    key=lambda e: ((player_pos[0] - e['location'][0]) ** 2 + 
                                (player_pos[1] - e['location'][1]) ** 2)
                )
                enemy_pos = closest_enemy['location']

                self.message.emit(f"Player at {player_pos}, Enemy at {enemy_pos}")
                distance = ((player_pos[0] - enemy_pos[0]) ** 2 + (player_pos[1] - enemy_pos[1]) ** 2) ** 0.5
                self.message.emit(f"Distance to enemy: {distance:.0f}")

                # Handle movement based on distance
                if distance < int(self.global_states["run_away_range"]):
                    self.message.emit("Enemy too close, running away!")
                    # Move away from enemy (reverse direction)
                    away_x = player_pos[0] + (player_pos[0] - enemy_pos[0])
                    away_y = player_pos[1] + (player_pos[1] - enemy_pos[1])
                    self.handle_movement(player_pos, (away_x, away_y), aggressive=False)
                elif distance < int(self.global_states["avoid_range"]):
                    self.message.emit("In avoid range, moving any way but toward enemy!")
                    self.handle_movement(player_pos, enemy_pos, aggressive=False, avoid=True)
                elif distance < int(self.global_states["approach_range"]):
                    self.message.emit("Enemy too far, approaching!")
                    self.handle_movement(player_pos, enemy_pos, aggressive=True)
                else:
                    self.message.emit("Enemy is very far, moving directly toward enemy.")
                    self.handle_movement(player_pos, enemy_pos, aggressive=True)
                
                # Attack logic (single call, less ifs):
                if self.global_states["attack_always"]:
                    self.execute_attack_sequence(0)  # Pass 0 to always trigger all attacks
                else:
                    self.execute_attack_sequence(distance)
            elif "player" in found_icons and "team" in found_icons:
                if self.change_state("following"):
                    self.message.emit("Now following team member")

                # Get player_pos with highest confidence
                player_matches = found_icons["player"]
                if not isinstance(player_matches, list):
                    player_matches = [player_matches]
                player_pos = player_matches[0]['location']

                # Get team_pos with highest confidence
                team_matches = found_icons["team"]
                if not isinstance(team_matches, list):
                    team_matches = [team_matches]
                team_pos = team_matches[0]['location']
                
                # Move toward team position
                self.handle_movement(player_pos, team_pos)
            elif "player" in found_icons:
                # Note: change_state method doesn't exist, removing this condition
                self.message.emit("Now exploring")
                # Random movement pattern
                self.intelligent_random_movement()


    
    def ui_loop(self, found_icons):
        if self.state["stop_flag"]:
            return
        
        self.message.emit(f"Found UI elements: {list(found_icons.keys())}")
            
        if "connection_lost" in found_icons or "retry_login" in found_icons:
            self.message.emit("Connection lost, retrying login...")
            self.trigger_action("retry_login")
        elif "play_button" in found_icons:
            if "current_game_mode" in found_icons:
                self.trigger_action("proceed_button")
            else:
                self.message.emit("Incorrect game mode, switching...")
                pyautogui.press("g")
                time.sleep(0.5)
                # scan and check for current game mode
                current_mode = None
                while not current_mode:
                    found_icons = self.ui_scanner.scan_screen(max_workers=2)
                    time.sleep(0.5)
                    if "current_game_mode" in found_icons:
                        current_mode = found_icons["current_game_mode"]
                        self.message.emit(f"Current game mode detected at {current_mode['center']}")
                        x, y = current_mode['center']
                        pyautogui.click(x, y)
                        time.sleep(0.5)
                        self.trigger_action("play_button")
                    else:
                        pyautogui.press("t")
                        time.sleep(1.5)
        elif "proceed_button" in found_icons or "exit_button" in found_icons:
            self.message.emit("Proceed button found, clicking...")
            self.trigger_action("proceed_button")
        elif "red_x" in found_icons:
            red_x_match = found_icons["red_x"]
            x, y = red_x_match['center']
            pyautogui.click(x, y)


    def smooth_key_transition(self, key, target_state):
        with self.movement_lock:
            current_state = self.global_states["movement_keys"][key]

            if current_state == target_state:
                return  # No change needed

            self.global_states["movement_keys"][key] = target_state

            if target_state:
                pyautogui.keyDown(key)
            else:
                pyautogui.keyUp(key)

    def trigger_action(self, action_name):
        action = self.ui_locations.get(action_name)
        if action:
            if self.global_states["use_keyboard"]:
                pyautogui.press(action["key"])
            else: 
                pyautogui.click(action["coords"])

    def handle_movement(self, player_pos, target_pos, aggressive=False, avoid=False):
        """Handle movement based on relative positions with optional aggressive mode and avoid (move any way but toward target)."""
        try:
            # Check if we should stop movement
            if self.state["stop_flag"]:
                if self.joystick_active:
                    pyautogui.mouseUp()
                    self.joystick_active = False
                return False

            # Extract coordinates, handling both dictionary and tuple formats
            if isinstance(player_pos, dict):
                px, py = player_pos['x'], player_pos['y']
            else:
                px, py = player_pos[0], player_pos[1]
            
            if isinstance(target_pos, dict):
                tx, ty = target_pos['x'], target_pos['y']
            else:
                tx, ty = target_pos[0], target_pos[1]
            
            # print(f"Player: ({px}, {py}), Target: ({tx}, {ty})")
            distance = ((px - tx) ** 2 + (py - ty) ** 2) ** 0.5
            print(f"Distance to target: {distance:.2f}")
            
            if self.global_states["use_mouse_movement"]:
                joystick_x = float(self.global_states["joystick_x"])
                joystick_y = float(self.global_states["joystick_y"])
                joystick_radius = float(self.global_states["joystick_radius"])

                if avoid:
                    # Move in a random direction that is not toward the target
                    base_angle = np.arctan2(float(ty - py), float(tx - px))
                    # Pick a random angle at least 60 degrees away from base_angle
                    options = [base_angle + np.pi/2, base_angle - np.pi/2, base_angle + np.pi, base_angle - np.pi]
                    angle = random.choice(options)
                    move_x = int(joystick_x + joystick_radius * np.cos(angle))
                    move_y = int(joystick_y + joystick_radius * np.sin(angle))
                    if not self.joystick_active:
                        pyautogui.moveTo(int(joystick_x), int(joystick_y))
                        pyautogui.mouseDown()
                        self.joystick_active = True
                    pyautogui.moveTo(move_x, move_y, duration=0.05)
                    print(f"Avoiding enemy: move to ({move_x},{move_y}) at angle {angle:.2f}")
                    return False
                    
                # Calculate direction vector from joystick base to target
                dx = float(tx - px)
                dy = float(ty - py)
                norm = np.sqrt(dx * dx + dy * dy)
                if norm < 0.0001:  # Avoid division by zero
                    norm = 1
                # Clamp movement to joystick radius
                move_x = int(joystick_x + joystick_radius * dx / norm)
                move_y = int(joystick_y + joystick_radius * dy / norm)
                
                # Move mouse to joystick base and hold down if not already
                if not self.joystick_active:
                    pyautogui.moveTo(int(joystick_x), int(joystick_y))
                    pyautogui.mouseDown()
                    self.joystick_active = True
                    print(f"Joystick mouseDown at ({int(joystick_x)},{int(joystick_y)})")
                
                # Move mouse within joystick radius
                pyautogui.moveTo(int(move_x), int(move_y), duration=0.05)
                print(f"Moving joystick to ({move_x},{move_y})")
                # print(f"Joystick move to ({move_x},{move_y}) from base ({JOYSTICK_X},{JOYSTICK_Y})")
            else:
                if avoid:
                    # Move in a random WASD direction that is not toward the target
                    for key in ["a", "d", "s", "w"]:
                        self.smooth_key_transition(key, False)
                    # Determine direction toward target
                    toward = []
                    if py > ty:
                        toward.append("w")
                    if py < ty:
                        toward.append("s")
                    if px > tx:
                        toward.append("a")
                    if px < tx:
                        toward.append("d")
                    # Pick a random direction not in toward
                    options = [k for k in ["w", "a", "s", "d"] if k not in toward]
                    if options:
                        avoid_key = random.choice(options)
                        self.smooth_key_transition(avoid_key, True)
                        print(f"Avoiding enemy: move with key {avoid_key}")
                    return False
                # Determine desired key states
                desired_states = {
                    "w": py > ty,  # Move up if target is above
                    "s": py < ty,  # Move down if target is below
                    "a": px > tx,  # Move left if target is to the left
                    "d": px < tx   # Move right if target is to the right
                }
                print(f"Distance to target: {distance:.2f}, Desired states: {desired_states}")
                for key, target_state in desired_states.items():
                    self.smooth_key_transition(key, target_state)
            if aggressive and distance < self.global_states["attack_range"] and not self.global_states["use_mouse_movement"]:
                return True
            return False
        except Exception as e:
            print(f"Error in handle_movement: {e}")
            print(f"player_pos type: {type(player_pos)}, value: {player_pos}")
            print(f"target_pos type: {type(target_pos)}, value: {target_pos}")
            # Always release mouse if error
            if self.global_states["use_mouse_movement"] and self.joystick_active:
                pyautogui.mouseUp()
                self.joystick_active = False
            return False

    def execute_attack_sequence(self, distance):
        """Execute the attack sequence based on distance thresholds."""
        if distance <= self.global_states["super_range"]:
            # In super range: attack, sometimes use abilities
            self.trigger_action("hypercharge_button")
            self.trigger_action("super_button")
        if distance <= self.global_states["attack_range"]:
            # Close range: always attack, always use abilities
            self.trigger_action("gadget_button")
            self.trigger_action("attack_button")
            self.trigger_action("attack_button")

    def intelligent_random_movement(self):
        if self.global_states["use_mouse_movement"]:
            joystick_x = int(self.global_states["joystick_x"])
            joystick_y = int(self.global_states["joystick_y"])
            joystick_radius = int(self.global_states["joystick_radius"])
            # Use static variable to remember last angle
            if not hasattr(self, "last_angle"):
                self.last_angle = 3 * np.pi / 2  # Start up
            # Occasionally (10%) pick a new direction (left, right, or straight)
            if random.random() < 0.10:
                nudge = random.choice([-1, 0, 1])
                self.last_angle = 3 * np.pi / 2 + nudge * (np.pi / 6)
            angle = self.last_angle
            move_x = joystick_x + int(joystick_radius * np.cos(angle))
            move_y = joystick_y + int(joystick_radius * np.sin(angle))
            # If joystick not active, press and hold
            if not self.joystick_active:
                pyautogui.moveTo(joystick_x, joystick_y)
                pyautogui.mouseDown()
                self.joystick_active = True
                print(f"Joystick mouseDown at ({joystick_x},{joystick_y})")
            pyautogui.moveTo(move_x, move_y, duration=0.05)
            print(f"Random movement: Moving joystick to ({move_x},{move_y})")
        else:
            if random.random() < 0.10:
                for key in ["a", "d", "s", "w"]:
                    self.smooth_key_transition(key, False)
                # Always keep W pressed for forward movement
                self.smooth_key_transition("w", True)
                if random.random() < 0.8:
                    horizontal = random.choice(["a", "d"])
                    self.smooth_key_transition(horizontal, True)