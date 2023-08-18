import urwid
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

def html_to_terminal(html: str) -> str:
    # Define ANSI escape codes
    BOLD = '\033[1m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'
    
    # Replace the tags with the corresponding escape codes
    html = re.sub(r'<b>', BOLD, html)
    html = re.sub(r'</b>', RESET, html)
    html = re.sub(r'<i>', ITALIC, html)
    html = re.sub(r'</i>', RESET, html)
    html = re.sub(r'<u>', UNDERLINE, html)
    html = re.sub(r'</u>', RESET, html)
    
    # Remove any other HTML tags (for simplicity)
    html = re.sub(r'<[^>]+>', '', html)
    
    return html

def fetch_content(url: str) -> str:
    # Fetch the content
    response = requests.get(url)
    html_content = response.text
    
    # Simplify the content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove unwanted tags
    for tag in soup(['script', 'style', 'header', 'footer', 'nav']):
        tag.decompose()
    
    simplified_content = str(soup.body)
    
    return simplified_content

def extract_links_and_create_buttons(base_url: str, content: str) -> list:
    soup = BeautifulSoup(content, 'html.parser')
    buttons = []

    for link in soup.find_all('a'):
        href = link.get('href')
        text = link.get_text()

        # Convert relative URLs to absolute
        absolute_url = urljoin(base_url, href)

        if absolute_url:  # Ensure absolute_url is present
            button = urwid.Button(text, on_link_clicked, user_data=absolute_url)
            buttons.append(button)
    
    return buttons

def on_link_clicked(button, href):
    """Callback when a link button is clicked."""
    show_page(href)

def show_page(url):
    content = fetch_content(url)
    
    # Convert hyperlinks to clickable buttons
    buttons = extract_links_and_create_buttons(url, content)
    
    # Remove the old links from the display and append the new ones
    for widget in pile.contents:
        if isinstance(widget[0], urwid.Button):
            pile.contents.remove(widget)
    
    for button in buttons:
        pile.contents.append((button, pile.options()))
    
    # Convert other content to terminal displayable format
    content = re.sub(r'<a href="(.*?)">(.*?)</a>', '', content)
    text_content = html_to_terminal(content)
    
    response.set_text(('I say', text_content))

def on_ask_change(edit, new_edit_text):
    """Callback when the input field is edited."""
    response.set_text(('I say', f"Ready to fetch: {new_edit_text}"))

def on_exit_clicked(button):
    raise urwid.ExitMainLoop()

def on_go_clicked(button, user_data):
    """Callback when the Go button is clicked."""
    user_input = user_data[0].get_edit_text()
    show_page(user_input)

# UI Widgets
ask = urwid.Edit('Enter the URL: ', '')
response = urwid.Text(u'')
go_button = urwid.Button(u'Go', on_go_clicked, user_data=[ask])
exit_button = urwid.Button(u'Exit', on_exit_clicked)
pile = urwid.Pile([ask, go_button, response, exit_button])
fill = urwid.Filler(pile, 'top')

if __name__ == "__main__":
    loop = urwid.MainLoop(fill)
    loop.run()
