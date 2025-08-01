import pyautogui

print("Move your mouse. Press Ctrl+C to stop.\n")

try:
    while True:
        x1, y1 = pyautogui.position()
        print(f"pyautogui: x={x1:<4} y={y1:<4}", end="\r")
except KeyboardInterrupt:
    print("\nDone.")
