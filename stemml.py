# -*- coding: utf-8 -*-

# SongWrite
# Copyright (C) 2001-2004 Jean-Baptiste LAMY -- jibalamy@free.fr
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

# This is the parser/reader for StemML.

import sys, xml.sax as sax, xml.sax.handler as handler
from cStringIO import StringIO
import codecs

import songwrite2.model   as model
import songwrite2.plugins as plugins

def parse(file):
  if isinstance(file, unicode): file = file.encode(sys.getfilesystemencoding())
  
  parser = sax.make_parser()
  song_handler = SongHandler(parser, file)
  parser.setContentHandler(song_handler)
  parser.parse(file)
  
  if   hasattr(song_handler, "songbook"): return song_handler.songbook
  elif hasattr(song_handler, "notes"   ): return song_handler.click_x, song_handler.notes
  else:                                   return song_handler.song
  
  
class SongHandler(handler.ContentHandler):
  def __init__(self, parser, file):
    self.parser = parser
    self.current    = ""
    self.need_strip = 0
    self.file = file
    
  def startElement(self, name, attrs):
    if   name == "bar":
      self.bar_attrs.update(attrs)
      rythm = self.bar_attrs["rythm"]
      i = rythm.index("/")
      if self.song.mesures:
        self.song.mesures.append(model.Mesure(self.song, self.song.mesures[-1].end_time(), int(self.bar_attrs["tempo"]), int(rythm[:i]), int(rythm[i + 1:]), int(self.bar_attrs["syncope"])))
      else:
        self.song.mesures.append(model.Mesure(self.song, 0,                                int(self.bar_attrs["tempo"]), int(rythm[:i]), int(rythm[i + 1:]), int(self.bar_attrs["syncope"])))
        
    elif name == "play":
      self.song.playlist.playlist_items.append(model.PlaylistItem(self.song.playlist, int(attrs["from"]), int(attrs["to"])))
      
    elif name == "partition":
      partition_handler = PartitionHandler(self.parser, self, self.song, attrs)
      self.parser.setContentHandler(partition_handler)
      
    elif name == "lyrics":
      lyrics_handler = LyricsHandler(self.parser, self, self.song, attrs)
      self.parser.setContentHandler(lyrics_handler)
      
    elif name == "bars": pass
    elif name == "playlist": pass
    elif name == "song":
      self.bar_attrs = {"tempo" : 60, "syncope" : 0 , "rythm" : "4/4"}
      self.song = self.obj = model.Song()
      self.song.mesures      *= 0
      self.song.version       = attrs.get("version", model.VERSION)
      self.song.lang          = attrs.get("lang", "en")[:2]
      #self.song.printzoom     = int(attrs.get("printzoom", None) or attrs.get("printsize", 20))
      self.song.print_nb_mesures_per_line = int(attrs.get("print_nb_mesures_per_line", 4))
      self.song.printfontsize = int(attrs.get("printfontsize", 16))
      self.song.set_filename(self.file)
    elif name == "songfile":
      self.songbook.add_song_ref(model.SongRef(self.songbook, attrs.get("filename"), attrs.get("title")))
    elif name == "songbook":
      self.songbook = self.obj = model.Songbook(self.file, attrs.get("title", u""), attrs.get("authors", u""), attrs.get("comments", u""))
      self.songbook.version = attrs.get("version", model.VERSION)
    elif name == "notes":
      partition_handler = PartitionHandler(self.parser, self, None, attrs)
      self.parser.setContentHandler(partition_handler)
      self.click_x = partition_handler.partition.click_x
      self.notes   = partition_handler.partition.notes
    else: self.current = name
    
  def endElement(self, name):
    if   name == "song":
      self.song.playlist.analyse()
      
    if self.need_strip:
      setattr(self.obj, self.current, getattr(self.obj, self.current).strip())
      self.need_strip = 0
    self.current = ""
    
  def characters(self, content):
    if   self.current == "": pass
    else:
      setattr(self.obj, self.current, getattr(self.obj, self.current, u"") + content)
      self.need_strip = 1 # Will strip when the tag ends.


class PartitionHandler(handler.ContentHandler):
  def __init__(self, parser, previous_handler, song, attrs):
    self.parser               = parser
    self.previous_handler     = previous_handler
    self.partition            = model.Partition(song)
    for attr, value in attrs.items():
      try: value = int(value)
      except:
        try: value = float(value)
        except:
          if   value == "True" : value = 1
          elif value == "False": value = 0
      setattr(self.partition, attr, value)
    if song: song.partitions.append(self.partition)
    self.current     = ""
    self.id_to_notes = {}
    self.note_setter = {
      "time"        : None,
      "duration"    : None,
      "pitch"       : None,
      "volume"      : None,
      "linked_to"   : self.note_set_linked_to,
      "fx"          : self.note_set_fx,
      "link_fx"     : self.note_set_link_fx,
      "duration_fx" : self.note_set_duration_fx,
      "strum_dir_fx": self.note_set_strum_dir_fx,
      "appoggiatura": self.note_set_appoggiatura,
      "id"          : self.note_set_id,
      "string"      : self.note_set_string,
      "bend_pitch"  : self.note_set_bend_pitch,
      "label"       : self.note_set_label,
      }
    self.notes_linked_to = []
    self.view_hidden     = 0
    self.need_strip      = 0
    
  def note_set_id(self, note, id): self.id_to_notes[id] = note
  
  def note_set_linked_to(self, note, id):
    # Cannot be done yet, since the following notes are not parsed yet !
    # We put this request somewhere and treat it later.
    self.notes_linked_to.append((note, id))
    
  def note_set_fx(self, note, fx):
    if (fx == u"link") or (fx == u"slide") or (fx == u"hammer") or (fx == u"pull"):
      self.note_set_link_fx(note, fx)
    else:
      note.fx = fx
      
  def note_set_link_fx(self, note, fx):
    if (fx == u"hammer") or (fx == u"pull"): fx = u"link"
    note.link_fx = fx
    
  def note_set_duration_fx(self, note, fx):
    note.duration_fx = fx
    
  def note_set_appoggiatura(self, note, appoggiatura):
    if appoggiatura: note.duration_fx = u"appoggiatura"
    
  def note_set_string(self, note, string_id):
    note.string_id = int(string_id)
    
  def note_set_label(self, note, label):
    note.label = label
    
  def note_set_bend_pitch(self, note, bend_pitch):
    note.bend_pitch = float(bend_pitch)
    
  def note_set_strum_dir_fx(self, note, fx):
    note.strum_dir_fx = fx
    
  def startElement(self, name, attrs):
    if   name == "note":
      note = model.Note(self.partition,
                        int(round(float(attrs["time"    ]) * 96.0)),
                        int(round(float(attrs["duration"]) * 96.0)),
                        int(attrs["pitch"]),
                        int(attrs.get("volume") or self.partition.notes[-1].volume),
                        )
      for attr in attrs.keys():
        setter = self.note_setter.get(attr, 1)
        if   setter is 1:
          value = attrs[attr]
          try: value = int(value)
          except:
            try: value = float(value)
            except:
              if   value == "True" : value = 1
              elif value == "False": value = 0
          setattr(note, attr, value)
        elif setter: setter(note, attrs[attr])
        
      self.partition.notes.append(note)
      
    elif name == "notes"  : pass
    elif name == "strings": pass
    elif name == "string" :
      if attrs.get("type"):
        self.partition.view.strings.append(getattr(model, attrs.get("type"))(int(attrs.get("pitch") or attrs.get("patch"))))
      else:
        self.partition.view.strings.append(self._string_class(int(attrs.get("pitch") or attrs.get("patch"))))
        
    elif name == "view":
      if   attrs["type"] == "tablature":
        self.partition.view = model.TablatureView(self.partition, "", [])
        self._string_class = model.TablatureString
        
      elif attrs["type"] == "drums":
        self.partition.view = model.DrumsView(self.partition, "", [])
        self._string_class = model.DrumString
        
      elif attrs["type"] == "staff":
        if attrs.get("g8"): self.partition.g8 = 1
        self.partition.view = model.StaffView(self.partition, "")
        self._string_class = None
        
      else:
        self.partition.view, self._string_class = plugins.load_view(self.partition, attrs)
        
      if attrs.get("hidden"): self.partition.view.visible = 0
      
    else: self.current = name
    
  def endElement(self, name):
    if   (name == "partition") or (name == "notes"):
      for note, id in self.notes_linked_to:
        other = self.id_to_notes.get(id, None)
        note .linked_to = other
        if other: other.linked_from = note
        
      self.parser.setContentHandler(self.previous_handler)
        
    elif name == self.current:
      if self.need_strip:
        setattr(self.partition, self.current, getattr(self.partition, self.current).strip())
        self.need_strip = 0
      self.current = ""
      
  def characters(self, content):
    if   self.current == ""    : pass
    else:
      setattr(self.partition, self.current, getattr(self.partition, self.current, u"") + content)
      self.need_strip = 1 # Will strip when the tag ends.
      
class LyricsHandler(handler.ContentHandler):
  def __init__(self, parser, previous_handler, song, attrs):
    self.parser           = parser
    self.previous_handler = previous_handler
    self.lyrics           = model.Lyrics(song)
    #if attrs.get("show_all_lines_on_melody"  ): self.lyrics.show_all_lines_on_melody   = 1
    #if attrs.get("show_all_lines_after_score"): self.lyrics.show_all_lines_after_score = 1
    self.lyrics.show_all_lines_on_melody   = int(attrs.get("show_all_lines_on_melody"  , 0))
    self.lyrics.show_all_lines_after_score = int(attrs.get("show_all_lines_after_score", 1))
    song.partitions.append(self.lyrics)
    self.texts      = []
    self.current    = ""
    self.need_strip = 0
    
  def startElement(self, name, attrs):
    if   name == "br":       self.texts.append("\\\\")
    elif name == "br-verse": self.texts.append("\n")
    else: self.current = name
    
  def endElement(self, name):
    if   name == "lyrics":
      self.lyrics.text = "".join(self.texts).rstrip()
      self.parser.setContentHandler(self.previous_handler)
      
    elif name == self.current:
      if self.need_strip:
        setattr(self.lyrics, self.current, getattr(self.lyrics, self.current).strip())
        self.need_strip = 0
      self.current = ""
      
  def characters(self, content):
    if   self.current == ""    : pass
    elif self.current == "text":
      self.texts.append(content.replace("\n", ""))
    else:
      setattr(self.lyrics, self.current, getattr(self.lyrics, self.current, u"") + content)
      self.need_strip = 1 # Will strip when the tag ends.


