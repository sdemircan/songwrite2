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

import sys, array, bisect, cStringIO as StringIO
import string as string_module # not a guitar string !

import songwrite2.model as model

class GotoError(model.TimeError): pass

class ChordError(model.TimeError): pass


def partition_tablature_format(partition):
  if isinstance(partition.view, model.TablatureView):
    for string in partition.view.strings:
      if isinstance(string, model.Banjo5GTablatureString):
        return "#fret-number-tablature-format-banjo"
  return "#fret-number-tablature-format"

class LilyVoice:
  def __init__(self, lily, mesures, mesure2repeatcodes):
    self.time               = 0
    self.lily               = lily
    self.mesures            = mesures[:]
    self.last_rythm         = None
    self.last_duration      = None
    self.mesure2repeatcodes = mesure2repeatcodes
    self.last_tempo         = -1 # No previous tempo
    
  def goto(self, time):
    if   time < self.time: raise ChordError(time)
    elif time > self.time:
      rab = time - self.time
      
      dur = 384
      
      while rab:
        nb = int(rab / dur)
        if nb:
          next_time = self.time + nb * dur
          if self.mesures and (next_time >= self.mesures[0].time):
            mesure = self.mesures.pop(0)
            
            rab = rab - (mesure.time - self.time)
            
            self.goto(mesure.time)
            
            self.draw_mesure(mesure)
          else:
            self.time = next_time
            for i in range(nb): self.draw_wait(dur)
            rab = rab % dur
            dur = dur // 2
        else: dur = dur // 2
        
    else: # Do not advance the time, but check mesure
      mesure = None
      while self.mesures and (time >= self.mesures[0].time): mesure = self.mesures.pop(0)
      if mesure:
        self.draw_mesure(mesure)
        
    if self.time != time: raise GotoError(self.time)
    
  def draw_mesure(self, mesure):
    repeatcodes = self.mesure2repeatcodes.get(mesure)
    if repeatcodes:
      del self.mesure2repeatcodes[mesure]
      for code in repeatcodes:
        self.lily.write("\n        " + code)
        
    self.lily.write("\n       ")
    if self.last_rythm != (mesure.rythm1, mesure.rythm2):
      self.last_rythm = (mesure.rythm1, mesure.rythm2)
      self.lily.write(r" \time %s/%s" % self.last_rythm)
      
    if mesure.tempo != self.last_tempo:
      self.last_tempo = mesure.tempo
      self.lily.write(r" \tempo 4=%s" % mesure.tempo)
      
  def draw_wait(self, duration):
    if duration == self.last_duration:
      self.lily.write(" s")
    else:
      self.lily.write(" s%s" % _durations[duration])
      self.last_duration = duration
      
  def _draw_note(self, note, duration = None):
    unaltered_value, alteration = note.unaltered_value_and_alteration()
    #octavo = note.value / 12
    octavo = unaltered_value // 12
    
    self.lily.write(" " + _notes[unaltered_value % 12])
    if   alteration == -1: self.lily.write("b")
    elif alteration ==  1: self.lily.write("d")
    
    #self.lily.write(" " + _notes[note.value % 12])
    if octavo < 4: self.lily.write("," * (4 - octavo))
    else:          self.lily.write("'" * (octavo - 4))
    duration = duration or note.duration
    if duration != self.last_duration:
      self.lily.write(_durations[duration])
      self.last_duration = duration
      
  def draw_note(self, note, duration = None):
    self._draw_note(note, duration)
    
    if note.fx == u"tremolo": self.lily.write(r" \prall")
    if note.volume > 220: self.lily.write(r" \accent")
    
  def draw_chord(self, notes, duration = None):
    first = notes[0]
    if first.is_start_triplet(): self.lily.write(r" \times 2/3 {")
    
    if first.fx == u"dead":
      self.lily.write(r" \set tablatureFormat = #dead-note-tablature-format \override NoteHead #'style = #'cross")
      
    if len(notes) > 1:
      self.lily.write(" <")
      self.last_duration = notes[0].duration
      for note in notes:
        self.draw_note(note, self.last_duration)
      self.lily.write(" >%s" % _durations[self.last_duration])
      if notes[0].fx == u"roll":
        self.lily.write(r"\arpeggio")
        
      if u"link" in [note.link_fx for note in notes]:
        self.lily.write(" (")
        
      if u"link" in [note.linked_from.link_fx for note in notes if note.linked_from]:
        self.lily.write(" )")
        
    else:
      self.draw_note(first, duration)
      if first.linked_from and (first.linked_from.link_fx == u"link"): self.lily.write(" )")
      if                        first            .link_fx == u"link" : self.lily.write(" (")
      if first.fx == u"bend": self.lily.write(r"-\bendAfter #+%s" % int(round(first.bend_pitch * 4.0)))
      
    if first.link_fx == u"slide": self.lily.write(r" \glissando")
    
    if first.fx == u"dead":
      self.lily.write(r" \set tablatureFormat = %s \revert NoteHead #'style" % partition_tablature_format(note.partition))
      
    if first.is_end_triplet(): self.lily.write(r" }")
    
  def end(self):
    end_codes = self.mesure2repeatcodes.get(None, ())
    if end_codes: del self.mesure2repeatcodes[None]
    
    remnant_codes = map(lambda (mesure, codes): (mesure.time, codes),  self.mesure2repeatcodes.items())
    remnant_codes.sort()
    for time, codes in remnant_codes:
      for code in codes:
        self.lily.write("\n        " + code)
        
    for code in end_codes:
      self.lily.write("\n        " + code)
      
    self.lily.write(r"""
        \bar "|."
""")
    
class LilyStaffVoice(LilyVoice):
  def draw(self, notes):
    batch = []
    for note in notes:
      if (not batch) or note.time == batch[0].time: batch.append(note)
      else:
        first = batch[0]
        self.goto(first.time)
        duration = min(note.time - first.time, *map(lambda n: n.duration, batch))
        self.time = first.time + duration
        self.draw_chord(batch, duration)
        
        batch = [note]
        
    if batch:
      first = batch[0]
      self.goto(first.time)
      duration = min(map(lambda n: n.duration, batch))
      self.time = first.time + duration
      self.draw_chord(batch, duration)

class LilyTabVoice(LilyVoice):
  def __init__(self, lily, mesures, mesure2repeatcodes, strings):
    LilyVoice.__init__(self, lily, mesures, mesure2repeatcodes)
    self.strings = strings
    
  def _draw_note(self, note, duration = None):
    LilyVoice._draw_note(self, note, duration)
    self.lily.write(r"\%s" % (note.string_id + 1))
    
  def draw_chord(self, notes, duration = None):
    # Hack because Lilypond ignore string number inside chords
    if len(notes) > 1:
      min_fret_number = 1000
      for note in notes:
        fret_number = note.value - self.strings[note.string_id].base_note
        if fret_number < min_fret_number: min_fret_number = fret_number
      self.lily.write(" \set TabStaff.minimumFret = #%s " % min_fret_number)
      LilyVoice.draw_chord(self, notes, duration)
      self.lily.write(" \set TabStaff.minimumFret = #0 ") # Remove the hack
    else:
      LilyVoice.draw_chord(self, notes, duration)
      
  def draw(self, notes):
    batch = []
    for note in notes:
      if (not batch) or note.time == batch[0].time: batch.append(note)
      else:
        first = batch[0]
        self.goto(first.time)
        duration = min(note.time - first.time, *map(lambda n: n.duration, batch))
        self.time = first.time + duration
        self.draw_chord(batch, duration)
        
        batch = [note]
        
    if batch:
      first = batch[0]
      self.goto(first.time)
      duration = min(map(lambda n: n.duration, batch))
      self.time = first.time + duration
      
      self.draw_chord(batch, duration)
      
      
def lilypond(song, lily = None):
  # For testing errors :-)
  #raise model.TimeError(song.partitions[0].notes[-1].time, note = song.partitions[0].notes[-1])
  #raise model.TimeError(96 * 10.0, partition = song.partitions[0])
  #raise model.TimeError(96 * 10.0)
  
  
  mesure2repeatcodes = song.playlist.symbols
  end_time = max(map(lambda partition: partition.end_time(), song.partitions))
  
  if not lily: lily = StringIO.StringIO()
  lily.write(r"""
\include "italiano.ly"

#(define (dead-note-tablature-format x y z) "x")

\score { \simultaneous {
""")
  
  def draw_partition(partition, tablature, lyric):
      if lyric:
        i = song.partitions.index(partition) + 1
        text = []
        while (i < len(song.partitions)) and isinstance(song.partitions[i], model.Lyrics):
          texts = map(lambda line: line.split("\t"), song.partitions[i].text.split("\n"))

          for line in texts:
            for j in range(len(line)):
              if j < len(text):
                if not text[j]: text[j] = line[j]
              else: text.append(line[j])
          i = i + 1

        if text:
          lyric = "\t".join(text)
          lyric = lyric.replace("-\t_", "- _").replace("_", " __ ").replace("-\t", " -- ").replace("\t", " ").replace("\\\\", " ").replace("  ", " ").strip().encode("utf8")
        else: lyric = None
        
      if tablature:
        stafftype = "TabStaff"
        voicetype = "TabVoice"
      else:
        stafftype = "Staff"
        voicetype = "Voice"
        
      lily.write(r"""  \new StaffGroup << \new %s {
    <<
""" % stafftype)
#      lily.write(r"""  \new StaffGroup << \new %s {
#    \set Staff.instrument = "%s"
#    <<
#""" % (stafftype, first_word(partition.header).encode("utf8")))
      
      if tablature:
        tunings = map(lambda string: str(string.base_note - 60), partition.view.strings)
        tunings = " ".join(tunings)
        if tunings != "4 -1 -5 -10 -15 -20": # Default value => skip
          lily.write(r"""    \set TabStaff.stringTunings = #'(%s)
""" % tunings)
        tablature_format = partition_tablature_format(partition)
        if tablature_format != "#fret-number-tablature-format":
          lily.write(r"""    \set tablatureFormat = %s
""" % tablature_format)
          
      elif partition.g8:
        lily.write(r"""    \clef "G_8" """)
        
      voices = partition.voices(lyric)
      for voice in voices:
        if not voice: continue
        
        lily.write(r"""    {
     """)
        if voice is voices[-1]: lily.write(r""" \stemUp""")
        else:                   lily.write(r""" \stemUp""")
        
#         if voice is voices[-1]: lily.write(r""" \set %s.Stem \set #'direction = #'1
#      """ % voicetype)
#         else:                   lily.write(r""" \set %s.Stem \set #'direction = #'1
#      """ % voicetype)
        
        if tablature: voice_drawer = LilyTabVoice(lily, song.mesures, {}, partition.view.strings)
        else:
          voice_drawer = LilyStaffVoice(lily, song.mesures, {})
          lily.write(r""" \key %s \major
     """ % _tonalities[partition.tonality])
#     """ % _tonalities[model.OFFSETS[partition.tonality]])
        if voice is voices[0]:
          voice_drawer.mesure2repeatcodes = mesure2repeatcodes.copy()
        try: voice_drawer.draw(voice)
        #except model.TimeError, (time, error):
        except model.TimeError, error:
          print error
          error.partition = partition
          raise error
        except:
          sys.excepthook(*sys.exc_info())
          raise model.TimeError(voice_drawer.time, partition)
        
        voice_drawer.goto(end_time)
        
        if voice is voices[0]:
          #voice_drawer.goto(partition.end_time())
          voice_drawer.end()
          
        lily.write(r"""
    }
""")
            
      if lyric: lily.write(r"""    \addlyrics { %s }
""" % lyric)
      
      lily.write(r"""    >>
  }
  >>
""")
      
      
  
  for partition in song.partitions:
    if isinstance(partition, model.Partition):
      if   isinstance(partition.view, model.TablatureView):
        if partition.print_with_staff_too: draw_partition(partition, 0, 0)
        draw_partition(partition, 1, 1)

      elif isinstance(partition.view, model.StaffView):
        draw_partition(partition, 0, 1)


      
  lily.write(r"""}}""")
  
  return lily.getvalue()


_tonalities = {
  u"C"  : "do",
  
  u"G"  : "sol",
  u"D"  : "re",
  u"A"  : "la",
  u"E"  : "mi",
  u"B"  : "si",
  u"F#" : "fad",
  u"C#" : "dod",
  
  u"F"  : "fa",
  u"Bb" : "sib",
  u"Eb" : "mib",
  u"Ab" : "lab",
  u"Db" : "reb",
  u"Gb" : "solb",
  u"Cb" : "dob",
#   "do",
#   "dod",
#   "re",
#   "red",
#   "mi",
#   "fa",
#   "fad",
#   "sol",
#   "sold",
#   "la",
#   "lad",
#   "si",
  }
_notes = {
  0 : "do",
  2 : "re",
  4 : "mi",
  5 : "fa",
  7 : "sol",
  9 : "la",
  11: "si",
  }
_durations = {
  # Normal duration
  384 :   "1",
  192 :   "2",
   96 :   "4",
   48 :   "8",
   24 :  "16",
   12 :  "32",
    6 :  "64",
    3 : "128",

  # Doted durations
  576 :  "1.",
  288 :  "2.",
  144 :  "4.",
   72 :  "8.",
   36 : "16.",
   18 : "32.",
    9 : "64.",
  
  # Triplets
   32 :  "8",
   16 : "16",
    8 : "32",
    4 : "64",
  }

def first_word(text):
  return text.split()[0]

  br = min(text.find("\n"), text.find(" "))
  if br == -1: return text
  return text[0 : br]


class LilyPlaylistItem(model.PlaylistItem):
  def __init__(self, from_mesure, to_mesure, type):
    model.PlaylistItem.__init__(self, None, from_mesure, to_mesure)
    self.type = type
    
  def __unicode__(self): return u"%s : %s" % (model.PlaylistItem.__unicode__(self), self.type)
  
  
def contains_only(list, item):
  for i in list:
    if i != item: return 0
  return 1

