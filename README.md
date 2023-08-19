# Litter

Litter is a minimalistic, terminal-based read-only browser. It allows users to
browse the web without the bloat and distractions of modern web browsers. This
project is designed for lightweight browsing and reading, with an emphasis on
the content.

![Demo](./demo.gif)


## Features:

- Terminal-based browsing for a distraction-free reading experience.
- URL navigation and search functionality using DuckDuckGo Lite by default.
- Basic navigation options like forward and backward.
- Customizable keymap to adjust the controls to your liking.
- Lightweight bookmarking system.
- Help overlay with keybindings.
- Readability integration to clean and simplify webpage content.

## Dependencies:

- `requests`: For making HTTP requests.
- `urwid`: For the terminal-based UI.
- `readability`: For cleaning and simplifying webpage content.
- `BeautifulSoup4`: For parsing HTML.

## Installation:

1. Clone the repository:

```
git clone https://github.com/tuxcanfly/litter.git
```

2. Navigate to the project directory:

```
cd litter
```

3. Install the required dependencies:

```
pip install requests urwid readability-lxml beautifulsoup4
```

## Usage:

Simply run the `litter.py` script:

```
python litter.py
```

Upon launch, the default starting page is "https://example.com". You can
navigate to different URLs, search for terms using DuckDuckGo Lite, bookmark
your favorite pages, and much more.

### Keybindings:

- `q`, `Q`, `esc`: Quit the browser.
- `i`: Jump to the URL bar.
- `enter`: Load the URL or search for a keyword.
- `backspace`: Go back to the previous page.
- `b`: Bookmark the current URL.
- `?`: Toggle help screen.

You can also customize the keybindings by modifying the `keymap.json` file.

## Customizing:

### Key Map:

The key bindings for various actions can be modified by adjusting the `keymap.json` file.

For example, to change the quit key to `ctrl q`, you can modify the file like:

```json
{
    "quit": ["ctrl q"],
    ...
}
```

### Themes:

The color scheme of the interface can be modified by adjusting the `palette` in the main function.

## Contributing:

Feel free to open issues, suggest enhancements, or submit pull requests. All contributions are welcome!

## License:

MIT

## Credits:

[Runt](https://github.com/FreeFull/runt)
