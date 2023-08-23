import json
import requests
import threading
import urwid

from readability import Document
from bs4 import BeautifulSoup

"""
toy browser
"""


SEARCH_ENGINE = 'https://lite.duckduckgo.com/lite?q='

HEADERS = {
    'User-Agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

HELP_TEXT = [
    "q or Q or esc: Quit the browser",
    "i: Jump to the URL bar",
    "b: Bookmark current URL",
    "enter: Load the URL",
    "backspace: Go back to the previous page",
    "?: Help screen",
    # Add more keybindings here
]

DEFAULT_KEY_MAP = {
    'quit': ['q', 'Q', 'esc'],
    'enter': ['enter'],
    'back': ['backspace'],
    'next_line': ['j'],
    'prev_line': ['k'],
    'first_line': ['g'],
    'last_line': ['G'],
    'open': ['i'],
    'help': ['?'],
    'bookmark': ['b']
}

BOOKMARKS_FILE = "bookmarks.txt"

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

class Bookmarks:
    def __init__(self):
        self.file = BOOKMARKS_FILE

    def get_bookmarks(self):
        try:
            with open(self.file, 'r') as f:
                return [line.strip() for line in f.readlines()]
        except FileNotFoundError:
            with open(self.file, 'w') as f:  # Create the file if it doesn't exist.
                pass
            return []

    def save_bookmark(self, url):
        bookmarks = self.get_bookmarks()
        if url not in bookmarks:
            with open(self.file, 'a') as f:
                f.write(url + '\n')

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
        self.history = History()
        self.bookmarks = Bookmarks()
        self.main_loop = None

    def load_keymap(self, filename="keymap.json"):
        try:
            with open(filename, 'r') as f:
                custom_key_map = json.load(f)
            return custom_key_map
        except FileNotFoundError:
            return DEFAULT_KEY_MAP

    def help_overlay(self):
        help_content = urwid.Text("\n".join(HELP_TEXT))
        help_fill = urwid.Filler(help_content, 'middle')
        help_frame = urwid.LineBox(help_fill, title="Help - Press '?' to close")
        return urwid.Overlay(help_frame, self.main_loop.widget, 'center', ('relative', 30), 'middle', ('relative', 15))

    @classmethod
    def fetch_and_clean_article(self, url):
        """
        Fetch and clean article from a URL.

        :param url: URL of the article.
        :return: Tuple containing plain text of the article, links, and page title.
        """
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()  # Check for successful request

            # Additional checks for content type
            content_type = response.headers.get('Content-Type')
            if 'text/html' not in content_type:
                return "Error: Content type is not HTML.", [], ""

            doc = Document(response.text)
            page_title = doc.title()
            cleaned_content = doc.summary()

            soup = BeautifulSoup(cleaned_content, 'html.parser')
            plain_text = soup.get_text()

            # Extract links and present differently
            links = []
            for a in soup.find_all('a'):
                href = a.get('href')
                if href:
                    links.append((a.text, href))

            return plain_text, links, page_title
        except requests.RequestException as e:
            return f"Error: {str(e)}", [], ""

    @classmethod
    def fetch_content_async(self, url, callback):
        def worker():
            content, links, title = self.fetch_and_clean_article(url)
            callback(url, content, links, title)

        thread = threading.Thread(target=worker)
        thread.start()

    def on_content_fetched(self, url, content, links, title):
        new_view, new_edit = self.article_view(url, content, links, title)
        self.main_loop.widget = new_view
        self.main_loop.edit = new_edit
        self.main_loop.draw_screen()

    def article_view(self, url, content, links, title):
        # Represent links as (URL, displayed_text)
        txt_content = []
        link_map = {}  # To store links for navigation
        for line in content.split('\n'):
            matching_links = [link for link in links if link[0] == line]
            if matching_links:
                displayed_text, link_url = matching_links[0]
                link_map[displayed_text] = link_url  # Map text to URL
                txt_content.append(('link', displayed_text))
            else:
                txt_content.append(line)
        items = [
            urwid.AttrMap(urwid.SelectableIcon(item, 0), None, 'text_focused')
            if isinstance(item, str)
            else urwid.AttrMap(urwid.Button(item[1],
                on_press=self.link_pressed,
                user_data=link_map[item[1]]),
               'link',
               focus_map='reversed'
            ) for item in txt_content
        ]

        walker = urwid.SimpleFocusListWalker(items)
        listbox = urwid.ListBox(walker)

        # Status bar with the current page title or fallback to URL if title is not available
        status_bar_text = title
        status_bar = urwid.Text(status_bar_text)
        status_bar = urwid.AttrWrap(status_bar, 'status_bar')

        # URL bar to enter addresses
        edit = urwid.Edit(url)
        url_bar = urwid.AttrMap(edit, 'url_bar', 'url_bar_focused')

        # Combine listbox, status bar, and URL bar
        layout = urwid.Frame(header=url_bar, body=listbox, footer=status_bar)

        return layout, edit

    def open(self, url):
        self.history.add(url)
        self.fetch_content_async(url, self.on_content_fetched)

    def handle_input(self, key):
        global history
        if key in self.key_map['quit']:
            # Show the confirmation dialog
            self.confirm_quit()
        elif key in self.key_map['next_line']:
            listbox = self.main_loop.widget.body
            if listbox.focus_position < len(listbox.body) - 1:
                listbox.set_focus(listbox.focus_position + 1)
        elif key in self.key_map['prev_line']:
            listbox = self.main_loop.widget.body
            if listbox.focus_position > 0:
                listbox.set_focus(listbox.focus_position - 1)
        elif key in self.key_map['first_line']:
            listbox = self.main_loop.widget.body
            listbox.set_focus(0)
        elif key in self.key_map['last_line']:
            listbox = self.main_loop.widget.body
            listbox.set_focus(len(listbox.body) - 1)
        elif key in self.key_map['enter']:
            new_url = self.main_loop.edit.get_edit_text()
            if not new_url.startswith('https://'):
                new_url = SEARCH_ENGINE + new_url.replace(' ', '+')
            self.open(new_url)
        elif key in self.key_map['back'] and self.history:
            back_url = self.history.back()
            if back_url:
                self.fetch_content_async(back_url, self.on_content_fetched)
        elif key in self.key_map['open']:
            self.main_loop.widget.set_focus('header')  # Focus on URL bar
            self.main_loop.edit.set_caption('go: ')
        elif key in self.key_map['help']:
            if isinstance(self.main_loop.widget, urwid.Overlay):
                self.main_loop.widget = self.main_loop.widget[0]
            else:
                self.main_loop.widget = self.help_overlay()
        elif key in self.key_map['bookmark']:
            current_url = self.main_loop.widget.footer.original_widget.text  # Extracting the current URL from status bar
            self.bookmarks.save_bookmark(current_url)

    def link_pressed(self, button, link):
        self.history.add(link)
        self.fetch_content_async(link, self.on_content_fetched)

    def confirm_quit(self):
        # Callback when "Yes" is pressed
        def on_yes(button):
            raise urwid.ExitMainLoop()

        # Callback when "No" is pressed
        def on_no(button, widgets):
            self.main_loop.widget = widgets[0]  # Restore the original main widget

        yes_button = urwid.Button("Yes", on_press=on_yes)
        no_button = urwid.Button("No", on_press=on_no, user_data=[self.main_loop.widget])

        pile = urwid.Pile([urwid.Text("Are you sure you want to quit?"), yes_button, no_button])
        fill = urwid.Filler(pile, 'middle')
        frame = urwid.LineBox(fill, title="Confirm Quit")

        self.main_loop.widget = urwid.Overlay(frame, self.main_loop.widget, 'center', 30, 'middle', 7)

    def run(self):
        url = "https://example.com"
        palette = [
            ('status_bar', 'black', 'white'),
            ('url_bar', 'black', 'white'),
            ('link', 'yellow', 'black'),
            ('url_bar_focused', 'black', 'yellow'),
            ('text_focused', 'yellow', 'black')
        ]
        self.open(url)
        w = urwid.Filler(urwid.Text(u"Loading..."), 'top')
        self.main_loop = urwid.MainLoop(w, palette=palette, unhandled_input=lambda key: self.handle_input(key))
        self.main_loop.run()

if __name__ == "__main__":
    app = BrowserApp()
    app.run()
