"""The status item and the menu it drops down.

Every number shown is read from a Session as the menu opens and again while it
stays open, so the interface holds no count of its own. Nothing here knows
about audio: starting, stopping
and reading authorization are callables handed in, which is what lets the same
interface run against canned text with no microphone.

The first half of the module takes a Session and returns strings, and is
tested. The half below it builds AppKit objects from those strings.

docs/design-decisions.md carries the reasoning behind this design.
"""

import AppKit
import Foundation
import dispatch

APP_NAME = "Verbal Habits"

TRANSCRIBING_TITLE = "Listening…"

IDLE_HEADER = "Tracked Words"
TRANSCRIBING_HEADER = "Transcribing…"
TRACKING_HEADER = "Tracking"
SUMMARY_HEADER = "Session Summary"
ERROR_HEADER = "Recognition Stopped"

# The states audio.py reports, copied here so this module imports no Apple
# speech framework. A test holds the 2 sets together. The app prompts for an
# undetermined state, so only these 3 appear in the menu.
AUTHORIZED = "authorized"
DENIED = "denied"
RESTRICTED = "restricted"

MICROPHONE = "microphone"
SPEECH_RECOGNITION = "speech recognition"


def refused_permissions(state, mic_state, speech_state):
    """Which of the 2 permissions is in the reported state."""
    refused = []
    if mic_state == state:
        refused.append(MICROPHONE)
    if speech_state == state:
        refused.append(SPEECH_RECOGNITION)
    return refused


def authorization_lines(state, mic_state, speech_state, bundled=True):
    """The header and body shown in place of a session, naming the permissions
    that are in the reported state.
    """
    refused = refused_permissions(state, mic_state, speech_state)
    if state == DENIED:
        named = " and ".join(name.title() for name in refused)
        if bundled:
            body = f"{APP_NAME} needs {named} access."
        else:
            body = f"Turn on {named} for the app you launched {APP_NAME} from."
        return ("Access denied", (body,))
    named = " and ".join(refused)
    return ("Access restricted", (f"This Mac does not allow {named} access.",))


def has_run(session):
    """Whether a session has ever been started.

    Elapsed time is 0 until the first start, and a stop freezes it above 0.
    """
    return session.elapsed_seconds > 0


def status_title(session):
    """What the menu bar item shows beside its symbol."""
    if not session.is_active:
        return ""
    if session.segments_counted == 0:
        return TRANSCRIBING_TITLE
    return str(session.total_tracked_count)


def menu_header(session, errored=False):
    """The line above the word rows.

    A running session reads as transcribing until its first segment commits,
    and as tracking from then on.
    """
    if errored:
        return ERROR_HEADER
    if session.is_active:
        if session.segments_counted == 0:
            return TRANSCRIBING_HEADER
        return TRACKING_HEADER
    if has_run(session):
        return SUMMARY_HEADER
    return IDLE_HEADER


def word_rows(session, ordered_by_count=False):
    """Every tracked entry with its count, as (entry, count) pairs.

    Rows hold the order of the tracked list while a session runs so that no row
    moves under a reader, and sort by count once it stops.

    Words sharing a count come out in the order the tracked list gives them,
    since the count is the whole sort key and `list.sort` leaves equal items
    where they are.
    """
    rows = list(session.counts.items())
    if ordered_by_count:
        rows.sort(key=lambda row: row[1], reverse=True)
    return rows


def elapsed_text(seconds):
    """Elapsed time as minutes and seconds."""
    whole = int(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def totals_lines(session):
    return (
        f"{session.total_tracked_count} of {session.total_word_count}"
        f" words tracked ({session.tracked_percentage:.1f}%)",
        f"{elapsed_text(session.elapsed_seconds)} elapsed",
    )


# --- AppKit below this line --------------------------------------------------

SYMBOL_NAME = "mic"
SYMBOL_FALLBACK = "🎙"
MENU_MINIMUM_WIDTH_POINTS = 220.0
MENU_REDRAW_SECONDS = 1.0
ITEM_INSET_POINTS = 14.0  # left and right margin on an item
ITEM_PADDING_POINTS = 3.0  # above and below the text
COUNT_COLUMN_POINTS = 44.0  # column a count is right-aligned in
COUNT_GAP_POINTS = 16.0  # between the widest word and that column
WRAP_WIDTH_POINTS = 260.0  # text width given to a wrapping label
UNBOUNDED_HEIGHT_POINTS = 10000.0  # max height for sizeThatFits_, never reached
PRIVACY_SETTINGS_URLS = {
    MICROPHONE: (
        "x-apple.systempreferences:" "com.apple.preference.security?Privacy_Microphone"
    ),
    SPEECH_RECOGNITION: (
        "x-apple.systempreferences:"
        "com.apple.preference.security?Privacy_SpeechRecognition"
    ),
}


def on_main(work):
    """Run work on the main thread."""
    dispatch.dispatch_async(dispatch.dispatch_get_main_queue(), work)


def _attributed(text, attributes):
    return Foundation.NSAttributedString.alloc().initWithString_attributes_(
        text, attributes
    )


def _word_title(text):
    """The word half of a word row."""
    return _attributed(
        text,
        {
            AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(
                AppKit.NSFont.systemFontSize()
            ),
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.labelColor(),
        },
    )


def _count_title(count):
    """The count half of a word row, in the monospaced-digit system font."""
    return _attributed(
        str(count),
        {
            AppKit.NSFontAttributeName: (
                AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(
                    AppKit.NSFont.systemFontSize(), AppKit.NSFontWeightRegular
                )
            ),
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.labelColor(),
        },
    )


def _totals_title(text):
    """One of the total lines below the word rows."""
    return _attributed(
        text,
        {
            AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(
                AppKit.NSFont.smallSystemFontSize()
            ),
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.labelColor(),
        },
    )


def _muted_title(text):
    """A refusal's explanation."""
    return _attributed(
        text,
        {
            AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(
                AppKit.NSFont.smallSystemFontSize()
            ),
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.secondaryLabelColor(),
        },
    )


def _header_title(text):
    """The header above the word rows.

    `sectionHeaderWithTitle:` requires Sonoma; the target is macOS 13.
    """
    return _attributed(
        text,
        {
            AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_weight_(
                AppKit.NSFont.smallSystemFontSize(), AppKit.NSFontWeightSemibold
            ),
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.secondaryLabelColor(),
        },
    )


def _label(attributed):
    """A label sized to the text it is given."""
    label = AppKit.NSTextField.labelWithAttributedString_(attributed)
    label.sizeToFit()
    return label


def _holder(width, height):
    """The view an item is drawn by."""
    return AppKit.NSView.alloc().initWithFrame_(
        Foundation.NSMakeRect(0.0, 0.0, width, height)
    )


def text_width(attributed):
    """How wide the text runs when nothing wraps it."""
    return attributed.size().width


def item_width(content_width):
    """How wide an item runs once its text is inset on both sides."""
    return max(MENU_MINIMUM_WIDTH_POINTS, 2 * ITEM_INSET_POINTS + content_width)


def row_width(entries):
    """How wide a word row runs: the widest word, plus its count column."""
    widest = max((text_width(_word_title(entry)) for entry in entries), default=0.0)
    return item_width(widest + COUNT_GAP_POINTS + COUNT_COLUMN_POINTS)


def _note_view(attributed, width):
    """One menu item's text, drawn by a view so AppKit cannot dim it."""
    label = _label(attributed)
    text_height = label.frame().size.height
    # The label runs the whole item rather than the text it was built with,
    # since the totals and the header are rewritten while the menu is open and
    # a frame fitted to the first text would clip a longer one.
    label.setFrame_(
        Foundation.NSMakeRect(
            ITEM_INSET_POINTS,
            ITEM_PADDING_POINTS,
            width - 2 * ITEM_INSET_POINTS,
            text_height,
        )
    )

    holder = _holder(width, text_height + 2 * ITEM_PADDING_POINTS)
    holder.addSubview_(label)
    return holder


def _wrapped_view(attributed, width):
    """A sentence, run onto as many lines as it takes at this width."""
    label = AppKit.NSTextField.labelWithAttributedString_(attributed)
    label.setLineBreakMode_(AppKit.NSLineBreakByWordWrapping)
    label.setMaximumNumberOfLines_(0)

    text = width - 2 * ITEM_INSET_POINTS
    height = label.sizeThatFits_(
        Foundation.NSMakeSize(text, UNBOUNDED_HEIGHT_POINTS)
    ).height
    label.setFrame_(
        Foundation.NSMakeRect(ITEM_INSET_POINTS, ITEM_PADDING_POINTS, text, height)
    )

    holder = _holder(width, height + 2 * ITEM_PADDING_POINTS)
    holder.addSubview_(label)
    return holder


def _row_view(entry, count, width):
    """A tracked word on the left and its count in a column on the right."""
    word = _label(_word_title(entry))
    text_height = word.frame().size.height
    word.setFrameOrigin_(Foundation.NSMakePoint(ITEM_INSET_POINTS, ITEM_PADDING_POINTS))

    number = _label(_count_title(count))
    number.setAlignment_(AppKit.NSTextAlignmentRight)
    number.setFrame_(
        Foundation.NSMakeRect(
            width - ITEM_INSET_POINTS - COUNT_COLUMN_POINTS,
            ITEM_PADDING_POINTS,
            COUNT_COLUMN_POINTS,
            text_height,
        )
    )

    holder = _holder(width, text_height + 2 * ITEM_PADDING_POINTS)
    holder.addSubview_(word)
    holder.addSubview_(number)
    return holder


def _set_item_text(item, attributed, index=0):
    """Write text onto one of an item's labels, leaving it alone when nothing
    changed.

    A word row carries its word at 0 and its count at 1; every other item
    carries its only label at 0.
    """
    label = item.view().subviews()[index]
    if label.attributedStringValue().string() == attributed.string():
        return
    label.setAttributedStringValue_(attributed)


def running_bundled():
    """Whether this code is running inside its own application bundle.

    Unbundled, the main bundle is the interpreter's, and the permission a
    refusal names belongs to whichever app launched it.
    """
    name = Foundation.NSBundle.mainBundle().objectForInfoDictionaryKey_("CFBundleName")
    return name == APP_NAME


class _Responder(AppKit.NSObject):
    """Receives the menu's delegate messages and its clicks."""

    def menuNeedsUpdate_(self, menu):
        self.owner.rebuild(menu)

    def menuWillOpen_(self, menu):
        self.owner.menu_opened()

    def menuDidClose_(self, menu):
        self.owner.menu_closed()

    def start_(self, sender):
        self.owner.start()

    def stop_(self, sender):
        self.owner.stop()

    def openMicrophoneSettings_(self, sender):
        self.owner.open_settings(MICROPHONE)

    def openSpeechSettings_(self, sender):
        self.owner.open_settings(SPEECH_RECOGNITION)

    def quit_(self, sender):
        AppKit.NSApp().terminate_(None)


class MenuBarApp:
    """The status item, its menu, and the actions that drive one session.

    `on_start` is called when Start is chosen and returns the authorization
    state it found; the session begins only when that state is "authorized".
    `on_stop` is called after a stop is confirmed. `read_authorization` is
    called as the menu opens and returns the reported state together with the
    microphone's and speech recognition's own, which is what lets a refusal
    name the permission it is about.
    """

    def __init__(self, session, on_start, on_stop, read_authorization):
        self._session = session
        self._on_start = on_start
        self._on_stop = on_stop
        self._read_authorization = read_authorization
        self._error = None
        self._live = None
        self._menu_timer = None

        # Before any other AppKit object: spike 3 records the CGSConnectionByID
        # assertion that follows otherwise.
        self._app = AppKit.NSApplication.sharedApplication()
        self._app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        self._responder = _Responder.alloc().init()
        self._responder.owner = self

        self._status_item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
            AppKit.NSVariableStatusItemLength
        )
        self._symbol = (
            AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                SYMBOL_NAME, "Verbal Habits"
            )
        )
        if self._symbol is not None:
            self._symbol.setTemplate_(True)
            self._status_item.button().setImage_(self._symbol)
            self._status_item.button().setImagePosition_(AppKit.NSImageLeft)

        self._menu = AppKit.NSMenu.alloc().init()
        self._menu.setAutoenablesItems_(False)
        self._menu.setDelegate_(self._responder)
        self._status_item.setMenu_(self._menu)

        self.refresh()

    def run(self):
        self._app.run()

    def refresh(self):
        """Redraw the status item title, and an open menu, from the session."""
        on_main(self._apply_title)
        on_main(self._apply_open_menu)

    def report_error(self, error):
        """Note that recognition reported an error.

        The menu carries it as its header the next time it opens.
        """
        self._error = str(error)
        self.refresh()

    # --- actions ---

    def start(self):
        try:
            state = self._on_start()
        except Exception as error:
            self._alert("Verbal Habits cannot start listening.", str(error))
            return

        if state != AUTHORIZED:
            # The menu has closed by the time this runs.
            if state in (DENIED, RESTRICTED):
                reported, mic_state, speech_state = self._read_authorization()
                header, lines = authorization_lines(
                    reported, mic_state, speech_state, running_bundled()
                )
                self._alert(header, " ".join(lines))
            # An undetermined state raises nothing here. Whoever supplies
            # on_start owns requesting authorization.
            return

        self._error = None
        self._session.start()
        self.refresh()

    def stop(self):
        if not self._confirm_stop():
            return
        self._on_stop()
        self._session.stop()
        self.refresh()

    def open_settings(self, permission):
        AppKit.NSWorkspace.sharedWorkspace().openURL_(
            Foundation.NSURL.URLWithString_(PRIVACY_SETTINGS_URLS[permission])
        )

    def menu_opened(self):
        """Start the timer that redraws an open menu once a second.

        Only elapsed time moves between committed segments, so a stopped
        session gets no timer.
        """
        if self._menu_timer is not None or not self._session.is_active:
            return
        self._menu_timer = AppKit.NSTimer.timerWithTimeInterval_repeats_block_(
            MENU_REDRAW_SECONDS, True, lambda _timer: self._apply_open_menu()
        )
        Foundation.NSRunLoop.currentRunLoop().addTimer_forMode_(
            self._menu_timer, Foundation.NSRunLoopCommonModes
        )

    def menu_closed(self):
        """Stop the redraw timer and release the items a closed menu no longer
        shows.
        """
        if self._menu_timer is not None:
            self._menu_timer.invalidate()
            self._menu_timer = None
        self._live = None

    # --- drawing ---

    def _apply_title(self):
        text = status_title(self._session)
        if self._symbol is None and text:
            text = f"{SYMBOL_FALLBACK} {text}"
        elif self._symbol is None:
            text = SYMBOL_FALLBACK

        font = AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(
            AppKit.NSFont.systemFontSize(), AppKit.NSFontWeightRegular
        )
        self._status_item.button().setAttributedTitle_(
            _attributed(text, {AppKit.NSFontAttributeName: font})
        )

    def _apply_open_menu(self):
        """Re-read every number into the items an open menu is showing."""
        if self._live is None:
            return

        session = self._session
        header_item, row_items, totals_items = self._live

        _set_item_text(
            header_item,
            _header_title(menu_header(session, self._error is not None)),
        )
        # A row's word never changes, so only the count at index 1 is written.
        for entry, item in row_items:
            _set_item_text(item, _count_title(session.counts[entry]), 1)
        for item, line in zip(totals_items, totals_lines(session)):
            _set_item_text(item, _totals_title(line))

    def rebuild(self, menu):
        """Build the menu as it opens, reading every number from the session."""
        menu.removeAllItems()

        state, mic_state, speech_state = self._read_authorization()
        if state in (DENIED, RESTRICTED):
            self._build_authorization(menu, state, mic_state, speech_state)
        else:
            self._build_session(menu)

        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        self._add_action(menu, "Quit", b"quit:")

    def _build_authorization(self, menu, state, mic_state, speech_state):
        self._live = None
        header, lines = authorization_lines(
            state, mic_state, speech_state, running_bundled()
        )
        width = item_width(WRAP_WIDTH_POINTS)
        menu.setMinimumWidth_(width)

        self._add_item(menu, _note_view(_header_title(header), width))
        for line in lines:
            self._add_item(menu, _wrapped_view(_muted_title(line), width))

        # System Settings cannot lift a restriction, so it is not offered.
        if state != DENIED:
            return

        refused = refused_permissions(state, mic_state, speech_state)
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        if MICROPHONE in refused:
            self._add_action(
                menu, "Open Microphone Settings…", b"openMicrophoneSettings:"
            )
        if SPEECH_RECOGNITION in refused:
            self._add_action(
                menu, "Open Speech Recognition Settings…", b"openSpeechSettings:"
            )

    def _build_session(self, menu):
        session = self._session

        stopped_with_a_session = not session.is_active and has_run(session)
        rows = word_rows(session, ordered_by_count=stopped_with_a_session)

        # Every item is built to one width, so the counts line up and the menu
        # holds that width for as long as it stays open.
        width = max(
            row_width([entry for entry, _ in rows]),
            *(
                item_width(text_width(_totals_title(line)))
                for line in totals_lines(session)
            ),
        )
        menu.setMinimumWidth_(width)

        header_item = self._add_item(
            menu,
            _note_view(
                _header_title(menu_header(session, self._error is not None)),
                width,
            ),
        )

        row_items = []
        for entry, count in rows:
            row_items.append(
                (entry, self._add_item(menu, _row_view(entry, count, width)))
            )

        totals_items = []
        if has_run(session):
            menu.addItem_(AppKit.NSMenuItem.separatorItem())
            for line in totals_lines(session):
                totals_items.append(
                    self._add_item(menu, _note_view(_totals_title(line), width))
                )

        self._live = (header_item, row_items, totals_items)

        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        if session.is_active:
            self._add_action(menu, "Stop", b"stop:")
        else:
            self._add_action(menu, "Start", b"start:")

    def _add_item(self, menu, view):
        """Add an item nobody can click, drawn by a view of its own."""
        item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "", None, ""
        )
        item.setView_(view)
        item.setEnabled_(False)
        menu.addItem_(item)
        return item

    def _add_action(self, menu, title, selector):
        item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            title, selector, ""
        )
        item.setTarget_(self._responder)
        item.setEnabled_(True)
        menu.addItem_(item)

    # --- alerts ---

    def _confirm_stop(self):
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Stop this session?")
        alert.setInformativeText_("The totals stay in the menu until you start again.")
        alert.addButtonWithTitle_("Stop")
        alert.addButtonWithTitle_("Keep listening")
        self._app.activateIgnoringOtherApps_(True)
        return alert.runModal() == AppKit.NSAlertFirstButtonReturn

    def _alert(self, message, detail):
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_(message)
        alert.setInformativeText_(detail)
        alert.addButtonWithTitle_("OK")
        self._app.activateIgnoringOtherApps_(True)
        alert.runModal()


# --- checking the module on its own ------------------------------------------

CHECK_INTERVAL_SECONDS = 0.4

CHECK_WORDS = ("like", "the", "it", "words", "again", "end")

# 4 segments, each arriving as the whole transcript so far, the way the
# recognizer delivers them. A short opening collapses the one before it, which
# is what commits a segment.
CHECK_TRANSCRIPTS = (
    "I like",
    "I like the way",
    "I like the way it works",
    "I like the way it works and I like the words",
    "So",
    "So it counts",
    "So it counts the words again",
    "So it counts the words again and again until the end",
    "Then",
    "Then the words",
    "Then the words settle and it is like",
    "Then the words settle and it is like the end again",
    "One",
    "One more time",
    "One more time it says the words",
    "One more time it says the words like the end",
)


def _run_check(forced_state, refused_side):
    """Drive the real interface from recorded transcripts, with no microphone.

    Transcripts arrive on a timer in the common run loop modes, so both the
    status item and an open menu keep counting while the menu is on screen.
    """
    from matcher import SegmentTracker, count_tracked
    from session import Session

    session = Session(CHECK_WORDS)
    tracker = SegmentTracker()
    replay = iter(CHECK_TRANSCRIPTS)

    mic_state = forced_state if refused_side in ("microphone", "both") else AUTHORIZED
    speech_state = forced_state if refused_side in ("speech", "both") else AUTHORIZED

    app = MenuBarApp(
        session,
        on_start=lambda: forced_state,
        on_stop=lambda: None,
        read_authorization=lambda: (forced_state, mic_state, speech_state),
    )

    def feed(_timer):
        if not session.is_active:
            return
        try:
            transcript = next(replay)
        except StopIteration:
            segment = tracker.flush()
            if segment is not None:
                session.record(*count_tracked(segment, CHECK_WORDS))
            app.refresh()
            return

        segment = tracker.update(transcript)
        if segment is not None:
            session.record(*count_tracked(segment, CHECK_WORDS))
        app.refresh()

    timer = AppKit.NSTimer.timerWithTimeInterval_repeats_block_(
        CHECK_INTERVAL_SECONDS, True, feed
    )
    Foundation.NSRunLoop.currentRunLoop().addTimer_forMode_(
        timer, Foundation.NSRunLoopCommonModes
    )

    print(f"Reporting authorization as {forced_state}. Open the menu bar item.")
    app.run()
    return 0


if __name__ == "__main__":
    import sys

    # python src/menubar.py [authorized|denied|restricted] [microphone|speech|both]
    requested = sys.argv[1] if len(sys.argv) > 1 else AUTHORIZED
    side = sys.argv[2] if len(sys.argv) > 2 else "both"
    sys.exit(_run_check(requested, side))
