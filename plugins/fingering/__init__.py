# -*- coding: utf-8 -*-

# Songwrite 2
# Copyright (C) 2008 Jean-Baptiste LAMY -- jibalamy@free.fr
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
import songwrite2.model   as model
import songwrite2.plugins as plugins

class FingeringView(model.View):
  view_class         = u"fingering"
  default_instrument = 72
  
  def __init__(self, partition, name = u""):
    model.View.__init__(self, partition, name)
    if not hasattr(partition, "print_with_staff_too"): partition.print_with_staff_too = 0
    
  def get_drawer(self, canvas):
    from songwrite2.plugins.fingering.drawer import FingeringDrawer, SingleString
    return FingeringDrawer(canvas, self.partition, SingleString)

  def get_type(self):
    return self.__class__
  
  def note_2_fingering(self, note):
    v = abs(note.value)
    if getattr(self.partition, "g8", 0): v += 12
    return self.fingerings.get(v)
  

class TinWhistleView(FingeringView):
  default_instrument = 72
  fingerings = {
    #note : (hole1, hole2, hole3, hole4, hole5, hole6,   breath),
    62 : (1  , 1  , 1  , None, 1  , 1  , 1  ,     u""),
    63 : (1  , 1  , 1  , None, 1  , 1  , 0.5,     u""),
    64 : (1  , 1  , 1  , None, 1  , 1  , 0  ,     u""),
    65 : (1  , 1  , 1  , None, 1  , 0.5, 0  ,     u""),
    66 : (1  , 1  , 1  , None, 1  , 0  , 0  ,     u""),
    67 : (1  , 1  , 1  , None, 0  , 0  , 0  ,     u""),
    68 : (1  , 1  , 0.5, None, 0  , 0  , 0  ,     u""),
    69 : (1  , 1  , 0  , None, 0  , 0  , 0  ,     u""),
    70 : (1  , 0.5, 0  , None, 0  , 0  , 0  ,     u""),
    71 : (1  , 0  , 0  , None, 0  , 0  , 0  ,     u""),
    72 : (0  , 1  , 1  , None, 1  , 0  , 1  ,     u""),
    73 : (0  , 0  , 0  , None, 0  , 0  , 0  ,     u""),
    
    74 : (0  , 1  , 1  , None, 1  , 1  , 1  ,     u"+"),
    75 : (1  , 1  , 1  , None, 1  , 1  , 0.5,     u"+"),
    76 : (1  , 1  , 1  , None, 1  , 1  , 0  ,     u"+"),
    77 : (1  , 1  , 1  , None, 1  , 0.5, 0  ,     u"+"),
    78 : (1  , 1  , 1  , None, 1  , 0  , 0  ,     u"+"),
    79 : (1  , 1  , 1  , None, 0  , 0  , 0  ,     u"+"),
    80 : (1  , 1  , 0.5, None, 0  , 0  , 0  ,     u"+"),
    81 : (1  , 1  , 0  , None, 0  , 0  , 0  ,     u"+"),
    82 : (1  , 0.5, 0  , None, 0  , 0  , 0  ,     u"+"),
    83 : (1  , 0  , 0  , None, 0  , 0  , 0  ,     u"+"),
    85 : (0  , 0  , 0  , None, 0  , 0  , 0  ,     u"+"),
    }
  
  def __init__(self, partition, name = u""):
    if not hasattr(partition, "instrument_tonality"):
      partition.instrument_tonality = u"D"
      if not partition.notes: partition.tonality = u"D"
    FingeringView.__init__(self, partition, name or _(u"Tin whistle"))
    
  def get_icon_filename(self): return "flute_irlandaise.png"
  
  def note_2_fingering(self, note):
    v = abs(note.value)
    if getattr(self.partition, "g8", 0): v += 12
    return self.fingerings.get(v - model.OFFSETS[self.partition.instrument_tonality] + 2)
  
  def get_bell_note(self):
    bell_note = 62 + model.OFFSETS[self.partition.instrument_tonality] - 2
    if self.partition.g8: bell_note -= 12
    return bell_note
  
  def get_drawer(self, canvas):
    from songwrite2.plugins.fingering.drawer import FingeringDrawer, TinWhistleSingleString
    return FingeringDrawer(canvas, self.partition, TinWhistleSingleString)
  
  def __xml__(self, xml = None, context = None):
    xml.write(u'''\t\t<view type="tin_whistle"/>\n''')
    
    
class RecorderView(FingeringView):
  default_instrument = 73
  fingerings = {
    #note : (hole1, hole2, hole3, hole4, hole5, hole6,   breath),
    60 : (1  , None, 1  , 1  , 1  , None, 1  , 1  , (1, 1), (1, 1),    u""),
    61 : (1  , None, 1  , 1  , 1  , None, 1  , 1  , (1, 1), (1, 0),    u""),
    62 : (1  , None, 1  , 1  , 1  , None, 1  , 1  , (1, 1), (0, 0),    u""),
    63 : (1  , None, 1  , 1  , 1  , None, 1  , 1  , (1, 0), (0, 0),    u""),
    64 : (1  , None, 1  , 1  , 1  , None, 1  , 1  , (0, 0), (0, 0),    u""),
    65 : (1  , None, 1  , 1  , 1  , None, 1  , 0  , (1, 1), (1, 1),    u""),
    66 : (1  , None, 1  , 1  , 1  , None, 0  , 1  , (1, 1), (0, 0),    u""),
    67 : (1  , None, 1  , 1  , 1  , None, 0  , 0  , (0, 0), (0, 0),    u""),
    68 : (1  , None, 1  , 1  , 0  , None, 1  , 1  , (0, 0), (0, 0),    u""),
    69 : (1  , None, 1  , 1  , 0  , None, 0  , 0  , (0, 0), (0, 0),    u""),
    70 : (1  , None, 1  , 0  , 1  , None, 1  , 0  , (0, 0), (0, 0),    u""),
    71 : (1  , None, 1  , 0  , 0  , None, 0  , 0  , (0, 0), (0, 0),    u""),
    
    72 : (1  , None, 0  , 1  , 0  , None, 0  , 0  , (0, 0), (0, 0),    u""),
    73 : (0  , None, 1  , 1  , 0  , None, 0  , 0  , (0, 0), (0, 0),    u""),
    74 : (0  , None, 0  , 1  , 0  , None, 0  , 0  , (0, 0), (0, 0),    u""),
    75 : (0  , None, 1  , 1  , 1  , None, 1  , 1  , (1, 1), (1, 1),    u""),
    76 : (0.5, None, 1  , 1  , 1  , None, 1  , 1  , (0, 0), (0, 0),    u""),
    77 : (0.5, None, 1  , 1  , 1  , None, 1  , 0  , (1, 1), (0, 0),    u""),
    78 : (0.5, None, 1  , 1  , 1  , None, 0  , 1  , (0, 0), (0, 0),    u""),
    79 : (0.5, None, 1  , 1  , 1  , None, 0  , 0  , (0, 0), (0, 0),    u""),
    80 : (0.5, None, 1  , 1  , 0  , None, 1  , 0  , (0, 0), (0, 0),    u""),
    81 : (0.5, None, 1  , 1  , 0  , None, 0  , 0  , (0, 0), (0, 0),    u""),
    82 : (0.5, None, 1  , 1  , 0  , None, 1  , 1  , (1, 1), (0, 0),    u""),
    83 : (0.5, None, 1  , 1  , 0  , None, 1  , 1  , (0, 0), (0, 0),    u""),
    
    84 : (0.5, None, 1  , 0  , 0  , None, 1  , 1  , (0, 0), (0, 0),    u""),
    85 : (0.5, None, 1  , 0  , 1  , None, 1  , 0  , (0, 0), (0, 0),    u""),
    86 : (0.5, None, 1  , 0  , 1  , None, 1  , 0  , (1, 1), (0, 0),    u""),
    87 : (0.5, None, 0  , 1  , 1  , None, 0  , 1  , (1, 1), (0, 0),    u""),
    }
  
  def __init__(self, partition, name = u""):
    FingeringView.__init__(self, partition, name or _(u"Recorder"))
    
  def get_icon_filename(self): return "flute.png"
  
  def get_bell_note(self):
    bell_note = 60
    if self.partition.g8: bell_note -= 12
    return bell_note
  
  
  def __xml__(self, xml = None, context = None):
    xml.write(u'''\t\t<view type="recorder"/>''')
    
  
model.VIEW_CATEGORIES.append(u"fingering")
plugins.ViewPlugin(TinWhistleView, None, "tin_whistle", "fingering")
plugins.ViewPlugin(RecorderView  , None, "recorder"   , "fingering")

#descr = introsp.description(model.Partition)
#descr.set_field_for_attr("instrument_tonality"  , field.EnumField(dict([(_("tonality_%s" % tonality), tonality) for tonality in model.TONALITIES.keys()])))


