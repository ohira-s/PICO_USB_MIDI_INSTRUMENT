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
#########################################################################

import asyncio
import keypad

from board import *
import digitalio
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
import supervisor

import adafruit_ssd1306			# for SSD1306 OLED Display

from analogio import AnalogIn


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
                    print("pin went low: " + pin_name)
                    if callback_pressed is not None:
                        callback_pressed(pin_name)
                        
                elif event.released:
                    print("pin went high: " + pin_name)
                    if callback_released is not None:
                        callback_released(pin_name)

            # Gives away process time to the other tasks.
            # If there is no task, let give back process time to me.
            await asyncio.sleep(0.1)


##########################################
# Catch analog pin voltage in async task
##########################################
async def catch_adc_voltage(adc):
    while True:
        adc.adc_handler()

        # Gives away process time to the other tasks.
        # If there is no task, let give back process time to me.
        await asyncio.sleep(0.01)


led_status = True
async def led_flush():
    global led_status, adc0
    while True:
        led_status = not led_status
        pico_led.value = led_status

        await asyncio.sleep(1.0)


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
        self._note_on_ticks = [-1] * 8			# 8 pads on UI (Piezo elements)
        self._play_chord = False
        self._voltage_gate = [(100.0,70.0)] * 8
        self._adc_on = [False] * 8

        self._mute_string = False

    def adc(self):
        return self._adc

    def adc_name(self):
        return self._adc_name

    def get_voltage(self, analog_channel):
        self._4051_selectors[0].value =  analog_channel & 0x1
        self._4051_selectors[1].value = (analog_channel & 0x2) >> 1
        self._4051_selectors[2].value = (analog_channel & 0x4) >> 2
#        sleep(0.01)
        voltage = self._adc.value * 3.3 / 65535
#        sleep(0.01)
        return voltage

    def adc_handler(self):
        def velosity_curve(velosity):
            if velosity < 32:
                a = 4
                b = 20
            elif velosity < 64:
                a = 3
                b = 51
            elif velosity < 86:
                a = 2
                b = 144
            else:
                a = 1
                b = 248
                
            v = a * velosity + b
#            v = int((v - 20) * 107 / 355) + 20
            v = int((v - 20) * 107 / 355 / 1.5) + 60
            if v > 127:
                v = 127
                
            return v

        ###--- Main: adc_handler ---###
        current_ticks = supervisor.ticks_ms()
        from_note_on = [-1] * 8
        for string in list(range(8)):
            if self._note_on_ticks[string] >= 0:
                from_note_on[string] = ticks_diff(current_ticks, self._note_on_ticks[string])

        # Get voltages guitar strings
        for string in list(range(8)):
            voltage = self.get_voltage(string)
#            print('STR ' + str(string) + ' / VOL=', voltage)
            voltage = voltage * 1000.0
            
#            if string >= 6:
#                print('STRING ' + str(string) + ': ' + str(voltage))

            # Note on time out
            if from_note_on[string] >= 3000:
##            if from_note_on[string] == -99999:
                if string <= 5:
                    if self._note_on[string]:
                        self._note_on[string] = False
                        self._note_on_ticks[string] = -1
                        instrument_guitar.play_a_string(5 - string, 0)
                        self._adc_on[string] = False
                    
                elif string == 7:
                    if self._play_chord:
                        instrument_guitar.play_chord(False)
                        self._play_chord = False
                        self._note_on_ticks[string] = -1
                        self._adc_on[string] = False

                elif string <= 6:
                    if self._note_on[string]:
                        self._note_on[string] = False
                        self._note_on_ticks[string] = -1
                        synth.set_pitch_bend( 8192, 0)
                        self._adc_on[string] = False                    
                        print('PITCH BEND off')

            # Pad is released
            if voltage <= self._voltage_gate[string][1]:
                 self._adc_on[string] = False

            # Pad is tapped
            elif voltage >= self._voltage_gate[string][0] and self._adc_on[string] == False:
                # Velosity
                velosity = int(voltage / 3.5)
                if velosity > 127:
                    velosity = 127
                
                velosity = velosity_curve(velosity)
                
                # Play a string
                if string <= 5:
                    # Play a string
                    if self._note_on[string]:
                        print('PLAY a STRING OFF:', 5 - string)
                        self._note_on[string] = False
                        self._note_on_ticks[string] = -1
                        self._adc_on[string] = False
###                        instrument_guitar.play_a_string(5 - string, 0)

                    # Pitch bend off
                    if self._note_on[6]:
                        self._note_on[6] = False
                        self._note_on_ticks[6] = -1
                        synth.set_pitch_bend( 8192, 0)
                        self._adc_on[6] = False                    

                    print('PLAY a STRING:', 5 - string)
                    self._note_on[string] = True
                    self._note_on_ticks[string] = current_ticks
                    chord_note = instrument_guitar.play_a_string(5 - string, velosity)
                    self._adc_on[string] = True
                    
                # Play chord
                elif string == 7:
                    if self._play_chord:
                        print('PLAY CHORD OFF')
                        instrument_guitar.play_chord(False)
                        self._play_chord = False
                        self._note_on_ticks[string] = -1
                        self._adc_on[string] = False

                    # Pitch bend off
                    if self._note_on[6]:
                        self._note_on[6] = False
                        self._note_on_ticks[6] = -1
                        synth.set_pitch_bend( 8192, 0)
                        self._adc_on[6] = False                    
                        
                    print('PLAY CHORD')
                    instrument_guitar.play_chord(True, velosity)
                    self._play_chord = True
                    self._note_on_ticks[string] = current_ticks
                    self._adc_on[string] = True

                    if self._mute_string:
                        self._mute_string = False
                        display.fill_rect(0, 55, 128, 9, 0)
                        display.show()
                    
                # Pad 6
                elif string == 6:
##                    application._DEBUG_MODE = not application._DEBUG_MODE
##                    application.show_message('DEBUG:' + ('on' if application._DEBUG_MODE else 'off'), 0, 54, 1)
                    if self._note_on[string]:
                        self._note_on[string] = False
                        self._note_on_ticks[string] = -1
                        synth.set_pitch_bend( 8192, 0)
                        self._adc_on[string] = False                    
                        print('PITCH BEND OFF')

                    bend_velosity = 9000 + int((7000 / 127) * velosity)
                    print('PITCH BEND ON:', bend_velosity)
                    synth.set_pitch_bend(bend_velosity, 0)
                    self._note_on[string] = True
                    self._note_on_ticks[string] = current_ticks
                    self._adc_on[string] = True

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
        print('USB MIDI:', usb_midi.ports)
        self._send_note_on = [[]] * 16
        self._usb_midi = [None] * 16
#        self._usb_midi[0] = adafruit_midi.MIDI(midi_in=usb_midi.ports[0], midi_out=usb_midi.ports[1], out_channel=0)
        for channel in list(range(16)):
            self._usb_midi[channel] = adafruit_midi.MIDI(midi_in=usb_midi.ports[0], midi_out=usb_midi.ports[1], out_channel=channel)

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
            for cnt in list(range(5)):
                pico_led.value = False
                sleep(0.25)
                pico_led.value = True
                sleep(0.5)

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
    def midi_send(self, midi_msg, channel=0):
        if isinstance(midi_msg, NoteOn):
            if midi_msg.note in self._send_note_on[channel]:
                self.set_note_off(midi_msg.note, channel)
                print('NOTE OFF:' + str(midi_msg.note))
                return

            self._send_note_on[channel].append(midi_msg.note)
            print('SEND NOTE ON :' + str(midi_msg.note) + ' ONS=' + str(self._send_note_on[channel]))
            
        elif isinstance(midi_msg, NoteOff):
            if midi_msg.note in self._send_note_on[channel]:
                self._send_note_on[channel].remove(midi_msg.note)
                print('SEND NOTE OFF:' + str(midi_msg.note) + ' ONS=' + str(self._send_note_on[channel]))
            else:
                return
            
#        print('SEND:', channel, midi_msg)
        self._usb_midi[channel % 16].send(midi_msg)
#        print('SENT')

        if application._DEBUG_MODE:
            if isinstance(midi_msg, NoteOn):
                if midi_msg.velocity == 0:
                    application.show_message('off:' + str(midi_msg.note) + '/' + str(midi_msg.velocity), 0, 55, 1)
                else:
                    application.show_message('ON :' + str(midi_msg.note) + '/' + str(midi_msg.velocity), 0, 55, 1)
            elif isinstance(midi_msg, NoteOff):
                application.show_message('OFF:' + str(midi_msg.note), 0, 55, 1)

    # Send note on
    def set_note_on(self, note_key, velocity, channel=0):
        self.midi_send(NoteOn(note_key, velocity, channel=channel), channel)

    # Send note off
    def set_note_off(self, note_key, channel=0):
        self.midi_send(NoteOff(note_key, channel=channel), channel)
#        self.midi_send(NoteOn(note_key, 0, channel=channel), channel)

    # Send all notes off
    def set_all_notes_off(self, channel=0):
        pass
    
    def set_reverb(self, channel, prog, level, feedback):
        pass
#        status_byte = 0xB0 + channel
#        midi_msg = bytearray([status_byte, 0x50, prog, status_byte, 0x5B, level])
#        self.midi_out(midi_msg)
#        if feedback > 0:
#            midi_msg = bytearray([0xF0, 0x41, 0x00, 0x42, 0x12, 0x40, 0x01, 0x35, feedback, 0, 0xF7])
#            self.midi_out(midi_msg)
            
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

    # Send program change
    def set_program_change(self, program, channel=0):
        if program >= 0 and program <= 127:
            self.midi_send(ProgramChange(program, channel=channel), channel)

    # Send pitch bend value
    def set_pitch_bend(self, value, channel=0):
        self.midi_send(PitchBend(value, channel=channel), channel)

    def set_pitch_bend_range(self, value, channel=0):
        self.midi_send(ControlChange(0x65, 0, channel=channel), channel)			# RPN LSB
        self.midi_send(ControlChange(0x64, 0, channel=channel), channel)			# RPN MSB
        self.midi_send(ControlChange(0x06, value & 0x7f, channel=channel), channel)	# PRN DATA ENTRY

#        status_byte = 0xB0 + channel
#        midi_msg = bytearray([status_byte, 0x65, 0x00, 0x64, 0x00, 0x06, value & 0x7f])
#        self.midi_out(midi_msg)

    def set_modulation_wheel(self, modulation, value, channel=0):
        pass
#        self.midi_send(ControlChange(modulation, value, channel=channel), channel)

################# End of Unit-MIDI Class Definition #################


##################
### Guitar class
##################
class Guitar_class:
    def __init__(self, display_obj):
        self._display = display_obj

#        self.PARAM_GUITAR_ROOTs = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        self.PARAM_GUITAR_ROOTs = synth._note_key
        self.PARAM_GUITAR_CHORDs = ['M', 'M7', '7', '6', 'aug', 'm', 'mM7', 'm7', 'm6', 'm7-5', 'add9', 'sus4', '7sus4', 'dim7']
        self.GUITAR_STRINGS_OPEN = [16,11, 7, 2, -3, -8]	# 1st String: E, B, G, D, A, E: 6th String
        self.CHORD_STRUCTURE = {
            #Chord   : LO:1  2  3  4  5  6  HI:1  2  3  4  5  6			# Strings
            'CM'     : ([ 0, 1, 0, 2, 3,-1], [ 3, 5, 5, 5, 3,-1]),		# Fret number to press (-1 is not to play it)
            'CM7'    : ([ 0, 0, 0, 2, 3,-1], [ 3, 5, 4, 5, 3,-1]),
            'C7'     : ([ 0, 1, 3, 2, 3,-1], [ 3, 5, 3, 5, 3,-1]),
            'C6'     : ([ 0, 1, 2, 2, 3,-1], [ 5, 5, 5, 5, 3,-1]),
            'Caug'   : ([-1, 1, 1, 2, 3,-1], [ 8, 9, 9,10,-1,-1]),
            'Cm'     : ([ 3, 4, 5, 5, 3,-1], [ 8, 8, 8,10,10, 8]),
            'CmM7'   : ([ 3, 4, 4, 5, 3,-1], [ 8, 8, 8, 9,10, 8]),
            'Cm7'    : ([ 3, 4, 3, 5, 3,-1], [ 8, 8, 8, 8,10, 8]),
            'Cm6'    : ([ 3, 1, 2, 1, 3,-1], [ 8,10, 8,10,10, 8]),
            'Cm7-5'  : ([-1, 4, 3, 4, 3,-1], [12,12,12,10,-1,-1]),
            'Cadd9'  : ([ 0, 3, 0, 2, 3,-1], [ 3, 3, 5, 5, 3,-1]),
            'Csus4'  : ([ 1, 1, 0, 3, 3,-1], [ 8, 8,10,10,10, 8]),
            'C7sus4' : ([ 3, 6, 3, 5, 3,-1], [ 8, 8,10, 8,10, 8]),
            'Cdim7'  : ([-1, 4, 2, 4, 3,-1], [11,10,11,10,-1,-1]),

            'C#M'    : ([ 4, 6, 6, 6, 4,-1], [ 9, 9,10,11,11, 9]),
            'C#M7'   : ([ 4, 6, 5, 6, 4,-1], [ 9,10,11,12,-1,-1]),
            'C#7'    : ([ 4, 6, 4, 6, 4,-1], [ 9, 9,10, 9,11, 9]),
            'C#6'    : ([ 6, 6, 6, 6, 4,-1], [ 9,11,10,11,-1,-1]),
            'C#aug'  : ([-1, 2, 2, 3, 4,-1], [ 9,10,10,11,-1,-1]),
            'C#m'    : ([ 4, 5, 6, 6, 4,-1], [ 9, 9, 9,11,11, 9]),
            'C#mM7'  : ([ 4, 5, 5, 6, 4,-1], [ 9, 9, 9,10,11, 9]),
            'C#m7'   : ([ 4, 5, 4, 6, 4,-1], [12,12,12,10,-1,-1]),
            'C#m6'   : ([ 4, 2, 3, 2, 4,-1], [ 9,11, 9,11,11, 9]),
            'C#m7-5' : ([-1, 5, 4, 5, 4,-1], [12,12,12,10,-1,-1]),
            'C#add9' : ([ 4, 4, 6, 6, 4,-1], [10, 8, 9,10,-1,-1]),
            'C#sus4' : ([ 4, 7, 6, 6, 4,-1], [ 9, 9,11,11,11, 9]),
            'C#7sus4': ([ 4, 7, 4, 6, 4,-1], [ 9, 9,11, 9,11, 9]),
            'C#dim7' : ([-1, 5, 3, 5, 4,-1], [12,11,12,11,-1,-1]),

            'DM'     : ([ 2, 3, 2, 0,-1,-1], [ 5, 7, 7, 7, 5,-1]),
            'DM7'    : ([ 2, 2, 2, 0,-1,-1], [ 5, 7, 6, 7, 5,-1]),
            'D7'     : ([ 2, 1, 2, 0,-1,-1], [ 5, 7, 5, 7, 5,-1]),
            'D6'     : ([ 2, 0, 2, 0,-1,-1], [ 7, 7, 7, 7, 5,-1]),
            'Daug'   : ([ 2, 3, 3, 0,-1,-1], [11,12,12,13,-1,-1]),
            'Dm'     : ([ 1, 3, 2, 0,-1,-1], [ 5, 6, 7, 7, 5,-1]),
            'DmM7'   : ([ 1, 2, 2, 0,-1,-1], [ 5, 6, 6, 7, 5,-1]),
            'Dm7'    : ([ 1, 1, 2, 0,-1,-1], [ 5, 6, 5, 7, 5,-1]),
            'Dm6'    : ([ 1, 0, 2, 0,-1,-1], [-1,10,10, 9,-1,10]),
            'Dm7-5'  : ([ 1, 1, 1, 0,-1,-1], [-1, 6, 5, 6, 5,-1]),
            'Dadd9'  : ([ 0, 3, 2, 0,-1,-1], [ 5, 5, 7, 7, 5,-1]),
            'Dsus4'  : ([ 3, 3, 2, 0,-1,-1], [ 5, 8, 7, 7, 5,-1]),
            'D7sus4' : ([ 3, 1, 2, 0,-1,-1], [ 5, 8, 5, 7, 5,-1]),
            'Ddim7'  : ([ 1, 0, 1, 0,-1,-1], [-1, 9,10, 9,-1,10]),

            'D#M'    : ([ 6, 8, 8, 8, 6,-1], [ 6, 8, 8, 8, 6,-1]),
            'D#M7'   : ([ 6, 8, 7, 8, 6,-1], [ 6, 8, 7, 8, 6,-1]),
            'D#7'    : ([ 6, 8, 6, 8, 6,-1], [ 6, 8, 6, 8, 6,-1]),
            'D#6'    : ([ 8, 8, 8, 8, 6,-1], [ 8, 8, 8, 8, 6,-1]),
            'D#aug'  : ([-1, 4, 4, 5, 6,-1], [ 6, 7, 7, 8,-1,-1]),
            'D#m'    : ([ 6, 7, 8, 8, 6,-1], [ 6, 7, 8, 8, 6,-1]),
            'D#mM7'  : ([ 6, 7, 7, 8, 6,-1], [ 6, 7, 7, 8, 6,-1]),
            'D#m7'   : ([ 6, 7, 6, 8, 6,-1], [ 6, 7, 6, 8, 6,-1]),
            'D#m6'   : ([ 6, 4, 5, 4, 6,-1], [-1,10,10, 9,-1,10]),
            'D#m7-5' : ([-1, 7, 6, 7, 6,-1], [-1, 7, 6, 7, 6,-1]),
            'D#add9' : ([ 6, 6, 8, 8, 6,-1], [ 6, 6, 8, 8, 6,-1]),
            'D#sus4' : ([ 6, 9, 8, 8, 6,-1], [ 6, 9, 8, 8, 6,-1]),
            'D#7sus4': ([ 6, 9, 6, 8, 6,-1], [ 6, 9, 6, 8, 6,-1]),
            'D#dim7' : ([-1, 7, 5, 7, 6,-1], [10, 9,10, 9,-1,-1]),

            'EM'     : ([ 0, 0, 1, 2, 2, 0], [ 7, 9, 9, 9, 7,-1]),
            'EM7'    : ([ 0, 0, 1, 1, 2, 0], [ 7, 9, 8, 9, 7,-1]),
            'E7'     : ([ 0, 0, 1, 0, 2, 0], [ 7, 9, 7, 9, 7,-1]),
            'E6'     : ([ 0, 2, 1, 2, 2, 0], [ 9, 9, 9, 9, 7,-1]),
            'Eaug'   : ([ 0, 2, 2, 3,-1,-1], [-1, 5, 5, 6, 7,-1]),
            'Em'     : ([ 0, 0, 0, 2, 2, 0], [ 7, 8, 7, 9, 7,-1]),
            'EmM7'   : ([-1, 0, 0, 1, 2, 0], [ 7, 8, 8, 9, 7,-1]),
            'Em7'    : ([ 0, 0, 0, 0, 2, 0], [ 7, 8, 7, 9, 7,-1]),
            'Em6'    : ([ 0, 2, 0, 2, 2, 0], [-1,12,12,11,-1,12]),
            'Em7-5'  : ([ 0, 3, 0, 2, 1, 0], [-1, 8, 7, 8, 7,-1]),
            'Eadd9'  : ([ 0, 0, 1, 4, 2, 0], [ 7, 7, 9, 9, 7,-1]),
            'Esus4'  : ([ 0, 0, 2, 2, 2, 0], [ 7,10, 9, 9, 7,-1]),
            'E7sus4' : ([ 0, 0, 2, 0, 2, 0], [ 7,10, 7, 9, 7,-1]),
            'Edim7'  : ([ 0, 2, 0, 2, 1, 0], [-1,11,12,11,-1,12]),

            'FM'     : ([ 1, 1, 2, 3, 3, 1], [ 8,10,10,10, 8,-1]),
            'FM7'    : ([-1, 1, 2, 2,-1, 1], [ 8,10, 9,10, 8,-1]),
            'F7'     : ([ 1, 1, 2, 1, 3, 1], [ 8,10, 8,10, 8,-1]),
            'F6'     : ([ 1, 3, 2, 3, 1, 1], [10,10,10,10, 8,-1]),
            'Faug'   : ([ 1, 2, 2, 3,-1.-1], [-1, 6, 6, 7, 8,-1]),
            'Fm'     : ([ 1, 1, 1, 3, 3, 1], [ 8, 9,10,10, 8,-1]),
            'FmM7'   : ([ 1, 1, 1, 2, 3, 1], [ 8, 9, 9,10, 8,-1]),
            'Fm7'    : ([ 1, 1, 1, 1, 3, 1], [ 8, 9, 8,10, 8,-1]),
            'Fm6'    : ([ 1, 3, 1, 3, 3, 1], [12,11,13,11,-1,-1]),
            'Fm7-5'  : ([-1, 0, 1, 1,-1, 1], [-1, 9, 8, 9, 8,-1]),
            'Fadd9'  : ([ 3, 1, 2, 3,-1,-1], [ 8, 8,10,10, 8,-1]),
            'Fsus4'  : ([ 1, 1, 3, 3, 3, 1], [ 8,11,10,10, 8,-1]),
            'F7sus4' : ([ 1, 1, 3, 1, 3, 1], [ 8,11, 8,10, 8,-1]),
            'Fdim7'  : ([ 1, 0, 1, 0,-1, 1], [-1,12,13,12,-1,13]),

            'F#M'    : ([ 2, 2, 3, 4, 4, 2], [ 9,11,11,11, 9, 9]),
            'F#M7'   : ([-1, 2, 3, 3,-1, 2], [ 9,11,10,11, 9, 9]),
            'F#7'    : ([ 2, 2, 3, 2, 4, 2], [ 9,11, 9,11, 9, 9]),
            'F#6'    : ([ 2, 4, 3, 4, 2, 2], [11,11,11,11, 9, 9]),
            'F#aug'  : ([ 2, 3, 3, 4,-1,-1], [ 6, 7, 7, 8,-1,-1]),
            'F#m'    : ([ 2, 2, 2, 4, 4, 2], [ 9,10,11,11, 9, 9]),
            'F#mM7'  : ([ 2, 2, 2, 3, 4, 2], [ 9,10,10,11, 9, 9]),
            'F#m7'   : ([ 2, 2, 2, 2, 4, 2], [ 9,10, 9,11, 9, 9]),
            'F#m6'   : ([ 2, 4, 2, 4, 4, 2], [ 5, 4, 6, 4,-1,-1]),
            'F#m7-5' : ([ 0, 1, 2, 2,-1, 2], [-1,10, 9,10, 9,-1]),
            'F#add9' : ([ 4, 2, 3, 4,-1,-1], [-1, 7, 6, 6, 9,-1]),
            'F#sus4' : ([ 2, 2, 4, 4, 4, 2], [ 9,12,11,11, 9, 9]),
            'F#7sus4': ([ 2, 2, 4, 2, 4, 2], [ 9,12, 9,11, 9, 9]),
            'F#dim7' : ([-1, 1, 2, 1,-1, 2], [ 5, 4, 5, 4,-1,-1]),

            'GM'     : ([ 3, 0, 0, 0, 2, 3], [ 3, 3, 4, 5, 5, 3]),
            'GM7'    : ([ 2, 0, 0, 0, 2, 3], [ 7, 7, 7, 5,-1,-1]),
            'G7'     : ([ 1, 0, 0, 0, 2, 3], [ 3, 3, 4, 3, 5, 3]),
            'G6'     : ([ 0, 0, 0, 0, 2, 3], [12,12,12,12,10,-1]),
            'Gaug'   : ([ 3, 4, 4, 5,-1,-1], [-1, 8, 8, 9,10,-1]),
            'Gm'     : ([ 3, 3, 3, 5, 5, 3], [10,11,12,12,10,-1]),
            'GmM7'   : ([ 3, 3, 3, 4, 5, 3], [10,11,11,12,10,-1]),
            'Gm7'    : ([ 3, 3, 3, 3, 5, 3], [10,11,10,12,10,-1]),
            'Gm6'    : ([ 3, 5, 3, 5, 5, 3], [ 6, 5, 7, 5,-1,-1]),
            'Gm7-5'  : ([-1, 2, 3, 3,-1, 3], [ 7, 7, 7, 5,-1,-1]),
            'Gadd9'  : ([ 3, 0, 2, 0, 0, 3], [10,10,12,12,10,-1]),
            'Gsus4'  : ([ 3, 1, 0, 0, 3, 3], [ 3, 3, 5, 5, 5, 3]),
            'G7sus4' : ([ 3, 3, 5, 3, 5, 3], [ 3, 3, 5, 3, 5, 3]),
            'Gdim7'  : ([-1, 2, 3, 2,-1, 3], [ 6, 5, 6, 5,-1,-1]),

            'G#M'    : ([ 4, 4, 5, 6, 6, 4], [11,13,13,13,11,-1]),
            'G#M7'   : ([-1, 4, 5, 5,-1, 4], [11,13,12,13,11,-1]),
            'G#7'    : ([ 4, 4, 5, 4, 6, 4], [-1, 9,11,10,11,-1]),
            'G#6'    : ([-1, 4, 5, 3,-1, 4], [-1, 9,10,10,11,-1]),
            'G#aug'  : ([ 4, 5, 5, 6,-1,-1], [-1, 9, 9,10,11,-1]),
            'G#m'    : ([ 4, 4, 4, 6, 6, 4], [11,12,13,13,11,-1]),
            'G#mM7'  : ([ 4, 4, 4, 5, 6, 4], [11,12,12,13,11,-1]),
            'G#m7'   : ([ 4, 4, 4, 4, 6, 4], [11,12,11,13,11,-1]),
            'G#m6'   : ([ 4, 6, 4, 6, 6, 4], [ 7, 6, 8, 6,-1,-1]),
            'G#m7-5' : ([ 0, 3, 4, 4,-1, 4], [ 7, 7, 7, 6,-1,-1]),
            'G#add9' : ([ 6, 4, 5, 6,-1,-1], [11,11,13,13,11,-1]),
            'G#sus4' : ([ 4, 4, 6, 6, 6, 4], [11,14,13,13,11,-1]),
            'G#7sus4': ([ 4, 4, 6, 4, 6, 4], [11,14,11,13,11,-1]),
            'G#dim7' : ([-1, 3, 4, 3,-1, 4], [ 7, 6, 7, 6,-1,-1]),

            'AM'     : ([ 0, 2, 2, 2, 0,-1], [ 5, 5, 6, 7, 7, 5]),
            'AM7'    : ([ 0, 2, 1, 2, 0,-1], [-1, 5, 6, 6,-1, 5]),
            'A7'     : ([ 0, 2, 0, 2, 0,-1], [ 5, 5, 6, 5, 7, 5]),
            'A6'     : ([ 2, 2, 2, 2, 0,-1], [-1,10,11,11,12,-1]),
            'Aaug'   : ([ 1, 2, 2, 3, 0,-1], [ 5, 6, 6, 7,-1,-1]),
            'Am'     : ([ 0, 1, 2, 2, 0,-1], [ 5, 5, 5, 7, 7, 5]),
            'AmM7'   : ([ 0, 1, 1, 2, 0,-1], [ 5, 5, 5, 6, 7, 5]),
            'Am7'    : ([ 0, 1, 0, 2, 0,-1], [ 5, 5, 5, 5, 7, 5]),
            'Am6'    : ([ 2, 1, 2, 2, 0,-1], [-1, 6, 6, 5,-1, 6]),
            'Am7-5'  : ([-1, 1, 0, 1, 0,-1], [ 9, 9, 9, 7,-1,-1]),
            'Aadd9'  : ([ 0, 0, 2, 2, 0,-1], [ 7, 5, 6, 7,-1,-1]),
            'Asus4'  : ([ 0, 3, 2, 2, 0,-1], [ 5, 5, 7, 7, 7, 5]),
            'A7sus4' : ([ 0, 3, 0, 2, 0,-1], [ 5, 5, 7, 5, 7, 5]),
            'Adim7'  : ([ 2, 1, 2, 1, 0,-1], [-1, 4, 5, 4,-1, 5]),

            'A#M'    : ([ 1, 3, 3, 3, 1,-1], [ 6, 6, 7, 8, 8, 6]),
            'A#M7'   : ([ 1, 3, 2, 3, 1,-1], [-1, 6, 7, 7,-1, 6]),
            'A#7'    : ([ 1, 3, 1, 3, 1,-1], [ 6, 6, 7, 6, 8, 6]),
            'A#6'    : ([ 3, 3, 3, 3, 1,-1], [-1,11,12,12,13,-1]),
            'A#aug'  : ([ 6, 7, 7, 8,-1,-1], [ 6, 7, 7, 8,-1,-1]),
            'A#m'    : ([ 1, 2, 3, 3, 1,-1], [ 6, 6, 6, 8, 8, 6]),
            'A#mM7'  : ([ 1, 2, 2, 3, 1,-1], [ 6, 6, 6, 7, 8, 6]),
            'A#m7'   : ([ 1, 2, 1, 3, 1,-1], [ 6, 6, 6, 6, 8, 6]),
            'A#m6'   : ([ 3, 2, 3, 1, 1,-1], [-1, 7, 7, 6,-1, 7]),
            'A#m7-5' : ([-1, 2, 1, 2, 1,-1], [10,10,10, 8,-1,-1]),
            'A#add9' : ([ 1, 1, 3, 3, 1,-1], [ 8, 6, 7, 8,-1,-1]),
            'A#sus4' : ([ 1, 4, 3, 3, 1,-1], [ 6, 6, 8, 8, 8, 6]),
            'A#7sus4': ([ 1, 4, 1, 3, 1,-1], [ 6, 6, 8, 6, 8, 6]),
            'A#dim7' : ([ 0, 2, 0, 2, 1,-1], [-1, 5, 6, 5,-1, 6]),

            'BM'     : ([ 2, 4, 4, 4, 2,-1], [ 7, 7, 8, 9, 9, 7]),
            'BM7'    : ([ 2, 4, 3, 4, 2,-1], [-1, 7, 8, 8,-1, 7]),
            'B7'     : ([ 2, 0, 2, 1, 2,-1], [ 7, 7, 8, 7, 9, 7]),
            'B6'     : ([ 4, 4, 4, 4, 2,-1], [ 7, 9, 8, 9,-1,-1]),
            'Baug'   : ([-1, 0, 0, 1, 2,-1], [ 7, 8, 8, 9,-1,-1]),
            'Bm'     : ([ 2, 3, 4, 4, 2,-1], [ 7, 7, 7, 9, 9, 7]),
            'BmM7'   : ([ 2, 3, 3, 4, 2,-1], [ 7, 7, 7, 8, 9, 7]),
            'Bm7'    : ([ 2, 3, 2, 4, 2,-1], [ 7, 7, 7, 7, 9, 7]),
            'Bm6'    : ([ 3, 0, 2, 0, 3,-1], [10, 9,11, 9,-1,-1]),
            'Bm7-5'  : ([-1, 3, 2, 3, 2,-1], [11,11,11, 9,-1,-1]),
            'Badd9'  : ([ 1, 1, 3, 3, 1,-1], [ 9, 7, 8, 9,-1,-1]),
            'Bsus4'  : ([ 2, 5, 4, 4, 2,-1], [ 7, 7, 9, 9, 9, 7]),
            'B7sus4' : ([ 2, 5, 2, 4, 2,-1], [ 7, 7, 9, 7, 9, 7]),
            'Bdim7'  : ([-1, 3, 1, 3, 2,-1], [-1, 6, 7, 6,-1, 7])
        }

        self.PARAM_ALL = -1
        self.PARAM_GUITAR_PROGRAM = 0
        self.PARAM_GUITAR_ROOT = 1
        self.PARAM_GUITAR_CHORD = 2
        self.PARAM_GUITAR_CHORDSET = 3
        self.PARAM_GUITAR_CAPOTASTO = 4
##        self.PARAM_GUITAR_EFFECTOR = 5
        self.PARAM_GUITAR_OCTAVE = 6
        
        self.value_guitar_root = 0		# Current root
        self.value_guitar_chord = 0		# Current chord
        self._chord_changed = False
        
        self._programs = [-1, 24, 25, 26, 27, 28, 29, 30, 31, 104, 105, 106, 107]	# Instrument number in GM
        self._program_number = 0  		# Steel Guitar
        self._scale_number = 4			# Normal guitar scale
        self._chord_position = 0		# 0: Low chord, 1: High chord
        self._capotasto = 0				# No capotasto (-12..0..+12)
        self._pitch_bend_range = 2		# 1 is semitone (0..12)
        self._notes_on  = None
        self._notes_off = None

        # Chord on button
        self._chord_bank = 0
        self._chord_on_button_number = 0
        self._chord_on_button = [
                {'ROOT': 0, 'CHORD': 0, 'POSITION': 0, 'SCALE': 4},		# CM Low
                {'ROOT': 7, 'CHORD': 0, 'POSITION': 0, 'SCALE': 4},		# GM Low
                {'ROOT': 9, 'CHORD': 5, 'POSITION': 0, 'SCALE': 4},		# Am Low
                {'ROOT': 4, 'CHORD': 5, 'POSITION': 0, 'SCALE': 4},		# Em Low
                {'ROOT': 5, 'CHORD': 0, 'POSITION': 0, 'SCALE': 4},		# FM Low
                {'ROOT': 2, 'CHORD': 5, 'POSITION': 0, 'SCALE': 4},		# Dm Low
                {'ROOT': 0, 'CHORD': 0, 'POSITION': 1, 'SCALE': 4},		# CM High
                {'ROOT': 7, 'CHORD': 0, 'POSITION': 1, 'SCALE': 4},		# GM High
                {'ROOT': 9, 'CHORD': 5, 'POSITION': 1, 'SCALE': 4},		# Am High
                {'ROOT': 4, 'CHORD': 5, 'POSITION': 1, 'SCALE': 4},		# Em High
                {'ROOT': 5, 'CHORD': 0, 'POSITION': 1, 'SCALE': 4},		# FM High
                {'ROOT': 2, 'CHORD': 5, 'POSITION': 1, 'SCALE': 4}		# Dm High
            ]

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
        input_device.device_alias('GUITAR_OCTAVE',     'BUTTON_5')
        input_device.device_alias('GUITAR_CAPOTASTO',  'BUTTON_6')
        input_device.device_alias('GUITAR_INSTRUMENT', 'BUTTON_7')

    def setup(self):
        display.fill(0)
        synth.set_program_change(self.program_number()[1], 0)
        synth.set_pitch_bend_range(self.pitch_bend_range(), 0)
        self.show_info(self.PARAM_ALL, 1)

    def setup_settings(self):
        display.fill(0)
        current_button = self.chord_on_button()
        self.set_chord_on_button(current_button)
        synth.set_program_change(self.program_number()[1], 0) 
        self.show_info_settings(self.PARAM_ALL, 1)

    def capotasto(self, capo=None):
        if capo is not None:
            if capo < -12:
                capo = 12
            elif capo > 12:
                capo = -12
                
            self._capotasto = capo
            
        return self._capotasto

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

    def chord_on_button(self, button=None, root=None, chord=None, position=None, scale=None):
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
        
        return self._chord_on_button[button]

    def pitch_bend_range(self, bend_range=None):
        if bend_range is not None:
            self._pitch_bend_range = bend_range % 13
            synth.set_pitch_bend_range(self._pitch_bend_range, 0)
            
        return self._pitch_bend_range

    def chord_bank(self, bank=None):
        if bank is not None:
            self._chord_bank = bank % 2
            
        return self._chord_bank

    def set_chord_on_button(self, button):
        button_data = self._chord_on_button[button]
        self.value_guitar_root = button_data['ROOT']		# Current root
        self.value_guitar_chord = button_data['CHORD']		# Current chord
        self._chord_position = button_data['POSITION']		# 0: Low chord, 1: High chord
        self._scale_number = button_data['SCALE']
        self._chord_changed = False

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
        
        print('root, chord=', root, chord)
        root_name = self.PARAM_GUITAR_ROOTs[root % 12]
        chord_name = root_name + self.PARAM_GUITAR_CHORDs[chord]
        print('CHORD NAME: ', chord_name, self.CHORD_STRUCTURE[chord_name][chord_position])
        return (root_name, chord_name)

    def chord_notes(self, chord_position=None, root=None, chord=None, scale=None):
        if chord_position is None:
            chord_position = self.chord_position()
            
        (root_name, chord_name) = self.chord_name(chord_position, root, chord, scale)
        notes = []
        print('CHORD NAME: ', chord_name, self.CHORD_STRUCTURE[chord_name][chord_position])
        fret_map = self.CHORD_STRUCTURE[chord_name][chord_position]
        for strings in list(range(6)):
            note = self.guitar_string_note(strings, fret_map[strings])
            if note is not None:
#                notes.append(note + root)
                notes.append(note + (self._scale_number + 1) * 12)
            else:
                notes.append(-1)
            
        return notes

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
                    
                self._display.show_message(chord_name + ' ' + ('L' if button_data['POSITION'] == 0 else 'H'), x, y + (i % 3) * 9, color)
                
        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_PROGRAM:
            self._display.show_message(self.abbrev(synth.get_instrument_name(self.program_number()[1])), 0, 18, color)
            
        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_ROOT:
            self._display.show_message(self.PARAM_GUITAR_ROOTs[self.value_guitar_root], 0, 9, color)

        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_CHORD or param == self.PARAM_GUITAR_ROOT:
            self._display.show_message(self.PARAM_GUITAR_CHORDs[self.value_guitar_chord] + '  ' + ('L' if self.chord_position() == 0 else 'H') + ' {:+d}'.format(self.capotasto()), 12, 9, color)

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
            self._display.show_message('P-BND: {:+d}'.format(self.pitch_bend_range()), 0, 54, color)
            
        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_ROOT:
            self._display.show_message('CHORD: ' + self.PARAM_GUITAR_ROOTs[self.value_guitar_root], 0, 18, color)

        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_CHORD or param == self.PARAM_GUITAR_ROOT:
            self._display.show_message(self.PARAM_GUITAR_CHORDs[self.value_guitar_chord] + (' Low' if self.chord_position() == 0 else ' High'), 54, 18, color)

        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_OCTAVE:
            self._display.show_message('OCTAV: ' + str(self.scale_number()), 0, 27, color)

        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_CAPOTASTO:
            self._display.show_message('CAPO : {:+d}'.format(self.capotasto()), 0, 36, color)
            
        if param == self.PARAM_ALL or param == self.PARAM_GUITAR_PROGRAM:
            self._display.show_message('INST : ' + self.abbrev(synth.get_instrument_name(self.program_number()[1])), 0, 45, color)

        self._display.show()

    # Play a string
    def play_a_string(self, string, string_velosity):
        print('PLAY a STRING:', string_velosity)
        capo = self.capotasto()
        
        # Notes off (previous chord)
        if self._chord_changed:
            if self._notes_off is not None:
                for chord_note in self._notes_off:
                    synth.set_note_off(chord_note + capo, 0)
                    self._notes_off.remove(chord_note)
##                    sleep(0.001)

                if len(self._notes_off) == 0:
                    self._notes_off = None
                        
            self._chord_changed = False

        # Play strings in the current chord
        string_notes = self.chord_notes()
        chord_note = string_notes[string]
        if chord_note >= 0:
            # Note off
            if self._notes_off is not None:
                off_notes = self._notes_off
                if chord_note in off_notes:
                    synth.set_note_off(chord_note + capo, 0)
                    self._notes_off.remove(chord_note)
##                    sleep(0.001)


                if len(self._notes_off) == 0:
                    self._notes_off = None
                        
            # Note on
            if string_velosity > 0:
                synth.set_note_on(chord_note + capo, string_velosity, 0)
                if self._notes_off is None:
                    self._notes_off = []
                self._notes_off.append(chord_note)
##                sleep(0.001)

        return chord_note

    # Play strings with each velocities
    #   string_velosities: [-1,0,127,63,85,-1] ---> String 6=Ignore, 5=Note off, 4=Note on in velosity 127,...
    def play_strings(self, string_velosities):
        print('PLAY STRINGS:', string_velosities)
        capo = self.capotasto()
        
        # Notes off (previous chord)
        if self._chord_changed:
            if self._notes_off is not None:
                off_notes = self._notes_off
                for chord_note in off_notes:
                    synth.set_note_off(chord_note + capo, 0)
                    self._notes_off.remove(chord_note)
##                    sleep(0.001)

                if len(self._notes_off) == 0:
                    self._notes_off = None
                        
            self._chord_changed = False

        # Play strings in the current chord
        string_notes = self.chord_notes()
        for string in list(range(6)):
            chord_note = string_notes[string]
            if chord_note >= 0:
                # Note off
                if self._notes_off is not None:
                    off_notes = self._notes_off
                    for chord_note in off_notes:
                        synth.set_note_off(chord_note + capo, 0)
                        self._notes_off.remove(chord_note)
##                        sleep(0.001)

                    if len(self._notes_off) == 0:
                        self._notes_off = None
                            
                # Note on
                if string_velosities[string] > 0:
                    synth.set_note_on(chord_note + capo, string_velosities[string], 0)
                    if self._notes_off is None:
                        self._notes_off = []
                    self._notes_off.append(chord_note)
##                    sleep(0.001)

    def play_chord(self, play=True, velosity=127):
        try:
            capo = self.capotasto()
        
            # Play a chord selected
            if play:
                if self._notes_on is None:
                    pico_led.value = True                    
                    self._notes_on = self.chord_notes()
                    
                    print('CHORD NOTEs ON : ', self._notes_on)
                    for nt in self._notes_on:
                        if nt >= 0:
                            synth.set_note_on(nt + capo, velosity, 0)
                            if self._notes_off is None:
                                self._notes_off = []
                            self._notes_off.append(nt)
##                            sleep(0.001)

                    pico_led.value = False
                
##                else:
##                    sleep(0.006)

            # Notes in chord off
            else:
                # Notes off
                if self._notes_off is not None:
                    pico_led.value = True                    
                    print('CHORD NOTEs OFF: ', self._notes_off)
                    for nt in self._notes_off:
                        if nt >= 0:
                            synth.set_note_off(nt + capo, 0)
##                            sleep(0.001)
                        
                    self._notes_on  = None
                    self._notes_off = None
                    self._chord_changed = False
                    pico_led.value  = False                    

##                else:
##                    sleep(0.006)

                self._chord_changed = False

        except Exception as e:
            led_flush = False
            for cnt in list(range(5)):
                pico_led.value = led_flush
                led_flush = not led_flush
                sleep(0.5)

            led_flush = False
            print('EXCEPTION: ', e)

    def do_task(self):
        try:
            bank = self.chord_bank() * 6
            if input_device.device_info('GUITAR_CHORD1') == False:
                print('CHORD1')
                self.set_chord_on_button(bank)
                self.show_info(self.PARAM_GUITAR_ROOT, 1)

            if input_device.device_info('GUITAR_CHORD2') == False:
                print('CHORD2')
                self.set_chord_on_button(bank + 1)
                self.show_info(self.PARAM_GUITAR_ROOT, 1)

            if input_device.device_info('GUITAR_CHORD3') == False:
                print('CHORD3')
                self.set_chord_on_button(bank + 2)
                self.show_info(self.PARAM_GUITAR_ROOT, 1)

            if input_device.device_info('GUITAR_CHORD4') == False:
                print('CHORD4')
                self.set_chord_on_button(bank + 3)
                self.show_info(self.PARAM_GUITAR_ROOT, 1)

            if input_device.device_info('GUITAR_CHORD5') == False:
                print('CHORD5')
                self.set_chord_on_button(bank + 4)
                self.show_info(self.PARAM_GUITAR_ROOT, 1)

            if input_device.device_info('GUITAR_CHORD6') == False:
                print('CHORD6')
                self.set_chord_on_button(bank + 5)
                self.show_info(self.PARAM_GUITAR_ROOT, 1)

            if input_device.device_info('GUITAR_CHORD_BANK') == False:
                print('CHORD BANK')
                self.chord_bank(self.chord_bank() + 1)
                self.show_info(self.PARAM_GUITAR_CHORDSET, 1)
                
        except Exception as e:
            led_flush = False
            for cnt in list(range(5)):
                pico_led.value = led_flush
                led_flush = not led_flush
                sleep(0.5)

            led_flush = False
            print('EXCEPTION: ', e)

    def do_task_settings(self):
        print('GUITAR SETTINGS')
        try:
            current_button = self.chord_on_button()
            
            if input_device.device_info('GUITAR_BUTTON') == False:
                print('GUITAR_BUTTON')
                self.chord_on_button(current_button + 1)
                current_button = self.chord_on_button()
                self.set_chord_on_button(current_button)
                self.show_info_settings(self.PARAM_ALL, 1)

            button_data = self.chord_on_button(current_button)
            
            if input_device.device_info('GUITAR_ROOT') == False:
                print('GUITAR_ROOT')
                self.chord_on_button(current_button, button_data['ROOT'] + 1)
                self.set_chord_on_button(current_button)
                self.show_info_settings(self.PARAM_ALL, 1)
        
            if input_device.device_info('GUITAR_CHORD') == False:
                print('GUITAR_CHORD')
                self.chord_on_button(current_button, None, button_data['CHORD'] + 1)
                self.set_chord_on_button(current_button)
                self.show_info_settings(self.PARAM_ALL, 1)
        
            if input_device.device_info('GUITAR_POSITION') == False:
                print('GUITAR_POSITION')
                self.chord_on_button(current_button, None, None, button_data['POSITION'] + 1)
                self.set_chord_on_button(current_button)
                self.show_info_settings(self.PARAM_ALL, 1)
        
            if input_device.device_info('GUITAR_OCTAVE') == False:
                print('GUITAR_OCTAVE')
                self.chord_on_button(current_button, None, None, None, button_data['SCALE'] + 1)
                self.set_chord_on_button(current_button)
                self.show_info_settings(self.PARAM_ALL, 1)
        
            if input_device.device_info('GUITAR_CAPOTASTO') == False:
                print('GUITAR_CAPOTASTO')
                self.capotasto(self.capotasto() + 1)
                self.show_info_settings(self.PARAM_GUITAR_CAPOTASTO, 1)
        
            if input_device.device_info('GUITAR_INSTRUMENT') == False:
                print('GUITAR_INSTRUMENT')
                self.program_number(self.program_number()[0] + 1)
                synth.set_program_change(self.program_number()[1], 0) 
                self.show_info_settings(self.PARAM_ALL, 1)
        
##            if input_device.device_info('GUITAR_EFFECTOR') == False:
##                print('GUITAR_EFFECTOR')
##                self.pitch_bend_range(self.pitch_bend_range() + 1)
##                self.show_info_settings(self.PARAM_GUITAR_EFFECTOR, 1)

        except Exception as e:
            led_flush = False
            for cnt in list(range(5)):
                pico_led.value = led_flush
                led_flush = not led_flush
                sleep(0.5)

            led_flush = False
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
            self._screen_mode = inst_num % 2
            
        return self._screen_mode

    def show_info(self, param=-1):
        sc_mode = self.screen_mode()
        if   sc_mode == self.PLAY_GUITAR:
            instrument_guitar.show_info(param, 1)
            
        elif sc_mode == self.GUITAR_SETTINGS:
            instrument_guitar.show_info_settings(param, 1)

    # Application task called from asyncio, never call this directly.
    def do_task(self):
        # Screen mode change
        if input_device.device_info('MODE_CHANGE') == False:
            sc_mode = self.screen_mode(self.screen_mode() + 1)
            if   sc_mode == self.PLAY_GUITAR:
                instrument_guitar.setup()
                
            elif sc_mode == self.GUITAR_SETTINGS:
                instrument_guitar.setup_settings()

            display.fill(0)
            self.show_info()

        # Play the current instrument
        sc_mode = self.screen_mode()
        if   sc_mode == self.PLAY_GUITAR:
            instrument_guitar.do_task()

        elif sc_mode == self.GUITAR_SETTINGS:
            instrument_guitar.do_task_settings()


################# End of Application Class Definition #################
        

def setup():
    global pico_led, sdcard, synth, display, input_device, instrument_guitar, instrument_drum, application

    # LED on board
#    pico_led = digitalio.DigitalInOut(GP25)
    pico_led = digitalio.DigitalInOut(LED)
    pico_led.direction = digitalio.Direction.OUTPUT
    pico_led.value = True

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
    interrupt_led   = asyncio.create_task(led_flush())
    await asyncio.gather(interrupt_task1, interrupt_task2, interrupt_task3, interrupt_task4, interrupt_adc0, interrupt_led)

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




