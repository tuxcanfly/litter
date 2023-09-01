import json
import requests
import threading
import pyperclip
import urwid
import urwid_readline

from readability import Document
from bs4 import BeautifulSoup
from urllib.parse import urljoin

"""
toy browser
"""


SEARCH_ENGINE = "https://lite.duckduckgo.com/lite?q="

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
}

HELP_TEXT = [
    ["---", "------"],
    ["key", "action"],
    ["---", "------"],
    ["q", "quit"],
    ["⏎", "open url or search keyword"],
    ["⇦", "go back to previous page"],
    ["j", "next line"],
    ["k", "previous line"],
    ["g", "goto top"],
    ["G", "goto bottom"],
    ["i", "edit url or keyword"],
    ["?", "help"],
    ["c", "copy highlighted text"],
    ["b", "bookmark page"],
]

DEFAULT_KEY_MAP = {
    "quit": ["q", "Q", "esc"],
    "enter": ["enter"],
    "back": ["backspace"],
    "next_line": ["j"],
    "prev_line": ["k"],
    "first_line": ["g"],
    "last_line": ["G"],
    "open": ["i"],
    "help": ["?"],
    "copy": ["c"],
    "bookmark": ["b"],
}

DEFAULT_REDIRECT = {
    "twitter.com": "nitter.net",
    "www.reddit.com": "teddit.pussthecat.org",
    "github.com": "gh.bloatcat.tk",
}

BOOKMARKS_FILE = "bookmarks.txt"


superscript_map = {
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
}


class ClickyText(urwid.Text):
    ignore_focus = False
    _selectable = True

    def __init__(self, text, cursor_position=0):
        self.__super.__init__(text)
        self._cursor_position = cursor_position

    def render(self, size, focus=False):
        c = self.__super.render(size, focus)
        if focus:
            c = urwid.CompositeCanvas(c)
            c.cursor = self.get_cursor_coords(size)
        return c

    def get_cursor_coords(self, size):
        (maxcol,) = size
        trans = self.get_line_translation(maxcol)
        x, y = urwid.text_layout.calc_coords(self.text, trans, self._cursor_position)
        if maxcol <= x:
            return None
        return x, y

    def keypress(self, size, key):
        return key


class History:
    def __init__(self):
        self.stack = []
        self.position = -1

    def current(self):
        if self.position != -1:
            return self.stack[self.position]
        return ""

    def add(self, url):
        self.stack = self.stack[: self.position + 1]  # Remove forward history
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
            with open(self.file, "r") as f:
                return [line.strip() for line in f.readlines()]
        except FileNotFoundError:
            with open(self.file, "w") as f:  # Create the file if it doesn't exist.
                pass
            return []

    def save_bookmark(self, url):
        bookmarks = self.get_bookmarks()
        if url not in bookmarks:
            with open(self.file, "a") as f:
                f.write(url + "\n")


class BrowserApp:
    def __init__(self):
        self.key_map = self.load_keymap()
        self.history = History()
        self.bookmarks = Bookmarks()
        self.main_loop = None

    def autocomplete(self, text, state):
        bookmarks = self.bookmarks.get_bookmarks()
        tmp = [c for c in bookmarks if c and c.find(text) != -1] if text else bookmarks
        try:
            return tmp[state]
        except (IndexError, TypeError):
            return None

    def load_keymap(self, filename="keymap.json"):
        try:
            with open(filename, "r") as f:
                custom_key_map = json.load(f)
            return custom_key_map
        except FileNotFoundError:
            return DEFAULT_KEY_MAP

    def load_redirect(self, filename="redirect.json"):
        try:
            with open(filename, "r") as f:
                custom_redirect_map = json.load(f)
            return custom_redirect_map
        except FileNotFoundError:
            return DEFAULT_REDIRECT

    def redirect(self, url):
        custom_redirect_map = self.load_redirect()
        for k, v in custom_redirect_map.items():
            if url.find(k) != -1:
                return url.replace(k, v)
        return url

    def help_overlay(self):
        help_content = [
            urwid.Columns(
                [
                    urwid.Padding(urwid.Text(cell, align="left"), width="pack")
                    for cell in row
                ]
            )
            for row in HELP_TEXT
        ]
        help_fill = urwid.Filler(urwid.Pile(help_content), "middle")
        help_frame = urwid.LineBox(help_fill, title="Help - Press '?' to close")
        return urwid.Overlay(
            help_frame,
            self.main_loop.widget,
            "center",
            ("relative", 30),
            "middle",
            ("relative", 30),
        )

    @classmethod
    def fetch_and_clean_article(self, url):
        """
        Fetch and clean article from a URL.

        :param url: URL of the article.
        :return: Tuple containing plain text of the article, links, and page title.
        """

        inline_elements = [
            "abbr",
            "acronym",
            "b",
            "bdi",
            "bdo",
            "big",
            "br",
            "button",
            "cite",
            "code",
            "data",
            "datalist",
            "dfn",
            "em",
            "i",
            "img",
            "input",
            "kbd",
            "label",
            "mark",
            "meter",
            "nobr",
            "object",
            "output",
            "q",
            "ruby",
            "rbc",
            "rb",
            "rp",
            "rt",
            "rtc",
            "s",
            "samp",
            "script",
            "select",
            "small",
            "span",
            "strong",
            "sub",
            "sup",
            "textarea",
            "time",
            "tt",
            "u",
            "var",
            "wbr",
        ]

        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()  # Check for successful request

            # Additional checks for content type
            content_type = response.headers.get("Content-Type")
            if not content_type.startswith("text"):
                return ["Error: Content type is not HTML."], [], ""

            doc = Document(response.text)
            page_title = doc.title()
            cleaned_content = doc.summary()

            soup = BeautifulSoup(cleaned_content, "html.parser")
            for tag in soup.find_all(inline_elements):
                tag.unwrap()
            soup = BeautifulSoup(str(soup), "html.parser")

            # Extract links and present differently
            links = []
            for a in soup.find_all("a"):
                href = a.get("href")
                text = a.text.strip()
                if href and text:
                    links.append((text, href))

            return soup.stripped_strings, links, page_title
        except requests.RequestException as e:
            return [f"Error: {str(e)}"], [], ""

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
        for line in content:
            matching_links = [link for link in links if link[0] == line]
            if matching_links:
                displayed_text, link_url = matching_links[0]
                if not link_url.startswith("http"):
                    link_url = urljoin(url, link_url)
                link_map[displayed_text] = link_url  # Map text to URL
                txt_content.append(("link", displayed_text))
            else:
                txt_content.append(line)
        items = [
            urwid.AttrMap(urwid.Text(item), None, "text_focused")
            if isinstance(item, str)
            else urwid.AttrMap(
                urwid.Button(
                    item[1], on_press=self.link_pressed, user_data=link_map[item[1]]
                ),
                "link",
                "link_focused",
            )
            for item in txt_content
        ]

        walker = urwid.SimpleFocusListWalker(items)
        listbox = urwid.ListBox(walker)

        # Status bar with the current page title or fallback to URL if title is not available
        status_bar_text = title
        status_bar = urwid.Text(" 🌍 " + status_bar_text)
        status_bar = urwid.AttrWrap(status_bar, "status_bar")

        help_bar_text = "? → help j/k → move i → edit ⏎ → open ⇦ → back q → quit"
        help_bar = urwid.Text(" 🔤  " + help_bar_text)
        help_bar = urwid.AttrWrap(help_bar, "help_bar")

        footer = urwid.Pile([help_bar, status_bar])

        # URL bar to enter addresses
        edit = urwid_readline.ReadlineEdit(" 🔍 " + url)
        edit.enable_autocomplete(self.autocomplete)
        url_bar = urwid.AttrMap(edit, "url_bar", "url_bar_focused")

        # Combine listbox, status bar, and URL bar
        layout = urwid.Frame(header=url_bar, body=listbox, footer=footer)

        return layout, edit

    def open(self, url):
        url = self.redirect(url)
        self.history.add(url)
        self.fetch_content_async(url, self.on_content_fetched)

    def handle_input(self, key):
        global history
        if isinstance(self.main_loop.widget, urwid.Overlay):
            if key not in self.key_map["help"]:
                return
        if key in self.key_map["quit"]:
            if self.main_loop.widget.get_focus() == "header":
                self.main_loop.widget.set_focus("body")
                return
            # Show the confirmation dialog
            self.confirm_quit()
        elif key in self.key_map["next_line"]:
            listbox = self.main_loop.widget.body
            if listbox.focus_position < len(listbox.body) - 1:
                listbox.set_focus(listbox.focus_position + 1)
        elif key in self.key_map["prev_line"]:
            listbox = self.main_loop.widget.body
            if listbox.focus_position > 0:
                listbox.set_focus(listbox.focus_position - 1)
        elif key in self.key_map["first_line"]:
            listbox = self.main_loop.widget.body
            listbox.set_focus(0)
        elif key in self.key_map["last_line"]:
            listbox = self.main_loop.widget.body
            listbox.set_focus(len(listbox.body) - 1)
        elif key in self.key_map["enter"]:
            new_url = self.main_loop.edit.get_edit_text()
            if new_url.strip():
                if not new_url.startswith("https://"):
                    new_url = SEARCH_ENGINE + new_url.replace(" ", "+")
                self.open(new_url)
        elif key in self.key_map["back"] and self.history:
            back_url = self.history.back()
            if back_url:
                self.fetch_content_async(back_url, self.on_content_fetched)
        elif key in self.key_map["open"]:
            self.main_loop.widget.set_focus("header")  # Focus on URL bar
            self.main_loop.edit.set_caption(" 👉 ")
        elif key in self.key_map["help"]:
            if isinstance(self.main_loop.widget, urwid.Overlay):
                self.main_loop.widget = self.main_loop.widget[0]
            else:
                self.main_loop.widget = self.help_overlay()
        elif key in self.key_map["bookmark"]:
            self.bookmarks.save_bookmark(self.history.current())
        elif key in self.key_map["copy"]:
            listbox = self.main_loop.widget.body
            item, _ = listbox.get_focus()
            selected_text = item.base_widget.get_text()[0]
            # Copy to clipboard
            pyperclip.copy(selected_text)

    def link_pressed(self, button, link):
        self.open(link)

    def confirm_quit(self):
        # Callback when "Yes" is pressed
        def on_yes(button):
            raise urwid.ExitMainLoop()

        # Callback when "No" is pressed
        def on_no(button, widgets):
            self.main_loop.widget = widgets[0]  # Restore the original main widget

        yes_button = urwid.Button("Yes", on_press=on_yes)
        no_button = urwid.Button(
            "No", on_press=on_no, user_data=[self.main_loop.widget]
        )

        pile = urwid.Pile(
            [urwid.Text("Are you sure you want to quit?"), yes_button, no_button]
        )
        fill = urwid.Filler(pile, "middle")
        frame = urwid.LineBox(fill, title="Confirm Quit")

        self.main_loop.widget = urwid.Overlay(
            frame, self.main_loop.widget, "center", 30, "middle", 7
        )

    def run(self):
        url = "https://simple-web.org/"
        palette = [
            ("status_bar", "black", "white"),
            ("url_bar", "black", "white"),
            ("link", "yellow", "black"),
            ("link_focused", "yellow,underline", "black"),
            ("url_bar_focused", "black", "yellow"),
            ("text_focused", "yellow", "black"),
        ]
        self.open(url)
        w = urwid.Filler(urwid.Text("Loading..."), "top")
        self.main_loop = urwid.MainLoop(
            w, palette=palette, unhandled_input=lambda key: self.handle_input(key)
        )
        self.main_loop.run()


if __name__ == "__main__":
    app = BrowserApp()
    app.run()
