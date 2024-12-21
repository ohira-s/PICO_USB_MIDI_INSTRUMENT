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
        # USB MIDI device
        print('USB MIDI:', usb_midi.ports)
        self._usb_midi = [None] * 16
        for channel in list(range(16)):
            self._usb_midi[channel] = adafruit_midi.MIDI(midi_in=usb_midi.ports[0], midi_out=usb_midi.ports[1], out_channel=channel)

    def midi_send(self, midi_msg, channel=0):
        print('SEND:', channel, midi_msg)
        self._usb_midi[channel % 16].send(midi_msg)
        print('SENT')

    # MIDI-OUT to UART MIDI
    def midi_out(self, midi_msg, channel=0):
        self.midi_send(midi_msg, channel)

    def set_note_on(self, note_key, velosity, channel=0):
        self.midi_send(NoteOn(note_key, velosity, channel=channel), channel)

    def set_note_off(self, note_key, channel=0):
        self.midi_send(NoteOff(note_key, channel=channel), channel)

    def set_all_notes_off(self, channel=0):
        pass
    
    def set_reverb(self, channel, prog, level, feedback):
        status_byte = 0xB0 + channel
        midi_msg = bytearray([status_byte, 0x50, prog, status_byte, 0x5B, level])
        self.midi_out(midi_msg)
        if feedback > 0:
            midi_msg = bytearray([0xF0, 0x41, 0x00, 0x42, 0x12, 0x40, 0x01, 0x35, feedback, 0, 0xF7])
            self.midi_out(midi_msg)
            
    def set_chorus(self, channel, prog, level, feedback, delay):
        status_byte = 0xB0 + channel
        midi_msg = bytearray([status_byte, 0x51, prog, status_byte, 0x5D, level])
        self.midi_out(midi_msg)
        if feedback > 0:
            midi_msg = bytearray([0xF0, 0x41, 0x00, 0x42, 0x12, 0x40, 0x01, 0x3B, feedback, 0, 0xF7])
            self.midi_out(midi_msg)

        if delay > 0:
            midi_msg = bytearray([0xF0, 0x41, 0x00, 0x42, 0x12, 0x40, 0x01, 0x3C, delay, 0, 0xF7])
            self.midi_out(midi_msg)

    def set_vibrate(self, channel, rate, depth, delay):
        status_byte = 0xB0 + channel
        midi_msg = bytearray([status_byte, 0x63, 0x01, 0x62, 0x08, 0x06, rate, status_byte, 0x63, 0x01, 0x62, 0x09, 0x06, depth, status_byte, 0x63, 0x01, 0x62, 0x0A, 0x06, delay])
        self.midi_out(midi_msg)

    def set_pitch_bend(self, value, channel=0):
        self.midi_send(PitchBend(value), channel)

    def set_program_change(self, program, channel=0):
        self.midi_send(ProgramChange(program), channel)

    def set_pitch_bend_range(self, channel, value):
        status_byte = 0xB0 + channel
        midi_msg = bytearray([status_byte, 0x65, 0x00, 0x64, 0x00, 0x06, value & 0x7f])
        self.midi_out(midi_msg)

    def set_modulation_wheel(self, channel, modulation, value):
        status_byte = 0xB0 + channel
        midi_msg = bytearray([status_byte, 0x41, 0x00, 0x42, 0x12, 0x40, (0x20 | (channel & 0x0f)), modulation, value, 0x00, 0xF7])
        self.midi_out(midi_msg)

    def do_task(self):
        try:
            pico_led.value = True
            
            self.set_program_change(random.randint(0, 127), 1)

            print('NOTE ON')
            note0 = random.randint(60, 84)
            note1 = random.randint(60, 84)

            self.set_note_on(note0, 127, 0)
            print('NOTE ON DONE')
            self.set_pitch_bend(random.randint(0, 2000), 0)
            sleep(0.5)

            self.set_note_on(note1, 127, 1)
            sleep(0.5)
            
            print('NOTE OFF')
            self.set_note_off(note0, 0)
            sleep(0.5)
            self.set_note_off(note1, 1)
            print('DONE')
            sleep(0.5)
                
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
        self._ignore_midi = False
        
        self.DISPLAY_TYPE_SYNTH  = 0
        self.DISPLAY_TYPE_CONFIG = 1
        self._display_type = self.DISPLAY_TYPE_SYNTH
        
        self.COMMAND_MODE_NONE = -999
        self.COMMAND_MODE_U = -4
        self.COMMAND_MODE_R = -3
        self.COMMAND_MODE_C = -2
        self.COMMAND_MODE_V = -1
        self.COMMAND_MODE_CHANNEL = 0
        self.COMMAND_MODE_PROGRAM = 1
        self.COMMAND_MODE_REVERB_PROGRAM = 2
        self.COMMAND_MODE_REVERB_LEVEL = 4
        self.COMMAND_MODE_REVERB_FEEDBACK = 5
        self.COMMAND_MODE_CHORUS_PROGRAM = 6
        self.COMMAND_MODE_CHORUS_LEVEL = 7
        self.COMMAND_MODE_CHORUS_FEEDBACK = 8
        self.COMMAND_MODE_CHORUS_DELAY = 9
        self.COMMAND_MODE_VIBRATE_RATE = 10
        self.COMMAND_MODE_VIBRATE_DEPTH = 11
        self.COMMAND_MODE_VIBRATE_DELAY = 12
        self.COMMAND_MODE_FILE_LOAD = 13
        self.COMMAND_MODE_FILE_SAVE = 14
        
        self.COMMAND_MODE_MIDI_IN = 15
        self.COMMAND_MODE_MIDI_OUT_UART0 = 16
        self.COMMAND_MODE_MIDI_OUT_UART1 = 17

        self._command_mode = self.COMMAND_MODE_NONE
        
        self._hilights = [
            [],
            [self.COMMAND_MODE_VIBRATE_RATE, self.COMMAND_MODE_VIBRATE_DEPTH, self.COMMAND_MODE_VIBRATE_DELAY],
            [self.COMMAND_MODE_CHANNEL, self.COMMAND_MODE_CHORUS_PROGRAM, self.COMMAND_MODE_CHORUS_LEVEL, self.COMMAND_MODE_CHORUS_FEEDBACK, self.COMMAND_MODE_CHORUS_DELAY],
            [self.COMMAND_MODE_REVERB_PROGRAM, self.COMMAND_MODE_REVERB_LEVEL, self.COMMAND_MODE_REVERB_FEEDBACK],
            [self.COMMAND_MODE_MIDI_OUT_UART0, self.COMMAND_MODE_MIDI_OUT_UART1]
        ]

    def ignore_midi(self, flg=None):
        if flg is not None:
            self._ignore_midi = flg

        return self._ignore_midi

    def show_message(self, msg, x=0, y=0, color=1):
        self._display.text(msg, x, y, color)
        self._display.show()

    def channel(self, ch=None):
        if ch is not None:
            self._channel = ch % 16
            
        return self._channel
    
    def display_type(self, disp_type=None):
        if disp_type is not None:
            self._display_type = disp_type % 2
            
        return self._display_type
            
    def command_mode(self, command=None):
        if command is not None:
            self.show_midi_channel(False)
            self._command_mode = command
            self.show_midi_channel()

        return self._command_mode
        
    def show_midi_channel(self, disp=True, disp_all=False, channel=None):
        
        def show_a_parameter_synth(command, color):
            if command == self.COMMAND_MODE_CHANNEL:
                if synth.as_host():
                    self._display.text('[CH]an:' + ' {:02d}'.format(channel + 1), 0, 0, color[self.COMMAND_MODE_CHANNEL])
                else:
                    self._display.text('<CH>an:' + ' {:02d}'.format(channel + 1), 0, 0, color[self.COMMAND_MODE_CHANNEL])

            elif command == self.COMMAND_MODE_PROGRAM:
                if channel == 9:
                    self._display.text('[P]rog:DRM', 64, 0, color[self.COMMAND_MODE_PROGRAM])
                    self._display.text('DRUM SET', 64, 9, color[self.COMMAND_MODE_PROGRAM])
                else:
                    self._display.text('[P]rog:' + '{:03d}'.format(synth.midi_get_instrument(channel)), 64, 0, color[self.COMMAND_MODE_PROGRAM])
                    self._display.text(synth.get_instrument_name(synth.midi_get_instrument(channel)), 64, 9, color[self.COMMAND_MODE_PROGRAM])
            
            elif command == self.COMMAND_MODE_REVERB_PROGRAM:
                self._display.text('[RP]rg:' + '  {:01d}'.format(synth.midi_get_reverb(channel, 0)), 0, 9, color[self.COMMAND_MODE_REVERB_PROGRAM])
            
            elif command == self.COMMAND_MODE_REVERB_LEVEL:
                self._display.text('[RL]vl:' + '{:03d}'.format(synth.midi_get_reverb(channel, 1)), 0, 18, color[self.COMMAND_MODE_REVERB_LEVEL])
            
            elif command == self.COMMAND_MODE_REVERB_FEEDBACK:
                self._display.text('[RF]bk:' + '{:03d}'.format(synth.midi_get_reverb(channel, 2)), 64, 18, color[self.COMMAND_MODE_REVERB_FEEDBACK])
            
            elif command == self.COMMAND_MODE_CHORUS_PROGRAM:
                self._display.text('[CP]rg:' + '  {:01d}'.format(synth.midi_get_chorus(channel, 0)), 0, 27, color[self.COMMAND_MODE_CHORUS_PROGRAM])
            
            elif command == self.COMMAND_MODE_CHORUS_LEVEL:
                self._display.text('[CL]vl:' + '{:03d}'.format(synth.midi_get_chorus(channel, 1)), 64, 27, color[self.COMMAND_MODE_CHORUS_LEVEL])
            
            elif command == self.COMMAND_MODE_CHORUS_FEEDBACK:
                self._display.text('[CF]bk:' + '{:03d}'.format(synth.midi_get_chorus(channel, 2)), 0, 36, color[self.COMMAND_MODE_CHORUS_FEEDBACK])
            
            elif command == self.COMMAND_MODE_CHORUS_DELAY:
                self._display.text('[CD]ly:' + '{:03d}'.format(synth.midi_get_chorus(channel, 3)), 64, 36, color[self.COMMAND_MODE_CHORUS_DELAY])
            
            elif command == self.COMMAND_MODE_VIBRATE_RATE:
                self._display.text('[VR]at:' + '{:03d}'.format(synth.midi_get_vibrate(channel, 0)), 0, 45, color[self.COMMAND_MODE_VIBRATE_RATE])
            
            elif command == self.COMMAND_MODE_VIBRATE_DEPTH:
                self._display.text('[VD]pt:' + '{:03d}'.format(synth.midi_get_vibrate(channel, 1)), 64, 45, color[self.COMMAND_MODE_VIBRATE_DEPTH])
            
            elif command == self.COMMAND_MODE_VIBRATE_DELAY:
                self._display.text('[VdL]y:' + '{:03d}'.format(synth.midi_get_vibrate(channel, 2)), 0, 54, color[self.COMMAND_MODE_VIBRATE_DELAY])

            elif command == self.COMMAND_MODE_FILE_LOAD:
                fnum = synth.midi_file_number_exist()[1]
                if self.command_mode() == self.COMMAND_MODE_FILE_LOAD:
                    if color[self.COMMAND_MODE_FILE_LOAD] == 0:
                        if fnum >= 0:
                            self._display.text('[F]lod:' + '{:03d}'.format(synth.midi_file_number_exist()[1]), 64, 54, 0)
                        else:
                            self._display.text('[F]lod:NON', 64, 54, 0)

                        return

                if fnum >= 0:
                    self._display.text('[L|S]f:' + '{:03d}'.format(synth.midi_file_number_exist()[1]), 64, 54, 1)
                else:
                    self._display.text('[L|S]f:NON', 64, 54, 1)
 
            elif command == self.COMMAND_MODE_FILE_SAVE:
                if self.command_mode() == self.COMMAND_MODE_FILE_SAVE:
                    if color[self.COMMAND_MODE_FILE_SAVE] == 0:
                        self._display.text('[F]sav:' + '{:03d}'.format(synth.midi_file_number()), 64, 54, 0)
                        return

                self._display.text('[L|S]f:' + '{:03d}'.format(synth.midi_file_number()), 64, 54, 1)        
        

        def show_a_parameter_config(command, color):
            if command == self.COMMAND_MODE_MIDI_IN:
                if synth.midi_in_via_usb():
                    self._display.text('[MdIn]:USB', 64, 0, color[self.COMMAND_MODE_MIDI_IN])
                else:
                    self._display.text('[MdIn]:UAT', 64, 0, color[self.COMMAND_MODE_MIDI_IN])

            elif command == self.COMMAND_MODE_MIDI_OUT_UART0:
                if synth.midi_out_to(0):
                    self._display.text('[UA]t0:OUT', 0, 9, color[self.COMMAND_MODE_MIDI_OUT_UART0])
                else:
                    self._display.text('[UA]t0:OFF', 0, 9, color[self.COMMAND_MODE_MIDI_OUT_UART0])


            elif command == self.COMMAND_MODE_MIDI_OUT_UART1:
                if synth.midi_out_to(1):
                    self._display.text('[UaT]1:OUT', 64, 9, color[self.COMMAND_MODE_MIDI_OUT_UART1])
                else:
                    self._display.text('[UaT]1:OFF', 64, 9, color[self.COMMAND_MODE_MIDI_OUT_UART1])

            elif command < 0:
                if synth.as_host():
                    self._display.text('USB HOST',   0, 0, 1)
                else:
                    self._display.text('USB DEVICE', 0, 0, 1)
                    
                    
        def show_a_parameter(command, color):
            if self._display_type == self.DISPLAY_TYPE_SYNTH:
                show_a_parameter_synth(command, color)

            elif self._display_type == self.DISPLAY_TYPE_CONFIG:
                show_a_parameter_config(command, color)


        #--- show_midi_channel MAIN ---#
        channel = self.channel() if channel is None else channel % 16
        
        # Hilight parameter
        color = [1] * 18
        command = self.command_mode()
        hilight = command
        print('COMMAND=', command, ' ALL=', disp_all)
            
        if disp_all:
            if disp == False:
#                print('=== CLEAR')
                self._display.clear()
                return

            # Synthesize parameter setting display
            if self._display_type == self.DISPLAY_TYPE_SYNTH:
                if command == self.COMMAND_MODE_CHANNEL:
                    self._display.fill_rect(0, 0, 63, 8, 1)
                    color[self.COMMAND_MODE_CHANNEL] = 0

#	            print('=== SHOW ALL')
                for cmd in list(range(self.COMMAND_MODE_CHANNEL, self.COMMAND_MODE_FILE_LOAD + 1)):
                    show_a_parameter(cmd, color)

                if command == self.COMMAND_MODE_FILE_LOAD or command == self.COMMAND_MODE_FILE_SAVE:
                    show_a_parameter(command, color)
                else:
                    show_a_parameter(self.COMMAND_MODE_FILE_LOAD, color)
            
            # Configuration display
            elif self._display_type == self.DISPLAY_TYPE_CONFIG:
                show_a_parameter(-1, color)
                for cmd in list(range(self.COMMAND_MODE_MIDI_IN, self.COMMAND_MODE_MIDI_OUT_UART1 + 1)):
                    show_a_parameter(cmd, color)

            # Show display
            self._display.show()
            return

        # Disp the current one command
        if hilight >= 0:
            print('=== SHOW: ', command)
            color[hilight] = 0 if disp else 1
            if hilight == self.COMMAND_MODE_FILE_SAVE:
                hilight = self.COMMAND_MODE_FILE_LOAD

            hx = 0 if hilight % 2 == 0 else 64
            if self._display_type == self.DISPLAY_TYPE_SYNTH:
                hy = int(hilight / 2) * 9
            elif self._display_type == self.DISPLAY_TYPE_CONFIG:
                hy = int((hilight - 14) / 2) * 9
                
            self._display.fill_rect(hx, hy, 63, 8, 1 if disp else 0)
            if hilight == self.COMMAND_MODE_PROGRAM:
                self._display.fill_rect(hx, hy + 9, 63, 8, 1 if disp else 0)

            show_a_parameter(command, color)

        # Some command candidates
        elif hilight != -999:
            print('=== MULT: ', self._hilights[-hilight])
            for cmd in self._hilights[-hilight]:
                hx = 0 if cmd % 2 == 0 else 64
                if self._display_type == self.DISPLAY_TYPE_SYNTH:
                    hy = int(cmd / 2) * 9
                elif self._display_type == self.DISPLAY_TYPE_CONFIG:
                    hy = int((cmd - 14) / 2) * 9
                    
                self._display.fill_rect(hx, hy, 63, 8, 1 if disp else 0)        
                color[cmd] = 0 if disp else 1
                show_a_parameter(cmd, color)

        self._display.show()
            
################# End of Application Class Definition #################
        

def setup():
    global pico_led, sdcard, synth, display, cardkb, view, application

    # LED on board
#    pico_led = digitalio.DigitalInOut(GP25)
    pico_led = digitalio.DigitalInOut(LED)
    pico_led.direction = digitalio.Direction.OUTPUT
    pico_led.value = True

    # OLED SSD1306
#    print('setup')
#    try:
#        print('OLED setup')
#        i2c1 = I2C(GP7, GP6)		# I2C-1 (SCL, SDA)
#        display = OLED_SSD1306_class(i2c1, 0x3C, 128, 64)
#        device_oled = adafruit_ssd1306.SSD1306_I2C(display.width(), display.height(), display.i2c())
#        display.init_device(device_oled)
#        display.fill(1)
#        display.text('PICO SYNTH', 5, 15, 0, 2)
#        display.text('(C) 2024 S.Ohira', 15, 35, 0)
#        display.show()
#        
#    except:
#        display = OLED_SSD1306_class(None)
#        pico_led.value = False
#        print('ERROR I2C1')
#        for cnt in list(range(10)):
#            pico_led.value = False
#            sleep(0.5)
#            pico_led.value = True
#            sleep(1.0)

#    print('Start application.')
#    application = Application_class(display)

    # SD card
#    sdcard = sdcard_class()
#    sdcard.setup()

    # USB MIDI Device
    synth = USB_MIDI_Instrument_class()
    
#    application.show_midi_channel(True, True)
    synth.set_all_notes_off()


######### MAIN ##########
if __name__=='__main__':
    # Setup
    pico_led = None
    sdcard = None
    synth = None
#    display = None
#    application = None
    setup()

    while True:
        try:
            # USB MIDI Device task
            synth.do_task()

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



