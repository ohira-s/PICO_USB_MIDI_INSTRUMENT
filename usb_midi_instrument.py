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
#            Guitar Chrod Player test.
#     0.0.3: 12/25/2024
#            Drum Set Player test.
#     0.1.0: 12/25/2024
#            asyncio to catch pin transitions.
#     0.2.0: 12/26/2024
#            ADC test.
#     0.2.1: 12/27/2024
#            Piezo elements for guitar UI.
#     0.2.2: 01/06/2025
#            Guitar low and high chords.
#            Instrument change.
#     0.2.3: 01/07/2025
#            Fixing problem sending too many Note On events (chattering)
#            Guitar note name bug fixed.
#     0.2.4: 01/08/2025
#            8 buttons as digital inputs are available.
#     0.3.0: 01/08/2025
#            Separate play mode and settings mode.
#     0.4.0: 01/08/2025
#            Eliminate drum due to memory shortage.
#     0.4.1: 01/09/2025
#            Use hysteresis for ADC on/off voltage.
#            Pitch bend is available.
#            Design change of play mode screen.
#     0.4.2: 01/10/2025
#            Chord bank is available to extend assigning chords.
#            Octave change and apotasto are available.
#     0.4.3: 01/10/2025
#            Note on/off debugging.
#     0.5.0: 01/13/2025
#            Use another piezo element (Change velocity contrtol.)
#            Fixed the note on problem preliminary.
#     0.5.1: 01/15/2025
#            Configuration screen: Offset velocity, Pitch bend range,
#                                  Velocity curve.
#     1.0.0: 01/15/2025
#            Change the switchs' layout for the device box.
#     1.0.1: 01/16/2025
#            Load chord set from file.
#            Music player.
#            On note chord is available.
#     1.0.2: 01/17/2025
#            Improve the on-note chord generation.
#     1.0.3: 01/18/2025
#            Instrument selector moved to the config mode.
#            On-chord selector is available in the chord settings mode.
#            Remove all timing control codes to keep MIDI-SEND duration.
#     1.0.4: 01/20/2025
#            Improve the velocity curve more natural.
#            After touch effect (chorus).
#            MIDI channel selector is available.
#########################################################################

import asyncio
import keypad

from board import *
import digitalio
from busio import I2C			# for I2C
from time import sleep
#import os, re
import json

import usb_midi					# for USB MIDI
import adafruit_midi
from adafruit_midi.control_change import ControlChange
from adafruit_midi.note_off import NoteOff
from adafruit_midi.note_on import NoteOn
from adafruit_midi.pitch_bend import PitchBend
from adafruit_midi.program_change import ProgramChange

import board
import supervisor

import adafruit_ssd1306			# for SSD1306 OLED Display

from analogio import AnalogIn
import math


###############################################
# Catch digital pin transitions in async task
###############################################
async def catch_pin_transitions(pin, pin_name, callback_pressed=None, callback_released=None):
    # Catch pin transition
    with keypad.Keys((pin,), value_when_pressed=False) as keys:
        while True:
            event = keys.events.get()
            if event:
                if event.pressed:
#                    print("pin went low: " + pin_name)
                    if callback_pressed is not None:
                        callback_pressed(pin_name)
                        
                elif event.released:
#                    print("pin went high: " + pin_name)
                    if callback_released is not None:
                        callback_released(pin_name)

            # Gives away process time to the other tasks.
            # If there is no task, let give back process time to me.
            await asyncio.sleep(0.01)


##########################################
# Catch analog pin voltage in async task
##########################################
async def catch_adc_voltage(adc):
    while True:
        adc.adc_handler()

        # Gives away process time to the other tasks.
        # If there is no task, let give back process time to me.
        await asyncio.sleep(0.0)


#led_status = True
#async def led_flush():
#    global led_status, adc0
#    while True:
#        led_status = not led_status
#        pico_led.value = led_status
#
#        await asyncio.sleep(1.0)


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
#        print('DISPLAY')
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

    def show_message(self, msg, x=0, y=0, color=1):
        self._display.fill_rect(x, y, 128, 9, 0 if color == 1 else 1)
        self._display.text(msg, x, y, color)
#        self._display.show()

    def show(self):
        if self.is_available():
            self._display.show()

    def clear(self, color=0, refresh=True):
        self.fill(color)
        if refresh:
            self.show()
        
################# End of OLED SSD1306 Class Definition #################


###############
### ADC class
###############
_TICKS_PERIOD = const(1<<29)
_TICKS_MAX = const(_TICKS_PERIOD-1)
_TICKS_HALFPERIOD = const(_TICKS_PERIOD//2)

def ticks_add(ticks, delta):
    "Add a delta to a base number of ticks, performing wraparound at 2**29ms."
    return (ticks + delta) % _TICKS_PERIOD

def ticks_diff(ticks1, ticks2):
    "Compute the signed difference between two ticks values, assuming that they are within 2**28 ticks"
    diff = (ticks1 - ticks2) & _TICKS_MAX
    diff = ((diff + _TICKS_HALFPERIOD) & _TICKS_MAX) - _TICKS_HALFPERIOD
    return diff

def ticks_less(ticks1, ticks2):
    "Return true iff ticks1 is less than ticks2, assuming that they are within 2**28 ticks"
    return ticks_diff(ticks1, ticks2) < 0

class ADC_Device_class:
    def __init__(self, adc_pin, adc_name):
        self._adc = AnalogIn(adc_pin)
        self._4051_selectors = [digitalio.DigitalInOut(GP13), digitalio.DigitalInOut(GP14), digitalio.DigitalInOut(GP15)]
        self._4051_selectors[0].direction = digitalio.Direction.OUTPUT
        self._4051_selectors[1].direction = digitalio.Direction.OUTPUT
        self._4051_selectors[2].direction = digitalio.Direction.OUTPUT

        self._adc_name = adc_name
        self._note_on = [False] * 7				# 6 strings on guitar, and effector
        self._play_chord = False
#        self._voltage_gate = [(400.0,200.0)] * 8		# for Resistor elements
        self._voltage_gate = [(800.0,100.0)] * 8		# for Resistor elements
        self._adc_on = [False] * 8
        self._velocity_curve = 2.7
        self._on_counter = [0.0] * 8
        self._after_touch_count = 1000

    def adc(self):
        return self._adc

    def adc_name(self):
        return self._adc_name

    def after_touch_counter(self, cnt=None):
        if cnt is not None:
            self._after_touch_count = cnt
            
        return self._after_touch_count

    def velocity_curve(self, curve=None):
        if curve is not None:
            if curve < 1.5:
                curve = 1.5
            elif curve > 4.0:
                curve = 1.5
                
            self._velocity_curve = curve

        return self._velocity_curve

    def get_voltage(self, analog_channel):
        self._4051_selectors[0].value =  analog_channel & 0x1
        self._4051_selectors[1].value = (analog_channel & 0x2) >> 1
        self._4051_selectors[2].value = (analog_channel & 0x4) >> 2
#        voltage = self._adc.value * 5.0 / 65535
        voltage = self._adc.value * 4.55 / 65535
        return voltage

    def adc_handler(self):
        # Get voltages guitar strings
        velo_curve = self.velocity_curve()
        velo_factor = math.pow(velo_curve, 5)
        for string in list(range(8)):
            voltage_raw = self.get_voltage(string)
#            voltage = (math.pow(velo_curve, voltage) - 1) / velo_factor * 10000.0
            voltage = voltage_raw * (voltage_raw/3.55) * (voltage_raw/3.55) / velo_factor * 1000000.0
            if voltage > 5000.0:
                voltage = 5000.0

            # Pad is released
            if   voltage <= self._voltage_gate[string][1]:
                # Turn off after touch effect
                if self._on_counter[string] < 0:
                    synth.set_chorus(0, 0, 0, 0)

                self._on_counter[string] = 0

#                print('PAD RELEASED:', string, voltage)
                #Note a string off
                if string <= 5:
                    if self._note_on[string]:
                        self._note_on[string] = False
                        self._adc_on[string] = False
                
                # Note a chord off
                elif string == 7:
                    if self._play_chord:
                        self._play_chord = False
                        self._adc_on[string] = False

                # Finish pitch bend
                elif string == 6:
                    if self._note_on[string]:
                        self._note_on[string] = False
                        synth.set_pitch_bend(8192)
                        self._adc_on[string] = False                    
#                        print('PITCH BEND off')
                        
            # Pad is tapped
            elif voltage >= self._voltage_gate[string][0]:
                pass_voltage = self._voltage_gate[string][0]

                # velocity
#                velocity = int((voltage - pass_voltage) * 128.0 * 3.0 / (5000.0 - pass_voltage)) + 30
                velocity = int((voltage - pass_voltage) * 128.0 / (5000.0 - pass_voltage)) + 1
                if velocity > 127:
                    velocity = 127

                # First touch
                if self._adc_on[string] == False:
#                    self._on_counter[string] = 0
                    self._on_counter[string] = supervisor.ticks_ms()

#                    if string == 5:
#                        print('PAD PRESSED:', string, voltage_raw, voltage, velocity)

                    # Play a string
                    if string <= 5:
                        # Play a string
                        if self._note_on[string]:
                            print('PLAY a STRING OFF:', 5 - string)
                            self._note_on[string] = False
                            self._adc_on[string] = False

                        # Pitch bend off
                        if self._note_on[6]:
                            self._note_on[6] = False
                            synth.set_pitch_bend(8192)
                            self._adc_on[6] = False                    

                        print('PLAY a STRING:', 5 - string, voltage, velocity)
                        self._note_on[string] = True
                        chord_note = instrument_guitar.play_a_string(5 - string, velocity)
                        self._adc_on[string] = True
                    
                    # Play chord
                    elif string == 7:
                        if self._play_chord:
                            print('PLAY CHORD OFF')
                            self._play_chord = False
                            self._adc_on[string] = False

                        # Pitch bend off
                        if self._note_on[6]:
                            self._note_on[6] = False
                            synth.set_pitch_bend(8192)
                            self._adc_on[6] = False                    
                        
                        print('PLAY CHORD:', voltage, velocity)
                        instrument_guitar.play_chord(True, velocity)
                        self._play_chord = True
                        self._adc_on[string] = True
                    
                    # Pad 6
                    elif string == 6:
##                        application._DEBUG_MODE = not application._DEBUG_MODE
##                        application.show_message('DEBUG:' + ('on' if application._DEBUG_MODE else 'off'), 0, 54, 1)
                        if self._note_on[string]:
                            self._note_on[string] = False
                            synth.set_pitch_bend(8192)
                            self._adc_on[string] = False                    
                            print('PITCH BEND OFF')

                        bend_velocity = 9000 + int((7000 / 127) * velocity)
                        print('PITCH BEND ON:', bend_velocity, voltage, velocity)
                        synth.set_pitch_bend(bend_velocity)
                        self._note_on[string] = True
                        self._adc_on[string] = True
                        
                # Pad after touch
                else:
#                    self._on_counter[string] = self._on_counter[string] + 1
#                    if self._on_counter[string] == self._after_touch_count:
                    if self._on_counter[string] > 0 and ticks_diff(supervisor.ticks_ms(), self._on_counter[string]) >= self._after_touch_count:
                        synth.set_chorus(3, instrument_guitar.chorus_level(), instrument_guitar.chorus_feedback(), 0)
                        self._on_counter[string] = -1

#                    elif self._on_counter[string] > self._after_touch_count:
#                        self._on_counter[string] = self._after_touch_count


################# End of ADC Class Definition #################


#########################
### Imput Devices class
#########################
class Input_Devices_class:
    def __init__(self, display_obj):
        self._display = display_obj
        
        self._device_alias = {}
        self._device_info = {
                'BUTTON_1': True, 'BUTTON_2': True, 'BUTTON_3': True, 'BUTTON_4': True,
                'BUTTON_5': True, 'BUTTON_6': True, 'BUTTON_7': True, 'BUTTON_8': True,
                'PIEZO_A1': True, 'PIEZO_A2': True, 'PIEZO_A3': True, 'PIEZO_A4': True,
                'PIEZO_A5': True, 'PIEZO_A6': True, 'PIEZO_A7': True, 'PIEZO_A8': True,
                'PIEZO_B1': True, 'PIEZO_B2': True, 'PIEZO_B3': True, 'PIEZO_B4': True,
                'PIEZO_B5': True, 'PIEZO_B6': True, 'PIEZO_B7': True, 'PIEZO_B8': True
            }

    # Device alias names list
    def device_alias(self, alias_name, device_name=None):
        if device_name is not None:
            self._device_alias[alias_name] = device_name
        
        return self._device_alias[alias_name]

    # Get a device information
    def device_info(self, device_name=None, val=None):
        if device_name is None:
            return self._device_info

        if not device_name in self._device_info.keys():
            device_name = self.device_alias(device_name)

        if device_name in self._device_info.keys():
            if val is not None:
                self._device_info[device_name] = val
                
            return self._device_info[device_name]
        
        return None

    # Call from asyncio just after a pin transition catched, never call this directly
    def button_pressed(self, device_name):
        self.device_info(device_name, False)
        application.do_task()

    # Call from asyncio just after a pin transition catched, never call this directly
    def button_released(self, device_name):
        self.device_info(device_name, True)
        application.do_task()
        
################# End of Input Devices Class Definition #################


################################
### Unit-MIDI Instrument class
################################
send_note_on = []
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

        self._note_key = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

        # USB MIDI device
#        print('USB MIDI:', usb_midi.ports)
        self._midi_channel = 0
        self._send_note_on = [[]] * 16
        self._usb_midi = [None] * 16
#        self._usb_midi[0] = adafruit_midi.MIDI(midi_in=usb_midi.ports[0], midi_out=usb_midi.ports[1], out_channel=0)
        for channel in list(range(16)):
            self._usb_midi[channel] = adafruit_midi.MIDI(midi_in=usb_midi.ports[0], midi_out=usb_midi.ports[1], out_channel=channel)

    def midi_channel(self, channel=None):
        if channel is not None:
            self._midi_channel = channel % 15
            
        return self._midi_channel

    # Get instrument name
    def get_instrument_name(self, program, gmbank=0):
        if program < 0:
            return '---'

        try:
            # PICO internal memory file system
            with open('SYNTH/MIDIFILE/GM0.TXT', 'r') as f:
                prg = -1
                for instrument in f:
                    prg = prg + 1
                    if prg == program:
                        return instrument.strip()

        except Exception as e:
            application.show_message('GM LIST:' + e)
            sleep(5.0)
            display.clear()
            application.show_info()

        return '???'

    # Get note name
    def get_note_name(self, note):
        name = self._note_key[note % 12]
        octave = int(note / 12) - 1
        if octave >= 0:
            name = name + str(octave)
        
        return name

    # MIDI sends to USB as a USB device
    def midi_send(self, midi_msg, channel=None):
        if channel is None:
            channel = self.midi_channel()

        print('MIDI SEND:', channel, midi_msg)
#        print('INSTANCE:', isinstance(midi_msg, NoteOn), isinstance(midi_msg, NoteOff), self._send_note_on[channel])
        if isinstance(midi_msg, NoteOn):
            if midi_msg.note in self._send_note_on[channel]:
                self._usb_midi[channel].send(NoteOff(midi_msg.note, channel=channel))
#                print('MIDI NOTE OFF:', midi_msg.note)

            else:
                self._send_note_on[channel].append(midi_msg.note)
                
            pico_led.value = True

        elif isinstance(midi_msg, NoteOff):
#            print('GET NOTE OFF:' + str(midi_msg.note))
            if midi_msg.note in self._send_note_on[channel]:
                self._send_note_on[channel].remove(midi_msg.note)

            pico_led.value = False

        # Send a MIDI message
        self._usb_midi[channel].send(midi_msg)

        # DEBUG
        if application._DEBUG_MODE:
            if isinstance(midi_msg, NoteOn):
                if midi_msg.velocity == 0:
                    application.show_message('off:' + str(midi_msg.note) + '/' + str(midi_msg.velocity), 0, 55, 1)
                else:
                    application.show_message('ON :' + str(midi_msg.note) + '/' + str(midi_msg.velocity), 0, 55, 1)
            elif isinstance(midi_msg, NoteOff):
                application.show_message('OFF:' + str(midi_msg.note), 0, 55, 1)

    # Send note on
    def set_note_on(self, note_key, velocity, channel=None):
        if channel is None:
            channel = self.midi_channel()

        self.midi_send(NoteOn(note_key, velocity, channel=channel), channel)

    # Send note off
    def set_note_off(self, note_key, channel=None):
        if channel is None:
            channel = self.midi_channel()

        self.midi_send(NoteOff(note_key, channel=channel), channel)
#        self.midi_send(NoteOn(note_key, 0, channel=channel), channel)

    # Send all notes off
    def set_all_notes_off(self, channel=None):
        pass
    
    def set_reverb(self, prog, level, feedback, channel=None):
        pass
#        status_byte = 0xB0 + channel
#        midi_msg = bytearray([status_byte, 0x50, prog, status_byte, 0x5B, level])
#        self.midi_out(midi_msg)
#        if feedback > 0:
#            midi_msg = bytearray([0xF0, 0x41, 0x00, 0x42, 0x12, 0x40, 0x01, 0x35, feedback, 0, 0xF7])
#            self.midi_out(midi_msg)
            
    def set_chorus(self, prog, level, feedback, delay, channel=None):
        if channel is None:
            channel = self.midi_channel()

        if prog is not None:
            self.midi_send(ControlChange(self.ControlChange_Chorus_Program,  prog, channel=channel),     channel)

        if level is not None:
            self.midi_send(ControlChange(self.ControlChange_Chorus_Level,    level, channel=channel),    channel)

        if feedback is not None:
            self.midi_send(ControlChange(self.ControlChange_Chorus_Feedback, feedback, channel=channel), channel)

        if delay is not None:
            self.midi_send(ControlChange(self.ControlChange_Chorus_Delay,    delay, channel=channel),    channel)

    def set_vibrate(self, rate, depth, delay, channel=None):
        if channel is None:
            channel = self.midi_channel()

        if rate is not None:
            self.midi_send(ControlChange(self.ControlChange_Vibrate_Rate,  rate, channel=channel),  channel)

        if depth is not None:
            self.midi_send(ControlChange(self.ControlChange_Vibrate_Depth, depth, channel=channel), channel)

        if delay is not None:
            self.midi_send(ControlChange(self.ControlChange_Vibrate_Delay, delay, channel=channel), channel)

    # Send program change
    def set_program_change(self, program, channel=None):
        if program >= 0 and program <= 127:
            if channel is None:
                channel = self.midi_channel()

            self.midi_send(ProgramChange(program, channel=channel), channel)
###            synth._usb_midi[channel].send(NoteOff(0, channel=channel))		# THIS CODE IS NEEDED TO NOTE ON IMMEDIATELY

    # Send pitch bend value
    def set_pitch_bend(self, value, channel=None):
        if channel is None:
            channel = self.midi_channel()

        self.midi_send(PitchBend(value, channel=channel), channel)
###        synth._usb_midi[channel].send(NoteOff(0, channel=channel))		# THIS CODE IS NEEDED TO NOTE ON IMMEDIATELY

    # Send pitch bend range value
    def set_pitch_bend_range(self, value, channel=None):
        if channel is None:
            channel = self.midi_channel()

        self.midi_send(ControlChange(0x65, 0, channel=channel), channel)			# RPN LSB
        self.midi_send(ControlChange(0x64, 0, channel=channel), channel)			# RPN MSB
        self.midi_send(ControlChange(0x06, value & 0x7f, channel=channel), channel)	# PRN DATA ENTRY
###        synth._usb_midi[channel].send(NoteOff(0, channel=channel))		# THIS CODE IS NEEDED TO NOTE ON IMMEDIATELY

#        status_byte = 0xB0 + channel
#        midi_msg = bytearray([status_byte, 0x65, 0x00, 0x64, 0x00, 0x06, value & 0x7f])
#        self.midi_out(midi_msg)

    def set_modulation_wheel(self, modulation, value, channel=None):
        pass
#        self.midi_send(ControlChange(modulation, value, channel=channel), channel)

################# End of Unit-MIDI Class Definition #################


##################
### Guitar class
##################
class Guitar_class:
    def __init__(self, display_obj):
        self._display = display_obj

        # Note sign like A#
        self.PARAM_GUITAR_ROOTs = synth._note_key
#        self.PARAM_GUITAR_CHORDs = ['M', 'M7', '7', '6', 'aug', 'm', 'mM7', 'm7', 'm6', 'm7-5', 'add9', 'sus4', '7sus4', 'dim7']
#        self.GUITAR_STRINGS_OPEN = [16,11, 7, 2, -3, -8]	# 1st String: E, B, G, D, A, E: 6th String

        #Chord   : LO:1  2  3  4  5  6  HI:1  2  3  4  5  6				# Strings
        #  {'CM' : ([ 0, 1, 0, 2, 3,-1], [ 3, 5, 5, 5, 3,-1]),...}		# Fret number to press (-1 is not to play it)
        self.PARAM_GUITAR_CHORDs = None
        self.GUITAR_STRINGS_OPEN = None
        self.CHORD_STRUCTURE = None
        with open('SYNTH/MIDIFILE/chords.json', 'r') as f:
            data = json.load(f)
            self.PARAM_GUITAR_CHORDs = data['CHORDS']				# M, M7, ...
            self.GUITAR_STRINGS_OPEN = data['STRING_NOTES']			# Note offset of Strings [1..6] opened (B=-1,C=0,C#=1)
            self.CHORD_STRUCTURE = data['CHORD_DEFINITIONS']		# Positions to press frets for each chord

        self.PARAM_ALL = -1
        self.PARAM_GUITAR_PROGRAM = 0
        self.PARAM_GUITAR_ROOT = 1
        self.PARAM_GUITAR_CHORD = 2
        self.PARAM_GUITAR_CHORDSET = 3
        self.PARAM_GUITAR_CAPOTASTO = 4
        self.PARAM_GUITAR_OCTAVE = 5
        self.PARAM_GUITAR_ONCHORD = 6
##        self.PARAM_GUITAR_EFFECTOR = 9
        
        self.value_guitar_root = 0		# Current root
        self.value_guitar_chord = 0		# Current chord
        self.value_guitar_on_note = -1	# Current on note (-1 means no note)
        
        self._programs = [-1, 24, 25, 26, 27, 28, 29, 30, 31, 104, 105, 106, 107]	# Instrument number in GM
        self._program_number = 0  		# Steel Guitar
        self._scale_number = 4			# Normal guitar scale
        self._chord_position = 0		# 0: Low chord, 1: High chord
        self._capotasto = 0				# No capotasto (-12..0..+12)
        self._pitch_bend_range = 2		# 1 is semitone (0..12)
        self._offset_velocity = 30		# Note on velocity offset (0,10,20,...,100)
        self._chorus_level = 80
        self._chorus_feedback = 20
        self._midi_channel = 0			# MIDI channel to send messages

        # Chord on button
        self._chord_bank = 0
        self._chord_on_button_number = 0
        self._chord_on_button = [
                {'ROOT': 0, 'CHORD': 0, 'POSITION': 0, 'ON_NOTE': -1, 'SCALE': 4},		# CM Low
                {'ROOT': 7, 'CHORD': 0, 'POSITION': 0, 'ON_NOTE': -1, 'SCALE': 4},		# GM Low
                {'ROOT': 9, 'CHORD': 5, 'POSITION': 0, 'ON_NOTE': -1, 'SCALE': 4},		# Am Low
                {'ROOT': 4, 'CHORD': 5, 'POSITION': 0, 'ON_NOTE': -1, 'SCALE': 4},		# Em Low
                {'ROOT': 5, 'CHORD': 0, 'POSITION': 0, 'ON_NOTE': -1, 'SCALE': 4},		# FM Low
                {'ROOT': 2, 'CHORD': 5, 'POSITION': 0, 'ON_NOTE': -1, 'SCALE': 4},		# Dm Low
                {'ROOT': 0, 'CHORD': 0, 'POSITION': 1, 'ON_NOTE': -1, 'SCALE': 4},		# CM High
                {'ROOT': 7, 'CHORD': 0, 'POSITION': 1, 'ON_NOTE': -1, 'SCALE': 4},		# GM High
                {'ROOT': 9, 'CHORD': 5, 'POSITION': 1, 'ON_NOTE': -1, 'SCALE': 4},		# Am High
                {'ROOT': 4, 'CHORD': 5, 'POSITION': 1, 'ON_NOTE': -1, 'SCALE': 4},		# Em High
                {'ROOT': 5, 'CHORD': 0, 'POSITION': 1, 'ON_NOTE': -1, 'SCALE': 4},		# FM High
                {'ROOT': 2, 'CHORD': 5, 'POSITION': 1, 'ON_NOTE': -1, 'SCALE': 4}		# Dm High
            ]

        # Preset chord set files
        self._chord_file_num = -1
        self._chord_files = []
        with open('SYNTH/CHORD/list.json', 'r') as f:
            self._chord_files = json.load(f)

#        print(self._chord_files)

        # Music data
        self._music_chord_num = -1
        self._music = []
        self._music_num = -1
        self._music_list = []
        with open('SYNTH/MUSIC/list.json', 'r') as f:
            self._music_list = json.load(f)

#        print(self._music_list)

        # Device aliases for play mode
        input_device.device_alias('GUITAR_CHORD_BANK', 'BUTTON_1')		# Chord set bank
        input_device.device_alias('GUITAR_CHORD1', 'BUTTON_2')
        input_device.device_alias('GUITAR_CHORD2', 'BUTTON_3')
        input_device.device_alias('GUITAR_CHORD3', 'BUTTON_4')
        input_device.device_alias('GUITAR_CHORD4', 'BUTTON_5')
        input_device.device_alias('GUITAR_CHORD5', 'BUTTON_6')
        input_device.device_alias('GUITAR_CHORD6', 'BUTTON_7')

        # Device aliases for settings mode
        input_device.device_alias('GUITAR_BUTTON',     'BUTTON_1')
        input_device.device_alias('GUITAR_ROOT',       'BUTTON_2')
        input_device.device_alias('GUITAR_CHORD',      'BUTTON_3')
        input_device.device_alias('GUITAR_POSITION',   'BUTTON_4')
        input_device.device_alias('GUITAR_ONCHORD',    'BUTTON_5')
        input_device.device_alias('GUITAR_OCTAVE',     'BUTTON_6')
        input_device.device_alias('GUITAR_CHORD_FILE', 'BUTTON_7')

        # Device aliases for config mode
        input_device.device_alias('GUITAR_BASE_VOLUME',      'BUTTON_2')
        input_device.device_alias('GUITAR_VELOCITY_CURVE',   'BUTTON_3')
        input_device.device_alias('GUITAR_PITCH_BEND_RANGE', 'BUTTON_4')
        input_device.device_alias('GUITAR_CHORUS_LEVEL',     'BUTTON_5')
        input_device.device_alias('GUITAR_CHORUS_FEEDBACK',  'BUTTON_6')
        input_device.device_alias('GUITAR_AFTER_TOUCH',      'BUTTON_7')

        input_device.device_alias('GUITAR_CAPOTASTO',        'BUTTON_2')
        input_device.device_alias('GUITAR_INSTRUMENT',       'BUTTON_3')
        input_device.device_alias('GUITAR_MIDI_CHANNEL',     'BUTTON_4')

        # Device aliases for music mode
        input_device.device_alias('GUITAR_CHORD_NEXT', 'BUTTON_1')
        input_device.device_alias('GUITAR_MUSIC_PREV', 'BUTTON_2')
        input_device.device_alias('GUITAR_MUSIC_NEXT', 'BUTTON_3')
        input_device.device_alias('GUITAR_CHORD_PREV', 'BUTTON_5')
        input_device.device_alias('GUITAR_CHORD_TOP',  'BUTTON_6')
        input_device.device_alias('GUITAR_CHORD_LAST', 'BUTTON_7')

    def setup(self):
        display.fill(0)
        synth.set_program_change(self.program_number()[1])
        synth.set_pitch_bend_range(self.pitch_bend_range())
        self.show_info(self.PARAM_ALL, 1)

    def setup_settings(self):
        display.fill(0)
        current_button = self.chord_on_button()
        self.set_chord_on_button(current_button)
        synth.set_program_change(self.program_number()[1]) 
        self.show_info_settings(self.PARAM_ALL, 1)

    def setup_config1(self):
        display.fill(0)
        self.show_info_config1(self.PARAM_ALL, 1)

    def setup_config2(self):
        display.fill(0)
        self.show_info_config2(self.PARAM_ALL, 1)

    def setup_music(self):
        display.fill(0)
        self.show_info_music(self.PARAM_ALL, 1)

    def midi_channel(self, channel=None):
        if channel is not None:
            self._midi_channel = channel % 16
            synth.midi_channel(self._midi_channel)

        return self._midi_channel

    def chorus_level(self, level=None):
        if level is not None:
            self._chorus_level = level % 128
            
        return self._chorus_level

    def chorus_feedback(self, fback=None):
        if fback is not None:
            self._chorus_feedback = fback % 128
            
        return self._chorus_feedback

    def capotasto(self, capo=None):
        if capo is not None:
            if capo < -12:
                capo = 12
            elif capo > 12:
                capo = -12
                
            self._capotasto = capo
            
        return self._capotasto

    def offset_velocity(self, offset=None):
        if offset is not None:
            self._offset_velocity = offset % 110
            
        return self._offset_velocity

    def program_number(self, prog=None):
        if prog is not None:
            self._program_number = prog % len(self._programs)
        
        return (self._program_number, self._programs[self._program_number])

    def abbrev(self, instrument):
        if instrument.find(' Guitar ') < 0:
            return instrument
        
        if len(instrument) <= 14:
            return instrument
        
        instrument = instrument.replace(' Guitar', ' GT')
        chars = len(instrument)
        if chars <= 14:
            return instrument
        
        dels = chars - 14
        guitar_pos = instrument.find(' GT')
        if guitar_pos <= dels:
            return instrument
        
        return instrument[0:guitar_pos][0:guitar_pos - dels] + instrument[guitar_pos:]

    def chord_on_button(self, button=None, root=None, chord=None, position=None, scale=None, on_note=None):
        if button is None:
            return self._chord_on_button_number
        
        button = button % len(self._chord_on_button)
        self._chord_on_button_number = button
        
        if root is not None:
            self._chord_on_button[button]['ROOT'] = root % 12
        
        if chord is not None:
            self._chord_on_button[button]['CHORD'] = chord % len(self.PARAM_GUITAR_CHORDs)
        
        if position is not None:
            self._chord_on_button[button]['POSITION'] = position % 2
        
        if scale is not None:
            self._chord_on_button[button]['SCALE'] = scale % 9
        
        if on_note is not None:
            self._chord_on_button[button]['ON_NOTE'] = -1 if on_note < 0 else on_note % 12
        
        return self._chord_on_button[button]

    def chord_file(self, file_num=None):
        if file_num is None or len(self._chord_files) <= 0:
            return self._chord_file_num

        try:
            self._chord_file_num = file_num % len(self._chord_files)

            with open('SYNTH/CHORD/' + self._chord_files[self._chord_file_num][0], 'r') as f:
                json_data = json.load(f)

            self._chord_files[self._chord_file_num][1] = json_data['NAME']
            cd = -1
            for chord in json_data['CHORDS']:
                cd = cd + 1
                
                data = chord[0]
                index = self.PARAM_GUITAR_ROOTs.index(data) if data in self.PARAM_GUITAR_ROOTs else 0
                self._chord_on_button[cd]['ROOT'] = index

                data = 'M' if len(chord[1]) == 0 else chord[1]
                index = self.PARAM_GUITAR_CHORDs.index(data) if data in self.PARAM_GUITAR_CHORDs else 0
                self._chord_on_button[cd]['CHORD'] = index

                data = 'LOW' if len(chord[1]) == 0 else chord[2]
                self._chord_on_button[cd]['POSITION'] = 1 if data == 'HIGH' else 0
                
                data = chord[3]
                if data in self.PARAM_GUITAR_ROOTs:
                    index = self.PARAM_GUITAR_ROOTs.index(data) if data in self.PARAM_GUITAR_ROOTs else 0
                else:
                    index = -1
                    
                self._chord_on_button[cd]['ON_NOTE'] = index
                
                self._chord_on_button[cd]['SCALE'] = chord[4]
                        
            return self._chord_file_num

        except Exception as e:
            print(e, self._chord_files[self._chord_file_num][0])
            return self._chord_file_num

    def music_file(self, file_num=None):
        if file_num is None or len(self._music_list) <= 0:
            return self._music_num

        try:
            if file_num < 0:
                file_num = -1
                
            self._music_num = file_num % len(self._music_list)
#            print("MUSIC FILE:", file_num, len(self._music_list), self._music_num)
            with open('SYNTH/MUSIC/' + self._music_list[self._music_num][0], 'r') as f:
                json_data = json.load(f)

            self._music_list[self._music_num][1] = json_data['NAME']
            self._music = []
            for chord in json_data['MUSIC']:
                chord[0] = self.PARAM_GUITAR_ROOTs.index(chord[0]) if chord[0] in self.PARAM_GUITAR_ROOTs else 0
                chord[1] = self.PARAM_GUITAR_CHORDs.index(chord[1]) if chord[1] in self.PARAM_GUITAR_CHORDs else 0
                chord[2] = 1 if chord[2] == 'HIGH' else 0
                chord[3] = self.PARAM_GUITAR_ROOTs.index(chord[3]) if chord[3] in self.PARAM_GUITAR_ROOTs else -1
                self._music.append(chord)
            
            if len(self._music) > 0:
                self._music.append([-1, -1, 0, -1])		# Sign at the end of music
                self.music_chord(0)
            else:
                self._music_chord_num = -1

#            print('MUSIC ', self._music_num, self._music)
            return self._music_num
            
        except Exception as e:
            print(e, self._music_list[self._music_num][0])
            return self._music_num

    def music_chord(self, chord_num=None):
        if chord_num is not None and len(self._music) > 0:
            if chord_num < 0:
                chord_num = len(self._music) - 2		# The last is the sign data at the end of music
                
            self._music_chord_num = chord_num % len(self._music)
            if self._music_chord_num < len(self._music) - 1: 
                chord = self._music[self._music_chord_num]
                self.value_guitar_root    = chord[0]	# Current root
                self.value_guitar_chord   = chord[1]	# Current chord
                self._chord_position      = chord[2]	# 0: Low chord, 1: High chord
                self.value_guitar_on_note = chord[3]	# on-note
                self._scale_number        = chord[4]	# Scale

        return self._music_chord_num

    def pitch_bend_range(self, bend_range=None):
        if bend_range is not None:
            self._pitch_bend_range = bend_range % 13
            synth.set_pitch_bend_range(self._pitch_bend_range)
            
        return self._pitch_bend_range

    def chord_bank(self, bank=None):
        if bank is not None:
            self._chord_bank = bank % 2
            
        return self._chord_bank

    def set_chord_on_button(self, button):
        button_data = self._chord_on_button[button]
        self.value_guitar_root = button_data['ROOT']		# Current root
        self.value_guitar_chord = button_data['CHORD']		# Current chord
        self.value_guitar_on_note = button_data['ON_NOTE']	# On note
        self._chord_position = button_data['POSITION']		# 0: Low chord, 1: High chord
        self._scale_number = button_data['SCALE']

    def guitar_string_note(self, strings, frets):
        if frets < 0:
            return None
        
        return self.GUITAR_STRINGS_OPEN[strings] + frets

    def scale_number(self, scale=None):
        if scale is not None:
            self._scale_number = scale % 9
            
        return self._scale_number

    def chord_position(self, pos=None):
        if pos is not None:
            pos = pos % 2                
            self._chord_position = pos
        
        return self._chord_position
    
    def root_note(self, scale=None):
        if scale is None:
            scale = self.scale_number()
            
        return (scale + 1) * 12 + self.value_guitar_root

    def chord_name(self, chord_position=None, root=None, chord=None, scale=None):
        if chord_position is None:
            chord_position = self.chord_position()
            
        if root is None:
            root = self.root_note(scale)

        if chord is None:
            chord = self.value_guitar_chord
            chord = chord % 14							# SOS DEBUG
        
#        print('root, chord=', root, chord)
        root_name = self.PARAM_GUITAR_ROOTs[root % 12]
        chord_name = root_name + self.PARAM_GUITAR_CHORDs[chord]
#        print('CHORD NAME: ', chord_name, self.CHORD_STRUCTURE[chord_name][chord_position])
        return (root_name, chord_name)

    def chord_notes(self, chord_position=None, root=None, chord=None, scale=None):
        if chord_position is None:
            chord_position = self.chord_position()
            
        (root_name, chord_name) = self.chord_name(chord_position, root, chord, scale)
            
#        print('CHORD NAME: ', chord_name, self.CHORD_STRUCTURE[chord_name][chord_position])
        root_mod = -1 if self.value_guitar_on_note < 0 else self.PARAM_GUITAR_ROOTs.index(root_name) % 12
        notes = []
        fret_map = self.CHORD_STRUCTURE[chord_name][chord_position]
#        for strings in list(range(6)):
        for strings in list(range(5, -1, -1)):
            note = self.guitar_string_note(strings, fret_map[strings])
            if note is not None:
                # Replace the root note with the on-chord note
                if note % 12 == root_mod:
                    notes.insert(0, -1)
                    root_mod = -1
#                    print('IGNORE ROOT for ON-NOTE:', note + (self._scale_number + 1) * 12, self.value_guitar_on_note)
                else:
                    notes.insert(0, note + (self._scale_number + 1) * 12)
            else:
                notes.insert(0, -1)
        
        # Simple chord
        if self.value_guitar_on_note < 0:
            notes.append(-1)
            
        # A chord with on-note like C on D
        else:
            # Make a base note
            on_note = self.value_guitar_on_note + (self._scale_number + 1) * 12
            if on_note in notes:
                notes.append(self.value_guitar_on_note + self._scale_number * 12)
            else:
                notes.append(self.value_guitar_on_note + (self._scale_number + 1) * 12)
            
        return notes

    # Play a string
    def play_a_string(self, string, string_velocity, channel=None):
#        print('PLAY a STRING VELO:', string_velocity)
        capo = self.capotasto()
        if channel is None:
            channel = self.midi_channel()

        # Play strings in the current chord
        string_notes = self.chord_notes()
        chord_note = string_notes[string]
        if chord_note >= 0:
            # Note on
            if string_velocity > 0:
                velocity = string_velocity + self.offset_velocity()
                synth.set_note_on(chord_note + capo, velocity if velocity <= 127 else 127, channel)
                synth._usb_midi[channel].send(NoteOff(0, channel=channel))		# THIS CODE IS NEEDED TO NOTE ON IMMEDIATELY
            # Note off
            else:
                synth.set_note_off(chord_note + capo, 0)
                synth._usb_midi[channel].send(NoteOff(0, channel=channel))		# THIS CODE IS NEEDED TO NOTE ON IMMEDIATELY

        return chord_note

    def play_chord(self, play=True, velocity=127, channel=None):
        try:
            capo = self.capotasto()
            notes_in_chord = self.chord_notes()        
            if channel is None:
                channel = self.midi_channel()

            # Play a chord selected
            if play:
                print('CHORD NOTEs ON : ', notes_in_chord)
                velocity = velocity + self.offset_velocity()
                if velocity > 127:
                    velocity = 127
                    
                count_nt = 0
                for nt in notes_in_chord:
                    if nt >= 0:
                        synth.set_note_on(nt + capo, velocity, channel)
                        synth._usb_midi[channel].send(NoteOff(0, channel=channel))	# THIS CODE IS NEEDED TO NOTE ON IMMEDIATELY
                        count_nt = count_nt + 1
                        sleep(0.005)

                if count_nt % 2 == 1:											# THIS CODE IS NEEDED TO NOTE ON IMMEDIATELY
                    synth._usb_midi[channel].send(NoteOff(0, channel=channel))	# THIS CODE IS NEEDED TO NOTE ON IMMEDIATELY

            # Notes in chord off
            else:
                # Notes off
                print('CHORD NOTEs OFF: ', notes_in_chord)
                count_nt = 0
                for nt in notes_in_chord:
                    if nt >= 0:
                        synth.set_note_off(nt + capo, 0)
                        synth._usb_midi[channel].send(NoteOff(0, channel=channel))	# THIS CODE IS NEEDED TO NOTE ON IMMEDIATELY
                        count_nt = count_nt + 1
                        sleep(0.005)

                if count_nt % 2 == 1:											# THIS CODE IS NEEDED TO NOTE ON IMMEDIATELY
                    synth._usb_midi[channel].send(NoteOff(0, channel=channel))	# THIS CODE IS NEEDED TO NOTE ON IMMEDIATELY

        except Exception as e:
            print('EXCEPTION: ', e)

    def show_info(self, param, color):
        if param == self.PARAM_ALL:
            self._display.show_message('---GUITAR PLAY---', 0, 0, color)
            
        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_CHORDSET:
            bank = self.chord_bank() * 6
            x = 0
            y = 36
            for i in list(range(6)):
                button_data = self._chord_on_button[i + bank]
                (root_name, chord_name) = self.chord_name(button_data['POSITION'], button_data['ROOT'], button_data['CHORD'], button_data['SCALE'])

                if i == 3:
                    x = 64
                
                if button_data['ON_NOTE'] >= 0:
                    on_note = '/' + self.PARAM_GUITAR_ROOTs[button_data['ON_NOTE']]
                    
                else:
                    on_note = ''
                    
                self._display.show_message(chord_name + ' ' + ('L' if button_data['POSITION'] == 0 else 'H') + on_note, x, y + (i % 3) * 9, color)
                
        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_PROGRAM:
            self._display.show_message(self.abbrev(synth.get_instrument_name(self.program_number()[1])), 0, 18, color)
            
        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_ROOT:
            self._display.show_message(self.PARAM_GUITAR_ROOTs[self.value_guitar_root], 0, 9, color)

        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_CHORD or param == self.PARAM_GUITAR_ROOT:
            self._display.show_message(self.PARAM_GUITAR_CHORDs[self.value_guitar_chord] + '  ' + ('L' if self.chord_position() == 0 else 'H') + ' {:+d}'.format(self.capotasto()), 12, 9, color)

            # On-note
            if self.value_guitar_on_note >= 0:
                st = synth.get_note_name(self.value_guitar_on_note) + str(self._scale_number)
                if len(st) <= 2:
                    st = st + ' '
            else:
                st = '-- '
                
#            print('ON NOTE:', self.value_guitar_on_note, '/' + st + '/')
            for y in list(range(3)):
                self._display.show_message(st[y], 72, 9 + y * 9, color)
                
            # Notes in chord
            notes = self.chord_notes()
            print('NOTES=', notes)
            for i in list(range(6)):
                nt = notes[5-i]
                if nt < 0:
                    st = 'xx '
                else:
                    st = synth.get_note_name(nt)
                    if len(st) <= 2:
                        st = st + ' '
                
                for y in list(range(3)):
                    self._display.show_message(st[y], 80 + i * 8, 9 + y * 9, color)

        self._display.show()

    def show_info_settings(self, param, color):
        if param == self.PARAM_ALL:
            self._display.show_message('--GUITAR SETTINGS--', 0, 0, color)
            self._display.show_message('BUTTN: ' + str(self._chord_on_button_number + 1), 0, 9, color)
            index = self.chord_file()
            self._display.show_message('FILE : ' + (self._chord_files[index][1] if index >= 0 else '---'), 0, 36, color)
            
        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_ROOT:
            self._display.show_message('CHORD: ' + self.PARAM_GUITAR_ROOTs[self.value_guitar_root], 0, 18, color)

        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_CHORD or param == self.PARAM_GUITAR_ROOT:
            if self.value_guitar_on_note == -1:
                on_note = ''
            else:
                on_note = '/' + self.PARAM_GUITAR_ROOTs[self.value_guitar_on_note]

            self._display.show_message(self.PARAM_GUITAR_CHORDs[self.value_guitar_chord] + (' L' if self.chord_position() == 0 else ' H') + on_note, 54, 18, color)

        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_OCTAVE:
            self._display.show_message('OCTAV: ' + str(self.scale_number()), 0, 27, color)

        self._display.show()

    def show_info_config1(self, param, color):
        if param == self.PARAM_ALL:
            self._display.show_message('--GUITAR CONFIG1--', 0, 0, color)
            self._display.show_message('OFFSET VELOCITY : {:d}'.format(self.offset_velocity()), 0, 9, color)
            self._display.show_message('VELOCITY CURVE  : {:3.1f}'.format(adc0.velocity_curve()), 0, 18, color)
            self._display.show_message('PITCH BEND RANGE:{:+d}'.format(self.pitch_bend_range()), 0, 27, color)
            self._display.show_message('CHORUS LEVEL    : {:d}'.format(self.chorus_level()), 0, 36, color)
            self._display.show_message('CHORUS FEEDBACK : {:d}'.format(self.chorus_feedback()), 0, 45, color)
            self._display.show_message('AFTER TOUCH ON  : {:3.1f}'.format(adc0.after_touch_counter() / 1000.0), 0, 54, color)

        self._display.show()

    def show_info_config2(self, param, color):
        if param == self.PARAM_ALL:
            self._display.show_message('--GUITAR CONFIG2--', 0, 0, color)
            self._display.show_message('MIDI OUT CHANNEL: ' + str(self.midi_channel() + 1), 0, 27, color)

        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_CAPOTASTO:
            self._display.show_message('CAPOTASTO FRETS :{:+d}'.format(self.capotasto()), 0, 9, color)
             
        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_PROGRAM:
            self._display.show_message('INST: ' + self.abbrev(synth.get_instrument_name(self.program_number()[1])), 0, 18, color)

        self._display.show()

    def show_info_music(self, param, color):
        if param == self.PARAM_ALL:
            self._display.show_message('--GUITAR MUSIC--', 0, 0, color)
            music_name = self._music_list[self.music_file()][1]
            self._display.show_message('MUSIC: ' + ('---' if self.music_file() < 0 else music_name[0:14]), 0, 9, color)
            self._display.show_message('       ' + ('---' if self.music_file() < 0 else music_name[14:]), 0, 18, color)
            chord = self.music_chord()
            music_len = len(self._music)
            self._display.show_message('PLAY : ' + ('---' if chord < 0 else str(chord + 1) + '/' + str(music_len - 1)), 0, 27, color)

            if self.value_guitar_on_note >= 0:
                on_note = ' on ' + self.PARAM_GUITAR_ROOTs[self.value_guitar_on_note]
            else:
                on_note = ''
            self._display.show_message('CHORD: ' + ('---' if chord < 0 else ('END' if chord == music_len - 1 else self.chord_name()[1] + on_note)), 0, 36, color)

        self._display.show()

    def do_task(self):
        try:
            bank = self.chord_bank() * 6
            if input_device.device_info('GUITAR_CHORD1') == False:
                self.set_chord_on_button(bank)
                self.show_info(self.PARAM_GUITAR_ROOT, 1)

            if input_device.device_info('GUITAR_CHORD2') == False:
                self.set_chord_on_button(bank + 1)
                self.show_info(self.PARAM_GUITAR_ROOT, 1)

            if input_device.device_info('GUITAR_CHORD3') == False:
                self.set_chord_on_button(bank + 2)
                self.show_info(self.PARAM_GUITAR_ROOT, 1)

            if input_device.device_info('GUITAR_CHORD4') == False:
                self.set_chord_on_button(bank + 3)
                self.show_info(self.PARAM_GUITAR_ROOT, 1)

            if input_device.device_info('GUITAR_CHORD5') == False:
                self.set_chord_on_button(bank + 4)
                self.show_info(self.PARAM_GUITAR_ROOT, 1)

            if input_device.device_info('GUITAR_CHORD6') == False:
                self.set_chord_on_button(bank + 5)
                self.show_info(self.PARAM_GUITAR_ROOT, 1)

            if input_device.device_info('GUITAR_CHORD_BANK') == False:
                self.chord_bank(self.chord_bank() + 1)
                self.show_info(self.PARAM_GUITAR_CHORDSET, 1)
                
        except Exception as e:
            print('EXCEPTION: ', e)

    def do_task_settings(self):
        try:
            current_button = self.chord_on_button()
            
            if input_device.device_info('GUITAR_BUTTON') == False:
                self.chord_on_button(current_button + 1)
                current_button = self.chord_on_button()
                self.set_chord_on_button(current_button)
                self.show_info_settings(self.PARAM_ALL, 1)

            button_data = self.chord_on_button(current_button)
            
            if input_device.device_info('GUITAR_ROOT') == False:
                self.chord_on_button(current_button, button_data['ROOT'] + 1, None, None, None, None)
                self.set_chord_on_button(current_button)
                self.show_info_settings(self.PARAM_ALL, 1)
        
            if input_device.device_info('GUITAR_CHORD') == False:
                self.chord_on_button(current_button, None, button_data['CHORD'] + 1, None, None, None)
                self.set_chord_on_button(current_button)
                self.show_info_settings(self.PARAM_ALL, 1)
        
            if input_device.device_info('GUITAR_POSITION') == False:
                self.chord_on_button(current_button, None, None, button_data['POSITION'] + 1, None, None)
                self.set_chord_on_button(current_button)
                self.show_info_settings(self.PARAM_ALL, 1)
        
            if input_device.device_info('GUITAR_ONCHORD') == False:
                on_note = -1 if button_data['ON_NOTE'] >= 11 else (button_data['ON_NOTE'] + 1)
                self.chord_on_button(current_button, None, None, None, None, on_note)
                self.set_chord_on_button(current_button)
                self.show_info_settings(self.PARAM_ALL, 1)

            if input_device.device_info('GUITAR_OCTAVE') == False:
                self.chord_on_button(current_button, None, None, None, button_data['SCALE'] + 1, None)
                self.set_chord_on_button(current_button)
                self.show_info_settings(self.PARAM_ALL, 1)
        
            if input_device.device_info('GUITAR_CHORD_FILE') == False:
                self.chord_file(self.chord_file() + 1)
                self.show_info_settings(self.PARAM_ALL, 1)

        except Exception as e:
            print('EXCEPTION: ', e)

    def do_task_config1(self):
        try:
            if   input_device.device_info('GUITAR_BASE_VOLUME') == False:
                self.offset_velocity(self.offset_velocity() + 10)
                self.show_info_config1(self.PARAM_ALL, 1)
                
            elif input_device.device_info('GUITAR_VELOCITY_CURVE') == False:
                adc0.velocity_curve(adc0.velocity_curve() + 0.1)
                self.show_info_config1(self.PARAM_ALL, 1)
                
            elif input_device.device_info('GUITAR_PITCH_BEND_RANGE') == False:
                self.pitch_bend_range(self.pitch_bend_range() + 1)
                synth.set_pitch_bend_range(self.pitch_bend_range())
                self.show_info_config1(self.PARAM_ALL, 1)
                
            elif input_device.device_info('GUITAR_CHORUS_LEVEL') == False:
                val = self.chorus_level() + 10
                if val > 127:
                    val = 0
                    
                self.chorus_level(val)
                self.show_info_config1(self.PARAM_ALL, 1)
                
            elif input_device.device_info('GUITAR_CHORUS_FEEDBACK') == False:
                val = self.chorus_feedback() + 10
                if val > 127:
                    val = 0
                    
                self.chorus_feedback(val)
                self.show_info_config1(self.PARAM_ALL, 1)
                
            elif input_device.device_info('GUITAR_AFTER_TOUCH') == False:
                val = adc0.after_touch_counter() + 200
                if val > 3000:
                    val = 200
                    
                adc0.after_touch_counter(val)
                self.show_info_config1(self.PARAM_ALL, 1)

        except Exception as e:
            print('EXCEPTION: ', e)

    def do_task_config2(self):
        try:
            if input_device.device_info('GUITAR_CAPOTASTO') == False:
                self.capotasto(self.capotasto() + 1)
                self.show_info_config2(self.PARAM_GUITAR_CAPOTASTO, 1)
       
            elif input_device.device_info('GUITAR_INSTRUMENT') == False:
                self.program_number(self.program_number()[0] + 1)
                synth.set_program_change(self.program_number()[1]) 
                self.show_info_config2(self.PARAM_ALL, 1)
       
            elif input_device.device_info('GUITAR_MIDI_CHANNEL') == False:
                self.midi_channel(self.midi_channel() + 1)
                self.show_info_config2(self.PARAM_ALL, 1)

        except Exception as e:
            print('EXCEPTION: ', e)

    def do_task_music(self):
        try:
            if   input_device.device_info('GUITAR_CHORD_NEXT') == False:
                self.music_chord(self.music_chord() + 1)
                self.show_info_music(self.PARAM_ALL, 1)
                
            elif input_device.device_info('GUITAR_MUSIC_PREV') == False:
                self.music_file(self.music_file() - 1)
                self.show_info_music(self.PARAM_ALL, 1)

            elif input_device.device_info('GUITAR_MUSIC_NEXT') == False:
                self.music_file(self.music_file() + 1)
                self.show_info_music(self.PARAM_ALL, 1)

            elif input_device.device_info('GUITAR_CHORD_PREV') == False:
                self.music_chord(self.music_chord() - 1)
                self.show_info_music(self.PARAM_ALL, 1)

            elif input_device.device_info('GUITAR_CHORD_TOP') == False:
                self.music_chord(0)
                self.show_info_music(self.PARAM_ALL, 1)

            elif input_device.device_info('GUITAR_CHORD_LAST') == False:
                self.music_chord(-1)
                self.show_info_music(self.PARAM_ALL, 1)
                
        except Exception as e:
            print('EXCEPTION: ', e)
        
################# End of Guitar Class Definition #################
 

#######################
### Application class
#######################
class Application_class:
    def __init__(self, display_obj):
        self._DEBUG_MODE = False
        
        self._display = display_obj
        self._channel = 0
        
        self.PLAY_GUITAR = 0
        self.GUITAR_SETTINGS = 1
        self.GUITAR_CONFIG1 = 2
        self.GUITAR_CONFIG2 = 3
        self.PLAY_MUSIC = 4
        self._screen_mode = self.PLAY_GUITAR

        # Device aliases
        input_device.device_alias('CHORD_1', 'BUTTON_1')
        input_device.device_alias('CHORD_2', 'BUTTON_2')
        input_device.device_alias('CHORD_3', 'BUTTON_3')
        input_device.device_alias('CHORD_4', 'BUTTON_4')
        input_device.device_alias('CHORD_5', 'BUTTON_5')
        input_device.device_alias('CHORD_6', 'BUTTON_6')
        input_device.device_alias('CHORD_7', 'BUTTON_7')
        input_device.device_alias('MODE_CHANGE', 'BUTTON_8')

    def setup(self):
        instrument = self.screen_mode()
        if   instrument == self.PLAY_GUITAR:
            instrument_guitar.setup()
#        elif instrument == self.PLAY_DRUM:
#            instrument_drum.setup()

    def show_message(self, msg, x=0, y=0, color=1):
        self._display.fill_rect(x, y, 128, 9, 0 if color == 1 else 1)
        self._display.text(msg, x, y, color)
        self._display.show()

    def channel(self, ch=None):
        if ch is not None:
            self._channel = ch % 16
            
        return self._channel

    def screen_mode(self, inst_num=None):
        if inst_num is not None:
            self._screen_mode = inst_num % 5
            
        return self._screen_mode

    def show_info(self, param=-1):
        sc_mode = self.screen_mode()
        if   sc_mode == self.PLAY_GUITAR:
            instrument_guitar.show_info(param, 1)
            
        elif sc_mode == self.GUITAR_SETTINGS:
            instrument_guitar.show_info_settings(param, 1)
            
        elif sc_mode == self.GUITAR_CONFIG1:
            instrument_guitar.show_info_config1(param, 1)
            
        elif sc_mode == self.GUITAR_CONFIG2:
            instrument_guitar.show_info_config2(param, 1)

    # Application task called from asyncio, never call this directly.
    def do_task(self):
        # Screen mode change
        if input_device.device_info('MODE_CHANGE') == False:
            sc_mode = self.screen_mode(self.screen_mode() + 1)
            if   sc_mode == self.PLAY_GUITAR:
                instrument_guitar.setup()
                
            elif sc_mode == self.GUITAR_SETTINGS:
                instrument_guitar.setup_settings()
                
            elif sc_mode == self.GUITAR_CONFIG1:
                instrument_guitar.setup_config1()
                
            elif sc_mode == self.GUITAR_CONFIG2:
                instrument_guitar.setup_config2()
                
            elif sc_mode == self.PLAY_MUSIC:
                instrument_guitar.setup_music()

            display.fill(0)
            self.show_info()

        # Play the current instrument
        sc_mode = self.screen_mode()
        if   sc_mode == self.PLAY_GUITAR:
            instrument_guitar.do_task()

        # Guitar settings
        elif sc_mode == self.GUITAR_SETTINGS:
            instrument_guitar.do_task_settings()

        # Guitar configs
        elif sc_mode == self.GUITAR_CONFIG1:
            instrument_guitar.do_task_config1()

        # Guitar configs
        elif sc_mode == self.GUITAR_CONFIG2:
            instrument_guitar.do_task_config2()

        # Play a music
        elif sc_mode == self.PLAY_MUSIC:
            instrument_guitar.do_task_music()


################# End of Application Class Definition #################
        

def setup():
    global pico_led, sdcard, synth, display, input_device, instrument_guitar, instrument_drum, application

    # LED on board
#    pico_led = digitalio.DigitalInOut(GP25)
    pico_led = digitalio.DigitalInOut(LED)
    pico_led.direction = digitalio.Direction.OUTPUT

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
        display.text('PicoGuitar', 5, 15, 0, 2)
        display.text('(C) 2025 S.Ohira', 15, 35, 0)
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

    # USB MIDI Device
    synth = USB_MIDI_Instrument_class()
    synth.set_all_notes_off()

    # Input devices
    input_device = Input_Devices_class(display)

    # Instruments and application
    print('Start application.')
    instrument_guitar = Guitar_class(display)
    application = Application_class(display)

    # Initial screen
    sleep(3.0)
    application.setup()
    pico_led.value = False                    


# Asyncronous functions
async def main():
    interrupt_task1 = asyncio.create_task(catch_pin_transitions(board.GP21, 'BUTTON_1', input_device.button_pressed, input_device.button_released))
    interrupt_task2 = asyncio.create_task(catch_pin_transitions(board.GP20, 'BUTTON_2', input_device.button_pressed, input_device.button_released))
    interrupt_task3 = asyncio.create_task(catch_pin_transitions(board.GP19, 'BUTTON_3', input_device.button_pressed, input_device.button_released))
    interrupt_task4 = asyncio.create_task(catch_pin_transitions(board.GP18, 'BUTTON_4', input_device.button_pressed, input_device.button_released))
 
    interrupt_task5 = asyncio.create_task(catch_pin_transitions(board.GP2,  'BUTTON_5', input_device.button_pressed, input_device.button_released))
    interrupt_task6 = asyncio.create_task(catch_pin_transitions(board.GP3,  'BUTTON_6', input_device.button_pressed, input_device.button_released))
    interrupt_task7 = asyncio.create_task(catch_pin_transitions(board.GP4,  'BUTTON_7', input_device.button_pressed, input_device.button_released))
    interrupt_task8 = asyncio.create_task(catch_pin_transitions(board.GP5,  'BUTTON_8', input_device.button_pressed, input_device.button_released))

    interrupt_adc0  = asyncio.create_task(catch_adc_voltage(adc0))
#    interrupt_led   = asyncio.create_task(led_flush())
#    await asyncio.gather(interrupt_task1, interrupt_task2, interrupt_task3, interrupt_task4, interrupt_adc0, interrupt_led)
    await asyncio.gather(interrupt_task1, interrupt_task2, interrupt_task3, interrupt_task4, interrupt_adc0)

######### MAIN ##########
if __name__=='__main__':
    adc0 = ADC_Device_class(A0, 'ADC0')
    # Setup
    pico_led = None
    
    input_device = None

    sdcard = None
    display = None
    
    synth = None
    instrument_guitar = None

    application = None
    setup()

    asyncio.run(main())





