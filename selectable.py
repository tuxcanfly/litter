import urwid
import typing


from typing_extensions import Literal


class HyperText(urwid.Widget):
    """
    a horizontally resizeable text widget
    """

    _sizing = frozenset([urwid.FLOW])

    ignore_focus = True
    _repr_content_length_max = 140

    def __init__(
        self,
        markup,
        align: Literal["left", "center", "right"] = urwid.LEFT,
        wrap: Literal["space", "any", "clip", "ellipsis"] = urwid.SPACE,
        layout=None,
    ) -> None:
        """
        :param markup: content of text widget, one of:

            bytes or unicode
              text to be displayed

            (*display attribute*, *text markup*)
              *text markup* with *display attribute* applied to all parts
              of *text markup* with no display attribute already applied

            [*text markup*, *text markup*, ... ]
              all *text markup* in the list joined together

        :type markup: :ref:`text-markup`
        :param align: typically ``'left'``, ``'center'`` or ``'right'``
        :type align: text alignment mode
        :param wrap: typically ``'space'``, ``'any'``, ``'clip'`` or ``'ellipsis'``
        :type wrap: text wrapping mode
        :param layout: defaults to a shared :class:`StandardTextLayout` instance
        :type layout: text layout instance

        >>> Text(u"Hello")
        <Text flow widget 'Hello'>
        >>> t = Text(('bold', u"stuff"), 'right', 'any')
        >>> t
        <Text flow widget 'stuff' align='right' wrap='any'>
        >>> print(t.text)
        stuff
        >>> t.attrib
        [('bold', 5)]
        """
        super().__init__()
        self._cache_maxcol = None
        self.set_text(markup)
        self.set_layout(align, wrap, layout)

    def _repr_words(self):
        """
        Show the text in the repr in python3 format (b prefix for byte
        strings) and truncate if it's too long
        """
        first = super()._repr_words()
        text = self.get_text()[0]
        rest = repr(text)
        if len(rest) > self._repr_content_length_max:
            rest = (
                rest[: self._repr_content_length_max * 2 // 3 - 3]
                + "..."
                + rest[-self._repr_content_length_max // 3 :]
            )
        return first + [rest]

    def _repr_attrs(self):
        attrs = dict(
            super()._repr_attrs(), align=self._align_mode, wrap=self._wrap_mode
        )
        return remove_defaults(attrs, Text.__init__)

    def _invalidate(self) -> None:
        self._cache_maxcol = None
        super()._invalidate()

    def set_text(self, markup):
        """
        Set content of text widget.

        :param markup: see :class:`Text` for description.
        :type markup: text markup

        >>> t = Text(u"foo")
        >>> print(t.text)
        foo
        >>> t.set_text(u"bar")
        >>> print(t.text)
        bar
        >>> t.text = u"baz"  # not supported because text stores text but set_text() takes markup
        Traceback (most recent call last):
        AttributeError: can't set attribute
        """
        self._text, self._attrib = urwid.decompose_tagmarkup(markup)
        self._invalidate()

    def get_text(self):
        """
        :returns: (*text*, *display attributes*)

            *text*
              complete bytes/unicode content of text widget

            *display attributes*
              run length encoded display attributes for *text*, eg.
              ``[('attr1', 10), ('attr2', 5)]``

        >>> Text(u"Hello").get_text() # ... = u in Python 2
        (...'Hello', [])
        >>> Text(('bright', u"Headline")).get_text()
        (...'Headline', [('bright', 8)])
        >>> Text([('a', u"one"), u"two", ('b', u"three")]).get_text()
        (...'onetwothree', [('a', 3), (None, 3), ('b', 5)])
        """
        return self._text, self._attrib

    @property
    def text(self) -> str:
        """
        Read-only property returning the complete bytes/unicode content
        of this widget
        """
        return self.get_text()[0]

    @property
    def attrib(self):
        """
        Read-only property returning the run-length encoded display
        attributes of this widget
        """
        return self.get_text()[1]

    def set_align_mode(self, mode: Literal["left", "center", "right"]):
        """
        Set text alignment mode. Supported modes depend on text layout
        object in use but defaults to a :class:`StandardTextLayout` instance

        :param mode: typically ``'left'``, ``'center'`` or ``'right'``
        :type mode: text alignment mode

        >>> t = Text(u"word")
        >>> t.set_align_mode('right')
        >>> t.align
        'right'
        >>> t.render((10,)).text # ... = b in Python 3
        [...'      word']
        >>> t.align = 'center'
        >>> t.render((10,)).text
        [...'   word   ']
        >>> t.align = 'somewhere'
        Traceback (most recent call last):
        TextError: Alignment mode 'somewhere' not supported.
        """
        if not self.layout.supports_align_mode(mode):
            raise TextError(f"Alignment mode {mode!r} not supported.")
        self._align_mode = mode
        self._invalidate()

    def set_wrap_mode(self, mode: Literal["space", "any", "clip", "ellipsis"]):
        """
        Set text wrapping mode. Supported modes depend on text layout
        object in use but defaults to a :class:`StandardTextLayout` instance

        :param mode: typically ``'space'``, ``'any'``, ``'clip'`` or ``'ellipsis'``
        :type mode: text wrapping mode

        >>> t = Text(u"some words")
        >>> t.render((6,)).text # ... = b in Python 3
        [...'some  ', ...'words ']
        >>> t.set_wrap_mode('clip')
        >>> t.wrap
        'clip'
        >>> t.render((6,)).text
        [...'some w']
        >>> t.wrap = 'any'  # Urwid 0.9.9 or later
        >>> t.render((6,)).text
        [...'some w', ...'ords  ']
        >>> t.wrap = 'somehow'
        Traceback (most recent call last):
        TextError: Wrap mode 'somehow' not supported.
        """
        if not self.layout.supports_wrap_mode(mode):
            raise TextError(f"Wrap mode {mode!r} not supported.")
        self._wrap_mode = mode
        self._invalidate()

    def set_layout(
        self,
        align: Literal["left", "center", "right"],
        wrap: Literal["space", "any", "clip", "ellipsis"],
        layout=None,
    ):
        """
        Set the text layout object, alignment and wrapping modes at
        the same time.

        :type align: text alignment mode
        :param wrap: typically 'space', 'any', 'clip' or 'ellipsis'
        :type wrap: text wrapping mode
        :param layout: defaults to a shared :class:`StandardTextLayout` instance
        :type layout: text layout instance

        >>> t = Text(u"hi")
        >>> t.set_layout('right', 'clip')
        >>> t
        <Text flow widget 'hi' align='right' wrap='clip'>
        """
        if layout is None:
            layout = text_layout.default_layout
        self._layout = layout
        self.set_align_mode(align)
        self.set_wrap_mode(wrap)

    align = property(lambda self: self._align_mode, set_align_mode)
    wrap = property(lambda self: self._wrap_mode, set_wrap_mode)

    @property
    def layout(self):
        return self._layout

    def render(self, size: tuple[int], focus: bool = False) -> urwid.TextCanvas:
        """
        Render contents with wrapping and alignment.  Return canvas.

        See :meth:`Widget.render` for parameter details.

        >>> Text(u"important things").render((18,)).text # ... = b in Python 3
        [...'important things  ']
        >>> Text(u"important things").render((11,)).text
        [...'important  ', ...'things     ']
        """
        (maxcol,) = size
        text, attr = self.get_text()
        # assert isinstance(text, unicode)
        trans = self.get_line_translation(maxcol, (text, attr))
        return apply_text_layout(text, attr, trans, maxcol)

    def rows(self, size: tuple[int], focus: bool = False) -> int:
        """
        Return the number of rows the rendered text requires.

        See :meth:`Widget.rows` for parameter details.

        >>> Text(u"important things").rows((18,))
        1
        >>> Text(u"important things").rows((11,))
        2
        """
        (maxcol,) = size
        return len(self.get_line_translation(maxcol))

    def get_line_translation(self, maxcol: int, ta=None):
        """
        Return layout structure used to map self.text to a canvas.
        This method is used internally, but may be useful for
        debugging custom layout classes.

        :param maxcol: columns available for display
        :type maxcol: int
        :param ta: ``None`` or the (*text*, *display attributes*) tuple
                   returned from :meth:`.get_text`
        :type ta: text and display attributes
        """
        if not self._cache_maxcol or self._cache_maxcol != maxcol:
            self._update_cache_translation(maxcol, ta)
        return self._cache_translation

    def _update_cache_translation(self, maxcol: int, ta):
        if ta:
            text, attr = ta
        else:
            text, attr = self.get_text()
        self._cache_maxcol = maxcol
        self._cache_translation = self.layout.layout(
            text, maxcol, self._align_mode, self._wrap_mode
        )

    def pack(
        self, size: tuple[int] | None = None, focus: bool = False
    ) -> tuple[int, int]:
        """
        Return the number of screen columns and rows required for
        this Text widget to be displayed without wrapping or
        clipping, as a single element tuple.

        :param size: ``None`` for unlimited screen columns or (*maxcol*,) to
                     specify a maximum column size
        :type size: widget size

        >>> Text(u"important things").pack()
        (16, 1)
        >>> Text(u"important things").pack((15,))
        (9, 2)
        >>> Text(u"important things").pack((8,))
        (8, 2)
        """
        text, attr = self.get_text()

        if size is not None:
            (maxcol,) = size
            if not hasattr(self.layout, "pack"):
                return size
            trans = self.get_line_translation(maxcol, (text, attr))
            cols = self.layout.pack(maxcol, trans)
            return (cols, len(trans))

        i = 0
        cols = 0
        while i < len(text):
            j = text.find("\n", i)
            if j == -1:
                j = len(text)
            c = calc_width(text, i, j)
            if c > cols:
                cols = c
            i = j + 1
        return (cols, text.count("\n") + 1)


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
            if c is None or maxcol - used_space < len(w.text):
                # starting a new row
                if self.v_sep:
                    p.contents.append((divider, p.options()))
                c = urwid.Columns([], self.h_sep)
                column_focused = False
                pad = urwid.Padding(c, self.align)
                # extra attribute to reference contents position
                pad.first_position = i
                p.contents.append((pad, p.options()))

            c.contents.append((w, c.options(urwid.GIVEN, len(w.text))))
            if (i == self.focus_position) or (not column_focused and w.selectable()):
                c.focus_position = len(c.contents) - 1
                column_focused = True
            if i == self.focus_position:
                p.focus_position = len(p.contents) - 1
            used_space = sum(x[1][1] for x in c.contents) + self.h_sep * len(c.contents)
            if len(w.text) > maxcol:
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


class Hyperlink(urwid.WidgetWrap):
    def __init__(self, text, url):
        super().__init__(urwid.AttrMap(urwid.Text(text), None, "link"))
        self.url = url

    @property
    def text(self):
        return self._w.original_widget.text

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == "enter":
            pass
        else:
            return key


class TextWithLinks(urwid.WidgetWrap):
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


palette = [
    ("link", "underline", ""),
    ("link", "yellow", "black"),
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
