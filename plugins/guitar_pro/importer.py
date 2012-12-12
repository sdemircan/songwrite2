# -*- coding: utf-8 -*-

# Songwrite 2
# Copyright (C) 2003 Jean-Baptiste LAMY -- jibalamy@free.fr
# Copyright (C) 2003 Bertrand LAMY
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys, struct
import songwrite2.model as model

class GPBuffer:
    def __init__(self, buffer):
        self.buffer = buffer
        self.position = 0
        
    def advance(self, nb):
        self.position += nb

    def pop_byte(self):
        a = ord(self.buffer[self.position])
        self.advance(1)
        return a
    def pop_long(self):
        a = struct.unpack('l', self.buffer[self.position:self.position + 4])[0]
        self.advance(4)
        return a
    def pop_color(self):
        a = (ord(self.buffer[self.position]), ord(self.buffer[self.position + 1]), ord(self.buffer[self.position + 2]), ord(self.buffer[self.position + 3]))
        self.advance(4)
        return a
    def pop_string(self):
        size = ord(self.buffer[self.position])
        a = self.buffer[self.position + 1:self.position + 1 + size]
        self.advance(size + 1)
        return a
    def pop_nstring(self, total_size):
        size = ord(self.buffer[self.position])
        a = self.buffer[self.position + 1:self.position + 1 + size]
        self.advance(total_size + 1)
        return a
    def pop_l_string(self):
        size = struct.unpack('l', self.buffer[self.position:self.position + 4])[0]
        a = self.buffer[self.position + 4:self.position + 4 + size]
        self.advance(size + 4)
        return a
    def pop_long_string(self):
        size = self.pop_long()
        nb = ord(self.buffer[self.position])
        if(size == 0): size = nb
        a = self.buffer[self.position + 1:self.position + 1 + nb]
        self.advance(size)
        return a


def parse(data, verbose = 1):

    # create Songwrite 2 song object
    song = model.Song()
    song.partitions = []
    song.mesures    = []
    
    # open the file
    buf = GPBuffer(data)
    
    #--------------------
    # read file signature
    #--------------------
    signature_size = buf.pop_byte()
    if  (buf.buffer[1:19] == "FICHIER GUITAR PRO"):
        guitar_pro_file_version = float(buf.buffer[21:25])
    elif(buf.buffer[1:20] == "FICHIER GUITARE PRO"):
        guitar_pro_file_version = float(buf.buffer[22:26])
    else:
        print 'WARNING: seems that it is not a guitar pro file...'
        try:
            guitar_pro_file_version = float(buf.buffer[signature_size - 3:signature_size + 1])
        except:
            guitar_pro_file_version = 4.06
    buf.advance(signature_size)
    
    # UNKNWON
    buf.advance(6)

    #-----------------------
    # read the header part 1
    #-----------------------
    if(guitar_pro_file_version >= 3.0):
        title       = buf.pop_long_string()
        subtitle    = buf.pop_long_string()
        artist      = buf.pop_long_string()
        album       = buf.pop_long_string()
        author      = buf.pop_long_string()
        copyright   = buf.pop_long_string()
        tabled_by   = buf.pop_long_string()
        instruction = buf.pop_long_string()

        notice_nb_lines = buf.pop_long()
        notice = ''
        i = 0
        while (i < notice_nb_lines):
            str = buf.pop_long_string()
            notice += str + '\n'
            i += 1
        notice = notice[:-1]

        shuffle = buf.pop_byte()
    else:
        if(guitar_pro_file_version >= 2.0):
            buf.advance(1)
        title = buf.pop_nstring(100)
        # UNKNOWN
        buf.advance(1)
        subtitle    = ''
        artist      = ''
        album       = ''
        author      = buf.pop_nstring(50)
        # UNKNOWN
        buf.advance(1)
        copyright   = ''
        tabled_by   = ''
        instruction = buf.pop_nstring(100)
        notice      = ''
        shuffle = 0
        print title, author, instruction

    # Songwrite 2
    if(subtitle and title != subtitle): title += ' -- ' + subtitle
    song.title = unicode(title, 'latin')
    if(artist): author += '(' + artist + ')'
    song.authors = unicode(author, 'latin')
    song.copyright = unicode(copyright, 'latin')
    if(album): song.comments += _('Extract from album ') + unicode(album + '\n', 'latin')
    if(tabled_by): song.comments += _('Tabled by ') + unicode(tabled_by + '\n', 'latin')
    song.comments += unicode(instruction + notice, 'latin')
    
    #------------
    # read lyrics
    #------------
    if(guitar_pro_file_version >= 4.0):
        lyrics_track = buf.pop_long()
        lyrics_bar_beginnings = []
        lyrics_lines = []
        i = 0
        while(i < 5):
            lyrics_bar_beginnings.append(buf.pop_long())
            lyrics_lines.append(buf.pop_l_string())
            i += 1
            
        # Songwrite 2
        # TO DO
        
        print lyrics_lines
        
    #-----------------------
    # read the header part 2
    #-----------------------
    tempo = buf.pop_long()

    # UNKNOWN
    if  (guitar_pro_file_version >= 4.0):
        buf.advance(5)
    elif(guitar_pro_file_version >= 3.0):
        buf.advance(4)
    else:
        buf.advance(8)

    #-----------------
    # read instruments
    #-----------------
    if(guitar_pro_file_version >= 3.0):
        instruments = []
        i = 0
        while(i < 64):
            instruments.append((buf.pop_long(), buf.pop_byte(), buf.pop_byte(), buf.pop_byte(), buf.pop_byte(), buf.pop_byte(), buf.pop_byte()))
            # UNKNOWN
            buf.advance(2)
            i += 1
    else:
        i = 0
        while(i < 8):
            nb_long = buf.pop_long()
            buf.advance(nb_long * 4)
            i += 1

    #-----------------------
    # read the header part 3
    #-----------------------
    nb_bars   = buf.pop_long()
    nb_tracks = 0
    
    if(guitar_pro_file_version >= 3.0):
        nb_tracks = buf.pop_long()
    else:
        pass
      
    #-------------------
    # read the bars info
    #-------------------
    if(guitar_pro_file_version >= 3.0):
        i = 0
        time = 0
        bar_rythm_1  = 4
        bar_rythm_2  = 4
        prev_block   = 0
        repeat_start = 0
        repeat_end   = 0
        alt_start    = 0
        in_alt       = 0
        while (i < nb_bars):
            bar_flag = buf.pop_byte()
            if(bar_flag & 1):
                bar_rythm_1 = buf.pop_byte()
            if(bar_flag & 2):
                bar_rythm_2 = buf.pop_byte()
                
            mesure = model.Mesure(song, time, tempo, bar_rythm_1, bar_rythm_2, shuffle)
            
            if(bar_flag & 8):
                # repeat close
                volta = buf.pop_byte()
                if alt_start:
                    #print "close alt   ", len(song.mesures)
                    #print "    =>", alt_start, len(song.mesures)
                    song.playlist.append(model.PlaylistItem(song.playlist, alt_start, len(song.mesures)))
                    prev_block = len(song.mesures) + 1
                    
                    alt_start = 0
                    
                else:
                    #print "close repeat", len(song.mesures)
                    for j in range(volta):
                        #print "    =>", prev_block, len(song.mesures)
                        song.playlist.append(model.PlaylistItem(song.playlist, prev_block, len(song.mesures)))
                    prev_block = len(song.mesures) + 1
                    
            if(bar_flag & 4):
                #print "open repeat ", len(song.mesures)
                # repeat open
                in_alt = 0
                repeat_start = len(song.mesures)
                if prev_block <= len(song.mesures) - 1:
                    #print "    =>", prev_block, len(song.mesures) - 1
                    song.playlist.append(model.PlaylistItem(song.playlist, prev_block, len(song.mesures) - 1))
                    prev_block = len(song.mesures)
                    
            if(bar_flag & 16):
                #print "open alt    ", len(song.mesures)
                # alternate ending
                buf.pop_byte()
                alt_start = len(song.mesures)
                if not in_alt:
                    repeat_end = len(song.mesures) - 1
                    in_alt = 1
                #print "    =>", repeat_start, repeat_end
                song.playlist.append(model.PlaylistItem(song.playlist, repeat_start, repeat_end))
                in_alt = 1
                
            if(bar_flag & 32):
                # marker
                # TO DO
                bar_marker = buf.pop_long_string()
                bar_marker_color = buf.pop_color()
            if(bar_flag & 64):
                # change armor
                # TO DO
                armor_jump = buf.pop_byte()
                minor = buf.pop_byte()
            if(bar_flag & 128):
                # double ending
                pass
            
            
            # Songwrite 2
            song.mesures.append(mesure)
            time += song.mesures[-1].duration        
            i += 1
            
        last = len(song.mesures) - 1
        if prev_block <= last:
            #print "    =>", prev_block, last
            song.playlist.append(model.PlaylistItem(song.playlist, prev_block, last))
            
        song.playlist.analyse()
        
    #---------------------
    # read the tracks info
    #---------------------
    if(guitar_pro_file_version >= 3.0):
        i = 0
        while (i < nb_tracks):
            track_spc = buf.pop_byte()
            track_name = buf.pop_nstring(40)
            track_nb_strings = buf.pop_long()
            track_strings_pitch = []
            j = 0
            while(j < 7):
                p = buf.pop_long()
                if(j < track_nb_strings):
                    track_strings_pitch.append(p)
                j += 1
            track_midi_port = buf.pop_long()
            track_channel_1 = buf.pop_long()
            track_channel_2 = buf.pop_long()
            track_nb_frets  = buf.pop_long()
            track_capo      = buf.pop_long()
            track_color     = buf.pop_color()

            # Songwrite 2
            partition = model.Partition(song)
            partition.header = track_name
            if(track_spc & 1):
                partition.instrument = 128
                partition.set_view_type(model.EmptyDrumsView)
            else:
                partition.instrument = instruments[track_channel_1][0]
                strings = []
                for string in track_strings_pitch:
                    strings.append(model.TablatureString(string))
                partition.view = model.TablatureView(partition, _(u"Guitar"), strings)
                partition.capo = track_capo
            song.add_partition(partition)
            i += 1
    else:
        i = 0
        while(i < 8):
            # UNKNOWN
            buf.pop_long()
            track_nb_frets  = buf.pop_long()
            buf.pop_byte()
            track_name = buf.pop_nstring(40)
            print '>>> TRACK', track_name
            buf.advance(1 + 5 * 4)
            i += 1

    #-------------------
    # read the bars data
    #-------------------
    def convert_duration(duration):
        return 6 * (2 ** (4 - duration))

    i = 0
    time = 0
    while(i < nb_bars):
        j = 0
        
        if(verbose): print 'reading bar %s (out of %s)' % (i, nb_bars)
        
        while(j < nb_tracks):
            note_volume = 0xCC
            
            #---------
            # read bar
            #---------
            partition = song.partitions[j]
            nb_beats = buf.pop_long()

            if(verbose): print 'analyzing track %s (%s beats)' % (j, nb_beats)
            
            local_time = time
            k = 0
            while(k < nb_beats):
                
                #----------
                # read beat
                #----------
                beat_type = buf.pop_byte()
                if(beat_type & 64):
                    # rest
                    # UNKNOWN
                    #buf.advance(1)
                    b = buf.pop_byte()
                    if(verbose):  print '>>> REST found', b
                beat_duration = buf.pop_byte()
                if(beat_duration > 128): beat_duration -= 256
                beat_duration = convert_duration(beat_duration)
                if(beat_type & 1):
                    # dotted time
                    beat_duration = int(beat_duration * 1.5)
                if(beat_type & 32):
                    # tuplet
                    n_tuplet = buf.pop_long()
                    if(verbose):  print '>>> TUPLET found', n_tuplet
                    # TO DO
                if(beat_type & 2):
                    # chord
                    # TO DO
                    complete = buf.pop_byte()
                    if(complete == 0):
                        # incomplete chord
                        chord_name = buf.pop_long_string()
                    else:
                        if(guitar_pro_file_version >= 4.0):
                            buf.advance(16)
                            chord_name_size = buf.pop_byte()
                            chord_name = buf.buffer[buf.position: buf.position + chord_name_size]
                            buf.advance(10)
                            # UNKNOWN
                            buf.advance(15)
                        else:
                            buf.advance(25)
                            chord_name_size = buf.pop_byte()
                            chord_name = buf.buffer[buf.position: buf.position + chord_name_size]
                            buf.advance(10)
                            buf.advance(24)
                    top_fret = buf.pop_long()
                    if(top_fret != 0):
                        if(complete == 0):
                            buf.advance(6 * 4)
                        else:
                            buf.advance(7 * 4)
                    if(complete == 1):
                        if(guitar_pro_file_version >= 4.0):
                            buf.advance(24 + 7 + 1)
                        else:
                            buf.advance(32)
                    if(verbose): print '>>> CHORD found %s (%s)' % (chord_name, complete)
                if(beat_type & 4):
                    # text
                    text = buf.pop_long_string()
                    if(verbose): print '>>> TEXT found:', text
                if(beat_type & 8):
                    # beat effect

                    if(verbose): print '>>> BEAT EFFECT found'
                    effect_1 = buf.pop_byte()
                    if(guitar_pro_file_version >= 4.0):
                        effect_2 = buf.pop_byte()

                    # TO DO
                    if(effect_1 & 1):
                        if(verbose): print '   >>> vibrato'
                    if(effect_1 & 2):
                        if(verbose): print '   >>> wide vibrato'
                    if(effect_1 & 4):
                        if(verbose): print '   >>> natural harmonic'
                    if(effect_1 & 8):
                        if(verbose): print '   >>> other harmonic'
                    if(effect_1 & 16):
                        if(verbose): print '   >>> fade in'
                    if(effect_1 & 32):
                        if(guitar_pro_file_version >= 4.0):
                            if(verbose): print '   >>> strocke effect'
                            buf.pop_byte()
                        else:
                            if(verbose): print '   >>> tremolo bar'
                            buf.pop_byte()
                            buf.pop_long()
                    if(effect_1 & 64):
                        if(verbose): print '   >>> strocke'
                        buf.pop_byte()
                        buf.pop_byte()
                        
                    if(guitar_pro_file_version >= 4.0):
                        if(effect_2 & 1):
                            if(verbose): print '   >>> rasgueado'
                        if(effect_2 & 2):
                            if(verbose): print '   >>> pick strocke'
                            buf.pop_byte()
                        if(effect_2 & 4):
                            if(verbose): print '   >>> tremolo bar'
                            buf.pop_byte()
                            buf.pop_long()
                            nb_points = buf.pop_long()
                            buf.advance(nb_points * 9)

                if(beat_type & 16):
                    # change of instrument/volume/pan/chorus/reverb/phaser/tremolo/tempo
                    if(verbose): print '>>> CHANGE found'
                    # TO DO
                    new_instrument = buf.pop_byte()
                    new_volume = buf.pop_byte()
                    new_pan = buf.pop_byte()
                    new_chorus = buf.pop_byte()
                    new_reverb = buf.pop_byte()
                    new_phaser = buf.pop_byte()
                    new_tremolo = buf.pop_byte()
                    new_tempo = buf.pop_long()
                    if(new_volume != 255): buf.pop_byte()
                    if(new_pan != 255): buf.pop_byte()
                    if(new_chorus != 255): buf.pop_byte()
                    if(new_reverb != 255): buf.pop_byte()
                    if(new_phaser != 255): buf.pop_byte()
                    if(new_tremolo != 255): buf.pop_byte()
                    if(new_tempo != -1): buf.pop_byte()
                    if(guitar_pro_file_version >= 4.0):
                        # UNKNOWN
                        buf.pop_byte()
                if(beat_type & 128):
                    print '*** unknown time effect 128'
                    
                strings_fill = buf.pop_byte()
                notes_string = []
                if(strings_fill & 64): notes_string.append(0)
                if(strings_fill & 32): notes_string.append(1)
                if(strings_fill & 16): notes_string.append(2)
                if(strings_fill &  8): notes_string.append(3)
                if(strings_fill &  4): notes_string.append(4)
                if(strings_fill &  2): notes_string.append(5)
                if(strings_fill &  1): notes_string.append(6)
                for string in notes_string:
                
                    #----------
                    # read note
                    #----------
                    note_special = buf.pop_byte()
                    if(note_special & 32): note_alteration = buf.pop_byte()

                    if(note_special & 1):
                        # note duration is different from beat duration
                        if(verbose): print '>>> note duration != from beat duration'
                        note_duration = buf.pop_byte()
                        if(note_duration > 128): note_duration -= 256
                        note_duration = convert_duration(note_duration)
                        if(note_special & 2):
                            note_duration *= 1.5
                        # UNKNWON
                        buf.advance(1)
                    else:
                        note_duration = beat_duration
                    if(note_special & 16):
                        # changement of nuance
                        if(verbose): print '>>> note nuance'
                        nuance = buf.pop_byte()
                        note_volume = {
                            1 : 0,
                            2 : 36,
                            3 : 72,
                            4 : 109,
                            5 : 145,
                            6 : 182,
                            7 : 218,
                            8 : 255,
                            }[nuance]
                        
                    if(note_special & 32):
                        note_value = buf.pop_byte()
                        if(note_value == 255): note_value = 0
                        
                    # Songwrite 2
                    if(note_special & 32):
                        if(partition.instrument == 128):
                            # drums
                            for string in partition.view.strings:
                                if(string.base_note == note_value): break
                            else:
                                partition.view.strings.append(model.DrumString(note_value))
                            note = model.Note(partition, local_time, note_duration, note_value)
                            partition.add_note(note)
                        else:
                            # tablature
                            #if(string >= len(partition.view.strings)): continue
                            pitch = partition.view.strings[string].base_note + note_value + partition.capo
                            note = model.Note(partition, local_time, note_duration, pitch)
                            note.string_id = string
                            partition.add_note(note)
                            
                    if(note_alteration == 3):
                        # dead note
                        note.set_fx(u"dead")
                    elif (note_alteration == 2) and (partition.instrument != 128):
                        # note is linked from another one.
                        pass # Nothing to do for that in Songwrite 2
                        
                    if(note_special & 128):
                        # fingering
                        if(verbose): print '>>> fingering'
                        # TO DO
                        left_hand_finger  = buf.pop_byte()
                        right_hand_finger = buf.pop_byte()

                    if(note_special & 64):
                        # accentuated
                        if(verbose): print '>>> accentuated note'
                        note.volume = 255
                        
                    if(note_special & 4):
                        if(verbose): print '>>> ghost note'
                        note.set_fx(u"dead")
                        
                    #-----------------
                    # read note effect
                    #-----------------
                    if(note_special & 8):
                        # effect

                        effect_1 = buf.pop_byte()
                        if(guitar_pro_file_version >= 4.0):
                            effect_2 = buf.pop_byte()

                        if(effect_1 & 1):
                            # bend
                            if(verbose): print '>>> note effect: bend'
                            # TO DO
                            buf.pop_byte()
                            buf.pop_long()
                            nb_points = buf.pop_long()
                            bend_pitch = 0
                            for point in range(nb_points):
                                buf.pop_long()
                                bend_pitch = max(bend_pitch, buf.pop_long())
                                buf.pop_byte()
                            note.set_fx(u"bend")
                            note.bend_pitch = bend_pitch / 100.0
                        if(effect_1 & 2):
                            # hammer
                            if(verbose): print '>>> note effect: hammer'
                            note.set_link_fx(u"link")
                        if(effect_1 & 4):
                            # slide
                            if(verbose): print '>>> note effect: slide'
                            note.set_link_fx(u"slide")
                        if(effect_1 & 8):
                            # let ring
                            if(verbose): print '>>> note effect: let ring'
                            # TO DO
                        if(effect_1 & 16):
                            # appogiature
                            if(verbose): print '>>> note effect: appogiature'
                            # TO DO
                            previous_note = buf.pop_byte()
                            buf.pop_byte()
                            transition = buf.pop_byte()
                            duration = buf.pop_byte()
                        if(effect_1 &  32): print '*** unknown note effect1  32'
                        if(effect_1 &  64): print '*** unknown note effect1  64'
                        if(effect_1 & 128): print '*** unknown note effect1 128'

                        if(guitar_pro_file_version >= 4.0):
                            if(effect_2 & 1):
                                # staccato
                                if(verbose): print '>>> note effect: staccato'
                                # TO DO
                            if(effect_2 & 2):
                                # palm mute
                                if(verbose): print '>>> note effect: palm mute'
                                # TO DO
                            if(effect_2 & 4):
                                # tremolo picking
                                if(verbose): print '>>> note effect: tremolo picking'
                                duration = buf.pop_byte()
                                note.set_fx("tremolo")
                            if(effect_2 & 8):
                                # slide
                                if(verbose): print '>>> note effect: slide'
                                type = buf.pop_byte()
                            if(effect_2 & 16):
                                # harmonic
                                if(verbose): print '>>> note effect: harmonic'
                                type = buf.pop_byte()
                                # TO DO
                            if(effect_2 & 32):
                                # trill
                                if(verbose): print '>>> note effect: trill'
                                note_value = buf.pop_byte()
                                frequence = buf.pop_byte()
                                # TO DO
                            if(effect_2 & 64):
                                # vibrato
                                if(verbose): print '>>> note effect: vibrato'
                                note.set_fx("tremolo")
                            if(effect_2 & 128): print '*** unknown note effect2 128'
                    
                local_time += beat_duration
                k += 1
            j += 1
        time += song.mesures[i].duration
        i += 1

    return song


#t = load_guitar_pro('/home/jiba/tmp/gp3/VaiSteve-BluePowder.gp3')
