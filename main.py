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
    'open': ['i'],
    'help': ['?'],
    'bookmark': ['b']
}

BOOKMARKS_FILE = "bookmarks.txt"

def load_keymap(filename="keymap.json"):
    try:
        with open(filename, 'r') as f:
            custom_key_map = json.load(f)
        return custom_key_map
    except FileNotFoundError:
        return DEFAULT_KEY_MAP

key_map = load_keymap()

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

history = History()

def get_bookmarks():
    try:
        with open(BOOKMARKS_FILE, 'r') as f:
            return [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        with open(BOOKMARKS_FILE, 'w') as f:  # Create the file if it doesn't exist.
            pass
        return []

def save_bookmark(url):
    bookmarks = get_bookmarks()
    if url not in bookmarks:
        with open(BOOKMARKS_FILE, 'a') as f:
            f.write(url + '\n')

def help_overlay(main_widget):
    help_content = urwid.Text("\n".join(HELP_TEXT))
    help_fill = urwid.Filler(help_content, 'middle')
    help_frame = urwid.LineBox(help_fill, title="Help - Press '?' to close")
    return urwid.Overlay(help_frame, main_widget, 'center', ('relative', 30), 'middle', ('relative', 15))

def assign_loop_to_buttons(loop):
    for widget in loop.widget.body.body:
        if isinstance(widget.base_widget, urwid.Button):
            widget.base_widget._loop = loop


def fetch_and_clean_article(url):
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

def fetch_content_async(url, callback):
    def worker():
        content, links, title = fetch_and_clean_article(url)
        callback(content, links, title)
    
    thread = threading.Thread(target=worker)
    thread.start()

def on_content_fetched(content, links, title):
    global main_loop
    new_view, new_edit = article_view(content, links, title)
    main_loop.widget = new_view
    assign_loop_to_buttons(main_loop)
    main_loop.draw_screen()

def article_view(content, links, title):
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
            on_press=link_pressed,
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
    edit = urwid.Edit("Enter URL or keyword: ")
    url_bar = urwid.AttrMap(edit, 'url_bar', 'url_bar_focused')
    
    # Combine listbox, status bar, and URL bar
    layout = urwid.Frame(header=url_bar, body=listbox, footer=status_bar)
    

    return layout, edit

def handle_input(key, edit_widget, main_loop):
    global history
    if key in key_map['quit']:
        # Show the confirmation dialog
        main_loop.widget = confirm_quit(main_loop.widget)
    elif key in key_map['enter']:
        new_url = edit_widget.get_edit_text()
        if not new_url.startswith('https://'):
            new_url = SEARCH_ENGINE + new_url.replace(' ', '+')
        history.add(new_url)
        fetch_content_async(new_url, on_content_fetched)
    elif key in key_map['back'] and history:
        back_url = history.back()
        if back_url:
            fetch_content_async(back_url, on_content_fetched)
    elif key in key_map['open']:
        main_loop.widget.set_focus('header')  # Focus on URL bar
    elif key in key_map['help']:
        if isinstance(main_loop.widget, urwid.Overlay):
            main_loop.widget = main_loop.widget[0]
        else:
            main_loop.widget = help_overlay(main_loop.widget)
    elif key in key_map['bookmark']:
        current_url = main_loop.widget.footer.original_widget.text  # Extracting the current URL from status bar
        save_bookmark(current_url)

def link_pressed(button, link):
    loop = button._loop  # Retrieve the main loop reference
    history.add(link)
    fetch_content_async(link, on_content_fetched)

def confirm_quit(main_widget):
    # Callback when "Yes" is pressed
    def on_yes(button):
        raise urwid.ExitMainLoop()

    # Callback when "No" is pressed
    def on_no(button, widgets):
        main_loop.widget = widgets[0]  # Restore the original main widget

    yes_button = urwid.Button("Yes", on_press=on_yes)
    no_button = urwid.Button("No", on_press=on_no, user_data=[main_widget])

    pile = urwid.Pile([urwid.Text("Are you sure you want to quit?"), yes_button, no_button])
    fill = urwid.Filler(pile, 'middle')
    frame = urwid.LineBox(fill, title="Confirm Quit")

    return urwid.Overlay(frame, main_widget, 'center', 30, 'middle', 7)

def main():
    global main_loop
    global history

    url = "https://example.com"  # default starting page
    history.add(url)

    # Fetch initial content synchronously since it's the first load and UI is not yet running.
    content, links, title = fetch_and_clean_article(url)
    main_widget, edit_widget = article_view(content, links, title)

    palette = [
        ('status_bar', 'black', 'white'),
        ('url_bar', 'black', 'white'),
        ('link', 'yellow', 'black'),
        ('url_bar_focused', 'black', 'yellow'),
        ('text_focused', 'yellow', 'black')
    ]  # Define colors

    # Set up MainLoop
    main_loop = urwid.MainLoop(main_widget, palette=palette, unhandled_input=lambda key: handle_input(key, edit_widget, main_loop))
    assign_loop_to_buttons(main_loop)
    main_loop.run()

if __name__ == "__main__":
    main()
