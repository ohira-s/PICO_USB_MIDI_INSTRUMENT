#########################################################################
# USB MIDI Instrument with Raspberry Pi PICO W (USB DEVICE)
# FUNCTION:
#   MIDI-OUT to the built-in USB port on PICO W
# HARDWARE:
#   CONTROLER  : Raspberry Pi PICO W.
#                On board USB works as USB-MIDI device.
#   OLED       : SSD1306 (128x64) as a display.
#
# PROGRAM: circuitpython (V9.2.1)
#   usb_midi_instrument.py (USB device mode program)
#     0.0.1: 12/21/2024
#     0.0.2: 12/24/2024
#            Guitar Code Player test.
#########################################################################

from board import *
import digitalio
from busio import UART			# for UART MIDI
from busio import I2C			# for I2C
from time import sleep
import os, re
import json

import usb_midi					# for USB MIDI
import adafruit_midi
from adafruit_midi.control_change import ControlChange
from adafruit_midi.note_off import NoteOff
from adafruit_midi.note_on import NoteOn
from adafruit_midi.pitch_bend import PitchBend
from adafruit_midi.program_change import ProgramChange

import board
#import usb_host					# for USB HOST
#import usb.core
#from adafruit_usb_host_midi.adafruit_usb_host_midi import MIDI	# for USB MIDI HOST
#import supervisor

import adafruit_ssd1306			# for SSD1306 OLED Display

import busio
import sdcardio
import storage

import random

###################
### SD card class
###################
class sdcard_class:
  # Constructor
  def __init__(self):
    self.file_opened = None

  # Initialize SD Card device (MOSI=TX, MISO=RX)
  def setup(self, spi_unit=0, sck_pin=GP18, mosi_pin=GP19, miso_pin=GP16, cs_pin=GP17):
    print('SD CARD INIT.')
    spi = busio.SPI(sck_pin, MOSI=mosi_pin, MISO=miso_pin)
    sd = sdcardio.SDCard(spi, cs_pin)

    vfs = storage.VfsFat(sd)
    storage.mount(vfs, '/SD')

    fp = open('/SD/SYNTH/MIDIUNIT/MIDISET000.json', 'r')
    print(fp.read())
    fp.close()
    print('SD CARD INIT done.')

  # Opened file
  def file_opened(self):
    return self.file_opened

  # File open, needs to close the file
  def file_open(self, path, fname, mode = 'r'):
    try:
      if not self.file_opened is None:
        self.file_opened.close()
        self.file_opened = None

      self.file_opened = open(path + fname, mode)
      return self.file_opened

    except Exception as e:
      self.file_opened = None
      print('sccard_class.file_open Exception:', e, path, fname, mode)

    return None

  # Close the file opened currently
  def file_close(self):
    try:
      if not self.file_opened is None:
        self.file_opened.close()

    except Exception as e:
      print('sccard_class.file_open Exception:', e, path, fname, mode)

    self.file_opened = None

  # Read JSON format file, then retun JSON data
  def json_read(self, path, fname):
    json_data = None
    try:
      with open(path + fname, 'r') as f:
        json_data = json.load(f)

    except Exception as e:
      print('sccard_class.json_read Exception:', e, path, fname)

    return json_data

  # Write JSON format file
  def json_write(self, path, fname, json_data):
    try:
      with open(path + fname, 'w') as f:
        json.dump(json_data, f)

      return True

    except Exception as e:
      print('sccard_class.json_write Exception:', e, path, fname)

    return False

################# End of SD Card Class Definition #################


################################
### Unit-MIDI Instrument class
################################
class USB_MIDI_Instrument_class:
    # Constructor
    def __init__(self):
        # Constants                                 Value
        self.ControlChange_Modulation      =  1		# 0..127
        self.ControlChange_Sustain         = 64		# 127: On / 0: Off
        
        self.ControlChange_Portamento_Time =  5		# 0..127: Portamento time (0 is no effect)
        self.ControlChange_Portamento      = 65		# 64..127: On / 0..63: Off
        
        self.ControlChange_SoftPedal       = 67		# 127: On / 0: Off
        
        self.ControlChange_Vibrate_Rate    = 76		# 0(Low Freq)..64(Off)..127(High Freq)
        self.ControlChange_Vibrate_Depth   = 77		# 0..127
        self.ControlChange_Vibrate_Delay   = 78		# 0..127

        self.ControlChange_Chorus_Program  = 81		# 0..7
        self.ControlChange_Chorus_Level    = 93		# 0..127
        self.ControlChange_Chorus_Feedback = 59		# 0..127
        self.ControlChange_Chorus_Delay    = 60		# 0..127

        # USB MIDI device
        print('USB MIDI:', usb_midi.ports)
        self._usb_midi = [None] * 16
        for channel in list(range(16)):
            self._usb_midi[channel] = adafruit_midi.MIDI(midi_in=usb_midi.ports[0], midi_out=usb_midi.ports[1], out_channel=channel)

    # MIDI sends to USB as a USB device
    def midi_send(self, midi_msg, channel=0):
#        print('SEND:', channel, midi_msg)
        self._usb_midi[channel % 16].send(midi_msg)
#        print('SENT')

    # MIDI-OUT for keeping compatobolity to UART version
    def midi_out(self, midi_msg, channel=0):
        self.midi_send(midi_msg, channel)

    # Send note on
    def set_note_on(self, note_key, velocity, channel=0):
        self.midi_send(NoteOn(note_key, velocity, channel=channel), channel)

    # Send note off
    def set_note_off(self, note_key, channel=0):
        self.midi_send(NoteOff(note_key, channel=channel), channel)

    # Send all notes off
    def set_all_notes_off(self, channel=0):
        pass
    
    def set_reverb(self, channel, prog, level, feedback):
        status_byte = 0xB0 + channel
        midi_msg = bytearray([status_byte, 0x50, prog, status_byte, 0x5B, level])
        self.midi_out(midi_msg)
        if feedback > 0:
            midi_msg = bytearray([0xF0, 0x41, 0x00, 0x42, 0x12, 0x40, 0x01, 0x35, feedback, 0, 0xF7])
            self.midi_out(midi_msg)
            
    def set_chorus(self, prog, level, feedback, delay, channel=0):
        if prog is not None:
            self.midi_send(ControlChange(self.ControlChange_Chorus_Program,  prog, channel=channel),     channel)
        if level is not None:
            self.midi_send(ControlChange(self.ControlChange_Chorus_Level,    level, channel=channel),    channel)
        if feedback is not None:
            self.midi_send(ControlChange(self.ControlChange_Chorus_Feedback, feedback, channel=channel), channel)
        if delay is not None:
            self.midi_send(ControlChange(self.ControlChange_Chorus_Delay,    delay, channel=channel),    channel)

    def set_vibrate(self, rate, depth, delay, channel=0):
        if rate is not None:
            self.midi_send(ControlChange(self.ControlChange_Vibrate_Rate,  rate, channel=channel),  channel)
        if depth is not None:
            self.midi_send(ControlChange(self.ControlChange_Vibrate_Depth, depth, channel=channel), channel)
        if delay is not None:
            self.midi_send(ControlChange(self.ControlChange_Vibrate_Delay, delay, channel=channel), channel)

    # Send pitch bend value
    def set_pitch_bend(self, value, channel=0):
        self.midi_send(PitchBend(value, channel=channel), channel)

    # Send program change
    def set_program_change(self, program, channel=0):
        self.midi_send(ProgramChange(program, channel=channel), channel)

    def set_pitch_bend_range(self, channel, value):
        status_byte = 0xB0 + channel
        midi_msg = bytearray([status_byte, 0x65, 0x00, 0x64, 0x00, 0x06, value & 0x7f])
        self.midi_out(midi_msg)

    def set_modulation_wheel(self, modulation, value, channel=0):
        self.midi_send(ControlChange(modulation, value, channel=channel), channel)


    def do_task(self):
        pass

################# End of Unit-MIDI Class Definition #################


########################
### OLED SSD1306 class
########################
class OLED_SSD1306_class:
    def __init__(self, i2c, address=0x3C, width=128, height=64):
        self.available = False
        self._display = None
        self._i2c = i2c
        self.address = address
        self._width = width
        self._height = height

    def init_device(self, device):
        if device is None:
            return
        
        self._display = device
        self.available = True
        
    def is_available(self):
        return self.available

    def i2c(self):
        return self._i2c
    
    def get_display(self):
        print('DISPLAT')
        return self._display
    
    def width(self):
        return self._width
    
    def height(self):
        return self._height
    
    def fill(self, color):
        if self.is_available():
            self._display.fill(color)
    
    def fill_rect(self, x, y, w, h, color):
        if self.is_available():
            self._display.fill_rect(x, y, w, h, color)

    def text(self, s, x, y, color=1, disp_size=1):
        if self.is_available():
            self._display.text(s, x, y, color, font_name='font5x8.bin', size=disp_size)

    def show(self):
        if self.is_available():
            self._display.show()

    def clear(self, color=0, refresh=True):
        self.fill(color)
        if refresh:
            self.show()
        
################# End of OLED SSD1306 Class Definition #################


#######################
### Application class
#######################
class Application_class:
    def __init__(self, display_obj):
        self._display = display_obj
        self._channel = 0
        
        self.PARAM_GUITAR_ROOTs = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        self.PARAM_GUITAR_CHORDs = ['M', 'M7', '7', '6', 'aug', 'm', 'mM7', 'm7', 'm6', 'm7-5', 'add9', 'sus4', '7sus4', 'dim7']
        self.GUITAR_STRINGS_OPEN = [16,11, 7, 2, -3, -8]	# 1st String: E, B, G, D, A, E: 6th String
        self.CHORD_STRUCTURE = {
            #Chord   :   1  2  3  4  5  6		  Strings
            'CM'     : [ 0, 1, 0, 2, 3,-1],		# Fret number
            'CM7'    : [ 0, 0, 0, 2, 3,-1],
            'C7'     : [ 0, 1, 3, 2, 3,-1],
            'C6'     : [ 0, 1, 2, 2, 3,-1],
            'Caug'   : [-1, 1, 1, 2, 3,-1],
            'Cm'     : [ 3, 4, 5, 5, 3,-1],
            'CmM7'   : [ 3, 4, 4, 5, 3,-1],
            'Cm7'    : [ 3, 4, 3, 5, 3,-1],
            'Cm6'    : [ 3, 1, 2, 1, 3,-1],
            'Cm7-5'  : [-1, 4, 3, 4, 3,-1],
            'Cadd9'  : [ 0, 3, 0, 2, 3,-1],
            'Csus4'  : [ 1, 1, 0, 3, 3,-1],
            'C7sus4' : [ 3, 6, 3, 5, 3,-1],
            'Cdim7'  : [-1, 4, 2, 4, 3,-1],

            'C#M'    : [ 4, 6, 6, 6, 4,-1],
            'C#M7'   : [ 4, 6, 5, 6, 4,-1],
            'C#7'    : [ 4, 6, 4, 6, 4,-1],
            'C#6'    : [ 6, 6, 6, 6, 4,-1],
            'C#aug'  : [-1, 2, 2, 3, 4,-1],
            'C#m'    : [ 4, 5, 6, 6, 4,-1],
            'C#mM7'  : [ 4, 5, 5, 6, 4,-1],
            'C#m7'   : [ 4, 5, 4, 6, 4,-1],
            'C#m6'   : [ 4, 2, 3, 2, 4,-1],
            'C#m7-5' : [-1, 5, 4, 5, 4,-1],
            'C#add9' : [ 4, 4, 6, 6, 4,-1],
            'C#sus4' : [ 4, 7, 6, 6, 4,-1],
            'C#7sus4': [ 4, 7, 4, 6, 4,-1],
            'C#dim7' : [-1, 5, 3, 5, 4,-1],

            'DM'     : [ 2, 3, 2, 0,-1,-1],
            'DM7'    : [ 2, 2, 2, 0,-1,-1],
            'D7'     : [ 2, 1, 2, 0,-1,-1],
            'D6'     : [ 2, 0, 2, 0,-1,-1],
            'Daug'   : [ 2, 3, 3, 0,-1,-1],
            'Dm'     : [ 1, 3, 2, 0,-1,-1],
            'DmM7'   : [ 1, 2, 2, 0,-1,-1],
            'Dm7'    : [ 1, 1, 2, 0,-1,-1],
            'Dm6'    : [ 1, 0, 2, 0,-1,-1],
            'Dm7-5'  : [ 1, 1, 1, 0,-1,-1],
            'Dadd9'  : [ 0, 3, 2, 0,-1,-1],
            'Dsus4'  : [ 3, 3, 2, 0,-1,-1],
            'D7sus4' : [ 3, 1, 2, 0,-1,-1],
            'Ddim7'  : [ 1, 0, 1, 0,-1,-1],

            'D#M'    : [ 6, 8, 8, 8, 6,-1],
            'D#M7'   : [ 6, 8, 7, 8, 6,-1],
            'D#7'    : [ 6, 8, 6, 8, 6,-1],
            'D#6'    : [ 8, 8, 8, 8, 6,-1],
            'D#aug'  : [-1, 4, 4, 5, 6,-1],
            'D#m'    : [ 6, 7, 8, 8, 6,-1],
            'D#mM7'  : [ 6, 7, 7, 8, 6,-1],
            'D#m7'   : [ 6, 7, 6, 8, 6,-1],
            'D#m6'   : [ 6, 4, 5, 4, 6,-1],
            'D#m7-5' : [-1, 7, 6, 7, 6,-1],
            'D#add9' : [ 6, 6, 8, 8, 6,-1],
            'D#sus4' : [ 6, 9, 8, 8, 6,-1],
            'D#7sus4': [ 6, 9, 6, 8, 6,-1],
            'D#dim7' : [-1, 7, 5, 7, 6,-1],

            'EM'     : [ 0, 0, 1, 2, 2, 0],
            'EM7'    : [ 0, 0, 1, 1, 2, 0],
            'E7'     : [ 0, 0, 1, 0, 2, 0],
            'E6'     : [ 0, 2, 1, 2, 2, 0],
            'Eaug'   : [ 0, 2, 2, 3,-1,-1],
            'Em'     : [ 0, 0, 0, 2, 2, 0],
            'EmM7'   : [-1, 0, 0, 1, 2, 0],
            'Em7'    : [ 0, 0, 0, 0, 2, 0],
            'Em6'    : [ 0, 2, 0, 2, 2, 0],
            'Em7-5'  : [ 0, 3, 0, 2, 1, 0],
            'Eadd9'  : [ 0, 0, 1, 4, 2, 0],
            'Esus4'  : [ 0, 0, 2, 2, 2, 0],
            'E7sus4' : [ 0, 0, 2, 0, 2, 0],
            'Edim7'  : [ 0, 2, 0, 2, 1, 0],

            'FM'     : [ 1, 1, 2, 3, 3, 1],
            'FM7'    : [-1, 1, 2, 2,-1, 1],
            'F7'     : [ 1, 1, 2, 1, 3, 1],
            'F6'     : [ 1, 3, 2, 3, 1, 1],
            'Faug'   : [ 1, 2, 2, 3,-1.-1],
            'Fm'     : [ 1, 1, 1, 3, 3, 1],
            'FmM7'   : [ 1, 1, 1, 2, 3, 1],
            'Fm7'    : [ 1, 1, 1, 1, 3, 1],
            'Fm6'    : [ 1, 3, 1, 3, 3, 1],
            'Fm7-5'  : [-1, 0, 1, 1,-1, 1],
            'Fadd9'  : [ 3, 1, 2, 3,-1,-1],
            'Fsus4'  : [ 1, 1, 3, 3, 3, 1],
            'F7sus4' : [ 1, 1, 3, 1, 3, 1],
            'Fdim7'  : [ 1, 0, 1, 0,-1, 1],

            'F#M'    : [ 2, 2, 3, 4, 4, 2],
            'F#M7'   : [-1, 2, 3, 3,-1, 2],
            'F#7'    : [ 2, 2, 3, 2, 4, 2],
            'F#6'    : [ 2, 4, 3, 4, 2, 2],
            'F#aug'  : [ 2, 3, 3, 4,-1,-1],
            'F#m'    : [ 2, 2, 2, 4, 4, 2],
            'F#mM7'  : [ 2, 2, 2, 3, 4, 2],
            'F#m7'   : [ 2, 2, 2, 2, 4, 2],
            'F#m6'   : [ 2, 4, 2, 4, 4, 2],
            'F#m7-5' : [ 0, 1, 2, 2,-1, 2],
            'F#add9' : [ 4, 2, 3, 4,-1,-1],
            'F#sus4' : [ 2, 2, 4, 4, 4, 2],
            'F#7sus4': [ 2, 2, 4, 2, 4, 2],
            'F#dim7' : [-1, 1, 2, 1,-1, 2],

            'GM'     : [ 3, 0, 0, 0, 2, 3],
            'GM7'    : [ 2, 0, 0, 0, 2, 3],
            'G7'     : [ 1, 0, 0, 0, 2, 3],
            'G6'     : [ 0, 0, 0, 0, 2, 3],
            'Gaug'   : [ 3, 4, 4, 5,-1,-1],
            'Gm'     : [ 3, 3, 3, 5, 5, 3],
            'GmM7'   : [ 3, 3, 3, 4, 5, 3],
            'Gm7'    : [ 3, 3, 3, 3, 5, 3],
            'Gm6'    : [ 3, 5, 3, 5, 5, 3],
            'Gm7-5'  : [-1, 2, 3, 3,-1, 3],
            'Gadd9'  : [ 3, 0, 2, 0, 0, 3],
            'Gsus4'  : [ 3, 1, 0, 0, 3, 3],
            'G7sus4' : [ 3, 3, 5, 3, 5, 3],
            'Gdim7'  : [-1, 2, 3, 2,-1, 3],

            'G#M'    : [ 4, 4, 5, 6, 6, 4],
            'G#M7'   : [-1, 4, 5, 5,-1, 4],
            'G#7'    : [ 4, 4, 5, 4, 6, 4],
            'G#6'    : [-1, 4, 5, 3,-1, 4],
            'G#aug'  : [ 4, 5, 5, 6,-1,-1],
            'G#m'    : [ 4, 4, 4, 6, 6, 4],
            'G#mM7'  : [ 4, 4, 4, 5, 6, 4],
            'G#m7'   : [ 4, 4, 4, 4, 6, 4],
            'G#m6'   : [ 4, 6, 4, 6, 6, 4],
            'G#m7-5' : [ 0, 3, 4, 4,-1, 4],
            'G#add9' : [ 6, 4, 5, 6,-1,-1],
            'G#sus4' : [ 4, 4, 6, 6, 6, 4],
            'G#7sus4': [ 4, 4, 6, 4, 6, 4],
            'G#dim7' : [-1, 3, 4, 3,-1, 4],

            'AM'     : [ 0, 2, 2, 2, 0,-1],
            'AM7'    : [ 0, 2, 1, 2, 0,-1],
            'A7'     : [ 0, 2, 0, 2, 0,-1],
            'A6'     : [ 2, 2, 2, 2, 0,-1],
            'Aaug'   : [ 1, 2, 2, 3, 0,-1],
            'Am'     : [ 0, 1, 2, 2, 0,-1],
            'AmM7'   : [ 0, 1, 1, 2, 0,-1],
            'Am7'    : [ 0, 1, 0, 2, 0,-1],
            'Am6'    : [ 2, 1, 2, 2, 0,-1],
            'Am7-5'  : [-1, 1, 0, 1, 0,-1],
            'Aadd9'  : [ 0, 0, 2, 2, 0,-1],
            'Asus4'  : [ 0, 3, 2, 2, 0,-1],
            'A7sus4' : [ 0, 3, 0, 2, 0,-1],
            'Adim7'  : [ 2, 1, 2, 1, 0,-1],

            'A#M'    : [ 1, 3, 3, 3, 1,-1],
            'A#M7'   : [ 1, 3, 2, 3, 1,-1],
            'A#7'    : [ 1, 3, 1, 3, 1,-1],
            'A#6'    : [ 3, 3, 3, 3, 1,-1],
            'A#aug'  : [ 6, 7, 7, 8,-1,-1],
            'A#m'    : [ 1, 2, 3, 3, 1,-1],
            'A#mM7'  : [ 1, 2, 2, 3, 1,-1],
            'A#m7'   : [ 1, 2, 1, 3, 1,-1],
            'A#m6'   : [ 3, 2, 3, 1, 1,-1],
            'A#m7-5' : [-1, 2, 1, 2, 1,-1],
            'A#add9' : [ 1, 1, 3, 3, 1,-1],
            'A#sus4' : [ 1, 4, 3, 3, 1,-1],
            'A#7sus4': [ 1, 4, 1, 3, 1,-1],
            'A#dim7' : [ 0, 2, 0, 2, 1,-1],

            'BM'     : [ 2, 4, 4, 4, 2,-1],
            'BM7'    : [ 2, 4, 3, 4, 2,-1],
            'B7'     : [ 2, 0, 2, 1, 2,-1],
            'B6'     : [ 4, 4, 4, 4, 2,-1],
            'Baug'   : [-1, 0, 0, 1, 2,-1],
            'Bm'     : [ 2, 3, 4, 4, 2,-1],
            'BmM7'   : [ 2, 3, 3, 4, 2,-1],
            'Bm7'    : [ 2, 3, 2, 4, 2,-1],
            'Bm6'    : [ 3, 0, 2, 0, 3,-1],
            'Bm7-5'  : [-1, 3, 2, 3, 2,-1],
            'Badd9'  : [ 1, 1, 3, 3, 1,-1],
            'Bsus4'  : [ 2, 5, 4, 4, 2,-1],
            'B7sus4' : [ 2, 5, 2, 4, 2,-1],
            'Bdim7'  : [-1, 3, 1, 3, 2,-1]
        }

        self.PARAM_ALL = -1
        self.PARAM_GUITAR_ROOT = 0
        self.PARAM_GUITAR_CHORD = 1
        self.value_guitar_root = 0
        self.value_guitar_chord = 0
        
        self._scale_number = 4
        self._notes_on  = None
        self._notes_off = None

    def guitar_string_note(self, strings, frets):
        if frets < 0:
            return None
        
        return self.GUITAR_STRINGS_OPEN[strings] + frets

    def scale_number(self, scale=None):
        if scale is not None:
            if scale < -1:
                scale = -1
            elif scale > 9:
                scale = 9
                
            self._scale_number = scale
            
        return self._scale_number
    
    def root_note(self, scale=None):
        if scale is None:
            scale = self.scale_number()
            
        return (scale + 1) * 12 + self.value_guitar_root

    def chord_notes(self, root=None, chord=None, scale=None):
        if root is None:
            root = self.root_note(scale)

        if chord is None:
            chord = self.value_guitar_chord
            chord = chord % 14							# SOS DEBUG
        
        print('root, chord=', root, chord)
        root_name = self.PARAM_GUITAR_ROOTs[root % 12]
        chord_name = root_name + self.PARAM_GUITAR_CHORDs[chord]
        notes = []
        print('CHORD NAME: ', chord_name, self.CHORD_STRUCTURE[chord_name])
        fret_map = self.CHORD_STRUCTURE[chord_name]
        for strings in list(range(6)):
            note = self.guitar_string_note(strings, fret_map[strings])
            if note is not None:
                notes.append(note + root)
            
        return notes

    def show_message(self, msg, x=0, y=0, color=1):
        self._display.fill_rect(x, y, 128, 9, 0 if color == 1 else 1)
        self._display.text(msg, x, y, color)
        self._display.show()

    def channel(self, ch=None):
        if ch is not None:
            self._channel = ch % 16
            
        return self._channel
        
    def show_settings(self, param=-1):
        
        def show_a_parameter_guitar(param, color):
            if param == self.PARAM_ALL:
                self.show_message('---PICO GUITAR---', 0, 0, color)
                
            if param == self.PARAM_ALL or param == self.PARAM_GUITAR_ROOT:
                self.show_message('ROOT : ' + self.PARAM_GUITAR_ROOTs[self.value_guitar_root], 0, 9, color)
                
            if param == self.PARAM_ALL or param == self.PARAM_GUITAR_CHORD:
                self.show_message('CHORD: ' + self.PARAM_GUITAR_CHORDs[self.value_guitar_chord], 0, 18, color)

        def show_a_parameter_drum(param, color):
            pass

        #--- show_settings MAIN ---#
        show_a_parameter_guitar(param, 1)
        self._display.show()


    def do_task(self):
        try:
            GP18_val = switch_GP18.value
            GP19_val = switch_GP19.value
            GP20_val = switch_GP20.value
            GP21_val = switch_GP21.value
#            print('GP18, 19, 20, 21=', GP18_val, GP19_val, GP20_val, GP21_val)
            
            # Play a chord selected
            if GP18_val == False:
                if self._notes_on is None:
#                    program = random.randint(0, 60)
#                    synth.set_program_change(program, 0)                
                    synth.set_program_change(26, 0)   		# Steel Guitar             

                    pico_led.value = True                    
                    self._notes_on = self.chord_notes()
                    
                    print('CHORD NOTEs ON : ', self._notes_on)
#                    self._display.fill_rect(0, 27, 128, 18, 0)
#                    self.show_message(str(self._notes_on), 0, 27, color=1)
#                    self._display.show()

                    for nt in self._notes_on:
                        if nt >= 0:
                            synth.set_note_on(nt, 127, 0)
                            if self._notes_off is None:
                                self._notes_off = []
                            self._notes_off.append(nt)
                            sleep(0.001)
#                            print('NOTE ON : ', nt)

                    pico_led.value = False
                
                else:
                    sleep(0.006)

            else:
                if self._notes_off is not None:
                    pico_led.value = True                    
                    print('CHORD NOTEs OFF: ', self._notes_off)
#                    self._display.fill_rect(0, 27, 128, 18, 1)
#                    self.show_message(str(self._notes_off), 0, 36, color=0)
#                    self._display.show()
                    for nt in self._notes_off:
                        if nt >= 0:
                            synth.set_note_off(nt, 0)
                            sleep(0.001)
#                            print('NOTE OFF: ', nt)
                        
                    self._notes_on  = None
                    self._notes_off = None
                    pico_led.value  = False                    
                
                else:
                    sleep(0.006)

            # Effector
            if GP19_val == False:
                print('EFFECT ON')
                sleep(0.25)
                synth.set_pitch_bend( 9000, 0)
                sleep(0.25)
                synth.set_pitch_bend(12000, 0)
                sleep(0.25)
                synth.set_pitch_bend(15000, 0)
                sleep(0.25)
                synth.set_pitch_bend( 8192, 0)

#                self.set_modulation_wheel(1, 127, 0)
#                sleep(4.0)

#                print('NOTE0 and EFFECT OFF')
#                self.set_note_off(note, 0)
#                self.set_pitch_bend(0, 0)
#                self.set_modulation_wheel(1, 0, 0)
#                self.set_vibrate(64, 0, 0, 0)
#                self.set_chorus(0, 0, 0, 0, 0)
#                sleep(1.0)

            # Root change
            if GP21_val == False:
                print('ROOT CHANGE')
                self.value_guitar_root = (self.value_guitar_root + 1) % len(self.PARAM_GUITAR_ROOTs)
                self.show_settings(self.PARAM_GUITAR_ROOT)

            # Chord change
            if GP20_val == False:
                print('CHORD CHANGE')
                self.value_guitar_chord = (self.value_guitar_chord + 1) % len(self.PARAM_GUITAR_CHORDs)
                self.show_settings(self.PARAM_GUITAR_CHORD)
                
        except Exception as e:
            led_flush = False
            for cnt in list(range(5)):
                pico_led.value = led_flush
                led_flush = not led_flush
                sleep(0.5)

            led_flush = False
            print('EXCEPTION: ', e)
#            display.clear()
#            display.show()
#            display.text('EXCEPTION: MIDI-IN', 0, 0, 1)
#            display.show()

################# End of Application Class Definition #################
        

def setup():
    global pico_led, sdcard, synth, display, cardkb, view, application
    global switch_GP18, switch_GP19, switch_GP20, switch_GP21

    # LED on board
#    pico_led = digitalio.DigitalInOut(GP25)
    pico_led = digitalio.DigitalInOut(LED)
    pico_led.direction = digitalio.Direction.OUTPUT
    pico_led.value = True

    switch_GP18 = digitalio.DigitalInOut(GP18)
    switch_GP18.direction = digitalio.Direction.INPUT

    switch_GP19 = digitalio.DigitalInOut(GP19)
    switch_GP19.direction = digitalio.Direction.INPUT

    switch_GP20 = digitalio.DigitalInOut(GP20)
    switch_GP20.direction = digitalio.Direction.INPUT

    switch_GP21 = digitalio.DigitalInOut(GP21)
    switch_GP21.direction = digitalio.Direction.INPUT

    # OLED SSD1306
    print('setup')
    pico_led.value = True                    
    try:
        print('OLED setup')
        i2c0 = I2C(GP17, GP16)		# I2C-0 (SCL, SDA)
        display = OLED_SSD1306_class(i2c0, 0x3C, 128, 64)
        device_oled = adafruit_ssd1306.SSD1306_I2C(display.width(), display.height(), display.i2c())
        display.init_device(device_oled)
        display.fill(1)
        display.text('PICO Gt/Dr', 5, 15, 0, 2)
        display.text('(C) 2024 S.Ohira', 15, 35, 0)
        display.show()
        
    except:
        display = OLED_SSD1306_class(None)
        pico_led.value = False
        print('ERROR I2C1')
        for cnt in list(range(10)):
            pico_led.value = False
            sleep(0.5)
            pico_led.value = True
            sleep(1.0)

    print('Start application.')
    application = Application_class(display)

    # SD card
#    sdcard = sdcard_class()
#    sdcard.setup()

    # USB MIDI Device
    synth = USB_MIDI_Instrument_class()
    synth.set_all_notes_off()

    # Initial screen
    sleep(3.0)
    display.fill(0)
    application.show_settings()
    pico_led.value = False                    

######### MAIN ##########
if __name__=='__main__':
    # Setup
    pico_led = None
    switch_GP18 = None
    switch_GP19 = None
    switch_GP20 = None
    switch_GP21 = None
    sdcard = None
    synth = None
    display = None
    application = None
    setup()

    while True:
        try:
            # USB MIDI Device task
            application.do_task()

        except Exception as e:
            print('CATCH EXCEPTION:', e)
#            application.show_midi_channel(False, True)
#            application.show_message('ERROR: ' + str(e))
            for cnt in list(range(10)):
                pico_led.value = False
                sleep(0.5)
                pico_led.value = True
                sleep(1.0)

#            display.clear()
#            application.show_midi_channel(True, True)



