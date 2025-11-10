# BS-Farm-UI

BS-Farm-UI is a desktop automation tool with a graphical user interface (GUI) for automating gameplay tasks in Brawl Stars (or similar games), leveraging computer vision and input simulation. The project aims to simplify and automate repetitive in-game actions, such as character movement, attacking, and button presses, using screen regions, templates, and hotkeys defined by users through an integrated UI.

## Features

- **Automated Gameplay:** Implements bot actions such as movement, enemy avoidance, and attack sequences.
- **Configurable UI:** Intuitive tabs for main controls, variables, UI element locations, and screenshot regions.
- **Screen Region Selection:** Overlay tools for selecting arbitrary regions of the screen for template matching and automation triggers.
- **Hotkey Management:** Users can define and change hotkeys for specific automated actions through the interface.
- **Screenshot & Template Matching:** Integration of template images to identify UI elements and game states using screen captures.
- **Console Output:** Built-in console tab for logging and debugging bot actions.

## Technologies Used

- **Python**: Main programming language for backend logic and UI.
- **PyQt6**: Used for building the graphical interface, overlays, and dialog controls.
- **qt-material**: For modern UI themes and styling.
- **pydirectinput / pyautogui**: For simulating keyboard and mouse actions to control the game.
- **pynput**: For hotkey capturing and keyboard event handling.
- **OpenCV or template matching (assumed via FastTemplateScanner)**: For detecting game and UI elements in screenshots.
- **NumPy**: Used in movement calculations and vector math.
- **threading**: To manage concurrent state and input actions.

## Project Structure

Major files include:
- `main.py`: The main entry, GUI logic, and user controls.
- `bs_bot.py`: Core automation logic and bot actions.
- `afkMac.py`: Platform-specific automation and template scanning (macOS).
- `track-mouse.py`: Utility to monitor mouse coordinates for debug and setup.
- `img/`: Contains game UI element templates for vision matching.

## References

This project was inspired by and builds upon concepts from:
- [Custom game object recognition with YOLOv5](https://medium.com/better-programming/how-to-train-yolov5-for-recognizing-custom-game-objects-in-real-time-9d78369928a8)
- [Brawl Stars Bot projects](https://github.com/Jooi025/BrawlStarsBot), [PylaAI](https://github.com/PylaAI/PylaAI), [AngelFireLA/BrawlStarsBotMaking](https://github.com/AngelFireLA/BrawlStarsBotMaking)

## Getting Started

1. Ensure Python and dependencies (listed above) are installed.
2. Run `main.py` to launch the UI and configure bot and UI templates.
3. Capture required UI elements and regions within the app.
4. Start the bot to automate gameplay actions.

---

For more information and latest updates, visit the [GitHub repository](https://github.com/andruwsorensen/BS-Farm-UI).
