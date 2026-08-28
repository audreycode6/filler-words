"""The status item and the menu it drops down.

Every figure shown is read from a Session as the menu opens and again while it
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

TRANSCRIBING_TITLE = "…"

IDLE_HEADER = "Tracked words"
TRANSCRIBING_HEADER = "Transcribing…"
TRACKING_HEADER = "Tracking"
SUMMARY_HEADER = "Session summary"
ERROR_HEADER = "Recognition stopped"

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


def authorization_lines(state, mic_state, speech_state):
    """The header and body shown in place of a session, naming the permissions
    that are in the reported state.
    """
    named = " and ".join(refused_permissions(state, mic_state, speech_state))
    if state == DENIED:
        return ("Access denied", (f"Verbal Habits needs {named} access.",))
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


def menu_header(session):
    """The line above the word rows.

    A running session reads as transcribing until its first segment commits,
    and as tracking from then on.
    """
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
    """The two lines below the rows.

    The rate is tracked words per minute, and the label says so.
    """
    return (
        f"{session.total_tracked_count} tracked of {session.total_word_count} spoken",
        f"{elapsed_text(session.elapsed_seconds)} elapsed"
        f" · {session.tracked_rate:.1f} tracked/min",
    )


# --- AppKit below this line --------------------------------------------------

SYMBOL_NAME = "mic"
SYMBOL_FALLBACK = "🎙"
COUNT_COLUMN_POINTS = 168.0
MENU_MINIMUM_WIDTH_POINTS = 220.0
MENU_REDRAW_SECONDS = 1.0
PRIVACY_SETTINGS_URLS = {
    MICROPHONE: (
        "x-apple.systempreferences:"
        "com.apple.preference.security?Privacy_Microphone"
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


def _row_title(entry, count):
    """A row with the count on a tab stop, in a font whose digits share one
    width.
    """
    tab = AppKit.NSTextTab.alloc().initWithTextAlignment_location_options_(
        AppKit.NSTextAlignmentRight, COUNT_COLUMN_POINTS, {}
    )
    style = AppKit.NSMutableParagraphStyle.alloc().init()
    style.setTabStops_([tab])

    font = AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(
        AppKit.NSFont.systemFontSize(), AppKit.NSFontWeightRegular
    )
    return _attributed(
        f"{entry}\t{count}",
        {
            AppKit.NSParagraphStyleAttributeName: style,
            AppKit.NSFontAttributeName: font,
        },
    )


def _secondary_title(text):
    """Smaller and dimmer, for headers and totals.

    `sectionHeaderWithTitle:` requires Sonoma; the target is macOS 13.
    """
    return _attributed(
        text,
        {
            AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(
                AppKit.NSFont.smallSystemFontSize()
            ),
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.secondaryLabelColor(),
        },
    )


def _retitle(item, attributed_title):
    """Write a title onto a menu item, leaving it alone when nothing changed."""
    current = item.attributedTitle()
    if current is not None and current.string() == attributed_title.string():
        return
    item.setAttributedTitle_(attributed_title)


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
        self._app.setActivationPolicy_(
            AppKit.NSApplicationActivationPolicyAccessory
        )

        self._responder = _Responder.alloc().init()
        self._responder.owner = self

        self._status_item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
            AppKit.NSVariableStatusItemLength
        )
        self._symbol = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            SYMBOL_NAME, "Verbal Habits"
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
                    reported, mic_state, speech_state
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

        Elapsed time and the rate move between committed segments, so an open
        menu needs a redraw that no segment triggers. The timer runs in the
        common run loop modes so that it fires while the menu holds the app in
        event tracking. A stopped session has nothing that moves, so none is
        started for it.
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
        """Re-read every figure into the items an open menu is showing."""
        if self._live is None:
            return

        session = self._session
        header_item, row_items, totals_items = self._live

        _retitle(header_item, _secondary_title(self._error or menu_header(session)))
        for entry, item in row_items:
            _retitle(item, _row_title(entry, session.counts[entry]))
        for item, line in zip(totals_items, totals_lines(session)):
            _retitle(item, _secondary_title(line))

    def rebuild(self, menu):
        """Build the menu as it opens, reading every figure from the session."""
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
        header, lines = authorization_lines(state, mic_state, speech_state)
        self._add_note(menu, _secondary_title(header))
        for line in lines:
            self._add_note(menu, _secondary_title(line))

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

        # A menu sizes itself to its widest item, and the totals line grows
        # over a session. Opening at a width that already fits the longest one
        # keeps the panel from widening under the cursor.
        menu.setMinimumWidth_(MENU_MINIMUM_WIDTH_POINTS)

        header_item = self._add_note(
            menu, _secondary_title(self._error or menu_header(session))
        )

        stopped_with_a_session = not session.is_active and has_run(session)
        row_items = []
        for entry, count in word_rows(session, ordered_by_count=stopped_with_a_session):
            row_items.append((entry, self._add_note(menu, _row_title(entry, count))))

        totals_items = []
        if has_run(session):
            menu.addItem_(AppKit.NSMenuItem.separatorItem())
            for line in totals_lines(session):
                totals_items.append(self._add_note(menu, _secondary_title(line)))

        self._live = (header_item, row_items, totals_items)

        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        if session.is_active:
            self._add_action(menu, "Stop", b"stop:")
        else:
            self._add_action(menu, "Start", b"start:")

    def _add_note(self, menu, attributed_title):
        item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "", None, ""
        )
        item.setAttributedTitle_(attributed_title)
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
        alert.setInformativeText_(
            "The totals stay in the menu until you start again."
        )
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
    print(
        "Segments arrive far faster than speech produces them, so the rate reads"
        " high here."
    )
    app.run()
    return 0


if __name__ == "__main__":
    import sys

    # python src/menubar.py [authorized|denied|restricted] [microphone|speech|both]
    requested = sys.argv[1] if len(sys.argv) > 1 else AUTHORIZED
    side = sys.argv[2] if len(sys.argv) > 2 else "both"
    sys.exit(_run_check(requested, side))
