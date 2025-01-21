# Pico Guitar User's Manual
![pico_guitar.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/pico_guitar.jpg)

## 1. Introduction
Pico Guitar is a MIDI controller which works as a USB MIDI device.<br/>
This device has 6 momentary press switchs and 8 touch sensor pads.  You can assign any guitar chord for each momentary press switch.  6 pads correspond to 6 guitar strings.  The rest two pads are a strumming pad and a pitch bend pad.<br/>
Press a switch to select a chord, then touch the pads to play guitar.  Pico guitar sends MIDI NOTE-ON messages to a USB MIDI sound source module.<br/>
You can assign drum instruments for 6 pads of guitar strings.  So you can play a guitar chord and drums at the same time.<br/>
If you have guitar chord score files, you can play the music only to press "Next Chord" switch.<br/>

## 2. Appearance
![picoguitar_top_look.png](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/picoguitar_top_look.png)

1) 8 momentary press switches (S1 to S8) to select a chord playing and to set up parameters.<br/>
2) 8 touch sensor pads to play MIDI instrument like guitar.  The pads can get pressure information to control velocity and pitch bend depth.<br/>
3) OLED（Display） shows you Pico Guitar's information.<br/>
4) USB-A cable shoud connect to a USB MIDI sound source module.  Power (+5V) should be supplied via the cable.<br/>

## 3. Notes
A USB MIDI sound source module is needed.  This module must work as a USB HOST and  must supply power (+5V) to Pico Guitar.

## 4. Turn Pico Guitar on
![splash.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/splash.jpg)
1) Prepare a Pico Guitar.<br/>
2) Prepare a USB MIDI sound source module working as a USB HOST.<br/>
3) Prepare a USB cable.  Micro USB-B for Pico Guitar side.<br/>
4) Connect Pico Guitar to the USB MIDI sound souce module with the USB cable.<br/>
5) Turn on the MIDI sound source module.  Then Pico Guitar turns on by power supply from the sound module.  You will see a splash screen on the OLED display, then a title of "**---GUITAR PLAY---**".<br/>
6) Now you can play Pico Guitar.<br/>
<br/>
A photo below is a USB MIDI synthesizer I made and a Pico Guitar.  These devices are connected each other with a USB cable.<br/> 

![connection.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/connection.jpg)
<br/>

## 5. Chord Play Mode
You can play guitar chords in Chord Play Mode.  Just after turning on, Pico Guitar is under this mode.<br/>
 
![picoguitar_play_chord.png](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/picoguitar_play_chord.png)
### 5-1. Chord Selectors / Chord Page
You can select a chord to play with Chord Selectors (6 switches).  Each switch has two chords, chord-A and chord-B.  You can switch chord-A or B with Chord Page switch.<br/>
You can assign guitar chords for each Chord Selector switch on Chord Setting Mode.<br/>
 
### 5-2. 8 Pads
After selecting a chord, you can play the chord with 8 pads.  String1 to 8 correspond to 6 string on guitar.  String1 is the highest tone string, and String6 is the lowest tone's.<br/>
Strumming pad is for strumming the chord.<br/>
Pitch Bend pad is for pitch bend effect.<br/>
All pads detect pressure value.  Pressing stronger, getting loud sound or deep pitch bend effect.<br/>

### 5-3. Display
OLED display in this mode is as below.<br/>
![chord_play.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/chord_play.jpg)
<br/>
・A M L +0<br/>
This shows you the current chord to play.  "A" is base note, "M" is major chord, "L" is low chord position and "+0" is fret number setting capotasto ("+0" means no capotasto).<br/>
If the current chord is A/C, high position chord and capotasto is on the 2nd fret, you will see "A M H/C +2".<br/><br/>

・Banjo<br/>
This shows you the current instrument name in GM sounds source.<br/><br/>

・CM L, AM L/C#, ...<br/>
You will see 6 chords on the left-bottom region on OLED display.  These chords correspond to the Chord Selectors (6 switches).<br/>
"AM L/C" means A major on chord C and low position chord.<br/>
Press the Chord Page switch, then you will see another chord on each Chord Selector.<br/><br/>

・Notes on the right-top region<br/>
There are 7 notes name in vertical direction.  6 notes on the right side correspond to the 6 strings on guitar.  The most right string is the highest tone string.<br/>
"xx" means a mute string.  Even if you touch a mute string pad, you can't hear any sound.<br/>
The most left side string is for on-chord base note.  If the chord is A/C, you will see Cn (C4, C5, ...)  The chord is NOT on-chord, you will see "--".<br/>

### 5-4. Mode Change
Press this switch, switch to Chord Stting Mode.<br/>

## 6. Chord Setting Mode
In this mode, you can assign any chord for each Chord Selector switch.<br/>
![picoguitar_guitar_settings.png](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/picoguitar_guitar_settings.png)

### 6-1. Chord Switch Selector
You select a switch number in 6 Chord Selector switches.  The switch number changes from 1 to 12.　Next to 12 is 1.<br/>
Switch 1 to 6 correspond to green, yellow, orange, red, brown and gray switch.  Switch 7 to 12 correspond to the same switches, but you need to press Chord Page switch to get these chord set on the Chord Play Mode.<br/>

### 6-2. Root Selector
Select a base note from C, C#, D, ..., A#, B.  Next to B is C.<br/>

### 6-3. Chord Selector
Select a chord type from M(major), M7, 7, 6, ..., dim7.  Next to dim7 is M.<br/>

### 6-4. Low/High Selector
Select a chord position in Low or High.<br/>

### 6-5. On-chord Selector
If you make a on-chord, you need to select a on-chord note here.  Blank means that this chord does NOT have any on-chord note.　Select a note for on-chord note from C, C#, D, ..., A#, B.  Next to B is blank.<br/>

### 6-6. Octave Selector
Select a octave from 1 to 9.  Default is 4, chord C makes C4.  Next to 9 is 1.<br/>

### 6-7. Chord Set File Selector
You can assign twelve chords for the Chord Selectors switches by selecting a Chords Setting File.<br/>
You can save many kinds of the files in Rapsberry Pi PICO memory.  Press the switch, you will see a next chords set name.<br/>
 
### 6-8. 8 Pads
You can play the current setting chord.<br/>

### 6-9. Display
OLED display in this mode is as below.<br/>
![chord_settings.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/chord_settings.jpg)
<br/>
・BUTTN:<br/>
A Chord Selector switch number to assign it's chord.<br/><br/>

・CHORD:<br/>
A chord name to be assigned.<br/><br/>

・OCTAV:<br/>
An octave value to be assigned.<br/><br/>

・FILE:<br/>
A Chord Setting name.<br/><br/>

### 6-10. Mode Change
Press this switch, switch to Configuration Mode.<br/>

## 7. Configuration Mode1
This mode is for setting up the general parameters.<br/>
![picoguitar_guitar_config1.png](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/picoguitar_guitar_config1.png)
<br/>
### 7-1. Velocity Offset
You can select a smallest value of NOTE-ON velocity.<br/>
8 Pads can detect pressure strength.  Pico Guitar makes NOTE-ON velocity value by the value.  If you think the smallest velocity is too small (can't hear instrument sound), you can change the smallest velocity value.<br/>

### 7-2. Velocity Curve
The pressure strength values detected by the pad are not linear line but log-curve.  You can change the curve shape by Velocity Curve value.<br/>
The value range is from 1.5 to 4.0.  Larger value gets bigger curve.<br/>

### 7-3. Pitch Bend Range
You can select a pitch bend range value from 0 to +12. 1 correspond to half tone.<br/>
Select 0, the pitch bend does NOT work.<br/>

### 7-4. Modulation Level01
You can change the value of modulation level01(LSB).  The modulation works in the after touch phase.<br/>

### 7-5. Modulation Level02
You can change the value of modulation level02(MSB).  The modulation works in the after touch phase.<br/>

### 7-6. After Touch On
You can change the dulation in second to begin the after touch effect.<br/>
The after touch does not work on the drum pads.<br/>

### 7-7. 8 Pads
8 Pads work even in this mode.<br/>

### 7-8. Display
OLED display in this mode is as below.<br/>
![config1.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/config1.jpg)
<br/>
・OFFSET VELOCITY:<br/>
The current smallest velocity value.<br/><br/>

・VELOCITY CURVE:<br/>
The current velocity curve parameter value.<br/><br/>

・PITCH BEND RANGE:<br/>
The current pitch bend range value。<br/><br/>

・CAPOTASTO FRETS:<br/>
The current capotasto fret number.<br/>

・INST:<br/>
The current instrument name.<br/>

### 7-9. Mode Change
Press this switch, switch to Configuration Mode2.<br/>

## 8. Configuration Mode2
This mode is for setting up the general parameters.<br/>
![picoguitar_guitar_config2.png](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/picoguitar_guitar_config2.png)
<br/>
### 8-1. MIDI Channel
You can select a MIDI OUT channel to send MIDI messages playing guitar.<br/>
Channel 10 is used for playing drums.<br/>

### 8-2. Capotasto
You can attach a capotasto at a fret.  The Capotasto value is the fret number to attach capotasto.  You can select not only positive value but also negative value.  0 means NO capotasto.<br/>

### 8-3. Instrument Selector
Select an instrument in GM sounds source.  You can see only stringed instruments.<br/>
Select an instrument, Pico Guitar sends a MIDI program change message immediately.<br/>

### 8-4. Play Drum
You can change the Pad1-6 for playing drums.  ON is for drums, OFF is for guitar strings.<br/>
The strumming pad and the pitch bend pad is always for playing guitar.<br/>

### 8-5. Drum Set Selector
You can select a drum set from the drum setting files.  You need to edit these file with a text editor.<br/>
MIDI OUT channel 10 is used to send MIDI messages for drums.<br/>

### 8-6. Drum Pad Selector
Select a pad number to change it's drum instrument.<br/>

### 8-7. Drum Selector
Select a drum instrument.<br/>

### 8-8. 8 Pads
8 Pads work even in this mode.<br/>

### 8-9. Display
OLED display in this mode is as below.<br/>
![config2.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/config2.jpg)
<br/>
・MIDI CHANNEL:<br/>
MIDI OUT channel selected.<br/><br/>
・CAPOTASTO FRET:<br/>
Capotasto fret number selected.<br/>
・INST:<br/>
A GM instrument name selected.<br/>
・PLAY DRUM:<br/>
Assigned Pad1-6 for drums(ON) or guitar(OFF).<br/>
・DRUM:<br/>
A Drum set name selected.<br/><br/>
・DR2=5:<br/>
"DRn" means a drum pad number "n" selected.<br/>
"=x" means a drum instrument ID "x", this ID is an internal code of Pico Guitar.<br/>
You can see the drum instrument name selected on the right side.<br/><br/>

### 8-10. Mode Change
Press this switch, switch to Music Play Mode.<br/>

## 9. Music Play Mode
In this mode, you can play a music by only pressing one switch and 8 Pads.  It's so easy!!<br/>
Select a music file in pre-loaded music files, a series of chords for the music are loaded in Pico Guitar.  After that, press the NEXT switch and play with 8 Pads, then press the NEXT switch, and so on.<br/>
![picoguitar_play_music.png](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/picoguitar_play_music.png)

### 9-1. Previous File
Select a previous music file.<br/>

### 9-2. Next File
Select a next music file.<br/>

### 9-3. Previous Chord
Select a previous chord in the loaded music.<br/>

### 9-4. Next Chord
Select a next chord in the loaded music.<br/>

### 9-4. Head of Music
Rewind to the head of the music.<br/>

### 9-5. End of Music
Move to the end of the music.<br/>
 
### 9-6. 8 Pads
Play the current chord.<br/>

### 9-7. Display
OLED display in this mode is as below.<br/>
![music_player.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/music_player.jpg)
<br/>
・MUSIC:<br/>
A music title selected.<br/><br/>

・PLAY:<br/>
You can see the current chord position and the total number of chords separated by '/'.<br/><br/>

・CHORD:<br/>
The current chord to play.<br/>

### 9-8. Mode Change
Press this switch, switch to Chord Play Mode.<br/>
