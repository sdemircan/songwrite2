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
import songwrite2.model   as model
import songwrite2.plugins as plugins

#model.Note.accompaniment = None
model.Note.button_rank   = None
model.Note.bellows_dir   = None # -1 Push, 1 draw
model.NOTE_ATTRS.append("button_rank")
model.NOTE_ATTRS.append("bellows_dir")

accordion_tonalities = {
  -5 : _(u"C/F"),
   0 : _(u"G/C"),
   2 : _(u"A/D"),
  }

class AccordionView(model.View):
  view_class               = u"accordion"
  default_instrument       = 21
  link_type                = model.LINK_NOTES_DEFAULT
  can_paste_note_by_string = 1
  automatic_string_id      = 1
  def __init__(self, partition, name = u""):
    model.View.__init__(self, partition, name or _(u"Accordion"))
    if partition:
      if not hasattr(partition, "print_with_staff_too"): partition.print_with_staff_too = 0
      if not hasattr(partition, "accordion_tonalities"): partition.accordion_tonalities = 0
    self.strings = [
      AccordionLeftHandString (self, -1, { u"1" : 51, u"2" : 50, u"3" : 55, u"4" : 59, u"5" : 62, u"6" : 67, u"7" : 71, u"8" : 74, u"9" : 79, u"10" : 83, u"11" : 86,
                                           u"1'": 56, u"2'": 55, u"3'": 60, u"4'": 64, u"5'": 67, u"6'": 72, u"7'": 76, u"8'": 79, u"9'": 84, u"10'": 88 }), # Poussé
      AccordionLeftHandString (self,  1, { u"1" : 49, u"2" : 54, u"3" : 57, u"4" : 60, u"5" : 64, u"6" : 66, u"7" : 69, u"8" : 72, u"9" : 76, u"10" : 78, u"11" : 81,
                                           u"1'": 48, u"2'": 59, u"3'": 62, u"4'": 65, u"5'": 69, u"6'": 71, u"7'": 74, u"8'": 77, u"9'": 81, u"10'": 83}), # Tiré
#      AccordionRightHandString(), # Accords / basses
      ]
    
#  def note_is_accompaniment(self, note):
#    if note.accompaniment is None: note.accompaniment = 0
#    return note.accompaniment
  
  def note_string_id(self, note):
#    accompaniment = self.note_is_accompaniment(note)
#    if accompaniment:            return 2
    if   note.bellows_dir == -1: return 0
    elif note.bellows_dir ==  1: return 1
    return 1
  
  def get_drawer(self, canvas):
    from songwrite2.plugins.accordion.drawer import AccordionDrawer
    return AccordionDrawer(canvas, self.partition)
  
  def get_icon_filename(self): return "accordion.png"
  
  def __xml__(self, xml = None, context = None):
    xml.write(u'''\t\t<view type="accordion">\n''')
    xml.write(u"""\t\t</view>\n""")
    

class AccordionLeftHandString(object):
  def __init__(self, view, bellows_dir, button2value):
    self.view          = view
    self.bellows_dir   = bellows_dir
    self.button2value  = button2value
    self.value2buttons = {}
    # First pass for button rank 0, then second pass for button rank 1
    for button, value in button2value.iteritems():
      if not u"'" in button:
        if self.value2buttons.has_key(value): self.value2buttons[value].append(button)
        else:                                 self.value2buttons[value] = [button]
    for button, value in button2value.iteritems():
      if u"'" in button:
        if self.value2buttons.has_key(value): self.value2buttons[value].append(button)
        else:                                 self.value2buttons[value] = [button]
    self.base_note = self.button2value[u"3"]
    
  def text_2_value(self, note, text):
    value = self.button2value.get(text)
    if value is None:
      if len(text) > 1:
        value = self.button2value.get(text[-1])
      if value is None: 
        value = self.button2value[u"3"]
    note.button_rank = text.count("'")
    note.bellows_dir = self.bellows_dir
    return value
  def value_2_text(self, note, change_string = 1):
    buttons = self.value2buttons.get(note.value)
    if buttons is None:
      if change_string:
        for string in self.view.strings:
          if string is self: continue
          text = string.value_2_text(note, change_string = 0)
          if text:
            note.bellows_dir = string.bellows_dir
            return text
      return u"?"
    if len(buttons) == 1: return buttons[0]
    button_rank = note.button_rank
    if button_rank is None:
      if (note.partition.tonality == u"G") or (note.partition.tonality == u"D"): button_rank = 0
      else:                                                                      button_rank = 1
    return buttons[button_rank]
  
  def width(self):
    return 7


  
plugins.ViewPlugin(AccordionView,      None, "accordion"      , "tab")
