import urwid


class Hypertext(urwid.WidgetWrap):
    def __init__(self, markup, on_link_click):
        self.text = urwid.Text(markup)
        self.on_link_click = on_link_click
        self.focusable_items = self.get_focusable_items(markup)
        self.focused_item_index = 0
        super().__init__(self.text)

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

        # update the text to highlight the focused item
        focused_item = self.focusable_items[self.focused_item_index]
        new_markup = []
        for item in self.text.get_text()[0]:
            if item == focused_item:
                new_markup.append(("focused", item))
            else:
                new_markup.append(item)
        self.text.set_text(new_markup)
        self._invalidate()

    def selectable(self):
        return True


def on_link_click(link):
    print(f"Link clicked: {link}")


palette = [
    ("focused", "standout", ""),
]

markup = [
    "Here are some links:",
    "\n",
    ("https://example.com", "Example Domain"),
    "\n",
    ("https://example.org", "Example Organization"),
    "Some normal text",
    ("https://example.net", "Example Network"),
]


def main():
    urwid.MainLoop(urwid.Filler(Hypertext(markup, on_link_click)), palette).run()


if __name__ == "__main__":
    main()
