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

from __future__ import nested_scopes
import sys, array, StringIO as StringIO, re
import string as string_module # not a guitar string !

import songwrite2.model as model


def parse(texttab):
  if not isinstance(texttab, unicode):
    try:    texttab = texttab.decode("utf8")
    except: texttab = texttab.decode("latin")
    
  ASCII_STRING    = u"-="
  ASCII_BAR       = u"|"
  ASCII_STRESSED  = u"'"
  ASCII_HAMMER    = u"hpl"
  ASCII_SLIDE     = u"/\\s"
  ASCII_BEND      = u"b"
  ASCII_DEAD_NOTE = u"xd"
  ASCII_TREMOLO   = u"~vt"
  ASCII_TAB       = ASCII_STRING + ASCII_BAR + string_module.digits + ASCII_STRESSED + ASCII_HAMMER + ASCII_SLIDE + ASCII_BEND + ASCII_DEAD_NOTE + ASCII_TREMOLO
  
  TITRE_AUTHOR = re.compile(ur".*\(.*\)")
  COPYRIGHT    = re.compile(ur"(C|c)opy(right|left)\s*[0-9]{2,4}")
  TEMPO        = re.compile(ur"((?<=(T|t)empo(:|=)\s)|(?<=(T|t)empo(:|=))|(?<=(T|t)empo\s(:|=)\s)|(?<=(T|t)empo\s))([0-9]+)")
  
  song = model.Song()
  lines = texttab.split(u"\n")
  
  tempo = TEMPO.findall(texttab)
  if tempo: tempo = tempo[0][-1]
  else:     tempo = 60
  
  i = 0
  header = u""
  song_comments_ended = 0
  if (not lines[i]) or (not lines[i][0] in ASCII_TAB): # First line is guessed to be the title.
    if TITRE_AUTHOR.match(lines[i]):
      start = lines[i].find(u"(")
      song.title   = lines[i][: start]
      song.authors = lines[i][start + 1 : lines[i].find(u")")]
    else: song.title = lines[i]
    i = i + 1
    
  while 1:
    if   not lines[i]: song_comments_ended = 1
    elif not lines[i][0] in ASCII_TAB:
      if COPYRIGHT.search(lines[i]): song.copyright = lines[i]
      else:
        if song_comments_ended:
          if header: header = header + u"\n" + lines[i]
          else:      header = lines[i]
        else:
          if song.comments: song.comments = song.comments + u"\n" + lines[i]
          else:              song.comments = lines[i]
    else: break
    i = i + 1
    
  # Compute rythm
  if lines[i][0] in ASCII_BAR: mesure_len = lines[i][1:].find(u"|")
  else:                        mesure_len = lines[i].find(u"|")
  
  if   mesure_len % 4 == 0: unit = float(mesure_len / 4) # Guess it is 4/4
  elif mesure_len % 3 == 0: unit = float(mesure_len / 3) # Guess it is 3/4
  
  pos              = []
  last_bar_pos     = 0
  partition        = model.Partition(song)
  partition.header = header
  # adrian@sixfingeredman.net: hack to guess tuning
  if "DADGAD" in header: partition.view = model.GuitarDADGADView(partition)
  else:                  partition.view = model.GuitarView      (partition)
  current_note     = None
  next_note        = model.Note(partition, 0, 96, 0)
  song.partitions.append(partition)
  song.mesures *= 0
  
  while (i < len(lines)):
    string_id = 0
    
    while (i < len(lines)) and lines[i] and (lines[i][0] in ASCII_TAB):
      j = 0
      if string_id >= len(pos) - 1: pos.append(0)
      
      while j < len(lines[i]):
        char = lines[i][j]
        
        if char in ASCII_BAR:
          if (string_id == 0) and (partition is song.partitions[0]):
            if j > 1:
              song.add_mesure(model.Mesure(song,
                                           int(round(last_bar_pos / unit * 96.0)),
                                           rythm1 = int(round((pos[string_id] - last_bar_pos) / unit)),
                                           tempo  = tempo))
            last_bar_pos = pos[string_id]
          j = j + 1
          continue
        
        elif char in string_module.digits:
          if (j + 1 < len(lines[i])) and (lines[i][j + 1] in string_module.digits):
            fret = int(char + lines[i][j + 1])
            pos[string_id] = pos[string_id] + 1
            j = j + 1
          else: fret = int(char)
          next_note.value     = partition.view.strings[string_id].base_note + fret
          next_note.time      = int(round((pos[string_id] - 1)/ unit * 96.0))
          next_note.string_id = string_id
          partition.notes.append(next_note)
          
          current_note = next_note
          next_note = model.Note(partition, 0, 96, 0)
          
          
          
        elif char in ASCII_STRESSED : next_note.volume = 255
        elif char in ASCII_TREMOLO  : next_note.fx = u"tremolo"
        elif char in ASCII_DEAD_NOTE: next_note.fx = u"dead"
        elif char in ASCII_BEND     : next_note.fx = u"bend"
        elif char in ASCII_HAMMER:
          current_note.link_fx = u"link"
          current_note.link_to(next_note)
        elif char in ASCII_SLIDE:
          current_note.link_fx = u"slide"
          current_note.link_to(next_note)
        elif char in ASCII_STRING: pass
        else: print "* parse_texttab * Unknown character %s at line %s, position %s ! Skipping." % (char, i, j)
          
        pos[string_id] = pos[string_id] + 1
        j = j + 1
        
      i = i + 1
      string_id = string_id + 1
      
    while (i < len(lines)) and (not lines[i]): i = i + 1
    
    if (i < len(lines)) and ((len(lines[i]) < 3) or (not lines[i][0] in ASCII_TAB) or (not lines[i][1] in ASCII_TAB)): break
    
    
  # Compute notes' durations
  partition.notes.sort()
  last_notes = []
  for note in partition.notes:
    if last_notes and (last_notes[0].time != note.time):
      for last_note in last_notes:
        last_note.duration = note.time - last_note.time
      last_notes = []
    last_notes.append(note)
    
  last_duration = song.mesure_at(last_notes[0].time, 1).end_time() - last_notes[0].time
  for last_note in last_notes:
    last_note.duration = last_duration
    
  return song


def texttab(song, cut_tab_at = 80):
  "texttab(song) -> string -- Generates an ascii tablature from a song"
  min_duration = sys.maxint
  ternary      = 0
  partitions   = []
  
  for partition in song.partitions:
    if isinstance(partition, model.Partition) and isinstance(partition.view, model.TablatureView):
      partitions.append(partition)
      
      for note in partition.notes:
        dur = note.duration
        if note.is_triplet(): # Triplets are a hack...
          ternary = 1
          if note.duration == 32: dur = 48
          if note.duration == 16: dur = 24
          if note.duration ==  8: dur = 12
        else:
          rest = note.time % min_duration
          if rest > 0: min_duration = rest
          
        if dur < min_duration: min_duration = dur
        
  min_duration = float(min_duration)
  
  slotsize = 2
  for partition in song.partitions:
    if isinstance(partition, model.Partition) and isinstance(partition.view, model.TablatureView):
      for note in partition.notes:
        if note.is_triplet():
          slotsize = 3
          break
        
  duration = min_duration / slotsize
  
  alltabs = StringIO.StringIO()
  
  alltabs.write(u"%s (%s)\n" % (song.title, song.authors))
  if song.copyright: alltabs.write(song.copyright + u"\n")
  if song.comments : alltabs.write(song.comments  + u"\n")

  alltabs.write(u"\n")
  
  for partition in song.partitions:
    if   isinstance(partition, model.Lyrics):
      alltabs.write(partition.header + u"\n")
      text = partition.text.replace(u"\t_", u"").replace(u"_", u"").replace(u"-\t", u"").replace(u"\t", u" ").replace(u"\n", u"").replace(u"\\\\", u"\n").replace(u"  ", u" ")
      alltabs.write(u"\n".join(map(string_module.strip, text.split(u"\n"))))
      alltabs.write(u"\n")
      
    elif isinstance(partition.view, model.TablatureView):
      alltabs.write(partition.header + u"\n")
      strings = partition.view.strings
      tabs    = [array.array("u", u"-" * int(round(partition.end_time() / min_duration * slotsize))) for string in strings]
      
      def string_id(note): return getattr(note, "string_id", len(strings) - 1)
      
      for note in partition.notes:
        sid  = string_id(note)
        time = int(round(note.time / min_duration * slotsize))
        text = strings[sid].value_2_text(note)
        
        if note.linked_from:
          if   note.linked_from.link_fx == u"link":
            link_type = note.linked_from.link_type()
            if   link_type ==  0: continue # Don't show linked note, since ascii tab doesn't matter note duration !
            elif link_type == -1: tabs[sid][time] = u"p"
            elif link_type ==  1: tabs[sid][time] = u"h"
            
          elif note.linked_from.link_fx == u"slide":
            if note.linked_from.value > note.value: tabs[sid][time] = u"\\"
            else:                                   tabs[sid][time] = u"/"
              
        if   note.fx == u"dead"   : tabs[sid][time] = u"x"
        elif note.fx == u"tremolo": tabs[sid][time] = u"~"
        elif note.fx == u"bend"   : tabs[sid][time] = u"b"
        
        if (note.volume > 220) and (tabs[sid][time] == u"-"): tabs[sid][time] = u"'" # Stressed note
        
        if len(text) == 1: tabs[sid][time + 1] = text
        else:
          tabs[sid][time + 1] = text[0]
          tabs[sid][time + 2] = text[1]
          
      tabs = map(lambda tab: tab.tounicode(), tabs) # Turn arrays to strings.
      
      mesure = song.mesures[0]
      i = 0
      while i < len(song.mesures):
        mesures = []
        length = 1
        while i < len(song.mesures):
          length = length + mesure.duration / min_duration * slotsize + 1
          if length > cut_tab_at: break
          mesures.append(mesure)
          
          i = i + 1
          if i >= len(song.mesures): break
          mesure = song.mesures[i]
          

        string_base_note_length  = max([len(model.note_label(string.base_note, False)) for string in strings])
        string_base_note_pattern = u"%%-%ss" % string_base_note_length
        
        for sid in range(len(tabs)):
          tab = tabs[sid]
          
          # adrian@sixfingeredman.net: this screws up the importer
          # alltabs.write(string_base_note_pattern % model.note_label(strings[sid].base_note, False))
          
          for mes in mesures:
            content = tab[int(round(mes.time / min_duration * slotsize)) : int(round(mes.end_time() / min_duration * slotsize))]
            if not content:
              i = sys.maxint
              break
            alltabs.write(u"|" + content)
          alltabs.write(u"|\n")
          
        alltabs.write(u"\n")
        
  return alltabs.getvalue()


