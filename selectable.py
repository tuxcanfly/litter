import urwid
import typing


class TextWithLinks(urwid.WidgetWrap):
    def __init__(self, markup, on_link_click):
        self.on_link_click = on_link_click
        self.focusable_items = self.get_focusable_items(markup)
        self.focused_item_index = 0
        markup = self.get_markup_rewrite(markup)
        self.text = urwid.Text(markup)
        super().__init__(self.text)

    def get_markup_rewrite(self, markup):
        return [
            ("link", item[1])
            if isinstance(item, tuple) and item[0].startswith("http")
            else item
            for item in markup
        ]

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
        self._invalidate()

    def selectable(self):
        return True


palette = [
    ("link", "underline", ""),
    ("link_focused", "yellow", "black"),
]

markup = [
    "I am Thejaswi Puthraya, the owner of this ",
    ("http://thejaswi.info/", "website ¹"),
    " and a freelance software developer. I was born in ",
    ("https://en.wikipedia.org/wiki/Hyderabad", "Hyderabad ²"),
    " the city of pearls and the capital of Telangana, India. Ever since I have been living in this city famous for ",
    ("italics", "Irani Chai and"),
    ("italics", " Chalta Hai"),
    " attitude.",
]


def on_link_click(link):
    print(f"Link clicked: {link}")


txt = TextWithLinks(markup, on_link_click)
fill = urwid.Filler(txt, valign="top")
loop = urwid.MainLoop(urwid.Padding(fill, left=2, right=2), palette)
loop.run()
