# -*- coding: utf-8 -*-

# Songwrite 2
# Copyright (C) 2001-2007 Jean-Baptiste LAMY -- jibalamy@free.fr
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
import songwrite2.midi  as midi

def parse(file, rich_midi_tablature = 0):
  song = model.Song()
  
  partitions = {}
  def channel2partition(channel):
    return partitions.get(channel) or new_partition(channel)
  def new_partition(channel):
    partition = model.Partition(song)
    song.partitions.append(partition)
    if channel == 9: # Drums
      partition.instrument = 128
      
    partitions[channel] = partition
    return partition
  
  name, length = struct.unpack(">4si", file.read(8))
  if name != "MThd": raise ValueError, ("Not a midi file !", file)
  format, nb_tracks, tempo = struct.unpack(">hhh", file.read(6))

  for i in range(nb_tracks):
    name, length = struct.unpack(">4si", file.read(8))
    if name != "MTrk": raise ValueError, ("Not a track !", file)
    
    partitions   = {}
    time         = 0
    opened_notes = {}
    string_id    = None
    fx           = ""
    end_at       = file.tell() + length
    while file.tell() < end_at:
      time  = time + midi.readVarLength(file)
      event = struct.unpack(">B", file.read(1))[0]
      
      if   0x80 <= event < 0x90: # Note off
        channel = event - 0x80
        
        value = struct.unpack(">B", file.read(1))[0]
        try:
          note = opened_notes[channel, value]
          note.duration = time - note.time
          del opened_notes[channel, value]
        except:
          print "Warning ! Note off without note on at time %s !" % time
        file.read(1)
        
      elif 0x90 <= event < 0xA0: # Note on
        channel = event - 0x90
        
        value, volume = struct.unpack(">BB", file.read(2))
        
        if volume == 0: # A Note on with wolume == 0 is a Note off ???
          try:
            note = opened_notes[channel, value]
            note.duration = time - note.time
            del opened_notes[channel, value]
          except:
            print "Warning ! Note off without note on at time %s !" % time
            
        else:          
          note = opened_notes[channel, value] = model.Note(channel2partition(channel), time, 256, value, volume) # Duration is unknown
          
          if string_id is not None:
            note.string_id = string_id
            string_id      = None
            
          if fx:
            if fx in (u"link", u"slide"): note.link_fx = fx
            else:                         note.fx      = fx
            fx      = ""
            
          channel2partition(channel).add_note(note)
          
      elif 0xA0 <= event < 0xB0:
        print "Warning ! aftertouch not supported !"
        file.read(2)
        
      elif 0xB0 <= event < 0xC0:
        partition = channel2partition(event - 0xB0)
        
        event = struct.unpack(">B", file.read(1))[0]
        if   event == 0x5B: partition.reverb = struct.unpack(">B", file.read(1))[0]
        elif event == 0x5D: partition.chorus = struct.unpack(">B", file.read(1))[0]
        elif event == 0x07: partition.volume = struct.unpack(">B", file.read(1))[0] * 2
          
        else:
          print "Warning ! unknown midi controller : %s, value : %s" % (hex(event), struct.unpack(">B", file.read(1))[0])
          
      elif 0xC0 <= event < 0xD0:
        partition = channel2partition(event - 0xC0)
        if partition.instrument != 128: # Else it is drums ; an instrument event has no sens for the drums channel but it occurs in some mids...
          partition.instrument = struct.unpack(">B", file.read(1))[0]
          
      elif 0xD0 <= event < 0xE0:
        print "Warning ! aftertouch not supported !"
        file.read(1)
        
      elif 0xE0 <= event < 0xF0:
        print "Warning ! pitchwheel not supported ! Use rich midi if you want to import hammer/bend/...."
        file.read(1)
        file.read(1)
        
      elif event == 0xF0: # System exclusive
        print repr(file.read(1))
        while struct.unpack(">B", file.read(1))[0] != 0xF7: pass
        
      elif event == 0xFF:
        event   = struct.unpack(">B", file.read(1))[0]
        length  = struct.unpack(">B", file.read(1))[0]
        content = file.read(length)
        
        if   event == 0x01: # Comment ?
          if song.comments: song.comments = song.comments + "\n" + content
          else:             song.comments = content
          
        elif event == 0x02: # Copyright ?
          if song.copyright: song.copyright = song.copyright + content
          else:              song.copyright = content
          
        elif event == 0x10: # Rich tab midi event
          channel_id     = struct.unpack(">B", content[0])[0]
          partition      = channel2partition(channel_id - 1)
          partition.capo = struct.unpack(">B", content[1])[0]
          
          print channel_id
          
          strings   = []
          for c in content[2:]:
            strings.append(model.TablatureString(struct.unpack(">B", c)[0]))
          partition.view = model.TablatureView(partition, u"", strings)
          
        elif event == 0x11: # Rich tab midi event
          if rich_midi_tablature:
            string_id = struct.unpack(">B", content[0])[0]
            if len(content) > 1:
              spc = struct.unpack(">B", content[1])[0]

              if   spc == 0x01: fx = "link"
              elif spc == 0x02: fx = "link"
              elif spc == 0x03: fx = "slide"
              elif spc == 0x04: fx = "slide"
              elif spc == 0x06: fx = "roll"; print "roll"
              elif spc == 0x0A: fx = "tremolo"
              elif spc == 0x0E: fx = "dead"
              elif spc == 0x0C:
                fx = "bend"
                if len(content) > 2: bend_pitch = struct.unpack(">B", content[2])[0] * 0.25
                else:                bend_pitch = 0.5
              else: print "Warning ! unknown rich midi special effect :", hex(spc)
            
        elif event == 0x2F: # End of track
          file.seek(end_at)
          break
        
        else:
          print "Warning ! unknow sequence 0xFF", hex(event), "  content (%s bytes) : %s" % (len(content), content)

      else:
        print "Warning ! unknown midi event :", hex(event)
        continue

  for partition in song.partitions:
    if partition.instrument == 128: # Drums
      partition.setviewtype(drum.drums_view_type)
      strings = {}
      for note in partition.notes:
        if not strings.has_key(note.value):
          strings[note.value] = model.DrumString(note.value)
      partition.view = DrumsView(partition, _("Drums"), strings.values())
      
  for mesure in song.mesures: mesure.tempo = tempo
  
  # Removes partition without any note
  #song.partitions = [partition for partition in song.partitions if partition.notes]
  
  # Start the song at time == 0
  #start = min(map(lambda partition: min([sys.maxint] + [note.time for note in partition.notes]), song.partitions))
  if song.partitions:
    start = min([min([sys.maxint] + [note.time for note in partition.notes]) for partition in song.partitions])
    for partition in song.partitions:
      for note in partition.notes:
        note.time = note.time - start
        
      if not partition.view:
        partition.view = model.GuitarView(partition)
        
  return song
