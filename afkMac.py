import pydirectinput as pyautogui
import time
import random
import keyboard 
import threading
from pynput import keyboard
from fastScanner import FastTemplateScanner
import numpy as np

# icon_name: (path, use_grayscale, region, confidence)p
TEMPLATE_PATHS = {
    "player":    "img/player.png",
    "enemy":     "img/enemy.png",
    "enemy2":    "img/enemy2.png",
    # "team":      "img/team.png"
    
}

scanner = FastTemplateScanner(TEMPLATE_PATHS, confidence_threshold=0.75)

# UI coordinates and keyboard shortcuts
UI_LOCATIONS = {
    "attack_button": {"coords": (1100, 600), "key": "space"},      # J for attack
    "super_button": {"coords": (1225, 800), "key": "e"},       # K for super
    "gadget_button": {"coords": (1300, 880), "key": "f"},      # L for gadget
    "proceed_button": {"coords": (1200, 900), "key": "p"}, # Space to proceed
    "retry_login": {"coords": (1200, 900), "key": "r"},         # R to retry loginp
    "hypercharge_button": {"coords": (1180, 900), "key": "q"}  # H for hypercharge
}

# Global state
CURRENT_STATE = "idle"  # Current state of the bot
LAST_STATE_CHANGE = 0  # Time of last state chprange
UI_COOLDOWN = 3
MOVEMENT_KEYS = {"w": False, "a": False, "s": False, "d": False}  # Track key states
ATTACK_RANGE = 400  # Distance to consider close enough for regular attack
SUPER_RANGE = 600   # Distance to consider close enough for super
AVOID_RANGE = 300   # Distance to start avoiding (not approach, not run)
ATTACK_COOLDOWN = 0.5
APPROACH_RANGE = 600  # Distance to start approaching enemy
RUN_AWAY_DISTANCE = 150  # Distance to start running away (customizable)
USE_KEYBOARD = True  # Use keyboard for actions
USE_MOUSE_MOVEMENT = True  # Set to True to use mouse drag for movement instead of WASD
TIME_BETWEEN_SCANS = 0.1  # Time between scans in seconds
USE_ROI = True  # Use regions of interest for faster scanning
ROI_REGIONS = [
    # {"left": 100, "top": 40, "width": 1000, "height": 700},  # Top left win window
    {"left": 70, "top": 45, "width": 1100, "height": 650   },  # Top left win monitor
    # {"left": 100, "top": 60, "width": 750, "height": 540}, #Monitor top left
]
IDLE_COUNT = 0

IDLE_TIMEOUT = 90  # 3 minutes in seconds
IDLE_CLICK_1 = (525, 25 )  # First point to click after idle
IDLE_CLICK_2 = (1035, 400)  # Second point to click after 15s

# Joystick constants (used for both handle_movement and intelligent_random_movement)
JOYSTICK_X, JOYSTICK_Y = 245, 505
JOYSTICK_RADIUS = 75

ATTACK_ALWAYS_ON = False  # Toggle to attack constantly on every scan

state_lock = threading.Lock()  # Lock for state changes

movement_lock = threading.Lock()  # Lock for movement keys

state = {"stop_flag": False}
last_active_time = time.time()

def on_press(key):
    if key == keyboard.Key.esc:
        print("Stopping...")
        state["stop_flag"] = True
        return False  # Stop listening for keys
    
def smooth_key_transition(key, target_state):
    """Smoothly transition key states to reduce jittery movement"""
    global MOVEMENT_KEYS
    
    with movement_lock:
        current_state = MOVEMENT_KEYS[key]
        
        if current_state == target_state:
            return  # No change needed
        
        MOVEMENT_KEYS[key] = target_state
        
        if target_state:
            pyautogui.keyDown(key)
        else:
            pyautogui.keyUp(key)

def handle_movement(player_pos, target_pos, aggressive=False, avoid=False):
    """Handle movement based on relative positions with optional aggressive mode and avoid (move any way but toward target)."""
    try:
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
        
        if USE_MOUSE_MOVEMENT:
            if avoid:
                # Move in a random direction that is not toward the target
                base_angle = np.arctan2(ty - py, tx - px)
                # Pick a random angle at least 60 degrees away from base_angle
                options = [base_angle + np.pi/2, base_angle - np.pi/2, base_angle + np.pi, base_angle - np.pi]
                angle = random.choice(options)
                move_x = JOYSTICK_X + int(JOYSTICK_RADIUS * np.cos(angle))
                move_y = JOYSTICK_Y + int(JOYSTICK_RADIUS * np.sin(angle))
                if not getattr(handle_movement, "joystick_active", False):
                    pyautogui.moveTo(JOYSTICK_X, JOYSTICK_Y)
                    pyautogui.mouseDown()
                    handle_movement.joystick_active = True
                pyautogui.moveTo(move_x, move_y, duration=0.05)
                print(f"Avoiding enemy: move to ({move_x},{move_y}) at angle {angle:.2f}")
                return False
            # Calculate direction vector from joystick base to target
            dx = tx - px
            dy = ty - py
            norm = (dx ** 2 + dy ** 2) ** 0.5
            if norm == 0:
                norm = 1
            # Clamp movement to joystick radius
            move_x = JOYSTICK_X + int(JOYSTICK_RADIUS * dx / norm)
            move_y = JOYSTICK_Y + int(JOYSTICK_RADIUS * dy / norm)
            # Move mouse to joystick base and hold down if not already
            if not getattr(handle_movement, "joystick_active", False):
                pyautogui.moveTo(JOYSTICK_X, JOYSTICK_Y)
                pyautogui.mouseDown()
                handle_movement.joystick_active = True
                print(f"Joystick mouseDown at ({JOYSTICK_X},{JOYSTICK_Y})")
            # Move mouse within joystick radius
            pyautogui.moveTo(move_x, move_y, duration=0.05)
            # print(f"Joystick move to ({move_x},{move_y}) from base ({JOYSTICK_X},{JOYSTICK_Y})")
        else:
            if avoid:
                # Move in a random WASD direction that is not toward the target
                for key in ["a", "d", "s", "w"]:
                    smooth_key_transition(key, False)
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
                    smooth_key_transition(avoid_key, True)
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
                smooth_key_transition(key, target_state)
        if aggressive and distance < ATTACK_RANGE and not USE_MOUSE_MOVEMENT:
            return True
        return False
    except Exception as e:
        print(f"Error in handle_movement: {e}")
        print(f"player_pos type: {type(player_pos)}, value: {player_pos}")
        print(f"target_pos type: {type(target_pos)}, value: {target_pos}")
        # Always release mouse if error
        if USE_MOUSE_MOVEMENT and getattr(handle_movement, "joystick_active", False):
            pyautogui.mouseUp()
            handle_movement.joystick_active = False
        return False

def trigger_action(action_name):
    """Helper function to trigger an action using either keyboard or mouse"""
    action = UI_LOCATIONS.get(action_name)
    if action:
        if USE_KEYBOARD:
            pyautogui.press(action["key"])
        else: 
            pyautogui.click(action["coords"])

def execute_attack_sequence(distance):
    """Execute the attack sequence based on distance thresholds."""
    if distance <= SUPER_RANGE:
        # In super range: attack, sometimes use abilities
        trigger_action("hypercharge_button")
        trigger_action("super_button")
    if distance <= ATTACK_RANGE:
        # Close range: always attack, always use abilities
        trigger_action("gadget_button")
        trigger_action("attack_button")
        time.sleep(ATTACK_COOLDOWN)
        trigger_action("attack_button")

def intelligent_random_movement():
    """Simple joystick movement: only change direction (including straight) occasionally, otherwise keep last direction."""
    if USE_MOUSE_MOVEMENT:
        # Use static variable to remember last angle
        if not hasattr(intelligent_random_movement, "last_angle"):
            intelligent_random_movement.last_angle = 3 * np.pi / 2  # Start up
        # Occasionally (10%) pick a new direction (left, right, or straight)
        if random.random() < 0.10:
            nudge = random.choice([-1, 0, 1])
            intelligent_random_movement.last_angle = 3 * np.pi / 2 + nudge * (np.pi / 6)
            print(f"Joystick direction changed: nudge {nudge}")
        angle = intelligent_random_movement.last_angle
        move_x = JOYSTICK_X + int(JOYSTICK_RADIUS * np.cos(angle))
        move_y = JOYSTICK_Y + int(JOYSTICK_RADIUS * np.sin(angle))
        # If joystick not active, press and hold
        if not getattr(handle_movement, "joystick_active", False):
            pyautogui.moveTo(JOYSTICK_X, JOYSTICK_Y)
            pyautogui.mouseDown()
            handle_movement.joystick_active = True
            print(f"Joystick mouseDown at ({JOYSTICK_X},{JOYSTICK_Y})")
        pyautogui.moveTo(move_x, move_y, duration=0.05)
    else:
        if random.random() < 0.10:
            for key in ["a", "d", "s", "w"]:
                smooth_key_transition(key, False)
            # Always keep W pressed for forward movement
            smooth_key_transition("w", True)
            if random.random() < 0.8:
                horizontal = random.choice(["a", "d"])
                smooth_key_transition(horizontal, True)

def change_state(new_state):
    """Change the bot state with cooldown protection"""
    global CURRENT_STATE
    
    with state_lock:
        # print(f"Attempting to change state from {CURRENT_STATE} to {new_state}")
            
        if new_state != CURRENT_STATE:
            print(f"State change: {CURRENT_STATE} -> {new_state}")
            CURRENT_STATE = new_state
            return True
    
    return False
        
def process_game_state(found_icons):
    """Process the current game state based on detected icons"""
    global CURRENT_STATE
    global LAST_STATE_CHANGE
    global IDLE_COUNT

    # Combat mode - check for either enemy type
    if "player" in found_icons and ("enemy" in found_icons or "enemy2" in found_icons):
        if change_state("combat"):
            print("Now in combat mode")
        
        # Get player_pos with highest confidence
        player_matches = found_icons["player"]
        if not isinstance(player_matches, list):
            player_matches = [player_matches]
        player_pos = player_matches[0]['location']
        print(f"Player position: {player_pos}")

        # Get enemy_pos with highest confidence
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
        print("Closest enemy position:", enemy_pos)
        
        distance = ((player_pos[0] - enemy_pos[0]) ** 2 + (player_pos[1] - enemy_pos[1]) ** 2) ** 0.5
        print(f"Distance to enemy: {distance:.2f}")
        # --- Distance-based engagement logic ---
        if distance < RUN_AWAY_DISTANCE:
            print("Too close! Running away.")
            # Move away from enemy (reverse direction)
            away_x = player_pos[0] + (player_pos[0] - enemy_pos[0])
            away_y = player_pos[1] + (player_pos[1] - enemy_pos[1])
            handle_movement(player_pos, (away_x, away_y), aggressive=False)
        elif distance < AVOID_RANGE:
            print("In avoid range, moving any way but toward enemy!")
            handle_movement(player_pos, enemy_pos, aggressive=False, avoid=True)
        elif distance < APPROACH_RANGE:
            print("Enemy too far, approaching!")
            handle_movement(player_pos, enemy_pos, aggressive=True)
        else:
            print("Enemy is very far, moving directly toward enemy.")
            handle_movement(player_pos, enemy_pos, aggressive=True)
        # Attack logic (single call, less ifs):
        if ATTACK_ALWAYS_ON:
            execute_attack_sequence(0)  # Pass 0 to always trigger all attacks
        else:
            execute_attack_sequence(distance)
    elif "player" in found_icons and "team" in found_icons:
        if change_state("following"):
            print("Now following team member")

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
        handle_movement(player_pos, team_pos)
    elif "player" in found_icons:
        if change_state("exploring"):
            print("Now exploring")
        
        # Random movement pattern
        intelligent_random_movement()

    else:
        if change_state("idle"):
            print("No player found, going idle")
        
        print("No player or team found, trying to ineract with UI")
        IDLE_COUNT += 1
        if IDLE_COUNT > 5: 
            IDLE_COUNT = 0
            pyautogui.mouseUp()  # Release mouse if using joystick
            handle_movement.joystick_active = False  # Reset joystick state if idle too long

        proceed_time = time.time()
        if proceed_time - LAST_STATE_CHANGE > UI_COOLDOWN:
            trigger_action("proceed_button")
            # if random.random() < 1.0:
                # trigger_action("retry_login")
            LAST_STATE_CHANGE = proceed_time
    if "connection_lost" in found_icons:
        # Click reload button
        time.sleep(1)  # Small delay to ensure UI is ready
        trigger_action("retry_login")

EXTRA_SCAN_INTERVAL = 90  # Interval in seconds for extra scans (adjustable)
EXTRA_TEMPLATE_PATHS = {
    # Add your extra images here, e.g.:
    # "special_item": "img/special_item.png",
    # "rare_enemy": "img/rare_enemy.png",
    "connection_lost": "img/connection_lost.png",
    "red_x": "img/red_x.png",  # Example extra image
    "reload": "img/reload.png",  # Example extra image
}
last_extra_scan_time = time.time()
extra_scanner = FastTemplateScanner(EXTRA_TEMPLATE_PATHS, confidence_threshold=0.75)

def main_loop():
    """Main loop to continuously scan for templates"""
    global last_active_time
    global last_extra_scan_time
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    print("Listening for ESC key to stop...")
    try:
        while not state["stop_flag"]:
            # Regular scan
            if USE_ROI:
                found_icons = scanner.scan_roi_regions(ROI_REGIONS, max_workers=4)
            else:
                found_icons = scanner.scan_screen(max_workers=4)
            print(f"Found icons: {found_icons.keys()}")
            # Extra scan every EXTRA_SCAN_INTERVAL seconds
            if EXTRA_TEMPLATE_PATHS and time.time() - last_extra_scan_time > EXTRA_SCAN_INTERVAL:
                print("Performing extra scan for special images...")
                extra_found = extra_scanner.scan_screen(max_workers=2)
                print(f"Extra scan found: {extra_found}")
                # You can add custom logic here for handling extra_found
                if "connection_lost" in extra_found or "reload" in extra_found:
                    print("Connection lost or reload detected, clicking retry login...")
                    trigger_action("retry_login")
                elif "red_x" in extra_found:
                    print("Red X detected, clicking retry login...")
                    # Find x coordinates of red X and click
                    red_x_matches = extra_found["red_x"]
                    print(f"Red X matches: {red_x_matches}")
                    if red_x_matches:
                        # Click on the first red X found
                        x, y = red_x_matches['location']
                        print(f"Clicking red X at ({x}, {y})")
                        pyautogui.click(x, y)
                last_extra_scan_time = time.time()
            # Check for activity
            if any(k in found_icons for k in ["player", "enemy", "enemy2", "team"]):
                last_active_time = time.time()
            else:
                # If idle for more than 3 minutes, perform idle actions
                if time.time() - last_active_time > IDLE_TIMEOUT:
                    print("Idle detected: clicking first point...")
                    pyautogui.click(IDLE_CLICK_1[0], IDLE_CLICK_1[1])
                    time.sleep(5)
                    print("Idle detected: clicking second point...")
                    pyautogui.click(IDLE_CLICK_2[0], IDLE_CLICK_2[1])
                    last_active_time = time.time()  # Reset timer after action
            process_game_state(found_icons)
            time.sleep(TIME_BETWEEN_SCANS)
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        listener.stop()
        print("Stopped listening for keys.")
        for key in MOVEMENT_KEYS:
            pyautogui.keyUp(key)

# Ensure mouse is released on exit
if __name__ == "__main__":
    try:
        print("Starting bot...")
        main_loop()
        print("Bot stopped.")
    except KeyboardInterrupt:
        print("Bot stopped by user.")
    finally:
        # Clean up - release all keys
        for key in MOVEMENT_KEYS:
            pyautogui.keyUp(key)
        if USE_MOUSE_MOVEMENT and getattr(handle_movement, "joystick_active", False):
            pyautogui.mouseUp()
            handle_movement.joystick_active = False
        print("Automation ended. All keys released.")

