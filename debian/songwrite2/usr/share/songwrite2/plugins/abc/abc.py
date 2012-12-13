# -*- coding: utf-8 -*-

# SongWrite
# Copyright (C) 2004 Jean-Baptiste LAMY -- jibalamy@free.fr
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

# Ref : http://anamnese.online.fr/abc/guide_abc.txt


import cStringIO, string, re

import songwrite2.globdef as globdef
import songwrite2.model   as model

_tabnotes = "abcdefghiklmnopqrstuvwxyz"

_notes = {
  "C" : ( "c", "^c",  "d", "^d",  "e",  "f",  "f",  "g", "^g",  "a", "^a",  "b"),
  
  "G" : ( "c", "^c",  "d", "^d",  "e", "_f",  "f",  "g", "^g",  "a", "^a",  "b"),
  "D" : ("_c",  "c",  "d", "^d",  "e", "_f",  "f",  "g", "^g",  "a", "^a",  "b"),
  "A" : ("_c",  "c",  "d", "^d",  "e", "_f",  "f", "_g",  "g",  "a", "^a",  "b"),
  "E" : ("_c",  "c", "_d",  "d",  "e", "_f",  "f", "_g",  "g",  "a", "^a",  "b"),
  "B" : ("_c",  "c", "_d",  "d",  "e", "_f",  "f", "_g",  "g", "_a",  "a",  "b"),
  "F#": ("_c",  "c", "_d",  "d", "_e",  "e",  "f", "_g",  "g", "_a",  "a",  "b"),
  "C#": ( "b",  "c", "_d",  "d", "_e",  "e",  "f", "_g",  "g", "_a",  "a", "_b"),
  
  "F" : ( "c", "^c",  "d", "^d",  "e",  "f", "^f",  "g", "^g",  "a",  "b", "^b"),
  "Bb": ( "c", "^c",  "d",  "e", "^e",  "f", "^f",  "g", "^g",  "a",  "b", "^b"),
  "Eb": ( "c", "^c",  "d",  "e", "^e",  "f", "^f",  "g",  "a", "^a",  "b", "^b"),
  "Ab": ( "c",  "d", "^d",  "e", "^e",  "f", "^f",  "g",  "a", "^a",  "b", "^b"),
  "Db": ( "c",  "d", "^d",  "e", "^e",  "f",  "g", "^g",  "a", "^a",  "b", "^b"),
  "Gb": ("^c",  "d", "^d",  "e", "^e",  "f",  "g", "^g",  "a", "^a",  "b",  "c"),
  "Cb": ("^c",  "d", "^d",  "e",  "f", "^f",  "g", "^g",  "a", "^a",  "b",  "c"),
  }
_duration_2_abc = {
  # Normal duration
  768 : "8",
  384 : "4",
  192 : "2",
   96 : "1",
   48 :  "/2",
   24 :  "/4",
   12 :  "/8",
    6 :  "/16",
    3 :  "/32",
  
  # Doted durations
  576 : "6",
  288 : "3",
  144 : "3/2",
   72 : "3/4",
   36 : "3/8",
   18 : "3/16",
    9 : "3/32",
  
  # Triplets
   32 : "1/3",
   16 : "1/6",
    8 : "1/12",
    4 : "1/24",
  }
_abc_2_duration = dict([(abc, duration) for (duration, abc) in _duration_2_abc.items()])
_abc_2_duration["/"] = _abc_2_duration["/2"]
def duration_2_abc(duration, note = None):
  if note and note.is_start_triplet(): return "(3" + _duration_2_abc[duration]
  return _duration_2_abc[duration]
def abc_2_duration(abc):
  if abc.startswith(u"1/"): abc = abc[1:]
  return _abc_2_duration[abc] #* default_duration // 96


_abc_2_value = {
  "C" : { "C" : 60, "D" : 62, "E" : 64, "F" : 65, "G" : 67, "A" : 69, "B" : 71 },

  "G" : { "C" : 60, "D" : 62, "E" : 64, "F" : 66, "G" : 67, "A" : 69, "B" : 71 },
  "D" : { "C" : 61, "D" : 62, "E" : 64, "F" : 66, "G" : 67, "A" : 69, "B" : 71 },
  "A" : { "C" : 61, "D" : 62, "E" : 64, "F" : 66, "G" : 68, "A" : 69, "B" : 71 },
  "E" : { "C" : 61, "D" : 63, "E" : 64, "F" : 66, "G" : 68, "A" : 69, "B" : 71 },
  "B" : { "C" : 61, "D" : 63, "E" : 64, "F" : 66, "G" : 68, "A" : 70, "B" : 71 },
  "F#": { "C" : 61, "D" : 63, "E" : 65, "F" : 66, "G" : 68, "A" : 70, "B" : 71 },
  "C#": { "C" : 61, "D" : 63, "E" : 65, "F" : 66, "G" : 68, "A" : 70, "B" : 72 },
  
  "F" : { "C" : 60, "D" : 62, "E" : 64, "F" : 65, "G" : 67, "A" : 69, "B" : 70 },
  "Bb": { "C" : 60, "D" : 62, "E" : 63, "F" : 65, "G" : 67, "A" : 69, "B" : 70 },
  "Eb": { "C" : 60, "D" : 62, "E" : 63, "F" : 65, "G" : 67, "A" : 68, "B" : 70 },
  "Ab": { "C" : 60, "D" : 61, "E" : 63, "F" : 65, "G" : 67, "A" : 68, "B" : 70 },
  "Db": { "C" : 60, "D" : 61, "E" : 63, "F" : 65, "G" : 66, "A" : 68, "B" : 70 },
  "Gb": { "C" : 59, "D" : 61, "E" : 63, "F" : 65, "G" : 66, "A" : 68, "B" : 70 },
  "Cb": { "C" : 59, "D" : 61, "E" : 63, "F" : 64, "G" : 66, "A" : 68, "B" : 70 },
  }
def abc_2_value(abc, tonality):
  value = 0
  if abc in "abcdefg":
    abc = abc.upper()
    value += 12
  value += _abc_2_value[tonality][abc]
  return value
  
  
def parse(abc):
  if not isinstance(abc, unicode): abc = abc.decode("utf8")
  # Simplify bars placed at breakline
  abc = abc.replace("\r", "\n")
  abc = re.sub(u"\\|\\|", u"|", abc)
  abc = re.sub(u"\\|\\s+\\|", u"|", abc)
  abc = re.sub(u":\\|:", u"::", abc)
  
  song      = model.Song()
  partition = model.Partition(song, model.PianoView.default_instrument, view_type = model.PianoView)
  song.add_partition(partition)
  song.mesures = []
  
  titles     = []
  comments   = []
  tempo      = 90
  part_start = -1
  rhythm1    = 4
  rhythm2    = 4
  in_header  = 1
  time       = 0
  syncope    = 0
  note_value_offset = 0
  current_duration = 0
  duration_multiplicator = 1
  in_tripplet   = 0
  ornementation = 0
  in_link       = 0
  start_repeat  = None
  
  def last_mesure_end_time():
    if song.mesures: return song.mesures[-1].end_time()
    return 0
  
  def mesure_ended():
    if song.mesures:
      mesure = song.mesures[-1]
      if (len(song.mesures) == 1) or (mesure is start_repeat):
        #delta_t = mesure.end_time() - partition.notes[-1].end_time()
        delta_t = mesure.end_time() - (time + current_duration)
        if delta_t > 0:
          for note in reversed(partition.notes):
            if note.time < mesure.time: break
            note.time += delta_t
            
  lines = abc.split(u"\n")
  for line in lines:
    if not line: continue
    if "%" in line: line = line.split("%")[0] # ABC Comment
    if (len(line) > 1) and (line[1] == u":") and (line[0] in string.uppercase):
      attr  = line[0]
      value = line[2:]
      if not value: continue
      if value[0] == u" ": value = value[1:]
      
      if   attr == u"T": titles  .append(value)
      elif attr == u"C": song.authors  = value
      elif attr == u"B": comments.append(u"Source: " + value)
      elif attr == u"S": comments.append(u"Source: " + value)
      elif attr == u"A": comments.append(u"Region: " + value)
      elif attr == u"O": comments.append(u"Origin: " + value)
      elif attr == u"H": comments.append(u"History: " + value)
      elif attr == u"N": comments.append(value)
      elif attr == u"I": comments.append(value)
      elif attr == u"L":
        if rhythm2 == 8:
          if   value == u"1"   : default_duration = 384
          elif value == u"1/2" : default_duration = 192
          elif value == u"1/4" : default_duration = 96
          elif value == u"1/8" : default_duration = 48
          elif value == u"1/16": default_duration = 24
          elif value == u"1/32": default_duration = 12
          elif value == u"1/64": default_duration = 6
        else:
          if   value == u"1"   : default_duration = 384
          elif value == u"1/2" : default_duration = 192
          elif value == u"1/4" : default_duration = 96
          elif value == u"1/8" : default_duration = 48
          elif value == u"1/16": default_duration = 24
          elif value == u"1/32": default_duration = 12
          elif value == u"1/64": default_duration = 6
          
        #default_duration = abc_2_duration(value)
        
      elif attr == u"R":
        comments.append(value)
        if (u"jig" in value) or (u"gigue" in value) or (u"syncope" in value) or (u"ternary" in value) or (u"ternaire" in value):
          syncope = 1
        else:
          syncope = 0
      elif attr == u"M":
        if   value == u"C" : rhythm1 = rhythm2 = 4; default_duration = 48
        elif value == u"C|": rhythm1 = rhythm2 = 2; default_duration = 48
        else:
          rhythm1, rhythm2 = [int(i) for i in value.split(u"/")]
          if float(rhythm1) / float(rhythm2) < 0.75: default_duration = 24
          else:                                      default_duration = 48
      elif attr == u"Q":
        if "=" in value:
          duration, value = value.split("=")
          tempo = int(int(value) / abc_2_duration(duration) * 96.0)
        else:
          tempo = int(value)
      elif attr == u"P": pass # XXX
      elif attr == u"K":
        if (len(value) > 1) and (value[1] in u"b#"): partition.tonality = value[:2]
        else:                                        partition.tonality = value[0]
        
    else:
      if in_header:
        in_header = 0
        
      while line:
        print repr(line)
        
        if   line.startswith(u" "):
          line = line[1:]
        elif line.startswith(u","):
          note.value -= 12
          line = line[1:]
        elif line.startswith(u"'"):
          note.value += 12
          line = line[1:]
        elif line.startswith(u"^"):
          note_value_offset =  1
          line = line[1:]
        elif line.startswith(u"_"):
          note_value_offset = -1
          line = line[1:]
          
        elif line[0] in "abcdefgABCDEFGz":
          if not song.mesures: # first mesure bar is usually missing in ABC
            mesure = model.Mesure(song, 0, tempo, rhythm1, rhythm2, syncope)
            song.add_mesure(mesure)
            start_repeat = mesure
            
          time += current_duration
          duration = int(default_duration * duration_multiplicator)
          if in_tripplet:
            in_tripplet -= 1
            duration = int(duration / 1.5)
            
          if line[0] == u"z": # Pause
            note = None
          else:
            value = abc_2_value(line[0], partition.tonality)
            value += note_value_offset
            note = model.Note(partition, time, duration, value)
            if ornementation: note.volume = 255
            if in_link: note.set_link_fx("link")
            partition.add_note(note)
            
          current_duration = duration
          note_value_offset = 0
          duration_multiplicator = 1
          ornementation = 0
          line = line[1:]
          
        elif line.startswith(u"~"):
          ornementation = 1
          line = line[1:]
          
        elif line.startswith(u"{"): # XXX no grace note in Songwrite 2 yet!
          ornementation = 1
          line = line[line.find(u"}") + 1:]
          
        elif line.startswith(u'"'): # XXX no chord in Songwrite 2 yet!
          line = line[1:]
          line = line[line.find(u'"') + 1:]
          
        elif line.startswith(u"u") or line.startswith(u"v"):
          pass # XXX
          line = line[1:]
          
        elif line.startswith(u"!"):
          pass # XXX
          line = line[1:]
          
        elif line.startswith(u"."):
          ornementation = 1
          line = line[1:]
          
        elif line.startswith(u"-"):
          note.set__link_fx("link")
          line = line[1:]
          
        elif line.startswith(u">"):
          note.duration = current_duration = int(note.duration * 1.5)
          duration_multiplicator = 0.5
          line = line[1:]
        elif line.startswith(u"<"):
          note.duration = current_duration = note.duration // 2
          duration_multiplicator = 1.5
          line = line[1:]
          
        elif line.startswith(u"(3"):
          in_tripplet = 3
          line = line[2:]
          
        elif line.startswith(u"("):
          in_link = 1
          line = line[1:]
          
        elif line.startswith(u")"):
          in_link = 0
          if note: note.set_link_fx(u"")
          line = line[1:]
          
        elif line.startswith(u"|[1") or line.startswith(u"|1"):
          mesure_ended()
          repeated_part = song.mesures.index(start_repeat), len(song.mesures) - 1
          song.playlist.append(model.PlaylistItem(song.playlist, song.mesures.index(start_repeat), len(song.mesures) - 1))
          mesure = model.Mesure(song, last_mesure_end_time(), tempo, rhythm1, rhythm2, syncope)
          song.add_mesure(mesure)
          time = mesure.time
          current_duration = 0
          start_repeat = mesure
          if line.startswith(u"|[1"): line = line[3:]
          else:                       line = line[2:]
          
        elif line.startswith(u":|[2") or line.startswith(u":|2"):
          mesure_ended()
          song.playlist.append(model.PlaylistItem(song.playlist, song.mesures.index(start_repeat), len(song.mesures) - 1))
          song.playlist.append(model.PlaylistItem(song.playlist, *repeated_part))
          mesure = model.Mesure(song, last_mesure_end_time(), tempo, rhythm1, rhythm2, syncope)
          song.add_mesure(mesure)
          time = mesure.time
          current_duration = 0
          start_repeat = mesure
          if line.startswith(u":|[2"): line = line[4:]
          else:                        line = line[3:]
          
        elif line.startswith(u"|:"):
          mesure_ended()
          if start_repeat: song.playlist.append(model.PlaylistItem(song.playlist, song.mesures.index(start_repeat), len(song.mesures) - 1))
          mesure = model.Mesure(song, last_mesure_end_time(), tempo, rhythm1, rhythm2, syncope)
          song.add_mesure(mesure)
          time = mesure.time
          current_duration = 0
          start_repeat = mesure
          line = line[2:]
        elif line.startswith(u":|"):
          mesure_ended()
          song.playlist.append(model.PlaylistItem(song.playlist, song.mesures.index(start_repeat), len(song.mesures) - 1))
          song.playlist.append(model.PlaylistItem(song.playlist, song.mesures.index(start_repeat), len(song.mesures) - 1))
          mesure = model.Mesure(song, last_mesure_end_time(), tempo, rhythm1, rhythm2, syncope)
          song.add_mesure(mesure)
          time = mesure.time
          current_duration = 0
          line = line[2:]
          start_repeat = mesure
        elif line.startswith(u"::"):
          mesure_ended()
          song.playlist.append(model.PlaylistItem(song.playlist, song.mesures.index(start_repeat), len(song.mesures) - 1))
          song.playlist.append(model.PlaylistItem(song.playlist, song.mesures.index(start_repeat), len(song.mesures) - 1))
          mesure = model.Mesure(song, last_mesure_end_time(), tempo, rhythm1, rhythm2, syncope)
          song.add_mesure(mesure)
          time = mesure.time
          current_duration = 0
          start_repeat = mesure
          line = line[2:]
          
        elif line.startswith(u"|") or line.startswith(u"||") or line.startswith(u"[|") or line.startswith(u"|]"):
          mesure_ended()
          mesure = model.Mesure(song, last_mesure_end_time(), tempo, rhythm1, rhythm2, syncope)
          song.add_mesure(mesure)
          time = mesure.time
          current_duration = 0
          if mesure is song.mesures[0]: start_repeat = mesure
          if line.startswith(u"||") or line.startswith(u"[|") or line.startswith(u"|]"): line = line[2:]
          else:                                                                                                                              line = line[1:]
          
        else:
          for abc_duration, duration in _abc_2_duration.items():
            if line.startswith(abc_duration):
              duration = duration * default_duration // 96
              current_duration = duration
              if note: note.duration = duration
              line = line[len(abc_duration):]
              break
            
  song.title    = u" ".join(titles)
  song.comments = u" ".join(comments)
  
  if (partition.notes[-1].time <= song.mesures[-1].time):
    del song.mesures[-1]
    
  if song.playlist.playlist_items:
    try:
      start_repeat_index = song.mesures.index(start_repeat)
      song.playlist.append(model.PlaylistItem(song.playlist, start_repeat_index, len(song.mesures) - 1))
    except ValueError:
      pass
    
    song.playlist.analyse()
    
#   #Fix first bar, since it is often incomplete
#   first_mesure_end_time = song.mesures[0].end_time()
#   first_mesure_notes = [note for note in partition.notes if note.time < first_mesure_end_time]
#   first_mesure_note_end_time = max([note.end_time() for note in first_mesure_notes])
#   if first_mesure_note_end_time < first_mesure_end_time:
#     for note in first_mesure_notes:
#       note.time += first_mesure_end_time - first_mesure_note_end_time

  return song





class TimingError(Exception): pass


class Timer:
  def __init__(self, song):
    self.song      = song
    self.mesures   = song.mesures
    self.time      = 0
    self.mesure_id = 0
    
  def split(self, duration):
    time      = self.time
    mesure_id = self.mesure_id
    durations = []
    while 1:
      mesure_endtime = self.mesures[mesure_id].endtime()
      if time + duration < mesure_endtime:
        dur = duration
        durations.append(dur)
        time += duration
        break
      
      dur = mesure_endtime - time
      durations.append(dur)
      time = mesure_endtime
      mesure_id += 1
      duration -= dur
      if duration == 0: break
      
    return durations
    
  def advance(self, duration, add_rest = 0):
    print "avance de", duration, add_rest
    
    durations = []
    while 1:
      mesure_endtime = self.mesures[self.mesure_id].endtime()
      if self.time + duration < mesure_endtime:
        dur = duration
        if add_rest: self.add_rest(dur)
        durations.append(dur)
        self.time += duration
        break
      
      dur = mesure_endtime - self.time
      if add_rest: self.add_rest(dur)
      durations.append(dur)
      self.time = mesure_endtime
      self.mesure_id += 1
      duration -= dur
      self.change_mesure(self.mesures[self.mesure_id - 1], self.mesures[self.mesure_id])
      if duration == 0: break
      
    return durations
    
  def goto(self, time):
    if time < self.time: raise TimingError
    self.advance(time - self.time, 1)
    
    
class AbcTimer(Timer):
  def __init__(self, song, abc):
    Timer.__init__(self, song)
    self.abc = abc
    
  def add_rest(self, duration):
    dur = 384
    while duration:
      nb = duration / dur
      duration %= dur
      for i in range(nb): self.abc.write("z" + abcduration(dur))
      dur /= 2

  def start(self):
    for s in self.song.playlist.symbols.get(self.mesures[0], ()):
      if s.startswith(r"\repeat volta"):
        self.abc.write("|:")
        
  def end(self):
    self.abc.write("|]")
    
  def change_mesure(self, left, right):
    print "change mesure"
    #print left, self.song.playlist.symbols.get(left, None), right, self.song.playlist.symbols.get(right, None)
    
    for s in self.song.playlist.symbols.get(left, ()):
      if   s == r"} % end repeat":                   self.abc.write(":") 
      elif s == r"} % end repeat with alternatives": self.abc.write(":") 
      elif s == r"} % end alternative":              self.abc.write(":")
      elif s == r"} % end last alternative":         self.abc.write(":")
      
    self.abc.write("|")
    
    for s in self.song.playlist.symbols.get(right, ()):
      if   s.startswith(r"\repeat volta"):         self.abc.write(":")
      elif s.startswith(r"{ % start alternative"): self.abc.write("[" + s.split()[-1])
      
      
      
      
def abctab(s):
  abc = cStringIO.StringIO()
  print >> abc, "%%!abctab2ps -paper %s" % {"a3paper" : "a3", "a4paper" : "a4", "a5paper" : "a5", "letterpaper" : "letter", }[globdef.config.PAGE_FORMAT]
  print >> abc, "X:1"
  print >> abc, "L:1/4"
  if s.title   : print >> abc, "T:%s" % s.title
  if s.authors : print >> abc, "C:%s" % s.authors
  if s.comments: print >> abc, "N:%s" % s.comments.replace("\n", "N:\n")
  if s.filename: print >> abc, "F:%s" % s.filename
  
  for partition in s.partitions:
    if hasattr(partition, "tonality"):
      print >> abc, "K:%s" % partition.tonality
      break
  else:
    print >> abc, "K:C"
    
  nb = 0
  for partition in s.partitions:
    if   partition.view.__class__.__name__ == "Tablature":
      clef = " clef=guitartab"
      tab  = 6
    elif partition.view.__class__.__name__ == "Staff":
      clef = ""
      tab  = 0
    else: continue
    
    lyric    = None # XXX
    tonality = getattr(partition, "tonality", "C")
    
    print >> abc, "%"
    print >> abc, "V:%s name=%s%s" % (nb, partition.header, clef)
    print >> abc, "K:%s" % tonality
    
    nb += 1
    
    timer = AbcTimer(s, abc)
    timer.start()
    
    chords = chordify(partition.notes)
    for chord in chords:
      timer.goto(chord.time)
      
      if tab:
        for duration in timer.split(chord.duration):
          frets = [","] * tab
          for note in chord.notes:
            stringid = partition.view.stringid(note)
            frets[stringid] = _tabnotes[note.value - partition.view.strings[stringid].basenote]

          while frets and (frets[-1] == ","): frets.pop()
          abc.write("[%s%s]" % ("".join(frets), abcduration(duration)))
          
          timer.advance(duration)
          
      else:
        for duration in timer.advance(chord.duration):
          for note in chord.notes:
            abc.write(
              "[" * ((len(chord.notes) > 1) and (note is chord.notes[0])) +
              _notes[tonality][note.value % 12] +
              "," * (4 - note.value / 12) +
              "'" * (note.value / 12 - 4) +
              abcduration(duration, note) +
              "]" * ((len(chord.notes) > 1) and (note is chord.notes[-1]))
              )
      
    timer.end()
    
  print >> open("/home/jiba/tmp/test.abc", "w"), abc.getvalue()
  return abc.getvalue()



class Chord:
  def __init__(self, time):
    self.time  = time
    self.notes = []
    self.duration = 1000000
    
  def add(self, note):
    self.notes.append(note)
    self.duration = min(note.duration, self.duration)
    
  def __repr__(self):
    return "<Chord at %s duration %s %s>" % (self.time, self.duration, self.notes)
    
def chordify(notes):
  chords   = []
  previous = None
  notes    = notes[:]
  
  while notes:
    chord = Chord(notes[0].time)
    chords.append(chord)
    
    while notes:
      if notes[0].time == chord.time: chord.add(notes.pop(0))
      else: break
      
    if previous:
      if previous.time + previous.duration > chord.time: # Overlaps !!!
        previous.duration = chord.time - previous.time
        
    previous = chord

  return chords
  











