import logging
from enum import Enum

import rtmidi
from rtmidi.midiconstants import (PROGRAM_CHANGE, SONG_START, SONG_STOP,
                                  TIMING_CLOCK)


class Mute(Enum):
    ON = 127
    OFF = 0


class MIDIWrapper:

    BANKS = ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H')

    def __init__(self, channel=1):
        self.channel = channel
        self._midi_out = rtmidi.MidiOut()
        self._ports = self._midi_out.get_ports()

    def get_output_ports(self):
        return self._ports

    def set_output_port(self, port: str) -> bool:
        """Return True if port was opened, False otherwise."""
        try:
            port_id = self._ports.index(port)
            if not self._midi_out.is_port_open():
                self._midi_out.open_port(port_id)
                return True
            else:
                logging.debug('Selected MIDI port is already opened.')
        except ValueError:
            logging.error('Name of selected MIDI output is invalid.')
        return False

    def is_port_open(self) -> bool:
        return self._midi_out.is_port_open()

    def change_pattern(self, bank, pattern):
        try:
            bank_number = self.BANKS.index(bank)
        except ValueError:
            logging.error(f'Cannot change pattern: bank {bank} is invalid.')
        self._midi_out.send_message([
            PROGRAM_CHANGE + self.channel - 1,
            (pattern - 1) + bank_number * 16
        ])

    def start(self):
        self._midi_out.send_message([SONG_START])

    def stop(self):
        self._midi_out.send_message([SONG_STOP])

    def clock(self):
        self._midi_out.send_message([TIMING_CLOCK])

    def mute(self, track: int, mute_state: Mute) -> None:
        self._midi_out.send_message((175 + track, 94, mute_state.value))
