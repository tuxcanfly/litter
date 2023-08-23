import json
import requests
import threading
import urwid
from readability import Document
from bs4 import BeautifulSoup

SEARCH_ENGINE = 'https://lite.duckduckgo.com/lite?q='

HEADERS = {
    'User-Agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

DEFAULT_KEY_MAP = {
    'quit': ['q', 'Q', 'esc'],
    'enter': ['enter'],
    'back': ['backspace'],
    'open': ['i'],
    'help': ['?'],
    'bookmark': ['b']
}

BOOKMARKS_FILE = "bookmarks.txt"

class BrowserApp:
    HELP_TEXT = [
        "q or Q or esc: Quit the browser",
        "i: Jump to the URL bar",
        "b: Bookmark current URL",
        "enter: Load the URL",
        "backspace: Go back to the previous page",
        "?: Help screen",
        # Add more keybindings here
    ]

    def __init__(self):
        self.key_map = self.load_keymap()
        self.history = self.History()
        self.main_loop = None

    def load_keymap(self, filename="keymap.json"):
        try:
            with open(filename, 'r') as f:
                custom_key_map = json.load(f)
            return custom_key_map
        except FileNotFoundError:
            return DEFAULT_KEY_MAP

    class History:
        def __init__(self):
            self.stack = []
            self.position = -1

        def add(self, url):
            self.stack = self.stack[:self.position+1]  # Remove forward history
            self.stack.append(url)
            self.position += 1

        def back(self):
            if self.position > 0:
                self.position -= 1
                return self.stack[self.position]
            return None

        def forward(self):
            if self.position + 1 < len(self.stack):
                self.position += 1
                return self.stack[self.position]
            return None

    # Other methods for BrowserApp class (similar to the functions in the original script).
    # For instance, methods like `get_bookmarks`, `save_bookmark`, `help_overlay`, and so on...

    def run(self):
        url = "https://example.com"
        self.history.add(url)

        # Fetch initial content synchronously since it's the first load and UI is not yet running.
        content, links, title = self.fetch_and_clean_article(url)
        main_widget, edit_widget = self.article_view(content, links, title)

        palette = [
            ('status_bar', 'black', 'white'),
            ('url_bar', 'black', 'white'),
            ('link', 'yellow', 'black'),
            ('url_bar_focused', 'black', 'yellow'),
            ('text_focused', 'yellow', 'black')
        ]

        self.main_loop = urwid.MainLoop(main_widget, palette=palette, unhandled_input=lambda key: self.handle_input(key, edit_widget))
        self.assign_loop_to_buttons()
        self.main_loop.run()

if __name__ == "__main__":
    app = BrowserApp()
    app.run()
