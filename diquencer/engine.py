import logging
from threading import Event, Thread
from time import perf_counter, sleep

from .events import MuteEvent, PatternEvent, StopEvent
from .exceptions import ChangePatternError, InvalidBank
from .midi_wrapper import Mute
from .models import Position


class SequencerEngine(Thread):
    def __init__(
        self, sequence, midi_wrapper, 
        start_callback=None, 
        stop_callback=None,
        pattern_changed_callback=None,
        error_callback=None
    ):
        super().__init__()
        self._sequence = sequence
        self._midi = midi_wrapper
        self._start_callback = start_callback
        self._stop_callback = stop_callback
        self._pattern_changed_callback = pattern_changed_callback
        self._error_callback = error_callback
        self._pulsestamp = 0
        self._stop_event = Event()
        self._pulse_duration = 60.0 / self._sequence.tempo / 24.0
        self.current_pattern = None
        self.next_pattern = None

    @property
    def position(self):
        return Position(self._pulsestamp)

    def run(self):
        logging.info(f"[{self.position}] Sequencer started.")

        # Set initial pattern
        try:
            self._change_pattern(self._sequence.consume_event(self._pulsestamp))
        except ChangePatternError:
            return

        # Set initial playing tracks
        mute_event = self._sequence.consume_event(self._pulsestamp)
        self._play_tracks(mute_event.playing_tracks)
        logging.info(
            f"[{self.position}] Playing tracks: " f"{mute_event.playing_tracks}."
        )

        # Warm-up (4 quarter notes)
        # NOTE: this seems to add a considerable delay when calling start.
        #for _ in range(24 * 4):
        #    self._pulse()

        # Start
        if self._start_callback:
            self._start_callback()

        self._midi.start()

        # Consume events from queue
        while not self._stop_event.is_set():
            self._pulse()
            event = self._sequence.consume_event(self._pulsestamp)
            if isinstance(event, StopEvent):
                self.current_pattern = None
                break
            elif isinstance(event, PatternEvent):
                try:
                    self._change_pattern(event)
                except ChangePatternError:
                    return
            elif isinstance(event, MuteEvent):
                self._play_tracks(event.playing_tracks)
                logging.info(
                    f"[{self.position}] Playing tracks: " f"{event.playing_tracks}."
                )
            self._pulsestamp += 1

        self._midi.stop()
        logging.info(f"[{self.position}] Sequencer stopped.")

        self._sequence.reset()

    def stop(self):
        # Stop
        if self._stop_callback:
            self._stop_callback()
        self._stop_event.set()

    def _pulse(self):
        self._midi.tick()
        start = perf_counter()
        while perf_counter() < start + self._pulse_duration:
            sleep(0.0001)

    def _play_tracks(self, playing_tracks):
        for track in range(1, 17):
            state = Mute.OFF if track in playing_tracks else Mute.ON
            self._midi.mute(track, state)

    def _cleanup_after_abort(self, error):
        self._midi.stop()
        self._sequence.reset()
        logging.critical("Aborting sequencer engine.", exc_info=True)
        if self._error_callback:
            self._error_callback(error)

    def _change_pattern(self, event):
        pattern = event.pattern
        try:
            self._midi.change_pattern(pattern.bank_id, pattern.pattern_id)
        except InvalidBank as error:
            self._cleanup_after_abort(error)
            raise ChangePatternError()
        if self._pattern_changed_callback:
            self._pattern_changed_callback(pattern)
            
        logging.info(f"[{self.position}] Changing pattern to {pattern}.")
        self.current_pattern = pattern
        self.next_pattern = self._sequence.next_pattern
