import requests
from readability import Document
from bs4 import BeautifulSoup
import urwid

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
    
    items = [urwid.Text(item) if isinstance(item, str) else urwid.AttrMap(urwid.Button(item[1], on_press=link_pressed, user_data=link_map[item[1]]), 'link', focus_map='reversed') for item in txt_content]

    walker = urwid.SimpleFocusListWalker(items)
    listbox = urwid.ListBox(walker)

    # Status bar with the current URL
    status_bar = urwid.Text(url)
    status_bar = urwid.AttrWrap(status_bar, 'status_bar')
    
    # URL bar to enter addresses
    edit = urwid.Edit("Enter URL: ")
    url_bar = urwid.AttrWrap(edit, 'url_bar')
    
    # Combine listbox, status bar, and URL bar
    layout = urwid.Frame(header=url_bar, body=listbox, footer=status_bar)
    

    return layout, edit

history_stack = []

def handle_input(key, edit_widget, main_loop):
    global history_stack
    if key in ('q', 'Q', 'esc'):
        raise urwid.ExitMainLoop()
    elif key == 'enter':
        new_url = edit_widget.get_edit_text()
        history_stack.append(new_url)  # Add the URL to history
        new_view, new_edit = article_view(new_url)
        main_loop.widget = new_view
        main_loop.user_data['edit_widget'] = new_edit
    elif key == 'b' and history_stack:
        # Remove the current URL
        history_stack.pop()
        
        # Check if there's any URL left in the stack
        if history_stack:
            back_url = history_stack[-1]  # Peek at the top of the stack without popping
            new_view, new_edit = article_view(back_url)
            main_loop.widget = new_view
            main_loop.user_data['edit_widget'] = new_edit
            assign_loop_to_buttons(main_loop)

def link_pressed(button, link):
    loop = button._loop  # Retrieve the main loop reference
    history_stack.append(link)  # Add the clicked link to history
    new_view, new_edit = article_view(link)
    loop.widget = new_view
    loop.user_data['edit_widget'] = new_edit

def main():
    url = "https://thejaswi.info"  # default starting page
    history_stack.append(url)  # Add the URL to history
    main_widget, edit_widget = article_view(url)

    palette = [
        ('status_bar', 'white', 'dark blue'),
        ('url_bar', 'black', 'light gray'),
        ('link', 'yellow', 'black')
    ]  # Define colors

    # Setting up MainLoop and storing references in user_data
    loop = urwid.MainLoop(main_widget, palette=palette, unhandled_input=lambda key: handle_input(key, edit_widget, loop))
    loop.user_data = {'edit_widget': edit_widget, 'main_loop': loop}

    assign_loop_to_buttons(loop)

    loop.run()

if __name__ == "__main__":
    main()
