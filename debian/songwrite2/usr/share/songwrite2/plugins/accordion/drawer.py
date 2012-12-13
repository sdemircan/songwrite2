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

import editobj2
from editobj2.undoredo import *

import gtk.keysyms as keysyms

import songwrite2.model   as model
import songwrite2.globdef as globdef
import songwrite2.canvas  as canvas
import songwrite2.player  as player
from songwrite2.plugins.chord.chord import AccordionChordManager


class AccordionDrawer(canvas.TablatureDrawer):
  def __init__(self, canvas_, partition):
    canvas.TablatureDrawer.__init__(self, canvas_, partition)
    partition.g8 = 0
    self.chord_manager            = AccordionChordManager(partition)
    self.stem_extra_height_bottom = 0
    
  def drawers_changed(self):
    try:    next = self.canvas.drawers[self.canvas.drawers.index(self) + 1]
    except: self.right_hand_drawer = None
    else:
      if next.__class__.__name__ == "AccordionChordDrawer": self.right_hand_drawer = next
      else:                                                 self.right_hand_drawer = None

  def create_cursor(self, time, duration, string_id, value):
    cursor = canvas.PartitionDrawer.create_cursor(self, time, duration, string_id, value)
    if string_id == 0: cursor.bellows_dir = -1
    else:              cursor.bellows_dir =  1
    return cursor
      
  def on_key_press(self, keyval):
    if keyval == keysyms.quoteright: # '
      self.toggle_button_rank()
      return 1
    
  def toggle_button_rank(self):
    if not self.canvas.selections: return
    notes      = list(self.canvas.selections)
    old_values = {}
    for note in notes: old_values[note] = (note.value, note.button_rank)
    text = self.partition.view.strings[self.partition.view.note_string_id(notes[0])].value_2_text(notes[0])
    if u"'" in text: new_button_rank = 0
    else:            new_button_rank = 1
    first = [1]
    def do_it():
      for note in notes:
        string = self.partition.view.strings[self.partition.view.note_string_id(note)]
        text   = string.value_2_text(note)
        if   (    u"'" in text) and (new_button_rank == 0):
          note.value = string.text_2_value(note, text[:-1])
        elif (not u"'" in text) and (new_button_rank == 1):
          note.value = string.text_2_value(note, text + u"'")
        if first[0]:
          first[0] = 0
          player.play_note(note.partition.instrument, note.value)

    def undo_it():
      for note, (value, button_rank) in old_values.iteritems():
        note.value = value
        if not button_rank is None: note.button_rank = button_rank
    UndoableOperation(do_it, undo_it, _(u"change button rank"), self.canvas.main.undo_stack)
    
  def note_value_possible(self, note, value):
    return value in self.partition.view.strings[self.partition.view.note_string_id(note)].value2buttons
    for string in self.partition.view.strings:
      if value in string.value2buttons: return 1
  
  def draw(self, ctx, x, y, width, height, drag = 0, draw_icon = 1):
    canvas.TablatureDrawer.draw(self, ctx, x, y, width, height, drag, draw_icon)
    
  def draw_mesure(self, ctx, time, mesure, y, height):
    canvas.TablatureDrawer.draw_mesure(self, ctx, time, mesure, y - self.string_height // 2 - 1, height + self.string_height)
    
  def draw_strings(self, ctx, x, y, width, height):
    string_x  = x - 25.0 * self.scale
    string_x2 = x + width
    
    if (string_x < string_x2):
      ctx.set_source_rgb(0.0, 0.0, 0.0)
      ctx.set_line_width(1.0)
      for i in range(len(self.strings) + 1):
        string_y = self.string_id_2_y(i) - self.string_height // 2
        if i == 0: string_y0 = string_y
        if y - 2 < string_y < y + height + 2:
          string_y -= 0.5
          ctx.move_to(string_x, string_y)
          ctx.line_to(string_x2, string_y)
          ctx.stroke()
      ctx.move_to(string_x - 0.5, string_y  + 0.5)
      ctx.line_to(string_x - 0.5, string_y0 - 1)
      ctx.stroke()

      ctx.move_to(string_x + 8.0 * self.scale, string_y0 + self.string_height * 0.75)
      ctx.show_text(_(u"__accordion__push"))
      ctx.move_to(string_x + 8.0 * self.scale, string_y0 + self.string_height * 1.75)
      ctx.show_text(_(u"__accordion__draw"))
      
  #draw_note = canvas.PartitionDrawer.draw_note # No white rectangle below notes
  def draw_note(self, ctx, note, string_id, y):
    if self.right_hand_drawer:
      right_hand_notes = self.right_hand_drawer.partition.notes_before(note.time + 1)
      while right_hand_notes:
        p = right_hand_notes[-1].next()
        if p and (p.time < note.end_time()):
          right_hand_notes.append(p)
        else:
          break
      times = {}
      for right_hand_note in right_hand_notes:
        if right_hand_note.end_time() > note.time:
          if times.has_key(right_hand_note.time): times[right_hand_note.time].append(right_hand_note)
          else:                                   times[right_hand_note.time] =     [right_hand_note]
          
      ok = 1
      for time, right_hand_notes in times.items():
        if len(right_hand_notes) > 1: # chord
          rel_values = frozenset([right_hand_note.value for right_hand_note in right_hand_notes])
          chord      = self.right_hand_drawer.chord_manager.identify(rel_values)
          right_value = chord.base % 12
        else: # bass
          right_value = right_hand_notes[0].value % 12
          
        required_bellow_dir = CHORD_BELLOWS_DIR.get(right_value, 0)
        if required_bellow_dir and (note.bellows_dir != required_bellow_dir):
          ctx.set_source_rgb(1.0, 0.0, 0.0)
          x  = self.canvas.time_2_x(note.time)
          y += self.note_offset_y
          ctx.move_to(x + 3 * self.scale, y + self.canvas.default_ascent / 2 - self.canvas.default_descent / 2)
          ctx.show_text(u"X")
          break
      
    canvas.PartitionDrawer.draw_note(self, ctx, note, string_id, y)
    
      
    

CHORD_BELLOWS_DIR = {
   0 : -1, # Do
   2 :  1, # Ré
   4 : -1, # Mi
   5 :  0, # Fa
   7 :  0, # Sol
   9 :  1, # La
  }
