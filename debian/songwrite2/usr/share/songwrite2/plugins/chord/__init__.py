# -*- coding: utf-8 -*-

# Songwrite 2
# Copyright (C) 2011 Jean-Baptiste LAMY -- jibalamy@free.fr
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

import editobj2, editobj2.introsp as introsp, editobj2.field as field
from editobj2.undoredo import *
import songwrite2.model   as model
import songwrite2.plugins as plugins
from songwrite2.model import TablatureView, GuitarView, GuitarDADGADView, BassView, TablatureString

class ChordView(model.View):
  view_class               = u"chord"
  saved_chords             = None
  can_paste_note_by_string = 0
  ok_for_lyrics            = 0
  
  def __init__(self, partition, name = u""):
    super(ChordView, self).__init__(partition, name)
    
  def _wrap_view_type(self, view_type):
    class MyView(view_type):
      saved_chords = None
    MyView.__name__ = view_type.__name__
    self._last_returned_view_type = MyView
    return MyView
    
  def get_type(self): return self._wrap_view_type(super(ChordView, self).get_type())
  
  def change_to_view_type(self, view_type):
    if issubclass(view_type, ChordView) and (not self.__class__ is view_type):
      from songwrite2.plugins.chord.drawer import set_chord
      new_view = view_type(self.partition)
      
      if view_type.saved_chords: # Restore previous chord (UNDO / REDO)
        view_type.saved_chords[0]()
        
      else: # Convert chord from one chord manager to another
        old_chord_manager = self     .get_Drawer().ChordManager(self.partition)
        new_chord_manager = view_type.get_Drawer().ChordManager(self.partition)
        times    = {}
        do_its   = []
        undo_its = []
        for note in self.partition.notes: times[note.time] = 1
        for time in times:
          notes      = self.partition.notes_at(time)
          rel_values = frozenset([note.value for note in notes])
          chord      = old_chord_manager.identify(rel_values)
          v = [value or 0 for value in chord.identified_notes]
          #new_chord_manager.create(chord.base, v[1], v[2], v[3], v[4], v[5], v[6])
          self.partition.view = new_view # HACK : new_chord_manager may use the partition's view, e.g. for strings attribute !
          do_it1, undo_it1 = set_chord(None, self.partition, new_chord_manager, [time], chord.base, v[1], v[2], v[3], v[4], v[5], v[6])
          self.partition.view = self # HACK : restore view
          do_its  .append(  do_it1)
          undo_its.append(undo_it1)
        previous_instrument = self.partition.instrument
        def do_it():
          self.partition.instrument = view_type.default_instrument
          for func in do_its: func()
        def undo_it():
          self.partition.instrument = previous_instrument
          for func in undo_its: func()
        do_it()
        self._last_returned_view_type.saved_chords = [undo_it]
      return new_view
    
  def get_drawer(self, canvas): return self.get_Drawer()(canvas, self.partition)
  
  def note_string_id(self, note): return 0
    
  
  
class TablatureChordView(ChordView, TablatureView):
  link_type = model.LINK_NOTES_DEFAULT
  @classmethod
  def get_Drawer(Class):
    from songwrite2.plugins.chord.drawer import TablatureChordDrawer
    return TablatureChordDrawer
    
  def __xml__(self, xml = None, context = None, type = "tablature_chord"):
    TablatureView.__xml__(self, xml, context, type)
    
class GuitarChordView(TablatureChordView, GuitarView):
  link_type = model.LINK_NOTES_DEFAULT
  default_instrument = 24
  def __init__(self, partition, name = u""):
    super(GuitarChordView, self).__init__(partition, name)

from songwrite2.plugins.lyre import *
class LyreChordView(TablatureChordView):
  link_type = model.LINK_NOTES_DEFAULT
  default_instrument = 46
  @classmethod
  def get_Drawer(Class):
    from songwrite2.plugins.chord.drawer import LyreChordDrawer
    return LyreChordDrawer
    
  def __xml__(self, xml = None, context = None, type = "lyre_chord"):
    TablatureView.__xml__(self, xml, context, type)
    
  def get_type(self):
    if   len(self.strings) == 6: return self._wrap_view_type(model.TablatureView.get_type(self, SixStringLyreChordView))
    else:                        return self._wrap_view_type(model.TablatureView.get_type(self, SevenStringLyreChordView))
    

class SixStringLyreChordView(LyreChordView, SixStringLyreView):
  link_type = model.LINK_NOTES_DEFAULT
  def __init__(self, partition, name = u""):
    super(SixStringLyreChordView, self).__init__(partition, name)

class SevenStringLyreChordView(LyreChordView, SevenStringLyreView):
  link_type = model.LINK_NOTES_DEFAULT
  def __init__(self, partition, name = u""):
    super(SevenStringLyreChordView, self).__init__(partition, name)


class PianoChordView(ChordView):
  default_instrument = 0
  def __init__(self, partition, name = u""):
    super(PianoChordView, self).__init__(partition, name or _(u"Piano"))
    
  @classmethod
  def get_Drawer(Class):
    from songwrite2.plugins.chord.drawer import PianoChordDrawer
    return PianoChordDrawer
    
  def __xml__(self, xml = None, context = None):
    xml.write(u'''\t\t<view type="piano_chord"''')
    xml.write(u">\n")
    xml.write(u"""\t\t</view>\n""")
  

class AccordionChordView(ChordView):
  default_instrument = 21
  def __init__(self, partition, name = u""):
    super(AccordionChordView, self).__init__(partition, name or _(u"Accordion"))
    
  @classmethod
  def get_Drawer(Class):
    from songwrite2.plugins.chord.drawer import AccordionChordDrawer
    return AccordionChordDrawer
    
  def __xml__(self, xml = None, context = None):
    xml.write(u'''\t\t<view type="accordion_chord"''')
    xml.write(u">\n")
    xml.write(u"""\t\t</view>\n""")

model.VIEW_CATEGORIES.append(u"chords")
plugins.ViewPlugin(TablatureChordView      , TablatureString, "tablature_chord"        , None)
plugins.ViewPlugin(LyreChordView           , TablatureString, "lyre_chord"             , None)
plugins.ViewPlugin(GuitarChordView         , TablatureString, "guitar_chord"           , "chords")
plugins.ViewPlugin(SixStringLyreChordView  , TablatureString, "six_string_lyre_chord"  , "chords")
plugins.ViewPlugin(SevenStringLyreChordView, TablatureString, "seven_string_lyre_chord", "chords")
plugins.ViewPlugin(PianoChordView          , TablatureString, "piano_chord"            , "chords")
plugins.ViewPlugin(AccordionChordView      , TablatureString, "accordion_chord"        , "chords")

#descr = introsp.description(model.Partition)
#descr.set_field_for_attr("instrument_tonality"  , field.EnumField(dict([(_("tonality_%s" % tonality), tonality) for tonality in model.TONALITIES.keys()])))


