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

import editobj2
import songwrite2.model   as model
import songwrite2.globdef as globdef

if editobj2.GUI == "Gtk":
  import songwrite2.canvas     as canvas
else:
  import qt
  import songwrite2.canvas_qt  as canvas


class LyreDrawer(canvas.TablatureDrawer):
  def __init__(self, canvas_, partition):
    canvas.TablatureDrawer.__init__(self, canvas_, partition)
    self.note_offset_x = 10.0 * self.scale
    self.note_offset_y = -1.0 * self.scale #-self.string_height // 22.0
    self.string_height = int(0.8 * canvas_.default_line_height + 2)
    
  def mouse_motion_note(self, value, delta): return value + delta
  
  def note_listener(self, note, type, new, old):
    if type is object:
      if   (new.get("fx", u"") == u"harmonic") and (old.get("fx", u"") != u"harmonic"):
        string_value = self.strings[self.note_string_id(note)].base_note
        if string_value == note.value:
          note.value = string_value + 12
      elif (new.get("fx", u"") != u"harmonic") and (old.get("fx", u"") == u"harmonic"):
        string_value = self.strings[self.note_string_id(note)].base_note
        if string_value != note.value:
          note.value = string_value
      elif new["value"] != old["value"]:
        string_value = self.strings[self.note_string_id(note)].base_note
        if   (note.value == string_value + 12) and (note.fx == u""):
          note.set_fx(u"harmonic")
        elif (note.value == string_value     ) and (note.fx == u"harmonic"):
          note.set_fx(u"")
          
    canvas.TablatureDrawer.note_listener(self, note, type, new, old)

  def create_cursor(self, time, duration, string_id, value):
    return canvas.PartitionDrawer.create_cursor(self, time, duration, string_id, value)
    
  def note_text(self, note):
    if note.fx == u"dead":
      return " "
    if note.fx == u"harmonic":
      if note is self.canvas.cursor: return "_⋄"
      return u"●⋄" #u"●♢"
    if note is self.canvas.cursor: return "_"
    s = self.strings[self.note_string_id(note)].value_2_text(note)
    if s == u"0": return u"●"
    return s
    
  def note_width(self, note):
    return 0.97 * self.string_height
  
  def on_touchscreen_new_note(self, event):
    return canvas.PartitionDrawer.on_touchscreen_new_note(self, event)
  
  def note_value_possible(self, note, value):
    for i, string in enumerate(self.strings): # Search a string with the right tone
      if ((string.base_note % 12) == (value % 12)): return 1
    return 0
  
  def note_string_id(self, note):
    return self.partition.view.note_string_id(note)
  
  draw_note = canvas.PartitionDrawer.draw_note # No white rectangle below notes
  
  def draw_stem_and_beam_for_chord(self, ctx, notes, notes_y, previous, next, appo = 0):
    if not appo:
      canvas.TablatureDrawer.draw_stem_and_beam_for_chord(self, ctx, notes, notes_y, previous, next, 0)
  #def draw_stem_and_beam(self, ctx, x, note, y1, y2, mesure = None, previous = None, next = None):
  #  canvas.TablatureDrawer.draw_stem_and_beam(self, ctx, x, note, y1, y2, mesure, previous, next)
      
  def draw_note_fx_link(self, ctx, note, string_id): # No "p" / "h" for pull / hammer
    canvas.PartitionDrawer.draw_note_fx_link(self, ctx, note, string_id)
    
  if editobj2.GUI == "Gtk":
    def draw(self, ctx, x, y, width, height, drag = 0):
      canvas.TablatureDrawer.draw(self, ctx, x, y, width, height, drag)
      if not drag:
        ctx.set_source_rgb(0.4, 0.4, 0.4)
        ctx.set_font_size(self.canvas.default_font_size * 0.8)
        for i in range(len(self.strings)):
          label = model.note_label(self.strings[i].base_note, 0, self.partition.tonality)
          x_bearing, y_bearing, width, height, x_advance, y_advance = ctx.text_extents(label)
          ctx.move_to(self.canvas.start_x - width - self.canvas.char_h_size // 2, self.string_id_2_y(i) + height // 3)
          ctx.show_text(label)
          
        ctx.set_source_rgb(0.0, 0.0, 0.0)
        ctx.set_font_size(self.canvas.default_font_size)
        
  else: # Qt
    def draw(self, ctx, x, y, width, height, drag = 0):
      canvas.TablatureDrawer.draw(self, ctx, x, y, width, height, drag)
      if not drag:
        ctx.setFont(self.canvas.small_font)
        ctx.setPen (self.canvas.string_type_2_pen[5])
        for i in range(len(self.strings)):
          label = model.note_label(self.strings[i].base_note, 0, self.partition.tonality)
          ctx.drawText(self.canvas.start_x - 3 * self.canvas.char_h_size, self.string_id_2_y(i), label)

        ctx.setFont(self.canvas.default_font)
        ctx.setPen (self.canvas.default_pen)
        
    
