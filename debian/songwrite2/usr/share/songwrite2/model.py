# -*- coding: utf-8 -*-

# Songwrite 2
# Copyright (C) 2001-2010 Jean-Baptiste LAMY -- jibalamy@free.fr
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

import sys, os, bisect, weakref
import songwrite2.globdef as globdef

from xml.sax.saxutils import escape
from cStringIO import StringIO
import codecs

VERSION = "0.4"

class SongwriteError(StandardError): pass

class TimeError(SongwriteError):
  def __init__(self, time, partition = None, note = None):
    self.time      = time
    if   partition: self.song_title =      partition.song.title
    elif note     : self.song_title = note.partition.song.title
    self.partition = partition
    self.note      = note
    self.args      = time, partition, note
    
  def get_details(self):
    return _("__%s__" % self.__class__.__name__)
  
  def __unicode__(self): return unicode(self.__class__.__name__)
  
  
class UnsingablePartitionError(TimeError): pass
  
class _XMLContext(object):
  def __init__(self):
    self._next_id = 0
    self._ids = {}
    
  def id_for(self, obj):
    if obj is None: return ""
    
    id = self._ids.get(obj)
    if id is None:
      self._next_id += 1
      self._ids[obj] = self._next_id
      return self._next_id
    return id
  
  
DURATIONS = {
  384 : "Whole",
  192 : "Half",
   96 : "Quarter",
   48 : "Eighth",
   24 : "Sixteenth",
   12 : "Thirty-second",
  }
VALID_DURATIONS = set()
for duration in DURATIONS.keys():
  VALID_DURATIONS.add(duration)
  VALID_DURATIONS.add(int(duration * 1.5))
  VALID_DURATIONS.add(int(duration / 1.5))
  
  
def duration_label(duration):
  """duration_label(duration) -> string -- Return the string (e.g. "Eighth") for the given note int duration."""
  global DURATIONS
  
  dur = DURATIONS.get(duration)
  if dur: return _(dur)
  
  dur = DURATIONS.get(int(duration / 1.5))
  if dur: return _(dur) + u" (.)"
  
  dur = DURATIONS.get(int(duration * 1.5))
  if dur: return _(dur) + u" (3)"
  
  return u"???"

def note_label(value, show_octave = True, tonality = u"C", force_english = 0):
  """note_label(value, show_octave = True, tonality = u"C", force_english = 0) -> string -- Return the string (e.g. "C(2)") for the given note int value."""
  
  unaltered_value, alteration = TONALITY_NOTES[tonality][abs(value) % 12]
  unaltered_value += (abs(value) // 12) * 12
  if   alteration == -1: alteration = u" ♭"
  elif alteration ==  1: alteration = u" ♯"
  else:                  alteration = u""
  
  if force_english:
    if show_octave: return _("en_note_%s" % (unaltered_value % 12,)) + alteration + u" (%s)" % (unaltered_value // 12,)
    else:           return _("en_note_%s" % (unaltered_value % 12,)) + alteration
  else:
    if show_octave: return _("note_%s" % (unaltered_value % 12,)) + alteration + u" (%s)" % (unaltered_value // 12,)
    else:           return _("note_%s" % (unaltered_value % 12,)) + alteration

NOTES  = [0, 2, 4, 5, 7, 9, 11]
DIESES = [5, 0, 7, 2, 9, 4, 11] # FA DO SOL RE LA MI SI
BEMOLS = [11, 4, 9, 2, 7, 0, 5] # SI MI LA RE SOL DO FA

TONALITIES = {
  u"C"  : [],
  
  u"G"  : DIESES[:1],
  u"D"  : DIESES[:2],
  u"A"  : DIESES[:3],
  u"E"  : DIESES[:4],
  u"B"  : DIESES[:5],
  u"F#" : DIESES[:6],
  u"C#" : DIESES,
  
  u"F"  : BEMOLS[:1],
  u"Bb" : BEMOLS[:2],
  u"Eb" : BEMOLS[:3],
  u"Ab" : BEMOLS[:4],
  u"Db" : BEMOLS[:5],
  u"Gb" : BEMOLS[:6],
  u"Cb" : BEMOLS,
  }

TONALITY_NOTES = {
#          DO               RE              MI      FA              SOL             LA              SI     
# u"C" : [( 0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0)],
  u"C" : [( 0, 0), (0, 1), (2, 0), (4,-1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (11,-1), (11, 0)],

  u"G" : [( 0, 0), (0, 1), (2, 0), (4,-1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (11,-1), (11, 0)],
  u"D" : [( 0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (11,-1), (11, 0)],
  u"A" : [( 0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), ( 9, 1), (11, 0)],
  u"E" : [( 0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (4, 1), (5, 1), (7, 0), (7, 1), (9, 0), ( 9, 1), (11, 0)],
  u"B" : [(11, 1), (0, 1), (2, 0), (2, 1), (4, 0), (4, 1), (5, 1), (7, 0), (7, 1), (9, 0), ( 9, 1), (11, 0)],
  u"F#": [(11, 1), (0, 1), (2, 0), (2, 1), (4, 0), (4, 1), (5, 1), (7, 0), (7, 1), (9, 0), ( 9, 1), (11, 0)],
  u"C#": [(11, 1), (0, 1), (2, 0), (2, 1), (4, 0), (4, 1), (5, 1), (7, 0), (7, 1), (9, 0), ( 9, 1), (11, 0)],
  
  u"F" : [(0, 0), (0, 1), (2, 0), (4,-1), (4, 0), (5, 0), (5, 1), (7, 0), (9,-1), (9, 0), (11,-1), (11, 0)],
  u"Bb": [(0, 0), (2,-1), (2, 0), (4,-1), (4, 0), (5, 0), (5, 1), (7, 0), (9,-1), (9, 0), (11,-1), (11, 0)],
  u"Eb": [(0, 0), (2,-1), (2, 0), (4,-1), (4, 0), (5, 0), (7,-1), (7, 0), (9,-1), (9, 0), (11,-1), (11, 0)],
  u"Ab": [(0, 0), (2,-1), (2, 0), (4,-1), (4, 0), (5, 0), (7,-1), (7, 0), (9,-1), (9, 0), (11,-1), (12,-1)],
  u"Db": [(0, 0), (2,-1), (2, 0), (4,-1), (5,-1), (5, 0), (7,-1), (7, 0), (9,-1), (9, 0), (11,-1), (12,-1)],
  u"Gb": [(0, 0), (2,-1), (2, 0), (4,-1), (5,-1), (5, 0), (7,-1), (7, 0), (9,-1), (9, 0), (11,-1), (12,-1)],
  u"Cb": [(0, 0), (2,-1), (2, 0), (4,-1), (5,-1), (5, 0), (7,-1), (7, 0), (9,-1), (9, 0), (11,-1), (12,-1)],
  
#   u"G" : [( 0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (4, 1), (5, 0), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0)],
#   u"D" : [( 0,-1), (0, 0), (2, 0), (2, 1), (4, 0), (4, 1), (5, 0), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0)],
#   u"A" : [( 0,-1), (0, 0), (2, 0), (2, 1), (4, 0), (4, 1), (5, 1), (7,-1), (7, 0), (9, 0), (9, 1), (11, 0)],
#   u"E" : [( 0,-1), (0, 0), (2,-1), (2, 0), (4, 0), (4, 1), (5, 1), (7,-1), (7, 0), (9, 0), (9, 1), (11, 0)],
#   u"B" : [( 0,-1), (0, 0), (2,-1), (2, 0), (4, 0), (4, 1), (5, 1), (7,-1), (7, 0), (9,-1), (9, 0), (11, 0)],
#   u"F#": [( 0,-1), (0, 0), (2,-1), (2, 0), (4,-1), (4, 0), (5, 1), (7,-1), (7, 0), (9,-1), (9, 0), (11, 0)],
#   u"C#": [(-1, 0), (0, 0), (2,-1), (2, 0), (4,-1), (4, 0), (5, 1), (7,-1), (7, 0), (9,-1), (9, 0), (11,-1)],
  
#   u"F" : [(0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (11, 0), (11, 1)],
#   u"Bb": [(0, 0), (0, 1), (2, 0), (4, 0), (4, 1), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (11, 0), (11, 1)],
#   u"Eb": [(0, 0), (0, 1), (2, 0), (4, 0), (4, 1), (5, 0), (5, 1), (7, 0), (9, 0), (9, 1), (11, 0), (11, 1)],
#   u"Ab": [(0, 0), (2, 0), (2, 1), (4, 0), (4, 1), (5, 0), (5, 1), (7, 0), (9, 0), (9, 1), (11, 0), (11, 1)],
#   u"Db": [(0, 0), (2, 0), (2, 1), (4, 0), (4, 1), (5, 0), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0), (11, 1)],
#   u"Gb": [(0, 1), (2, 0), (2, 1), (4, 0), (4, 1), (5, 0), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0), (12, 0)],
#   u"Cb": [(0, 1), (2, 0), (2, 1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0), (12, 0)],

  # u"G" : [( 0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0)],
  # u"D" : [( 0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0)],
  # u"A" : [( 0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0)],
  # u"E" : [( 0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0)],
  # u"B" : [( 0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0)],
  # u"F#": [( 0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (4, 1), (5, 1), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0)],
  # u"C#": [(-1, 1), (0, 1), (2, 0), (2, 1), (4, 0), (4, 1), (5, 1), (7, 0), (7, 1), (9, 0), (9, 1), (11, 0)],
  
  # u"F" : [(0, 0), (0, 1), (2, 0), (2, 1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (11,-1), (11, 0)],
  # u"Bb": [(0, 0), (0, 1), (2, 0), (4,-1), (4, 0), (5, 0), (5, 1), (7, 0), (7, 1), (9, 0), (11,-1), (11, 0)],
  # u"Eb": [(0, 0), (0, 1), (2, 0), (4,-1), (4, 0), (5, 0), (5, 1), (7, 0), (9,-1), (9, 0), (11,-1), (11, 0)],
  # u"Ab": [(0, 0), (2,-1), (2, 0), (4,-1), (4, 0), (5, 0), (5, 1), (7, 0), (9,-1), (9, 0), (11,-1), (11, 0)],
  # u"Db": [(0, 0), (2,-1), (2, 0), (4,-1), (4, 0), (5, 0), (7,-1), (7, 0), (9,-1), (9, 0), (11,-1), (11, 0)],
  # u"Gb": [(0, 0), (2,-1), (2, 0), (4,-1), (4, 0), (5, 0), (7,-1), (7, 0), (9,-1), (9, 0), (11,-1), (12,-1)],
  # u"Cb": [(0, 0), (2,-1), (2, 0), (4,-1), (5,-1), (5, 0), (7,-1), (7, 0), (9,-1), (9, 0), (11,-1), (12,-1)],
  }

OFFSETS = {
  u"C"  : 0,
  u"G"  : 7,
  u"D"  : 2,
  u"A"  : 9,
  u"E"  : 4,
  u"B"  : 11,
  u"F#" : 6,
  u"C#" : 1,
  
  u"F"  : 5,
  u"Bb" : 10,
  u"Eb" : 3,
  u"Ab" : 8,
  u"Db" : 1,
  u"Gb" : 6,
  u"Cb" : 11,
  }


class Songbook(object):
  def __init__(self, filename = "", title = u"", authors = u"", comments = u""):
    self.title             = title
    self.authors           = authors
    self.comments          = comments
    self.song_refs         = []
    self.version           = "0.12"
    self.filename          = filename
    
  def add_song_ref(self, song_ref):
    self.song_refs.append(song_ref)
    
  def insert_song_ref(self, index, song_ref):
    self.song_refs.insert(index, song_ref)
    
  def remove_song_ref(self, song_ref):
    self.song_refs.remove(song_ref)

  def set_filename(self, filename):
    for song_ref in self.song_refs:
      song_ref.filename = rel_path(filename, os.path.join(self.filename, song_ref.filename))
    self.filename = filename
    
  def __unicode__(self): return self.title
  
  def __xml__(self, xml = None):
    if not xml:
      _xml = StringIO()
      xml  = codecs.lookup("utf8")[3](_xml)
      
    xml.write(u"""<?xml version="1.0" encoding="utf-8"?>

<songbook version="%s">
\t<title>%s</title>
\t<authors>%s</authors>
\t<comments>%s</comments>
""" % (VERSION, escape(self.title), escape(self.authors), escape(self.comments)))
    
    for song_ref in self.song_refs:
      if isinstance(song_ref.filename, str): f = song_ref.filename.decode("utf8")
      else:                                  f = song_ref.filename
      xml.write(u'\t<songfile title="%s" filename="%s"/>\n' % (song_ref.title, f))
      
    xml.write(u'</songbook>')
    
    xml.flush()
    return xml
  

def rel_path(base, path):
  if base == "": return path
  
  base = os.path.normpath(os.path.abspath(base))
  path = os.path.normpath(os.path.abspath(path))
  
  while 1:
    i = base.find(os.sep)
    if base[:i] == path[:path.find(os.sep)]:
      base = base[i + 1:]
      path = path[i + 1:]
    else: break
    
  return os.curdir + os.sep + (os.pardir + os.sep) * base.count(os.sep) + path


class SongRef:
  def __init__(self, songbook, filename = u"", title = u""):
    self.songbook = songbook
    self.ref      = None
    self.filename = filename
    self.title    = title
    
  def set_filename(self, filename, title = u""):
    self.filename = rel_path(self.songbook.filename, filename)
    self.title    = title or get_song(os.path.join(os.path.dirname(self.songbook.filename), filename)).title
    
  def get_song(self):
    #if self.ref:
    #  song = self.ref()
    #  if song: return song
    
    song = get_song(os.path.join(os.path.dirname(self.songbook.filename), self.filename))
    #self.ref   = weakref.ref(song)
    self.title = song.title
    return song
  
  def unload(self):
    unload_song(os.path.join(os.path.dirname(self.songbook.filename), self.filename))
    
  def __unicode__(self): return self.title


SONGS = weakref.WeakValueDictionary()

def get_song(filename):
  song = SONGS.get(filename)
  if not song:
    import songwrite2.stemml as stemml
    print "Loading %s ..." % filename
    song = stemml.parse(filename)
  return song

def unload_song(filename):
  try: del SONGS[filename]
  except KeyError: pass
  
  
class Song(object):
  def __init__(self):
    self.authors       = u""
    self.title         = u""
    self.copyright     = u""
    self.comments      = u""
    self.partitions    = []
    self.mesures       = [Mesure(self, 0)]
    self.lang          = unicode(os.environ.get("LANG", "en")[:2])
    self.version       = "0.9"
    self.playlist      = Playlist(self)
    self.filename      = ""
    self.printfontsize = 16
    self.print_nb_mesures_per_line = 4
    
  def set_filename(self, filename):
    if self.filename: del SONGS[self.filename]
    self.filename = filename
    if self.filename: SONGS[self.filename] = self
    
  def add_partition(self, partition):
    self.partitions.append(partition)
    
  def insert_partition(self, index, partition):
    self.partitions.insert(index, partition)
    
  def remove_partition(self, partition):
    self.partitions.remove(partition)
    
  def add_mesure(self, mesure = None):
    if mesure is None:
      previous = self.mesures[-1]
      mesure   = Mesure(self, previous.time + previous.duration, previous.tempo, previous.rythm1, previous.rythm2, previous.syncope)
    self.mesures.append(mesure)
    self.playlist.analyse()
    return mesure

  def remove_unused_mesures(self):
    last_time = 0
    for partition in self.partitions:
      if isinstance(partition, Partition) and partition.notes:
        if last_time < partition.notes[-1].time:
          last_time = partition.notes[-1].time
    while self.mesures[-1].time > last_time:
      del self.mesures[-1]
      
  def mesure_before(self, time):
    if time > self.mesures[-1].end_time(): return self.mesures[-1]
    i = bisect.bisect_right(self.mesures, time) - 2
    if i < 0: return None
    return self.mesures[i]
    
  def mesure_at(self, time, create = 0):
    mesure = self.mesures[bisect.bisect_right(self.mesures, time) - 1]
    if create:
      while time >= mesure.end_time(): mesure = self.addmesure()
    elif    time >= mesure.end_time(): return None
    return mesure
  
  def rythm_changed(self, start_from = None):
    # XXX optimize using start_from
    
    time = 0
    for mesure in self.mesures:
      mesure.time = time
      time = time + mesure.duration
      
    # Check if we need to add or remove some mesures.
    max_time = max(map(lambda partition: partition.end_time(), self.partitions))
    while max_time >= self.mesures[-1].end_time(): self.add_mesure()
    while max_time <  self.mesures[-1].time: del self.mesures[-1]
    
    self.playlist.analyse()
    
  def __unicode__(self): return self.title
  
  def __repr__(self):
    return u"""<Song %s
    Mesures :
%s
    Partitions :
%s
>""" % (
      self.title,
      u"\n".join(map(repr, self.mesures)),
      u"\n".join(map(repr, self.partitions)),
      )
  
  def date(self):
    import re
    year = re.findall(u"[0-9]{2,4}", self.copyright)
    if year: return year[0]
    return u""
  
  def __xml__(self, xml = None, context = None):
    if not xml:
      _xml = StringIO()
      xml  = codecs.lookup("utf8")[3](_xml)
      
    if not context: context = _XMLContext()
    
    xml.write("""<?xml version="1.0" encoding="utf-8"?>

<song version="%s" lang="%s" print_nb_mesures_per_line="%s" printfontsize="%s">
\t<title>%s</title>
\t<authors>%s</authors>
\t<copyright>%s</copyright>
\t<comments>%s</comments>
\t<bars>
""" % (VERSION, self.lang, self.print_nb_mesures_per_line, self.printfontsize, escape(self.title), escape(self.authors), escape(self.copyright), escape(self.comments)))
    
    for mesure in self.mesures: mesure.__xml__(xml, context)
    xml.write('\t</bars>\n')
    xml.write('\t<playlist>\n')
    self.playlist.__xml__(xml, context)
    xml.write('\t</playlist>\n')
    
    for partition in self.partitions: partition.__xml__(xml, context)
    
    xml.write('</song>')
    
    xml.flush()
    return xml
  
  

class TemporalData(object):
  def midi(self, midifier, start_time, end_time): return ()
  
  def __unicode__(self):
    text = self.header
    end_of_line = text.find("\n")
    if end_of_line != -1: return text[:end_of_line]
    else:                 return text
    

class Partition(TemporalData):
  def __init__(self, song, instrument = 24, view_type = None):
    self.song       = song
    self.notes      = []
    self.instrument = instrument
    self.chorus     = 0
    self.reverb     = 0
    self.header     = u""
    self.muted      = 0
    self.volume     = 255
    self.tonality   = u"C"
    self.g8         = 0
    if view_type: self.view = view_type(self)
    else:         self.view = None
    
  def __unicode__(self):
    return self.header.split(u"\n")[0]

  def set_tonality(self, tonality):
    self.tonality = tonality
    if self.view: self.view.set_tonality(tonality)
    
  def add_note(self, *notes):
    for note in notes:
      note.partition = self
      bisect.insort(self.notes, note)
      
    for note in notes:
      previous = note.previous()
      if previous and previous.is_linked_to():
        previous.link_to(note)
    
    for note in notes:
      if note.linked_to or note.is_linked_to():
        next = note.next()
        note.link_to(next)
    while self.notes[-1].time >= self.song.mesures[-1].end_time(): self.song.add_mesure()
    
  def notes_at(self, time1, time2 = 0):
    return self.notes[bisect.bisect_left(self.notes, time1) : bisect.bisect_right(self.notes, time2 or time1)]
  
  def note_before(self, time):
    if (not self.notes) or (time <= self.notes[0].time): return None
    return self.notes[bisect.bisect_left(self.notes, time) - 1]
  
  def notes_before(self, time):
    if (not self.notes) or (time <= self.notes[0].time): return ()
    i = bisect.bisect_left(self.notes, time) - 1
    notes = [self.notes[i]]
    time  = self.notes[i].time
    while (i > 0) and (self.notes[i - 1].time == time):
      i -= 1
      notes.append(self.notes[i])
    return notes
  
  def note_before_pred(self, time, pred = None):
    if (not self.notes) or (time <= self.notes[0].time): return None
    i = bisect.bisect_left(self.notes, time) - 1
    while i >= 0:
      if pred(self.notes[i]): return self.notes[i]
      i -= 1
      
  def note_after(self, time):
    if (not self.notes) or (time >= self.notes[-1].time): return None
    return self.notes[bisect.bisect_right(self.notes, time)]
  
  def note_after_pred(self, time, pred = None):
    if (not self.notes) or (time >= self.notes[-1].time): return None
    i = bisect.bisect_right(self.notes, time)
    while i < len(self.notes):
      if pred(self.notes[i]): return self.notes[i]
      i += 1
      
  def remove(self, *notes):
    notes = set(notes)
    for note in notes:
      self.notes.remove(note)
    for note in notes:
      if note.linked_to   and (not note.linked_to   in notes): note.linked_to  ._link_from(note.linked_to.previous())
    for note in notes: # Needs two loops, since all links sould be removed BEFORE adding new ones (else, we may remove the new links, if the creation occurs before the removal)
      if note.linked_from and (not note.linked_from in notes): note.linked_from.link_to   (note.linked_from.next())
      
  def end_time(self):
    if self.notes: return self.notes[-1].end_time()
    return 0
  
  def voices(self, single_voice = 0):
    "Gets the list of voices (non-overlapping sequence of notes) in this partition."
    if single_voice:
      voices = [[]]
      for note in self.notes:
        if note.chord_notes() or self._clash_note_voice(note, voices[0]):
          raise UnsingablePartitionError(note.time, self, self._clash_note_voice(note, voices[0]))
        voices[0].append(note)
        
    else:
      voices = [[], []]
      for note in self.notes:
        if   note.chord_notes(): voices[0].append(note) # Chords are not bass !
        elif self._clash_note_voice(note, voices[0]): voices[1].append(note)
        elif self._clash_note_voice(note, voices[1]): voices[0].append(note)
        else:
          if   note.linked_from: # Add with the other note !
            voices[note.linked_from in voices[1]].append(note)
          elif note.duration < 96: voices[0].append(note) # Too short for a bass !
          else:
            clashings = self.notes_at(note)
            if len(clashings) == 1:
              if getattr(note, "string_id", 6) >= 3: voices[1].append(note)
              else:                                 voices[0].append(note)
            else:
              clashings.sort(lambda a, b: cmp(a.value, b.value))
              if note is clashings[0]: voices[1].append(note)
              else:                    voices[0].append(note)

    return voices
  
  def __repr__(self):
    return u"""<Partition
    Notes :
%s
>""" % (
      "\n".join(map(repr, self.notes)),
      )
  
  def _clash_note_voice(self, note, voice):
    for note2 in voice:
      if note._clash(note2): return note2 # not self.is_in_chord(note)
    return 0
  
  def __xml__(self, xml, context):
    xml.write("\t<partition")
    
    for attr, val in self.__dict__.items():
      if (not attr in ("header", "notes", "view", "song", "oldview")) and not attr.startswith("_"):
        xml.write(' %s="%s"' % (attr, unicode(val)))
        
    xml.write(">\n\t\t<header>%s</header>\n" % escape(self.header))
    
    if hasattr(self, "view"): self.view.__xml__(xml, context)
    xml.write("\t\t<notes>\n")
    
    for note in self.notes: note.__xml__(xml, context)
    
    xml.write("""\t\t</notes>
\t</partition>
""")

  def get_view_type(self):
    return self.view.get_type()
  
  def set_view_type(self, view_type):
    if self.view:
      new_view = self.view.change_to_view_type(view_type)
      if new_view:
        self.view = new_view
        return
    self.view = view_type(self)
  
  
STRING_INSTRUMENTS    = set([15, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 48, 49, 50, 51, 104, 105, 106, 110, 120])
PIANO_INSTRUMENTS     = set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20])
VOCALS_INSTRUMENTS    = set([52, 53, 54, 85, 91, 121, 123, 126])
WIND_INSTRUMENTS      = set([22, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 109])
BATTERY_INSTRUMENTS   = set([114, 115, 116, 117, 118, 119, 127, 128])
ACCORDION_INSTRUMENTS = set([21, 22, 23])

LINK_NOTES_DEFAULT         = 0
LINK_NOTES_ON_SAME_STRING  = 1
LINK_NOTES_WITH_SAME_VALUE = 2

# class Instrument(object):
#   name  = u"Unamed instrument"
#   icon  = u"piano.png"
#   midi  = 0
#   Views = []
#   def __init__(self, partition):
#     if partition and not partition.header: partition.header = self.name
#     self.views = [View(partition) for View in self.Views]
#     partition.set_view(self.views[0])
    
# class StringedInstrument(Instrument):
#   def __init__(self, partition, strings = None):
#     super(StringedInstrument, self).__init__(partition)
#     self.strings = strings or []
    
# class String(object):
#   def __init__(self, base_note = 50):
#     self.base_note = base_note
    
#   def before(self, value): return max(self.base_note, value - 1)
#   def after (self, value): return max(self.base_note, value + 1)
  
#   def __xml__(self, xml = None, context = None):
#     if not self.__class__ is String:
#       xml.write(u"""\t\t\t\t<string pitch="%s" type="%s"/>\n""" % (self.base_note, self.__class__.__name__))
#     else:
#       xml.write(u"""\t\t\t\t<string pitch="%s"/>\n""" % self.base_note)
      
#   def __unicode__(self):
#     return _(self.__class__.__name__) % note_label(self.base_note)

# class GuitarInstrument(object):
#   name  = _(u"Vocals")
#   icon  = u"guitar.png"
#   midi  = 23
#   Views = [TablatureView, StaffView]

# class PianoInstrument(object):
#   name  = _(u"Piano")
#   icon  = u"piano.png"
#   midi  = 0
#   Views = [StaffView]

# class VocalInstrument(object):
#   name  = _(u"Vocals")
#   icon  = u"voice.png"
#   midi  = 52
#   Views = [StaffView]

    
class View(object):
  link_type                = LINK_NOTES_DEFAULT
  can_paste_note_by_string = 0
  automatic_string_id      = 1
  ok_for_lyrics            = 1
  def __init__(self, partition, name):
    self.partition = partition
    self.visible   = 1
    if partition and not partition.header: partition.header = name
    
  def load_attrs(self, attrs): pass
  
  def note_string_id(self, note): return 0
  
  def get_icon_filename(self):
    if self.partition.instrument in STRING_INSTRUMENTS   : return "guitar.png"
    if self.partition.instrument in VOCALS_INSTRUMENTS   : return "voice.png"
    if self.partition.instrument in WIND_INSTRUMENTS     : return "flute.png"
    if self.partition.instrument in BATTERY_INSTRUMENTS  : return "tamtam.png"
    if self.partition.instrument in ACCORDION_INSTRUMENTS: return "accordion.png"
    return "piano.png"
  
  def set_tonality(self, tonality): pass

  def get_type(self): return self.__class__
  
  def change_to_view_type(self, view_type): return None
  
class StaffView(View):
  view_class = u"staff"
  def __init__(self, partition, name):
    super(StaffView, self).__init__(partition, name)
    if not hasattr(partition, "g_key"): partition.g_key = 1
    if not hasattr(partition, "f_key"): partition.f_key = 0
    
  def get_type(self):
    if self.partition.g8:
      if self.partition.instrument in VOCALS_INSTRUMENTS   : return VocalsView
    if   self.partition.instrument in STRING_INSTRUMENTS   : return GuitarStaffView
    elif self.partition.instrument in ACCORDION_INSTRUMENTS: return AccordionStaffView
    return PianoView
    
  def __xml__(self, xml = None, context = None):
    xml.write(u'''\t\t<view type="staff"''')
    if not self.visible: xml.write(u' hidden="1"')
    xml.write(u">\n")
    xml.write(u"""\t\t</view>\n""")
    

class TablatureView(View):
  view_class               = u"tablature"
  link_type                = LINK_NOTES_ON_SAME_STRING
  can_paste_note_by_string = 1
  automatic_string_id      = 0
  def __init__(self, partition, name, strings = None):
    super(TablatureView, self).__init__(partition, name)
    self.strings = strings or []
    if partition:
      partition.g8 = 1
      if not hasattr(partition, "capo"                ): partition.capo                 = 0
      if not hasattr(partition, "print_with_staff_too"): partition.print_with_staff_too = 0
      if not hasattr(partition, "let_ring"            ): partition.let_ring             = 0

  @classmethod
  def new_strings(Class): return []
  
  def note_string_id(self, note):
    if not hasattr(note, "string_id"):
      #note.string_id = self.default_string_id(note.value)
      value = abs(note.value)
      for i, string in enumerate(self.strings):
        if string.base_note <= value:
          note.string_id = i
          break
      else: note.string_id = len(self.strings) - 1
    return min(note.string_id, len(self.strings) - 1)
  
  def get_icon_filename(self): return "guitar.png"
      
  def get_type(self, DefaultView = None):
    if not DefaultView: DefaultView = self.__class__
    default_strings = DefaultView.new_strings()
    if len(default_strings) == len(self.strings):
      for i in range(len(default_strings)):
        if default_strings[i].base_note != self.strings[i].base_note: break
      else:
        return DefaultView
      
    for subclass in _recursive_subclasses(self.__class__):
      if subclass.view_class == self.view_class:
        strings = subclass.new_strings()
        if len(strings) == len(self.strings):
          for i in range(len(strings)):
            if strings[i].base_note != self.strings[i].base_note: break
          else:
            return subclass
          
    string_bases = [string.base_note for string in self.strings]
    class MyView(DefaultView):
      @classmethod
      def new_strings(Class):
        return [TablatureString(base, -1) for base in string_bases]
    MyView.__name__ = DefaultView.__name__
    return MyView
    
  def __xml__(self, xml = None, context = None, type = "tablature"):
    if self.visible:
      xml.write(u"""\t\t<view type="%s">\n""" % type)
    else:
      xml.write(u"""\t\t<view type="%s" hidden="1">\n""" % type)
    xml.write(u"""\t\t\t<strings>\n""")
    for string in self.strings: string.__xml__(xml, context)
    xml.write(u"""\t\t\t</strings>\n""")
    xml.write(u"""\t\t</view>\n""")

def _recursive_subclasses(Class):
  for subclass in Class.__subclasses__():
    yield subclass
    for subclass2 in _recursive_subclasses(subclass):
      yield subclass2
      
class TablatureString(object):
  def __init__(self, base_note = 50, notation_pos = 1):
    self.base_note    = base_note
    self.notation_pos = notation_pos # The position of the notation of the note duration (-1 at top, 1 at bottom)
    
  def value_2_text(self, note):       return unicode(note.value - self.base_note - note.partition.capo)
  def text_2_value(self, note, text): return int    (text) + self.base_note + note.partition.capo
  
  def before(self, value): return max(self.base_note, value - 1)
  def after (self, value): return max(self.base_note, value + 1)
  
  def __xml__(self, xml = None, context = None):
    if not self.__class__ is TablatureString:
      xml.write(u"""\t\t\t\t<string pitch="%s" type="%s"/>\n""" % (self.base_note, self.__class__.__name__))
    else:
      xml.write(u"""\t\t\t\t<string pitch="%s"/>\n""" % self.base_note)
    
  def __unicode__(self):
    return _(self.__class__.__name__) % note_label(self.base_note)
  
  def width(self):
    if   self.base_note < 31: return 0
    elif self.base_note < 36: return 1
    elif self.base_note < 41: return 2
    elif self.base_note < 46: return 3
    elif self.base_note < 52: return 4
    elif self.base_note < 57: return 5
    elif self.base_note < 62: return 6
    else:                     return 7
    

class DrumsView(View):
  view_class          = u"drums"
  link_type           = LINK_NOTES_WITH_SAME_VALUE
  automatic_string_id = 0
  def __init__(self, partition, name, strings):
    super(DrumsView, self).__init__(partition, name)
    self.strings = strings or []
    
  def note_string_id(self, note):
    for i, string in enumerate(self.strings):
      if string.base_note == abs(note.value): return i
    return -1
    
  def get_type(self):
    for view_type in VIEWS[u"drums"]:
      view = view_type(None)
      if len(view.strings) != len(self.strings): continue
      for i in range(len(view.strings)):
        if view.strings[i].base_note == self.strings[i].base_note: break
      else: return view_type
      
  def get_icon_filename(self): return "tamtam.png"
      
  def __xml__(self, xml = None, context = None):
    if self.visible:
      xml.write(u"""\t\t<view type="drums">\n""")
    else:
      xml.write(u"""\t\t<view type="drums" hidden="1">\n""")
    xml.write(u"""\t\t\t<strings>\n""")
    for string in self.strings: string.__xml__(xml, context)
    xml.write(u"""\t\t\t</strings>\n""")
    xml.write(u"""\t\t</view>\n""")
    
class DrumString(object):
  def __init__(self, base_note = 50, notation_pos = 1):
    self.base_note    = base_note
    self.notation_pos = notation_pos # The position of the notation of the note duration (-1 at top, 1 at bottom)
    
  def value_2_text(self, note):        return u"O"
  def text_2_value(self, note, text):  return self.base_note
  
  def before(self, value): return self.base_note
  def after (self, value): return self.base_note
  
  def __unicode__(self): return _(u"Drum patch, %s") % DRUM_PATCHES[self.base_note]
  
  def __xml__(self, xml = None, context = None):
    xml.write(u"""\t\t\t\t<string patch="%s"/>\n""" % self.base_note)
    
  def width(self): return 5

DRUM_PATCHES = [s.split(None, 1) for s in _("__percu__").split("\n")]
DRUM_PATCHES = dict([(int(i), patch) for (i, patch) in DRUM_PATCHES])

class GuitarView(TablatureView):
  default_instrument = 24
  def __init__(self, partition, name = u""):
    super(GuitarView, self).__init__(partition, name or _(u"Guitar"), self.new_strings())
    #TablatureView.__init__(self, partition, name or _(u"Guitar"), self.new_strings())
  @classmethod
  def new_strings(Class):
    return [TablatureString(64, -1), TablatureString(59, -1), TablatureString(55, -1), TablatureString(50, 1), TablatureString(45, 1), TablatureString(40, 1)]
  
class GuitarDADGADView(TablatureView):
  default_instrument = 24
  def __init__(self, partition, name = u""):
    super(GuitarDADGADView, self).__init__(partition, name or _(u"Guitar DADGAD"), self.new_strings())
    #TablatureView.__init__(self, partition, name or _(u"Guitar DADGAD"), self.new_strings())
  @classmethod
  def new_strings(Class):
    return [TablatureString(62, -1), TablatureString(57, -1), TablatureString(55, -1), TablatureString(50, 1), TablatureString(45, 1), TablatureString(38, 1)]
  
class BassView(TablatureView):
  default_instrument = 33
  def __init__(self, partition, name = u""):
    super(BassView, self).__init__(partition, name or _(u"Bass"), self.new_strings())
    #TablatureView.__init__(self, partition, name or _(u"Bass"), self.new_strings())
  @classmethod
  def new_strings(Class):
    return [TablatureString(43, -1), TablatureString(38, -1), TablatureString(33, 1), TablatureString(28, 1)]

class PianoView(StaffView):
  default_instrument = 0
  def __init__(self, partition, name = u""):
    super(PianoView, self).__init__(partition, name or _(u"Piano"))
    if partition: partition.g8 = 0

class FluteView(StaffView):
  default_instrument = 73
  def __init__(self, partition, name = u""):
    super(FluteView, self).__init__(partition, name or _(u"Flute"))
    if partition: partition.g8 = 0

class GuitarStaffView(StaffView):
  default_instrument = 24
  def __init__(self, partition, set_g8 = 1, name = u""):
    super(GuitarStaffView, self).__init__(partition, name or _(u"Guitar (staff 1 octavo above)"))
    if partition and set_g8: partition.g8 = 1

class AccordionStaffView(StaffView):
  default_instrument = 21
  def __init__(self, partition, name = u""):
    super(AccordionStaffView, self).__init__(partition, name or _(u"Accordion"))
    if partition: partition.g8 = 0
    
class VocalsView(StaffView):
  default_instrument = 52
  def __init__(self, partition, name = u""):
    super(VocalsView, self).__init__(partition, name or _(u"Vocals"))
    if partition: partition.g8 = 0

class EmptyDrumsView(DrumsView):
  default_instrument = 128
  def __init__(self, partition, name = u""):
    super(EmptyDrumsView, self).__init__(partition, name or _(u"EmptyDrums"), self.new_strings())
  @classmethod
  def new_strings(Class):
    return []
  
class TomView(DrumsView):
  default_instrument = 128
  def __init__(self, partition, name = u""):
    super(TomView, self).__init__(partition, name or _(u"Tom"), self.new_strings())
  @classmethod
  def new_strings(Class):
    return [DrumString(50, -1), DrumString(48, -1), DrumString(47, -1), DrumString(45, -1), DrumString(43, -1), DrumString(41, -1)]

class CymbalView(DrumsView):
  default_instrument = 128
  def __init__(self, partition, name = u""):
    super(CymbalView, self).__init__(partition, name or _(u"Cymbal"), self.new_strings())
  @classmethod
  def new_strings(Class):
    return [DrumString(49, -1), DrumString(57, -1), DrumString(55, -1), DrumString(52, -1), DrumString(51, -1), DrumString(59, -1)]

class TriangleView(DrumsView):
  default_instrument = 128
  def __init__(self, partition, name = u""):
    super(TriangleView, self).__init__(partition, name or _(u"Triangle"), self.new_strings())
  @classmethod
  def new_strings(Class):
    return [DrumString(80, -1), DrumString(81, -1)]

class TimbaleView(DrumsView):
  default_instrument = 128
  def __init__(self, partition, name = u""):
    super(TimbaleView, self).__init__(partition, name or _(u"Timbale"), self.new_strings())
  @classmethod
  def new_strings(Class):
    return [DrumString(65, -1), DrumString(66, -1)]

class BongoView(DrumsView):
  default_instrument = 128
  def __init__(self, partition, name = u""):
    super(BongoView, self).__init__(partition, name or _(u"Bongo"), self.new_strings())
  @classmethod
  def new_strings(Class):
    return [DrumString(60, -1), DrumString(61, -1)]

class CongaView(DrumsView):
  default_instrument = 128
  def __init__(self, partition, name = u""):
    super(CongaView, self).__init__(partition, name or _(u"Conga"), self.new_strings())
  @classmethod
  def new_strings(Class):
    return [DrumString(62, -1), DrumString(63, -1), DrumString(64, -1)]

VIEW_CATEGORIES = [u"tab", u"staff", u"drums"]
VIEWS = {
  u"tab"   : [GuitarView, GuitarDADGADView, BassView],
  u"staff" : [PianoView, GuitarStaffView, FluteView, VocalsView, AccordionStaffView],
  u"drums" : [TomView, CymbalView, TriangleView, TimbaleView, BongoView, CongaView]
  }
#VIEW_TYPES = VIEWS[u"tab"] + VIEWS[u"staff"] + VIEWS[u"drums"]

FXS           = [u"", u"bend", u"tremolo", u"dead", u"roll", u"harmonic"]
LINK_FXS      = [u"", u"link", u"slide"]
DURATION_FXS  = [u"", u"appoggiatura", u"fermata", u"breath"]
STRUM_DIR_FXS = [u"", u"up", u"down", u"down_thumb"]

ALL_FXS = [
  (u""         , FXS),
  (u"link"     , LINK_FXS),
  (u"duration" , DURATION_FXS),
  (u"strum_dir", STRUM_DIR_FXS),
  ]

FXS_ARGS = { u"bend" : [0.5, 1.0, 1.5] }

class Note(object):
  linked_to    = None
  linked_from  = None
  fx           = u""
  link_fx      = u""
  duration_fx  = u""
  bend_pitch   = 0.0
  roll_decal   = 0 # 2
  strum_dir_fx = u""
  def __init__(self, partition = None, time = 0, duration = 0, value = 0, volume = 0xCC):
    self.partition    = partition
    self.time         = time
    self.duration     = duration
    self.value        = value
    self.volume       = volume
    
  def __unicode__(self):
    if self.value == -1: return u"_"
    if self.partition.instrument == 128: # Battery
      return DRUM_PATCHES.get(abs(self.value), _(u"(Unknown drum patch)"))
    else:
      return note_label(self.value, True, (self.partition and self.partition.tonality) or u"C")
    
  def unaltered_value_and_alteration(self):
    unaltered_value, alteration = TONALITY_NOTES[self.partition.tonality][abs(self.value) % 12]
    unaltered_value += (abs(self.value) // 12) * 12
    return unaltered_value, alteration
  
  def previous(self):
    if not self.partition.notes: return None
    if self.time <= self.partition.notes[0].time: return None
    i = bisect.bisect_left(self.partition.notes, self) - 1

    if self.partition.view:
      if   self.partition.view.link_type == LINK_NOTES_ON_SAME_STRING:
        while (i >= 0) and self.partition.notes[i].string_id != self.string_id: i -= 1
      elif self.partition.view.link_type == LINK_NOTES_WITH_SAME_VALUE:
        while (i >= 0) and self.partition.notes[i].value != self.value: i -= 1
    if i == -1: return None
    return self.partition.notes[i]
  
  def next(self):
    if not self.partition.notes: return None
    if self.time >= self.partition.notes[-1].time: return None
    i = bisect.bisect_right(self.partition.notes, self)
    if   self.partition.view.link_type == LINK_NOTES_ON_SAME_STRING:
      while (i < len(self.partition.notes)) and self.partition.notes[i].string_id != self.string_id: i += 1
    elif self.partition.view.link_type == LINK_NOTES_WITH_SAME_VALUE:
      while (i < len(self.partition.notes)) and self.partition.notes[i].value != self.value: i += 1
    if i > len(self.partition.notes) - 1: return None
    return self.partition.notes[i]

  def is_linked_to(self):
    return self.link_fx
  
  def chord_notes(self):
    chord_notes = self.partition.notes_at(self)
    if len(chord_notes) < 3: return None
    return chord_notes
  
  def _clash(self, other):
    "Checks if this note clashes with (= overlaps) other, and are not part of the same chord."
    return (self.end_time() > other.time) and (other.end_time() > self.time)
  
  def dissimilarity(self, other):
    "Gets a quantifier that quantifies how 2 notes differ."
    dissimilarity = 2 * abs(self.duration - other.duration) + 2 * abs(self.value - other.value) + abs(self.volume - other.volume) / 5
    if hasattr(self, "string_id") and hasattr(other, "string_id"):
      dissimilarity = dissimilarity + 10 * abs(self.string_id - other.string_id)
    return dissimilarity
  
  def end_time(self): return self.time + self.duration
  
  def is_dotted       (self): return int(self.duration / 1.5) in DURATIONS.keys()
  def is_triplet      (self): return int(self.duration * 1.5) in DURATIONS.keys()
  def is_start_triplet(self): return self.is_triplet() and ((self.time % int(self.duration * 1.5)) == 0)
  def is_end_triplet  (self): return self.is_triplet() and (0 < (self.time % int(self.duration * 1.5)) < self.duration)
  
  def base_duration(self):
    """Gets the duration of the note, without taking into account dot or triplet."""
    dur = set(DURATIONS.keys())
    if self.duration            in dur: return self.duration
    if int(self.duration / 1.5) in dur: return int(self.duration / 1.5)
    if int(self.duration * 1.5) in dur: return int(self.duration * 1.5)
    return self.duration
  
  def real_time(self):
    """Returns the real time at which the note starts, including offset due to rolls"""
    notes = self.chord_notes()
    if notes and (u"roll" in [note.fx for note in notes]):
      nb = 0
      for note in notes:
        if note.value < self.value: nb += 1
      return self.time + 12 * nb
    else: return self.time
    
  def set_fx(self, fx):
    self.fx = fx
    if (fx == "bend"):
      if self.bend_pitch == 0.0: self.bend_pitch = 0.5
      
  def set_link_fx(self, fx):
    if self.link_fx: self.link_to(None)
    self.link_fx = fx
    if fx: self.link_to(self.next())
    
  def set_duration_fx(self, fx):
    self.duration_fx = fx
    
  def set_strum_dir_fx(self, fx):
    self.strum_dir_fx = fx
    
  def link_to(self, other):
    if self.linked_to: self.linked_to._link_from(None)
    if other and other.linked_from: other.linked_from._link_to(None)
    self._link_to(other)
    if other: other._link_from(self)
  def _link_to  (self, other): self.linked_to   = other
  def _link_from(self, other): self.linked_from = other
  
  def link_duration(self):
    if self.linked_to: return self.duration + self.linked_to.link_duration()
    return self.duration
  
  def link_start(self):
    if self.linked_from: return self.linked_from.link_start()
    return self.time
  
  def link_end(self):
    if self.linked_to: return self.linked_to.link_end()
    return self.end_time()
  
  def link_min_max_real_values(self):
    "LinkedNote.link_min_max_real_values() -> min, max. Return the minimal and maximal note's value in the group of linked notes."
    if self.linked_from: return self.linked_from.link_min_max_real_values() # Start at the beginning of the link !
    values = []
    note = self
    while note:
      if note.fx == u"harmonic": values.append(note._real_value + 12)
      else:                      values.append(note._real_value)
      note = note.linked_to
    return min(values), max(values)
  
  def link_first_real_value(self):
    "Gets the value of the first note of this group of linked notes."
    if self.linked_from: return self.linked_from.link_first_real_value()
    return self._real_value
  
  def link_type(self):
    if not self.linked_to: return None
    if   self.value > self.linked_to.value: return -1
    elif self.value < self.linked_to.value: return  1
    else: return 0
    
  def set_strum_dir_fx(self, fx):
    self.strum_dir_fx = fx
    
  def __eq__(self, other): return self is other
  def __ne__(self, other): return self is not other
  def __cmp__(self, other):
    if isinstance(other, int) or isinstance(other, float): return self.time - other
    return self.time - other.time
  __hash__ = object.__hash__
  
  def __repr__(self):
    s = u"<%s %s at %s" % (self.__class__.__name__, self.value, self.time)
    if hasattr(self, "string_id"): s = s + u" on string %s" % self.string_id
    s = s + u", duration %s, volume %s" % (self.duration, self.volume)
    if self.linked_to  : s = s + u" linked to note at %s"   % self.linked_to.time
    if self.linked_from: s = s + u" linked from note at %s" % self.linked_from.time
    return s + ">"
  
  def __xml__(self, xml, context, extra = u""):
    xml.write('\t\t\t<note pitch="%s" time="%s" duration="%s" volume="%s"' % (self.value, self.time / 96.0, self.duration / 96.0, self.volume))
    if self.linked_from:  xml.write(' id="%s"'         % context.id_for(self))
    if self.fx:
      xml.write(' fx="%s"' % self.fx)
      if self.fx == "bend": xml.write(' bend_pitch="%s"' % self.bend_pitch)
    if self.link_fx:
      xml.write(' link_fx="%s"' % self.link_fx)
      xml.write(' linked_to="%s"'  % context.id_for(self.linked_to))
    if self.duration_fx:
      xml.write(' duration_fx="%s"' % self.duration_fx)
    if self.strum_dir_fx:
      xml.write(' strum_dir_fx="%s"'  % self.strum_dir_fx)
      
    if hasattr(self, "string_id"): xml.write(' string="%s"' % self.string_id)
    for attr in NOTE_ATTRS:
      if not getattr(self, attr) is None: xml.write(' %s="%s"' % (attr, getattr(self, attr)))
    xml.write('%s/>\n' % extra)

NOTE_ATTRS = []
  
class Lyrics(TemporalData):
  def __init__(self, song, text = u"", header = u""):
    self.song   = song
    self.header = header
    self.text   = text
    self.show_all_lines_on_melody   = 0
    self.show_all_lines_after_score = 1
    
  def get_melody(self):
    index = self.song.partitions.index(self)
    while index >= 0:
      if isinstance(self.song.partitions[index], Partition) and self.song.partitions[index].view.ok_for_lyrics:
        return self.song.partitions[index]
      index = index - 1
    return None
  
  def end_time(self): return 0
  
  def __repr__(self):
    return u"""<Lyrics :
%s
>""" % self.text
      
  def __xml__(self, xml, context):
    if self.show_all_lines_on_melody:       extra  = u' show_all_lines_on_melody="1"'
    else:                                   extra  = u""
    if not self.show_all_lines_after_score: extra += u' show_all_lines_after_score="0"'
    xml.write(u"""\t<lyrics%s>
\t\t<header>%s</header>
""" % (extra, escape(self.header)))
    
    if hasattr(self, "view"): self.view.__xml__(xml, context)
    
    text = self.text.replace("\\\\", "<br/>")
    if text and (text[-1] == "\n"): text = text[:-1]
    text = text.replace("\n", "<br-verse/>")
    
    xml.write(u"""\t\t<text>
%s
\t\t</text>
\t</lyrics>
""" % text)
  
    
class Mesure(object):
  def __init__(self, song, time, tempo = 90, rythm1 = 4, rythm2 = 4, syncope = 0):
    self.song     = song
    self.time     = time
    self.tempo    = tempo
    self.rythm1   = rythm1
    self.rythm2   = rythm2
    self.syncope  = syncope
    self.compute_duration()
    
  def get_number(self):
    return bisect.bisect_left(self.song.mesures, self)
  
  def __unicode__(self):
    return _("Bar #%s") % (self.get_number() + 1)
    
  def compute_duration(self):
    #self.duration = 384 / self.rythm2 * self.rythm1
    self.duration = 384 // self.rythm2 * self.rythm1
    if not((self.rythm2 == 4) or ((self.rythm2 == 8) and (self.rythm1 % 3 == 0))):
      print "Warning: unsupported rythm: %s/%s" % (self.rythm1, self.rythm2)
      
  def end_time(self): return self.time + self.duration
  
  def set_rythm1(self, rythm1):
    self.rythm1 = rythm1
    if (self.rythm2 == 8) and (self.rythm1 % 3 != 0): self.rythm2 = 4
    self.duration = 384 / self.rythm2 * self.rythm1
    self.song.rythm_changed(self)
    
  def set_rythm2(self, rythm2):
    if rythm2 == 8:
      self.rythm2 = 8
      if self.rythm1 % 3 != 0: self.rythm1 = (self.rythm1 // 3 + 1) * 3
    else:
      self.rythm2 = 4
    self.duration = 384 / self.rythm2 * self.rythm1
    self.song.rythm_changed(self)
    
  def __repr__(self): return "<Mesure at %s, duration %s>" % (self.time, self.duration)
  
  def __xml__(self, xml, context):
    xml.write("""\t\t<bar rythm="%s/%s" tempo="%s" syncope="%s"/>\n""" % (self.rythm1, self.rythm2, self.tempo, int(self.syncope)))
    
  def __eq__(self, other): return self is other
  
  def __cmp__(self, other):
    if isinstance(other, Mesure): return cmp(self.time, other.time)
    return cmp(self.time, other)
  
  __hash__ = object.__hash__
  
  
class Playlist(object):
  def __init__(self, song):
    self.song             = song
    self.playlist_items   = []
    self.symbols          = {}
    
  def __unicode__(self): return _("playlist")
  def __str__    (self): return _("playlist")
  
  def __xml__(self, xml, context):
    for item in self.playlist_items:
      xml.write("""\t\t<play from="%s" to="%s"/>\n""" % (item.from_mesure, item.to_mesure))

  def append(self, *items):
    for item in items: self.playlist_items.append(item)
    self.analyse()
    
#  def insert(self, after, item):
#    self.playlist_items.insert(self.playlist_items.index(after) + 1, item)
#    self.analyse()
    
  def insert(self, index, item):
    self.playlist_items.insert(index, item)
    self.analyse()
    
  def remove(self, *items):
    for item in items: self.playlist_items.remove(item)
    self.analyse()
    
  def analyse(self):
    self.symbols.clear()
    symbols = self.symbols

    bornes = {}
    for item in self.playlist_items: bornes[item.from_mesure] = bornes[item.to_mesure + 1] = 1
    bornes = bornes.keys()
    bornes.sort()
    
    splitted_playlist = []
    for item in self.playlist_items:
      a = bisect.bisect_right(bornes, item.from_mesure)
      b = bisect.bisect_left (bornes, item.to_mesure + 1)
      if a == b: # No borne inside => OK
        splitted_playlist.append(SplittedPlaylistItem(self, item.from_mesure, item.to_mesure))
      else: # we need to split this one
        cur = item.from_mesure
        for borne in bornes[a : b + 1]:
          splitted_playlist.append(SplittedPlaylistItem(self, cur, borne))
          cur = borne
          
    alternatives = {} # map a start block to its list of alternatives.
    onces = []
    too_complex = 0
    
    next_new  = 0
    in_repeat = None
    prev = prev2 = None
    for item in splitted_playlist:
      if   item == prev:
        if not alternatives.has_key(item):
          alternatives[item] = []
          
      elif in_repeat:
        alts = alternatives[in_repeat]
        if (item.from_mesure == next_new) or (len(filter(lambda i: i == item, alts)) == len(alts)):
          alts.append(item)
          in_repeat = None
        else:
          too_complex = 1
          break
        
      elif item == prev2:
        in_repeat = item
        if not alternatives.has_key(item): alternatives[item] = [prev]
        
      elif item.from_mesure != next_new:
        too_complex = 1
        break
      
      if next_new < item.to_mesure + 1: next_new = item.to_mesure + 1
      
      prev2 = prev
      prev  = item
      
    def add_to(mesure_id, code):
      if mesure_id < len(self.song.mesures): mesure = self.song.mesures[mesure_id]
      else:                                  mesure = None # None means "at the end"
      if symbols.has_key(mesure): symbols[mesure].append(code)
      else:                       symbols[mesure] = [code]

      
    # Do NOT remove comment ("% ...") at the end of Lilypond code !
    # They are used by Songwrite drawing stuff.
    
    if too_complex: # Too complex...
      print "Warning: playlist is too complex!"
      for borne in bornes[ 1:]: add_to(borne, r"} % end repeat")
      for borne in bornes[:-1]: add_to(borne, r"\repeat volta 2 {")
      
    else:
      for start, alts in alternatives.iteritems():
        add_to(start.from_mesure, r"\repeat volta %s {" % (len(alts) or 2))
        if alts:
          add_to(start.to_mesure + 1, r"} % end repeat with alternatives")
          add_to(alts[0].from_mesure, r"\alternative {")
          
          for i in range(len(alts)):
            alt = alts[i]
            add_to(alt.from_mesure,   "{ % start alternative " + str(i + 1))
            if alt is alts[-1]: add_to(alt.to_mesure + 1, "} % end last alternative")
            else:               add_to(alt.to_mesure + 1, "} % end alternative")
            
          add_to(alts[-1].to_mesure + 1, r"} % end alternatives")
          
        else: # No alternatives
          add_to(start.to_mesure + 1, r"} % end repeat")
          
class PlaylistItem(object):
  def __init__(self, playlist, from_mesure, to_mesure):
    self.playlist    = playlist
    self.from_mesure = from_mesure
    self.to_mesure   = to_mesure
    
  def __unicode__(self): return _(u"__PlaylistItem__") % (self.from_mesure + 1, self.to_mesure + 1)
  def __repr__   (self): return "<%s from %s to %s>" % (self.__class__.__name__, self.from_mesure + 1, self.to_mesure + 1)
  
class SplittedPlaylistItem(PlaylistItem):
  def __eq__  (self, other): return isinstance(other, PlaylistItem) and (self.from_mesure == other.from_mesure) and (self.to_mesure == other.to_mesure)
  def __cmp__ (self, other): return cmp(self.from_mesure, other.from_mesure)
  def __hash__(self):        return hash(self.from_mesure) ^ hash(self.to_mesure)
  

