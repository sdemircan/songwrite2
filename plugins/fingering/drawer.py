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

if editobj2.GUI == "Gtk":
  import songwrite2.canvas     as canvas
else:
  import qt
  import songwrite2.canvas_qt  as canvas


class FingeringDrawer(canvas.PartitionDrawer):
  def __init__(self, canvas_, partition, String):
    canvas.PartitionDrawer.__init__(self, canvas_, partition)
    self.height = 300
    self.strings = [String(self)]
    self.string_height = self.canvas.default_line_height * 0.3
    for hole in partition.view.fingerings.values()[0]:
      if hole is None: self.string_height += self.canvas.default_line_height * 0.3
      else:            self.string_height += self.canvas.default_line_height * 0.6
    self.stem_extra_height = self.canvas.default_line_height
    
    self.lh2  = self.canvas.default_line_height / 2
    self.lh3  = self.canvas.default_line_height / 3
    self.lh4  = self.canvas.default_line_height / 4.5
    self.lh7  = self.canvas.default_line_height / 7
    self.lh_6 = self.canvas.default_line_height * 0.6

  def partition_listener(self, partition, type, new, old):
    if type is object:
      if (new.get("instrument_tonality") != old.get("instrument_tonality")):
        self.canvas.render_all()
        
  def note_width(self, note):
    return 9.0 * self.scale
  
  # No "string" notion in fingering notation!
  def note_string_id(self, note): return 0
  #def default_string_id(self, value): return 0
  def y_2_string_id(self, y, force = 0):
    if force:
      if   self.y + self.start_y > y: return -1
      elif y > self.y + self.height:  return  1
      return 0
    else:
      if self.y + self.start_y <= y <= self.y + self.height: return 0
      return None
  def string_id_2_y(self, string_id = 0):
    return self.y + self.start_y + self.stem_extra_height + self.string_height // 2
  def draw_mesure(self, ctx, time, mesure, y, height):
    canvas.PartitionDrawer.draw_mesure(self, ctx, time, mesure, self.y + self.start_y + self.stem_extra_height, self.string_height)
  def draw_strings(self, ctx, x, y, width, height):
    self.height = int(self.start_y + self.stem_extra_height + self.string_height + self.stem_extra_height_bottom + 1)
    
  def note_text(self, note): return u"_"
  
  def note_dimensions(self, note):
    x = self.canvas.time_2_x(note.time)
    y = self.string_id_2_y()
    return (
      x + 3.0 * self.scale,
      y - self.string_height // 2,
      x + max(note.duration * self.canvas.zoom, self.canvas.char_h_size * 1.9),
      y + self.string_height // 2,
      )
    
  def draw_stem_and_beam(self, ctx, x, note, y1, y2, mesure = None, previous_time = -32000, next_time = 32000):
    x = x + self.canvas.default_line_height // 2
    canvas.PartitionDrawer.draw_stem_and_beam(self, ctx, x, note, y1, y2, mesure, previous_time, next_time)
    
  if editobj2.GUI == "Gtk":
    def draw_note(self, ctx, note, string_id, y):
      ctx.set_line_width(1.0)
      if note.value < 0: ctx.set_source_rgb(0.5, 0.5, 0.5)
      else:              self.note_color(ctx, note)
      x = self.canvas.time_2_x(note.time)
      y -= self.string_height // 2

      if note.is_dotted():
        ctx.arc(x + self.canvas.default_line_height // 2 + 4 * self.scale, y - 3 * self.scale, 1.5, 0, 6.2831853071795862)
        ctx.fill()

      fingering = self.partition.view.note_2_fingering(note)
      if fingering:
        holes  = fingering[:-1]
        breath = fingering[-1]
      else:
        holes = []
        breath = "?"

      for hole in holes:
        if   hole is None:
          y += self.lh3
        elif hole == 1:
          ctx.arc(x + self.lh2,
                  y + self.lh3,
                  self.lh4 + 0.5,
                  0, 6.2831853071795862)
          ctx.fill()
          y += self.lh_6
        elif hole == 0:
          ctx.arc(x + self.lh2,
                  y + self.lh3,
                  self.lh4,
                  0, 6.2831853071795862)
          ctx.stroke()
          y += self.lh_6
        elif hole == 0.5:
          ctx.arc(x + self.lh2,
                  y + self.lh3,
                  self.lh4,
                  1.5707963267948966, 4.7123889803846897)
          ctx.stroke_preserve()
          ctx.fill()
          ctx.arc(x + self.lh2,
                  y + self.lh3,
                  self.lh4,
                  -1.5707963267948966, 1.5707963267948966)
          ctx.stroke()
          y += self.lh_6
        else:
          x2 = x + self.lh2 - self.lh3 + self.lh7
          for sub_hole in hole:
            if   sub_hole == 1:
              ctx.arc(x2,
                      y + self.lh3,
                      self.lh7,
                      0, 6.2831853071795862)
              ctx.stroke_preserve()
              ctx.fill()
            elif sub_hole == 0:
              ctx.arc(x2,
                      y + self.lh3,
                      self.lh7,
                      0, 6.2831853071795862)
              ctx.stroke()
            x2 += self.lh3
          y += self.lh_6


      if breath:
        x_bearing, y_bearing, width, height, x_advance, y_advance = ctx.text_extents(breath)
        ctx.move_to(x + self.canvas.default_line_height // 2 - x_bearing - width / 2 - 1, y + self.canvas.default_line_height // 2 + self.canvas.default_ascent / 2 - self.canvas.default_descent / 2)
        ctx.show_text(breath)
        ctx.new_path() # Required, to avoid that the next drawing start after the text
        
      if note.fx     : getattr(self, "draw_note_fx_%s" % note.fx     )(ctx, note, string_id)
      if note.link_fx: getattr(self, "draw_note_fx_%s" % note.link_fx)(ctx, note, string_id)
      ctx.set_source_rgb(0.0, 0.0, 0.0)

    def on_touchscreen_new_note(self, event):
      y = event.y - self.y - self.start_y - self.stem_extra_height
      hole_clicked = -1
      for hole in self.partition.view.fingerings.values()[0]:
        if y < 0: break
        hole_clicked += 1
        if hole is None: y -= self.canvas.default_line_height * 0.3
        else:            y -= self.canvas.default_line_height * 0.6
      new_value = self.strings[0].on_click_at(hole_clicked)
      self.canvas.on_number_typed(new_value)
      return 1 # OK to change note by dragging up or down
              
    
class SingleString(object):
  def __init__(self, drawer, notation_pos = -1):
    self.drawer       = drawer
    self.notation_pos = notation_pos
    
  def get_base_note(self): return self.drawer.partition.view.get_bell_note()
  base_note = property(get_base_note)
  
  def text_2_value(self, note, text): return self.base_note
  def value_2_text(self, note): return u"o"
  
  def __unicode__(self): return u"Single string"
  
  def width(self): return -1
  
  def on_click_at(self, hole): return "0"
  

class TinWhistleSingleString(SingleString):
  def text_2_value(self, note, text):
    if   text ==  "0": return self.base_note + 11
    elif text ==  "9": return self.base_note + 10
    elif text ==  "1": return self.base_note + 9
    elif text ==  "2": return self.base_note + 7
    elif text ==  "3": return self.base_note + 5
    elif text ==  "4": return self.base_note + 4
    elif text ==  "5": return self.base_note + 2
    elif text ==  "6": return self.base_note
    elif text == "00": return self.base_note + 23
    elif text == "11": return self.base_note + 21
    elif text == "22": return self.base_note + 19
    elif text == "33": return self.base_note + 17
    elif text == "44": return self.base_note + 16
    elif text == "55": return self.base_note + 14
    elif text == "66": return self.base_note + 12
    if len(text) > 2: return self.text_2_value(note, text[-2:])
    if len(text) > 1: return self.text_2_value(note, text[-1])
    return self.base_note
  
  def on_click_at(self, note, hole):
    current_fingering = self.drawer.partition.view.note_2_fingering(note)
    g8 =   0
    if current_fingering and (current_fingering[-1] == u"+"): breath = 12
    else:                                                     breath = 0
    if   hole <  0: return self.base_note + g8 + breath + 11
    elif hole == 0: return self.base_note + g8 + breath + 9
    elif hole == 1: return self.base_note + g8 + breath + 7
    elif hole == 2: return self.base_note + g8 + breath + 5
    #    hole == 3 is the "None" separator
    elif hole == 4: return self.base_note + g8 + breath + 4
    elif hole == 5: return self.base_note + g8 + breath + 2
    elif hole == 6: return self.base_note + g8 + breath
    elif hole == 7: # Toggle breath
      if breath: return note.value - 12
      else:      return note.value + 12
    

  def on_click_at(self, hole):
    if   hole <  0: return "0"
    elif hole == 0: return "1"
    elif hole == 1: return "2"
    elif hole == 2: return "3"
    #    hole == 3 is the "None" separator
    elif hole == 4: return "4"
    elif hole == 5: return "5"
    elif hole == 6: return "6"    
