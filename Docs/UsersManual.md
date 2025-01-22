# Pico Guitar User's Manual
![pico_guitar.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/pico_guitar.jpg)

## 1. 機能
　Pico GuitarはUSB MIDIデバイスとして動作するMIDIコントローラーです。<br/>
　押しボタンスイッチにコードを割り当てておくことで、スイッチを押してギターの弦に相当するパッドを押すことでギターをコード演奏しているようにUSB MIDI音源にMIDIメッセージを送信できます。ピッチベンドをかけたり、アフタータッチでモジュレーションをかけて演奏に変化をつけることもできます。</br>
　パッドの一部をドラムに変更して、ギターコードとドラムでの演奏が可能です。<br/>
　コード譜をファイルで設定することで、ワンボタンで次のコードへ切り替えながら演奏を楽しむこともできます。<br/>

## 2. 外観
![picoguitar_top_look.png](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/picoguitar_top_look.png)

1) 8個の押しボタンスイッチ（S1〜S8）でコードを選んだり、各種設定を行います。<br/>
2) 8個のタッチパッド（8 Pads）でギターの様に演奏します。<br/>
3) OLED画面（Display）に各種情報が表示されます。<br/>
4) USB-AはMIDI音源に接続するためのUSBケーブルです。電源もここから供給されます。<br/>

## 3. 注意事項
　Pico GuitarのほかにUSBホストデバイスになるUSB MIDI音源が必要です。電源もUSBホストから供給される必要があります。

## 4. 接続〜起動
![splash.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/splash.jpg)
1) Pico Guitarを用意します。<br/>
2) USBホストとなるUSB MIDI音源を用意します。<br/>
3) Pico GuitarとMIDI音源を接続するUSBケーブルを用意します。Pico Guitar側はMicro USB-Bオスです。<br/>
4) Pico GuitarのRapsberry Pi PICOのUSBコネクタとMIDI音源をUSBケーブルで接続します。<br/>
5) MIDI音源の電源を入れます。MIDI音源からUSBケーブルで電源が供給されると、Pico Guitarが起動してOLED画面に「**PicoGuitar**」と表示されます。<br/>
6) OLED画面が「**---GUITAR PLAY---**」という演奏用画面になると演奏できます。<br/>
<br/>
　この画像は、Unit-SYNTH / Unit-MIDIというGM音源シンセモジュールをPICOで制御している自作のUSB MIDI音源と接続したものです。<br/>
 
![connection.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/connection.jpg)
<br/>
## 5. コード演奏モード
　起動直後はコード演奏画面になっています。このモードではギターのコード演奏ができます。<br/>
 
![picoguitar_play_chord.png](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/picoguitar_play_chord.png)
### 5-1. Chord Selectors / Chord Page
　6個のスイッチでコードを選択します。各スイッチのコードはコード設定モードで割り当てます。<br/>
　スイッチは6個ですが、1個のスイッチに2つのコードを割り当てることができます。Chord Pageスイッチを押すと、Chord Selectorsのスイッチに割り当てられている2つのコードの入れ替えができます。6個のスイッチの1ページ目と2ページ目を切り替えるイメージです。<br/>
 
### 5-2. 8 Pads
 　コードを選択したら、8個のパッドを指で押して演奏します。Strings1〜6はギターの6弦に対応します。String1が高音側です。Strummingはストーク奏法でコードを鳴らすパッドです。Pitch Bendは鳴っている音にピッチベンドをかけます。<br/>
　パッドは圧力を検知し、強く押すと音が大きくなったり、ピッチベンドが強くかかったりします。<br/>

### 5-3. Display
　コード演奏時の画面は以下のようになっています。<br/>
![chord_play.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/chord_play.jpg)
<br/>
・A M L +0<br/>
　選択されているベース音(A)、コード(M=major)、ロー／ハイコード(L)、カポタスト位置(+0=カポタストなし)が表示されています。<br/>
 　オンコード（分数コード）A/Cで、ハイコード、カポタスト位置2フレット目の場合は「A M H/C +2」のように表示されます。 <br/><br/>
・Banjo<br/>
　演奏するGM音源の楽器名が表示されています。<br/><br/>
・CM L, AM L/C#, ...<br/>
　画面左下の3行は6個のChord Selectorsスイッチに割り当てられているコードが表示されています。CM LはCメジャーのローコード、AM L/CはAメジャーのローコードでオンコードでベース音をCにしたコードを表しています。<br/>
　Chord Pageでコード設定のページを切り替えると、この表示も変化します。<br/><br/>
・画面右上のノート表示<br/>
　縦書きで音程が表示されています。右の6列がギターの6弦に相当し、右から高音の1弦になっています。画面のコードは高音側の4弦をF5, C#5, A4, F4で発音することを表しています。<br/>
　5弦と6弦はxxとなっていますが、これはこれらの弦がミュート弦で音を発しないことを表しています。これらのパッドを押しても音は出ません。<br/>
　一番左のB4はオンコード（分数コード）でベース音に変えて発音する音程を表しています。オンコードがない場合は--と表示されます。<br/>

### 5-4. Mode Change
　このスイッチを押すとコード設定モードに移行します。<br/>

## 6. コード設定モード
　コード設定モードでは、コード演奏モードのChord Selectorsの6個のスイッチにコードを割り当てることができます。<br/>
![picoguitar_guitar_settings.png](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/picoguitar_guitar_settings.png)

### 6-1. Switch Selector
　コードを割り当てるスイッチの番号を選択します。押すたびに番号が1〜12に変化し、12で押すと1に戻ります。<br/>
　1,2,3,4,5,6はスイッチの緑、黄、橙、赤、茶、灰に対応します。コード演奏モードのChord Pageで切り替えられる1ページ目に相当します。7〜12の6個はその2ページ目に相当します。演奏中によく使うコードを1ページ目、稀に登場するコードは2ページ目に割り当てると良いかもしれません。<br/>

### 6-2. Root Selector
　コードのベース音を選択します。スイッチを押すたびにC, C#, D, D#, E, F,...のように切り替わり、最後のBで押すとCに戻ります。<br/>

### 6-3. Chord Selector
　Root Selectorで選んだベース音にコードを設定します。スイッチを押すたびにM(major), M7, 7, 6, aug, m, mM7, ...のように切り替わります。最後のdim7で押すとMに戻ります。<br/>

### 6-4. Low/High Selector
　ローコード、ハイコードの切り替えをします。スイッチを押すたびにLow, Highが切り替わります。<br/>

### 6-5. On-chord Selector
　ベース音の代わりとする音程を指定します。押すたびにC,C##,...と変化し、Bの次は空欄となってオンコードとしないことになります。<br/>

### 6-6. Octave Selector
　1〜9の範囲でオクターブを切り替えられます。初期値は4です。9で押すと1に戻ります。<br/>

### 6-7. Chord Set File Selector
　曲調などに合ったコード進行を構成するコード群をあらかじめ定義した設定ファイルがあると、そのファイルを指定してChord Selectorsスイッチに一括してコードを割り当てることができます（設定ファイルの個数制限はありません。PICOのメモリが許す範囲で保存できます）<br/>
　スイッチを押すたびに設定ファイルが切り替わり、切り替わった時点でChord Selectorsのスイッチへのコード割り当ても変更されます。<br/>
 
### 6-8. 8 Pads
 　設定中のコードは8個のパッドを指で押して演奏できます。<br/>

### 6-9. Display
　コード設定時の画面は以下のようになっています。<br/>
![chord_settings.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/chord_settings.jpg)
<br/>
・SWTCH:<br/>
　Chord Switch Selectorで選択されたChord Selectorsスイッチの番号が表示されています。このスイッチにコードを設定することになります。<br/><br/>
・CHORD:<br/>
　Root Selector、Chord Selector、Low/High Selector、On-chord Selectorで指定されたコード名が表示されています。<br/><br/>
・OCTAV:<br/>
　設定されているオクターブが表示されます。通常は4です。<br/><br/>
・CD FL:<br/>
　選択されたコード設定ファイルのタイトルが表示されています。<br/><br/>

### 6-10. Mode Change
　このスイッチを押すとコンフィグレーションモードに移行します。<br/>

## 7. コンフィグレーションモード1
　コンフィグレーションモード1では、演奏の全体的な設定ができます。<br/>
![picoguitar_guitar_config1.png](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/picoguitar_guitar_config1.png)
<br/>
### 7-1. Velocity Offset
　8個のパッドは圧力を検知して、MIDI NOTE-ONのベロシティを変更して演奏する音の大きさを変えています。このスイッチを押すとベロシティの下限を変更できます。ベロシティの範囲が大きくて弱い音の音量が小さすぎるといった場合は、この値を大きくすることで解消できます。<br/>
　ただし、この値が大きくなるほどベロシティの変化範囲が狭くなるので、音の強弱の変化が少なくなります。<br/>

### 7-2. Velocity Curve
　パッドを押す圧力をベロシティに変換するときの変化の特性を変更できます。スイッチを押すたびに1.5〜4.0の範囲で0.1単位で値が変化します。値が大きいほど強弱の変化量がダイナミックになります。小さいと全体的にフラットになって強弱があまりつかなくなります。<br/>

### 7-3. Pitch Bend Range
　ピッチベンドで変化する音程の範囲を設定できます。スイッチを押すたびに0〜+12の範囲で変化します。1が半音に相当するので、最大1オクターブの範囲で設定できます。<br/>
　0を選ぶとピッチベンドのパッドを押しても音程は変化しなくなります。<br/>

### 7-4. Modulation Level01
　アフタータッチでかかるエフェクトのモジュレーションのレベル（LSB側）を設定します。<br/>

### 7-5. Modulation Level02
　アフタータッチでかかるエフェクトのモジュレーションのレベル（MSB側）を設定します。<br/>

### 7-6. After Touch On
　Padを押したままにしたときに機能するアフターエフェクトがかかるまでの秒数を指定します。<br/>
　なお、Padがドラムの場合にはアフターエフェクトは機能しません。<br/>

### 7-7. 8 Pads
 　設定中のコードは8個のパッドを指で押して演奏できます。<br/>

### 7-8. Display
　コンフィグレーション時の画面は以下のようになっています。<br/>
![config1.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/config1.jpg)
<br/>
・VELOC OFFSET:<br/>
　指定されたベロシティの下限値が表示されています。<br/><br/>
・VELOC CURVE:<br/>
　指定されたベロシティカーブの値が表示されています。<br/><br/>
・P-BEND RANGE:<br/>
　指定されたピッチベンドレンジの値が表示されています。<br/><br/>
・MODULA LVL01:<br/>
　指定されたモジュレーションのレベル01(LSB)が表示されています。<br/><br/>
・MODULA LVL02:<br/>
　指定されたモジュレーションのレベル02(MSB)が表示されています。<br/><br/>
・AFT-TOUCH ON:<br/>
　モジュレーションがかかるまでのアフタータッチの秒数が表示されています。<br/><br/>

### 7-9. Mode Change
　このスイッチを押すとコンフィグレーションモード2に移行します。<br/>

## 8. コンフィグレーションモード2
　コンフィグレーションモード2では、演奏の全体的な設定ができます。<br/>
![picoguitar_guitar_config2.png](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/picoguitar_guitar_config2.png)
<br/>
### 8-1. MIDI Channel
　ギター演奏データを送信するMIDI OUTチャンネルを指定します。<br/>
　ただし、ドラム演奏は強制的に10チャンネルに送信されます。<br/>

### 8-2. Capotasto
　カポタストを付けるフレットの位置を設定できます。-12〜+12の範囲で変更できます。0でカポタストなしです。実際のギターでマイナスのカポタストは付けられませんが、Pico Guitarでは可能としました。<br/>
　コード設定のOctave Selectorではオクターブ単位での音程を設定できましたが、カポタストではさらに半音単位で音程を変更できます。<br/>

### 8-3. Instrument Selector
　MIDI GM音源内の楽器を変更できます。スイッチを押すたびに切り替わります。各種ギターとシタールなどの弦楽器系から選択できます。<br/>
　選択した時点でMIDIのプログラムチェンジが送信され、音源のプログラムが切り替わります（その後、音源側でプログラムを変更した場合は、その音で演奏されます）

### 8-4. Play Drum
　Pad1〜6をドラム演奏用にするか、しないかの設定ができます。ONでドラム、OFFでギターの弦になります。<br/>

### 8-5. Drum Set Selector
　ファイルに保存されているドラムセット（Pad1〜6に割り当てるドラム系音色群）を変更できます。現時点でドラムセットの定義はファイルでしかできません。<br/>
　ドラムの演奏はMIDIチャンネル10で送信されます。<br/>

### 8-6. Drum Pad Selector
　ドラムの種類を変更したいPad1〜6を選択します。<br/>

### 8-7. Drum Selector
　ドラムの種類を変更します。<br/>

### 8-8. 8 Pads
 　設定中のコードは8個のパッドを指で押して演奏できます。<br/>

### 8-9. Display
　コンフィグレーション時の画面は以下のようになっています。<br/>
![config2.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/config2.jpg)
<br/>
・MIDI CHANNEL:<br/>
　指定されたMIDI OUT CHANNELが表示されています。<br/><br/>
・CAPOTASTO FRET:<br/>
　指定されたカポタストのフレット位置が表示されています。<br/>
・INST:<br/>
　選択されたGM音源楽器名が表示されています。<br/>
・PLAY DRUM:<br/>
　ドラム演奏機能のON/OFFが表示されています。ONのとき、ギターの6弦に相当するPad1〜6がドラム用に変化します。ストローク演奏とピッチベンドはそのままです。<br/>
・DRUM:<br/>
　指定されたドラムセット名が表示されています。<br/>
・DR2=5:<br/>
　指定されたドラムパッドのドラム名が表示されています。<br/>DR2の2はパッド番号、=の後ろの番号はドラムの種類番号（Pico Guitarの内部番号）です。その右側にドラムのGM音源名が表示されています。<br/><br/>

### 8-10. Mode Change
　このスイッチを押すとコード譜演奏モードに移行します。<br/>

## 9. コード譜演奏モード
　コード譜演奏モードでは、あらかじめ保存されているコード譜を使ってスイッチを押すだけでコードが切り替わって曲を演奏できます。コード譜は複数保存可能です（個数制限はありません。PICOのメモリが許す範囲で保存できます）<br/>
![picoguitar_play_music.png](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/picoguitar_play_music.png)

### 9-1. Previous File
　1つ前のコード譜ファイルを選択します。演奏対象のコードはコード譜の先頭になります。<br/>

### 9-2. Next File
　1つ後ろのコード譜ファイルを選択します。演奏対象のコードはコード譜の先頭になります。<br/>

### 9-3. Previous Chord
　演奏しているコードの1つ前のコードに戻します。譜面の先頭で押すと最後のコードに移動します。<br/>

### 9-4. Next Chord
　演奏しているコードの次のコードに移動ます。通常は曲に合わせてこのスイッチを押し、次のコードへ切り替えながらパッドでコードを演奏します。<br/>
　コード設定では12個のコードまで設定できましたが、コード譜ではその制限もなく、譜面通りに必要なコードを設定して演奏できます。<br/>
　最後のコードのところでNext Chordを押すと曲の終わりを表すEndという表示になります。ここでNext Chordを押すと先頭に戻ります。<br/>

### 9-4. Head of Music
　譜面の先頭のコードに戻します。<br/>

### 9-5. End of Music
　譜面の最後のコードに移動します。<br/>
 
### 9-6. 8 Pads
 　コード譜面で選択されているコードは8個のパッドを指で押して演奏できます。Next Chordでコードを切り替えながら簡単に演奏を楽しめます。<br/>

### 9-7. Display
　コード譜演奏時の画面は以下のようになっています。<br/>
![music_player.jpg](https://github.com/ohira-s/PICO_USB_MIDI_INSTRUMENT/blob/master/Docs/music_player.jpg)
<br/>
・MUSIC:<br/>
　選択されているコード譜のタイトルが表示されています。<br/><br/>
・PLAY:<br/>
　演奏対象のコード位置と全コード数がスラッシュで区切られて表示されています。最後のコードを演奏し終わるとENDと表示されます。<br/><br/>
・CHORD:<br/>
　演奏対象のコードが表示されています。パッドを押すとこのコードで演奏できます。<br/>
　歌詞と演奏タイミングデータが定義されている場合、その情報がコード名の下に2行で表示されます。<br/>

### 9-8. Mode Change
　このスイッチを押すとコード演奏モードに移行します。<br/>
