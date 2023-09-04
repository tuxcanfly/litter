import re
import json
import requests
import threading
import pyperclip
import urwid
import urwid_readline

from readability import Document
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import urljoin

"""
toy browser
"""

BULLET = "•"

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


class TextWithLinks(urwid.WidgetWrap):
    def __init__(self, markup, on_link_click):
        self.markup = markup
        self.on_link_click = on_link_click
        self.text = urwid.Text(markup)
        self.focused_item_index = 0
        self.focusable_items = self.get_focusable_items(markup)
        self.update_focus(markup)
        super().__init__(self.text)

    def update_focus(self, markup):
        rewrite = []
        index = 0
        for item in markup:
            if isinstance(item, tuple) and item[0].startswith("http"):
                if index == self.focused_item_index:
                    rewrite.append(
                        ("link_focused", f"{item[1]} {superscript_map[str(index+1)]}")
                    )
                else:
                    rewrite.append(
                        ("link", f"{item[1]} {superscript_map[str(index+1)]}")
                    )
                index += 1
            else:
                rewrite.append(item)
        self.text.set_text(rewrite)

    def get_focusable_items(self, markup):
        return [
            item
            for item in markup
            if isinstance(item, tuple) and item[0].startswith("http")
        ]

    def keypress(self, size, key):
        max_position = len(self.focusable_items) - 1
        if key == "up" or key == "left":
            self.focused_item_index = max(0, self.focused_item_index - 1)
        elif key == "down" or key == "right":
            self.focused_item_index = min(max_position, self.focused_item_index + 1)
        elif key == "enter":
            self.on_link_click(self.focusable_items[self.focused_item_index][0])
        else:
            return key
        self.update_focus(self.markup)

    def selectable(self):
        return True


class Hyperlink(urwid.SelectableIcon):
    def __init__(self, text, uri, on_enter):
        self.uri = uri
        self.on_enter = on_enter
        super().__init__(text)

    def keypress(self, size, key):
        if key == "enter":
            self.on_enter(self.uri)
        else:
            return key


class HTMLFlow(urwid.GridFlow):
    def generate_display_widget(self, size: tuple[int]) -> urwid.Divider | urwid.Pile:
        """
        Actually generate display widget (ignoring cache)
        """
        (maxcol,) = size
        divider = urwid.Divider()
        if not self.contents:
            return divider

        if self.v_sep > 1:
            # increase size of divider
            divider.top = self.v_sep - 1

        c = None
        p = urwid.Pile([])
        used_space = 0

        for i, (w, (width_type, width_amount)) in enumerate(self.contents):
            width_amount = len(w.text)
            if c is None or maxcol - used_space < width_amount:
                # starting a new row
                if self.v_sep:
                    p.contents.append((divider, p.options()))
                c = urwid.Columns([], self.h_sep)
                column_focused = False
                pad = urwid.Padding(c, self.align)
                # extra attribute to reference contents position
                pad.first_position = i
                p.contents.append((pad, p.options()))

            c.contents.append((w, c.options(urwid.GIVEN, width_amount)))
            if (i == self.focus_position) or (not column_focused and w.selectable()):
                c.focus_position = len(c.contents) - 1
                column_focused = True
            if i == self.focus_position:
                p.focus_position = len(p.contents) - 1
            used_space = sum(x[1][1] for x in c.contents) + self.h_sep * len(c.contents)
            if width_amount > maxcol:
                # special case: display is too narrow for the given
                # width so we remove the Columns for better behaviour
                # FIXME: determine why this is necessary
                pad.original_widget = w
            pad.width = used_space - self.h_sep

        if self.v_sep:
            # remove first divider
            del p.contents[:1]
        else:
            # Ensure p __selectable is updated
            p._contents_modified()

        return p


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
    def html_to_urwid(self, element):
        element_text = re.sub(r"\n\s*", r" ", str(element.string))

        if element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            return urwid.Text(("bold", element_text))

        elif element.name == "p":
            children = [
                self.html_to_urwid(child) for child in element.children if child != "\n"
            ]
            return urwid.LineBox(HTMLFlow(children, 256, 1, 1, "left"))

        elif element.name == "div":
            children = [
                self.html_to_urwid(child) for child in element.children if child != "\n"
            ]
            return urwid.Pile(children)

        elif element.name == "br":
            return urwid.Divider()

        elif element.name == "center":
            # As terminal doesn't really support centering,
            # you might want to just pass the children through unchanged or
            # add some sort of separator or visual cue
            return self.html_to_urwid(element.contents[0])

        elif element.name == "em":
            return urwid.Text(("italic", element_text))

        elif element.name == "code":
            return urwid.AttrWrap(urwid.Text(element_text), "code_style")

        elif element.name == "details":
            summary = element.find("summary")
            summary_text = summary.get_text().strip() if summary else "Details"
            details_content = [
                self.html_to_urwid(child)
                for child in element.children
                if child.name != "summary" and child != "\n"
            ]
            # This is a basic representation; real interaction requires more logic
            return urwid.Pile([urwid.Text(summary_text), urwid.Pile(details_content)])

        elif element.name == "label":
            return urwid.Text(element_text)

        elif element.name == "ul":
            list_items = []
            for idx, li in enumerate(element.children):
                if isinstance(li, Tag):
                    list_items.append(urwid.Text(BULLET + " " + li.get_text().strip()))
            return urwid.Pile(list_items)

        elif element.name == "li":
            list_items = []
            for idx, li in enumerate(element.children):
                if isinstance(li, Tag):
                    list_items.append(
                        urwid.Text("{}. ".format(idx + 1) + " " + li.get_text().strip())
                    )
            return urwid.Pile(list_items)

        elif element.name == "a":
            if element_text:
                return urwid.AttrWrap(
                    Hyperlink(
                        element_text, element.get("href", "#"), self.link_pressed
                    ),
                    "link",
                    "link_focused",
                )

        elif element.name == "span":
            children = [
                self.html_to_urwid(child) for child in element.children if child != "\n"
            ]
            return urwid.Columns([child for child in children if child])

        elif element.name == "strong":
            return urwid.Text(("bold", element_text))

        elif element.name == "img":
            # Since we can't display images in terminal, you might want to show the alt text if available
            alt_text = element.get("alt", "[Image]")
            if alt_text:
                return urwid.Text(alt_text)
            return None

        elif element.name == "abbr":
            # Using underline for abbreviation
            return urwid.Text(("underline", element_text))

        elif element.name == "form":
            # This would simply list out children, more complex interaction would need more work
            children = [
                self.html_to_urwid(child) for child in element.children if child != "\n"
            ]
            return urwid.Pile([child for child in children if child])

        elif element.name == "noscript":
            # Since we don't run scripts in terminal, always showing noscript content
            return self.html_to_urwid(element.contents[0])

        elif element.name == "button":
            # A basic button representation, more interaction would need more work
            return urwid.AttrWrap(urwid.Text(element_text), "button")

        elif element.name == "table":
            children = [
                self.html_to_urwid(child) for child in element.children if child != "\n"
            ]
            return urwid.Pile(children)

        elif element.name == "hr":
            return urwid.Divider(div_char="━")

        elif element.name == "input":
            # Simply create a basic text edit box for now.
            return urwid.Edit()

        elif isinstance(element, NavigableString):
            return urwid.Text(element_text, align="left")

        elif element.name in ["footer", "main", "header", "nav"]:
            # Treating these like divs for simplicity
            children = [
                self.html_to_urwid(child) for child in element.children if child != "\n"
            ]
            return urwid.LineBox(urwid.GridFlow(children, 256, 1, 1, "left"))

        elif element.name in ["script", "style", "meta", "style"]:
            return None

        else:
            children = [
                self.html_to_urwid(child) for child in element.children if child != "\n"
            ]
            return urwid.Pile([child for child in children if child])

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
            content_type = response.headers.get("Content-Type")
            if not content_type.startswith("text"):
                return ["Error: Content type is not HTML."], [], ""

            doc = Document(response.text)
            page_title = doc.title()
            cleaned_content = doc.summary()

            soup = BeautifulSoup(response.text, "html.parser")
            widgets = self.html_to_urwid(soup.body)

            return widgets, [], page_title
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

    def article_view(self, url, widgets, links, title):
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
        layout = urwid.Frame(
            header=url_bar, body=urwid.Filler(widgets, valign="top"), footer=footer
        )

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

    def link_pressed(self, link):
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
            ("link", "dark blue,underline", ""),
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
