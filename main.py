import requests
from readability import Document
from bs4 import BeautifulSoup
import urwid

history_stack = []
is_help_visible = False
main_widget_original = None

HELP_TEXT = [
    "q or Q or esc: Quit the browser",
    "i: Jump to the URL bar",
    "b: Bookmark current URL",
    "enter: Load the URL",
    "backspace: Go back to the previous page",
    "?: Help screen",
    # Add more keybindings here
]

BOOKMARKS_FILE = "bookmarks.txt"

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
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check for successful request
        doc = Document(response.text)
        cleaned_content = doc.summary()

        soup = BeautifulSoup(cleaned_content, 'html.parser')
        plain_text = soup.get_text()

        # Extract links and present differently
        links = []
        for a in soup.find_all('a'):
            if a['href']:
                links.append((a.text, a['href']))

        return plain_text, links
    except requests.RequestException:
        return "Error: Unable to fetch the content.", []

def article_view(url):
    article_content, links = fetch_and_clean_article(url)

    # Represent links as (URL, displayed_text)
    txt_content = []
    link_map = {}  # To store links for navigation
    for line in article_content.split('\n'):
        matching_links = [link for link in links if link[0] == line]
        if matching_links:
            displayed_text, link_url = matching_links[0]
            link_map[displayed_text] = link_url  # Map text to URL
            txt_content.append(('link', displayed_text))
        else:
            txt_content.append(line)
    
    items = [urwid.AttrMap(urwid.SelectableIcon(item, 0), None, 'text_focused') if isinstance(item, str) else urwid.AttrMap(urwid.Button(item[1], on_press=link_pressed, user_data=link_map[item[1]]), 'link', focus_map='reversed') for item in txt_content]

    walker = urwid.SimpleFocusListWalker(items)
    listbox = urwid.ListBox(walker)

    # Status bar with the current URL
    status_bar = urwid.Text(url)
    status_bar = urwid.AttrWrap(status_bar, 'status_bar')
    
    # URL bar to enter addresses
    edit = urwid.Edit("Enter URL: ")
    url_bar = urwid.AttrMap(edit, 'url_bar', 'url_bar_focused')
    
    # Combine listbox, status bar, and URL bar
    layout = urwid.Frame(header=url_bar, body=listbox, footer=status_bar)
    

    return layout, edit

def handle_input(key, edit_widget, main_loop):
    global history_stack
    global is_help_visible
    global main_widget_original
    if key in ('q', 'Q', 'esc'):
        raise urwid.ExitMainLoop()
    elif key == 'enter':
        new_url = edit_widget.get_edit_text()
        history_stack.append(new_url)  # Add the URL to history
        new_view, new_edit = article_view(new_url)
        main_loop.widget = new_view
        main_loop.user_data['edit_widget'] = new_edit
        assign_loop_to_buttons(main_loop)
    elif key == 'backspace' and history_stack:
        # Remove the current URL
        history_stack.pop()
        
        # Check if there's any URL left in the stack
        if history_stack:
            back_url = history_stack[-1]  # Peek at the top of the stack without popping
            new_view, new_edit = article_view(back_url)
            main_loop.widget = new_view
            main_loop.user_data['edit_widget'] = new_edit
            assign_loop_to_buttons(main_loop)
    elif key == 'i':
        main_loop.widget.set_focus('header')  # Focus on URL bar
    elif key == '?':
        if is_help_visible:
            main_loop.widget = main_widget_original  # Restore the original main widget
            is_help_visible = False
        else:
            main_widget_original = main_loop.widget  # Store the original main widget
            main_loop.widget = help_overlay(main_loop.widget)
            is_help_visible = True
    elif key == 'b':
        current_url = main_loop.widget.footer.original_widget.text  # Extracting the current URL from status bar
        save_bookmark(current_url)
        show_feedback(main_loop, "Bookmark saved successfully!")

def link_pressed(button, link):
    loop = button._loop  # Retrieve the main loop reference
    history_stack.append(link)  # Add the clicked link to history
    new_view, new_edit = article_view(link)
    loop.widget = new_view
    loop.user_data['edit_widget'] = new_edit

def show_feedback(main_loop, message, duration_in_seconds=2):
    original_footer = main_loop.widget.footer
    main_loop.user_data['original_footer'] = original_footer
    feedback_text = urwid.Text(message)
    feedback_bar = urwid.AttrWrap(feedback_text, 'status_bar')
    main_loop.widget.footer = feedback_bar
    main_loop.set_alarm_in(duration_in_seconds, restore_original_footer)

def restore_original_footer(main_loop, user_data):
    main_loop.widget.footer = main_loop.user_data.pop('original_footer', None)

def main():
    url = "https://example.com"  # default starting page
    history_stack.append(url)  # Add the URL to history
    main_widget, edit_widget = article_view(url)

    palette = [
        ('status_bar', 'white', 'dark blue'),
        ('url_bar', 'black', 'light gray'),
        ('link', 'yellow', 'black'),
        ('url_bar_focused', 'black', 'yellow'),
        ('text_focused', 'white', 'dark blue')
    ]  # Define colors

    # Setting up MainLoop and storing references in user_data
    loop = urwid.MainLoop(main_widget, palette=palette, unhandled_input=lambda key: handle_input(key, edit_widget, loop))
    loop.user_data = {'edit_widget': edit_widget, 'main_loop': loop}

    assign_loop_to_buttons(loop)

    loop.run()

if __name__ == "__main__":
    main()
