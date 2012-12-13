# -*- coding: utf-8 -*-0

# Songwrite 2
# Copyright (C) 2007-2010 Jean-Baptiste LAMY -- jibalamy@free.fr
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later verson.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import division
import os, os.path, sys, math, bisect, locale, codecs
from cStringIO import StringIO

import gobject, gtk, cairo, pango, pangocairo
import gtk.keysyms as keysyms
if gtk.pygtk_version < (2, 7, 0): import cairo.gtk

from editobj2.introsp  import *
from editobj2.observe  import *
from editobj2.undoredo import *
import editobj2.editor_gtk as editor_gtk

import songwrite2.globdef as globdef
import songwrite2.model   as model
import songwrite2.stemml  as stemml
import songwrite2.player  as player
import songwrite2.__editobj2__

zoom_levels          = [0.25, 0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0]
ZOOM_2_CLIP_DURATION = {
  0.25 : 96,
  0.35 : 96,
  0.5  : 96,
  0.75 : 48,
  1.0  : 48,
  1.5  : 24,
  2.0  : 24,
  3.0  : 12,
  4.0  : 12,
  }


SELECTION_COLOR  = None
SELECTION_COLOR2 = None

CLIPBOARD        = None
CLIPBOARD_SOURCE = None
CLIPBOARD_X1     = 0
CLIPBOARD_Y1     = 0
CLIPBOARD_X2     = 0
CLIPBOARD_Y2     = 0

CLIPBOARD2_NAME = "_SONGWRITE2_NOTES"
CLIPBOARD2 = gtk.Clipboard(selection = CLIPBOARD2_NAME)

def find_view_children(o):
  if isinstance(o, model.View) and hasattr(o, "strings"):
    return o.strings
  return []

class BaseCanvas(object):
  def __init__(self, song, zoom = 1.0):
    self.x                   = 0
    self.y                   = 0
    self.width               = 0
    self.height              = 0
    self.song                = song
    self.zoom                = zoom
    self.selection_x1        = 1000000
    self.selection_y1        = 1000000
    self.selection_x2        = -1
    self.selection_y2        = -1
    self.cursor              = None
    self.cursor_drawer       = None
    self.canvas              = None
    self.drawers             = None
    self.partition_2_drawer  = {}
    self.selections          = set()
    self.scale_pango_2_cairo = 72.0 / pangocairo.cairo_font_map_get_default().get_resolution()
    self.set_default_font_size(16.0)
    
  def set_default_font_size(self, size):
    self.default_font_size   = size
    self.scale               = self.default_font_size / 14.6666666667
    self.default_line_height = 0
    self.start_x             = int((editor_gtk.SMALL_ICON_SIZE + 42) * self.scale)
    
  def reset(self):
    for drawer in self.drawers: drawer.destroy()
    self.drawers = []
    self.update_mesure_size()

  def text_extents_default(self, text):
    self.default_layout.set_text(text)
    return self.default_layout.get_pixel_size()
    
  def draw_text_default(self, ctx, text, x, y):
    ctx.move_to(x, y)
    self.default_layout.set_text(text)
    ctx.show_layout(self.default_layout)
    
  def draw_text_at_size(self, ctx, text, x, y, font_size_factor):
    self.default_layout.set_font_description(pango.FontDescription(u"Sans %s" % (self.default_font_size * self.scale_pango_2_cairo * font_size_factor)))
    ctx.move_to(x, y)
    self.default_layout.set_text(text)
    ctx.show_layout(self.default_layout)
    self.default_layout.set_font_description(self.default_pango_font)
    
  def draw_text_max_width(self, ctx, text, x, y, max_width):
    ctx.move_to(x, y)
    self.default_layout.set_text(text)
    width0, height0 = self.default_layout.get_pixel_size()
    if width0 < max_width:
      ctx.show_layout(self.default_layout)
    else:
      font_size = self.default_font_size * self.scale_pango_2_cairo
      while font_size:
        font_size -= 1
        self.default_layout.set_font_description(pango.FontDescription(u"Sans %s" % font_size))
        width, height = self.default_layout.get_pixel_size()
        if width < max_width: break
      ctx.rel_move_to(0.0, 0.7 * (height0 - height))
      ctx.show_layout(self.default_layout)
      self.default_layout.set_font_description(self.default_pango_font)

  def note_string_id(self, note):
    return self.partition_2_drawer[note.partition].note_string_id(note)
  
  def y_2_drawer(self, y):
    for drawer in self.drawers:
      if y < drawer.y + drawer.height: return drawer
    return None
    
  def x_2_time(self, x):
    x0 = x - self.start_x + self.x
    if x0 <= 0: return 0.0
    mesure = self.song.mesure_at(x0 / self.zoom)
    if mesure is None:
      mesure = self.song.mesures[-1]
      if not self.mesure_2_extra_x.has_key(mesure): self.update_mesure_size()
      mesure_extra_x = self.mesure_2_extra_x[mesure]
      return (x0 - mesure_extra_x)  / self.zoom
    
    while 1:
      if not self.mesure_2_extra_x.has_key(mesure): self.update_mesure_size()
      mesure_extra_x = self.mesure_2_extra_x[mesure]
      time = (x0 - mesure_extra_x) / self.zoom
      mesure2 = self.song.mesure_at(time)
      if mesure2.time >= mesure.time: return time
      mesure = mesure2
      
  def time_2_x(self, time):
    mesure = self.song.mesure_at(time)
    if not self.mesure_2_extra_x.has_key(mesure): self.update_mesure_size()
    return self.start_x - self.x + self.mesure_2_extra_x[mesure] + time * self.zoom
  
  def update_mesure_size(self):
    self.mesure_2_extra_x = {}
    extra_x = self.scale * 3.0
    for mesure in self.song.mesures + [None]:
      symbols = self.song.playlist.symbols.get(mesure)
      if symbols:
        for symbol in symbols:
          if   symbol.startswith(r"\repeat"):    extra_x += self.scale * 15.0
          elif symbol == r"} % end alternative": extra_x += self.scale * 15.0
          elif symbol == r"} % end repeat":      extra_x += self.scale * 15.0
      self.mesure_2_extra_x[mesure] = extra_x
      extra_x += self.scale * 5.0
    self.need_update_selection = 1
    
    
class Canvas(gtk.Fixed, BaseCanvas):
  is_gui_interface = 1
  def __init__(self, main, song, scrolled, zoom = 1.0):
    BaseCanvas.__init__(self, song, zoom)
    gtk.Fixed.__init__(self)
    self.set_has_window(1)
    
    global SELECTION_COLOR
    if SELECTION_COLOR is None:
      global SELECTION_COLOR2
      color = gtk.Entry().rc_get_style().bg[gtk.STATE_SELECTED]
      SELECTION_COLOR2 = color.red / 65535.0, color.green / 65535.0, color.blue / 65535.0
      SELECTION_COLOR = [1.0 - 0.35 * (1.0 - x) for x in SELECTION_COLOR2]
      color = gtk.Entry().rc_get_style().bg[gtk.STATE_PRELIGHT]
      
    self.canvas = gtk.DrawingArea()
    self.put(self.canvas, 0, 0)
    
    self.main              = main
    self.song              = song
    self.hadjustment       = scrolled.get_hadjustment()
    self.vadjustment       = scrolled.get_vadjustment()
    self.last_selections   = set()
    self.drag_selections   = set()
    self.click_x           = 0
    self.click_y           = 0
    self.drag_start_x      = 0
    self.drag_start_y      = 0
    self.last_selection_x1 = 1000000
    self.last_selection_y1 = 1000000
    self.last_selection_x2 = -1
    self.last_selection_y2 = -1
    self.need_update_selection = 0
    self.current_duration  = 48
    self.previous_text     = "" # Previously typed text
    self.edit_timeout      = 0
    self.first_time        = 1
    self.x_before_tracking = -1
    self.touchscreen_new_note = None
    self.show_render_zone  = 0
    
    if globdef.config.FONTSIZE:
      self.set_default_font_size(globdef.config.FONTSIZE)
    else:
      self.set_default_font_size(self.get_style().font_desc.get_size() / pango.SCALE * pangocairo.cairo_font_map_get_default().get_resolution() / 72.0)

    #self.set_default_font_size(32.0)
    #print self.default_font_size
    
    self.canvas.add_events(gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.KEY_PRESS_MASK | gtk.gdk.BUTTON1_MOTION_MASK)
    self.canvas.set_flags(gtk.CAN_FOCUS)
    self.canvas.connect('expose_event'             , self.on_expose)
    self.canvas.connect('key_press_event'          , self.on_key_press)
    self.canvas.connect('motion_notify_event'      , self.on_mouse_motion)
    self.canvas.connect('button_press_event'       , self.on_button_press)
    self.canvas.connect('button_release_event'     , self.on_button_release)
    self.connect('drag-drop'                , self.on_drag_drop)
    self.connect('drag-data-received'       , self.on_drag_data_received)
    self.connect('drag-data-get'            , self.on_drag_data_get)
    self.connect('drag-data-delete'         , self.on_drag_data_delete)
    self.connect('size-allocate'            , self.on_resized)
    self.connect('scroll-event'            , self.on_before_scroll)
    self.vadjustment.connect("value-changed", self.on_scroll)
    self.hadjustment.connect("value-changed", self.on_scroll)
    self.vadjustment.step_increment = self.hadjustment.step_increment = 10
    
    observe(song                        , self.song_listener)
    observe(song.playlist               , self.playlist_listener)
    observe(song.playlist.playlist_items, self.playlist_listener)
    observe(song.mesures                , self.mesures_listener)
    for mesure in song.mesures:
      observe(mesure, self.mesure_listener)
      
    observe(song.partitions, self.partitions_listener)
    for partition in song.partitions:
      observe(partition      , self.partition_listener)
      if isinstance(partition, model.Partition):
        observe_tree(partition.view , self.view_listener, find_view_children)
        observe(partition.notes, self.notes_listener)
        for note in partition.notes: observe(note, self.note_listener)
          
    self.drag_source_set(gtk.gdk.BUTTON1_MASK, [(CLIPBOARD2_NAME, 0, 0)], gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY)
    self.drag_source_targets = self.drag_source_get_target_list()
    self.drag_source_unset()
    
    self.drag_dest_set(gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_DROP, [(CLIPBOARD2_NAME, 0, 0)], gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY)
    self.connect("drag-motion", self.on_drag_motion)
    
    self.context_menu_song = gtk.Menu()
    menu_item = gtk.MenuItem(_(u"Song and instruments...")); menu_item.connect("activate", self.main.on_song_prop      ); self.context_menu_song.append(menu_item)
    self.context_menu_song.show_all()
    
    self.context_menu_note = gtk.Menu()
    menu_item = gtk.MenuItem(_(u"Edit note..."      )); menu_item.connect("activate", self.main.on_note_prop      ); self.context_menu_note.append(menu_item)
    menu_item = gtk.MenuItem(_(u"Edit bar..."       )); menu_item.connect("activate", self.main.on_bars_prop      ); self.context_menu_note.append(menu_item)
    menu_item = gtk.MenuItem(_(u"Edit instrument...")); menu_item.connect("activate", self.main.on_instrument_prop); self.context_menu_note.append(menu_item)
    self.context_menu_note.show_all()
    
    self.update_mesure_size()
    
  def config_listener(self, obj, type, new, old):
    for drawer in self.drawers:
      drawer.config_listener(obj, type, new, old)
    if type is object:
      if   (new.get("FONTSIZE") != old.get("FONTSIZE")):
        if globdef.config.FONTSIZE:
          self.set_default_font_size(globdef.config.FONTSIZE)
        else:
          self.set_default_font_size(self.get_style().font_desc.get_size() / pango.SCALE * pangocairo.cairo_font_map_get_default().get_resolution() / 72.0)
        self.reset()
        self.need_update_selection = 1
        self.render_all()
        
  def on_drag_motion(self, widget, drag, x, y, timestamp):
    if drag.actions & gtk.gdk.ACTION_MOVE: drag.drag_status(gtk.gdk.ACTION_MOVE, timestamp)
    else:                                  drag.drag_status(gtk.gdk.ACTION_COPY, timestamp)
    return 1
  
  def play_tracker(self, time):
    if time == -1:
      self.render_selection()
      
      self.selection_x1     = 1000000
      self.selection_y1     = 1000000
      self.selection_x2     = -1
      self.selection_y2     = -1
      for note in self.selections:
        drawer = self.partition_2_drawer[note.partition]
        x1, y1, x2, y2 = drawer.note_dimensions(note)

        x1 += self.x
        y1 += self.y
        x2 += self.x
        y2 += self.y
        if x1 < self.selection_x1: self.selection_x1 = x1
        if y1 < self.selection_y1: self.selection_y1 = y1
        if x2 > self.selection_x2: self.selection_x2 = x2
        if y2 > self.selection_y2: self.selection_y2 = y2
        
      self.render_selection()
      self.x_before_tracking = -1
      
    else:
      if self.x_before_tracking == -1: self.x_before_tracking = max(0, self.x)
      self.render_selection()
      self.selection_x1 = self.time_2_x(time) + self.x
      self.selection_y1 = self.drawers[1].y + self.y
      self.selection_x2 = self.selection_x1 + 2 * self.char_h_size
      self.selection_y2 = self.drawers[-1].y + self.drawers[-1].height + self.y
      self.render_selection()
      
      if self.hadjustment.upper - self.hadjustment.lower > self.hadjustment.page_size:
        if   self.selection_x2 > self.x + self.width * 0.75:
          self.hadjustment.value = min(self.hadjustment.upper, self.selection_x2 - self.width * 0.1)
        elif self.selection_x1 < self.x:
          self.hadjustment.value = max(self.hadjustment.lower, self.selection_x2 - self.width * 0.1)
          
  def destroy(self):
    if self.drawers:
      for drawer in self.drawers: drawer.destroy()
    unobserve(self.cursor)
    unobserve(self.song                        , self.song_listener)
    unobserve(self.song.playlist               , self.playlist_listener)
    unobserve(self.song.playlist.playlist_items, self.playlist_listener)
    unobserve(self.song.mesures                , self.mesures_listener)
    unobserve(self.song.partitions             , self.partitions_listener)
    
    for mesure in self.song.mesures:
      unobserve(mesure, self.mesure_listener)
      
    for partition in self.song.partitions:
      unobserve(partition, self.partition_listener)
      if isinstance(partition, model.Partition):
        unobserve_tree(partition.view, self.view_listener, find_view_children)
        unobserve(partition.notes, self.notes_listener)
        for note in partition.notes:
          unobserve(note, self.note_listener)
          
    gtk.Fixed.destroy(self)
    
  def update_time(self):
    for drawer in self.drawers:
      if isinstance(drawer, LyricsDrawer): drawer.update_melody()
        
  def get_selected_time(self):
    if self.selections     : return list(self.selections     )[0].time
    if self.last_selections: return list(self.last_selections)[0].time
    return 0
  
  def get_selected_mesures(self):
    mesures = list(set([self.song.mesure_at(note.time) for note in self.selections]))
    mesures.sort() # Sort and reverse => if the user reduces the length of several mesures,
    mesures.reverse() # the change is first applied at the last mesure;
    # because if new mesures are created, there are created by cloning the last one.
    return mesures
    return list(set([self.song.mesure_at(note.time) for note in self.selections]))
  
  def get_selected_partitions(self):
    return list(set([note.partition for note in self.selections]))
  
  def song_listener(self, song, type, new, old):
    self.main.set_title(u"Songwrite2 -- %s" % song.title)
    self.render_all()
    
  def playlist_listener(self, playlist, type, new, old):
    self.update_mesure_size()
    self.render_all()
    
  def mesures_listener(self, obj, type, new, old):
    new = set(new)
    old = set(old)
    for mesure in new - old: observe  (mesure, self.mesure_listener)
    for mesure in old - new: unobserve(mesure, self.mesure_listener)
    self.update_mesure_size()
    
  def mesure_listener(self, mesure, type, new, old):
    self.update_mesure_size()
    self.render_all()
    
  def partitions_listener(self, obj, type, new, old):
    new = set(new)
    old = set(old)
    for partition in new - old:
      observe  (partition, self.partition_listener)
      if isinstance(partition, model.Partition):
        observe_tree(partition.view , self.view_listener, find_view_children)
        observe(partition.notes, self.notes_listener)
        for note in partition.notes: observe(note, self.note_listener)
        
    for partition in old - new:
      unobserve(partition, self.partition_listener)
      if isinstance(partition, model.Partition):
        unobserve_tree(partition.view , self.view_listener, find_view_children)
        unobserve(partition.notes, self.notes_listener)
        for note in partition.notes: unobserve(note, self.note_listener)
        
    self.update_melody_lyrics()
    for drawer in self.drawers: drawer.drawers_changed()
    self.deselect_all()
    self.reset()
    self.render_all()
    
  def update_melody_lyrics(self):
    current_melody = None
    for drawer in self.drawers:
      if   isinstance(drawer, LyricsDrawer):
        if current_melody: current_melody.associated_lyrics.append(drawer)
      elif isinstance(drawer, PartitionDrawer):
        drawer.associated_lyrics = []
        if drawer.partition.view.ok_for_lyrics:
          current_melody = drawer
          
  def partition_listener(self, partition, type, new, old):
    if type is object:
      if   (new.get("view") != old.get("view")):
        unobserve_tree(old.get("view"), self.view_listener, find_view_children)
        observe_tree  (new.get("view"), self.view_listener, find_view_children)
        
        self.deselect_all()
        self.reset()
        self.render_all()
      if   (new.get("g8") != old.get("g8")) or (new.get("tonality") != old.get("tonality")):
        self.deselect_all()
        self.reset()
        self.render_all()
      elif (new.get("instrument") != old.get("instrument")) or (new.get("header") != old.get("header")) or (new.get("visible") != old.get("visible")):
        self.render_all()
        
    self.partition_2_drawer[partition].partition_listener(partition, type, new, old)
    
  def view_listener(self, view, type, new, old):
    self.render_all()
    
  def strings_listener(self, view, type, new, old):
    self.render_all()
    
  def notes_listener(self, obj, type, new, old):
    new = set(new)
    old = set(old)
    for note in new - old:
      if not isobserved(note, self.note_listener): # Can be already observed if note was the cursor before
        observe  (note, self.note_listener)
    for note in old - new: unobserve(note, self.note_listener)
    
    drawer = self.partition_2_drawer.get(tuple(new or old)[0].partition)
    if drawer:
      drawer.notes_listener(obj, type, new, old)
      
  def note_listener(self, note, type, new, old):
    #print note, type, new, old
    if note in self.selections:
      self.need_update_selection = 1
      if (note is self.cursor) and (note.value > 0):
        self.cursor = None
      self.render_selection()
      self.main.set_selected_note(self.main.selected_note)
    drawer = self.partition_2_drawer.get(note.partition)
    if drawer:
      drawer.note_listener(note, type, new, old)
      drawer.render_note(note)
    
  def set_cursor(self, cursor, cursor_drawer):
    self.cursor        = cursor
    self.cursor_drawer = cursor_drawer
    
  def set_zoom(self, zoom):
    self.selection_x1 = (self.selection_x1 - self.start_x) * zoom / self.zoom + self.start_x
    self.selection_x2 = (self.selection_x2 - self.start_x) * zoom / self.zoom + self.start_x
    self.hadjustment.value = self.hadjustment.value  / self.zoom * zoom
    self.need_update_selection = 1
    
    self.zoom = zoom
    self.render_pixel(0, 0, self.width, self.height)
    self.update_time()
    self.main.zoom_menu.get_child().set_text(u"%s%%" % int(zoom * 100.0))
    
  def delayed_edit(self, note):
    if self.edit_timeout: gobject.source_remove(self.edit_timeout)
    self.edit_timeout = gobject.timeout_add(40, self.edit, note)
    
  def edit(self, note):
    mesures = self.get_selected_mesures()
    if len(mesures) == 1: mesure = mesures[0]
    else:                 mesure = ObjectPack(mesures)
    partitions = self.get_selected_partitions()
    if partitions:
      if len(partitions) == 1:
        partition = partitions[0]
      else:
        partition = ObjectPack(partitions)
        partition.song = ObjectPack([p.song for p in partitions])
      self.main.set_selected_partition(partition)
      
    self.main.set_selected_mesure(mesure)
    self.main.set_selected_note(note)
    
    if getattr(self.main, "notebook", None):
      if partitions: self.main.notebook.edit(-3, partition)
      self.main.notebook.edit(-2, mesure)
      self.main.notebook.edit(-1, note)
 #   else:
 #     self.main.set_title(u"Songwrite2 -- %s -- %s -- %s" % (self.song.title, self.song.mesure_at(note), description(note.__class__).label_for(note)))
      
  def arrange_selection_at_fret(self, fret):
    old_string_ids = dict([(note, note.string_id) for note in self.selections if hasattr(note, "string_id")])
    def do_it():
      for note, string_id in old_string_ids.iteritems():
        if isinstance(note.partition.view, model.TablatureView):
          strings = note.partition.view.strings
          if note.value - strings[string_id].base_note - note.partition.capo < fret:
            while (string_id < len(strings) - 1) and (note.value - strings[string_id].base_note - note.partition.capo < fret):
              string_id += 1
          else:
            while (string_id > 0) and (note.value - strings[string_id - 1].base_note - note.partition.capo >= fret):
              string_id -= 1
          note.string_id = string_id
      self.render_all()
      
    def undo_it():
      for note, string_id in old_string_ids.iteritems():
        note.string_id = string_id
      self.render_all()
    UndoableOperation(do_it, undo_it, _(u"arrange at fret #%s") % fret, self.main.undo_stack)
    
    
  def select_all(self):
    self.deselect_all()
    for partition in self.song.partitions:
      if isinstance(partition, model.Partition):
        drawer = self.partition_2_drawer[partition]
        for note in partition.notes:
          self.add_selection(note, render = 0, edit = 1, *drawer.note_dimensions(note))
    self.render_selection()
    
  def deselect_all(self):
    if self.cursor: self.cursor_drawer.destroy_cursor()
    if self.selection_x2 != -1:
      self.render_selection()
      self.selection_x1     = 1000000
      self.selection_y1     = 1000000
      self.selection_x2     = -1
      self.selection_y2     = -1
    self.selections      = set()
    self.cursor          = None
    self.previous_text   = ""
    self.touchscreen_new_note = None
    
  def extend_selection(self, x1, y1, x2, y2, note = None):
    if self.selection_x1 > x1:
      self.selection_x1 = x1
      if note and (note.time == 0):
        self.hadjustment.value = 0
      else:
        if x1 < self.x + self.start_x: self.hadjustment.value = x1 - self.start_x
        
    if self.selection_y1 > y1:
      self.selection_y1 = y1
      if y1 < self.y: self.vadjustment.value = y1
      
    if self.selection_x2 < x2:
      self.selection_x2 = x2
      if x2 > self.x + self.width: self.hadjustment.value = x2 - self.width
        
    if self.selection_y2 < y2:
      self.selection_y2 = y2
      if y2 > self.y + self.height: self.vadjustment.value = y2 - self.height
      
  def add_selection(self, note, x1, y1, x2, y2, render = 1, edit = 1):
    self.selections.add(note)
    self.extend_selection(x1 + self.x, y1 + self.y, x2 + self.x, y2 + self.y, note)
    
    if not note is self.cursor:
      global CLIPBOARD, CLIPBOARD_SOURCE, CLIPBOARD_X1, CLIPBOARD_Y1, CLIPBOARD_X2, CLIPBOARD_Y2
      CLIPBOARD_SOURCE = self
      CLIPBOARD        = self.last_selections   = self.selections
      CLIPBOARD_X1     = self.last_selection_x1 = self.selection_x1
      CLIPBOARD_Y1     = self.last_selection_y1 = self.selection_y1
      CLIPBOARD_X2     = self.last_selection_x2 = self.selection_x2
      CLIPBOARD_Y2     = self.last_selection_y2 = self.selection_y2
      
      CLIPBOARD2.set_with_data([(CLIPBOARD2_NAME, 0, 0)], self.clipboard_get, self.clipboard_clear, None)
    if render: self.render_selection()
    if edit  : self.delayed_edit(note)
    
  def clipboard_clear(self, clipboard, userdata): pass
  
  def clipboard_get(self, clipboard, selection_data, info, userdata):
    _xml    = StringIO()
    xml     = codecs.lookup("utf8")[3](_xml)
    context = model._XMLContext()
    xml.write("""<?xml version="1.0" encoding="utf-8"?>\n<notes click_x="0">""")
    
    min_y = 10000.0
    for note in CLIPBOARD:
      drawer = self.partition_2_drawer[note.partition]
      x1, y1, x2, y2 = drawer.note_dimensions(note)
      y = (y1 + y2) // 2
      if y < min_y: min_y = y
      
    for note in CLIPBOARD:
      drawer = self.partition_2_drawer[note.partition]
      x1, y1, x2, y2 = drawer.note_dimensions(note)
      nb_char = len(drawer.note_text(note))
      x = x1 + (self.char_h_size * nb_char) // 2 - CLIPBOARD_X1
      y = (y1 + y2) // 2 - min_y
      label = drawer.strings[note.partition.view.note_string_id(note)].value_2_text(note)
      note.__xml__(xml, context, ' x="%r" y="%r" label="%s" view_type="%s"' % (x, y, label, note.partition.view.__class__.__name__[:-4].lower()))
    xml.write("</notes>")
    
    selection_data.set(selection_data.target, 8, xml.getvalue())
    
  def on_button_press(self, obj, event):
    self.canvas.grab_focus()
    self.click_x = event.x + self.x
    self.click_y = event.y + self.y
    if   event.button == 1:
      if self.selections and (self.selection_x1 <= self.click_x <= self.selection_x2) and (self.selection_y1 <= self.click_y <= self.selection_y2):
        if self.cursor in self.selections:
          drawer = self.partition_2_drawer[list(self.selections)[0].partition]
          if drawer.on_touchscreen_new_note(event):
            self.touchscreen_new_note        = tuple(self.selections)[0]
            self.touchscreen_new_note_y0     = event.y
            self.touchscreen_new_note_value0 = self.touchscreen_new_note.value
      else:
        self.deselect_all()
        if event.x > self.start_x:
          for drawer in self.drawers:
            if drawer.y <= event.y <= drawer.y + drawer.height:
              drawer.on_button_press(event)
              break
        elif event.type == gtk.gdk._2BUTTON_PRESS:
          for drawer in self.drawers:
            if drawer.y <= event.y <= drawer.y + drawer.height:
              self.main.set_selected_partition(getattr(drawer, "partition", None) or getattr(drawer, "lyrics"))
              self.main.on_instrument_prop()
              break
          
    elif event.button == 2:
      if CLIPBOARD:
        drag = CLIPBOARD_SOURCE.drag_begin(self.drag_source_targets, gtk.gdk.ACTION_COPY, 2, event)
        CLIPBOARD_SOURCE.drag_start_x    = self.drag_start_x = CLIPBOARD_X1 + 20
        CLIPBOARD_SOURCE.drag_start_y    = self.drag_start_y = CLIPBOARD_Y1 + 20
        CLIPBOARD_SOURCE.drag_selections = set(CLIPBOARD)
        
        width  = int(CLIPBOARD_X2 - CLIPBOARD_X1) + 2
        height = int(CLIPBOARD_Y2 - CLIPBOARD_Y1) + 2
        pixmap = gtk.gdk.Pixmap(self.window, width, height)
        ctx = pixmap.cairo_create()
        
        CLIPBOARD_SOURCE.draw_drag_icon(ctx, CLIPBOARD_X1 - 1, CLIPBOARD_Y1 - 1, width, height)
        pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, 1, 8, max(width, 100), height) # It seems that GTK doesn't like small drag icons !
        pixbuf.fill(0x00000000)
        pixbuf.get_from_drawable(pixmap, self.window.get_colormap(), 0, 0, 0, 0, width, height)
        pixbuf = pixbuf.add_alpha(1, chr(255), chr(255), chr(255))
        drag.set_icon_pixbuf(pixbuf, 20, 20)
        
    elif event.button == 3:
      #self.deselect_all()
      if event.x > self.start_x:
        for drawer in self.drawers:
          if drawer.y <= event.y <= drawer.y + drawer.height: drawer.on_button_press(event)
          
  def on_button_release(self, obj, event):
    if (not self.selections) and (self.selection_x2 != -1):
      time1 = self.x_2_time(self.selection_x1 - self.x)
      time2 = self.x_2_time(self.selection_x2 - self.x)
      y1 = self.selection_y1 - self.y
      y2 = self.selection_y2 - self.y
      
      self.deselect_all()
      for partition in self.song.partitions:
        if not isinstance(partition, model.Partition): continue
        drawer = self.partition_2_drawer[partition]
        string_id1 = drawer.y_2_string_id(y1 + drawer.string_height // 2, 1)
        string_id2 = drawer.y_2_string_id(y2 - drawer.string_height // 2, 1)
        
        for note in partition.notes_at(time1, time2):
          if string_id1 <= drawer.note_string_id(note) <= string_id2:
            self.add_selection(note, render = 0, edit = 0, *drawer.note_dimensions(note))
            
      if self.selections:
        self.render_selection()
        if len(self.selections) == 1:
          self.delayed_edit(tuple(self.selections)[0])
        else:
          pack = ObjectPack(list(self.selections))
          self.delayed_edit(pack)
          
  def on_mouse_motion(self, obj, event):
    if   self.touchscreen_new_note:
      drawer = self.partition_2_drawer[self.touchscreen_new_note.partition]
      value  = self.touchscreen_new_note_value0
      delta  = int((self.touchscreen_new_note_y0 - event.y) // (20.0 * self.scale))
      value  = drawer.mouse_motion_note(value, delta)
      while not drawer.note_value_possible(self.touchscreen_new_note, value):
        if delta >= 0: value += 1
        else:          value -= 1
      if self.touchscreen_new_note.value != value:
        self.touchscreen_new_note.value = value
        scan()
        
    elif self.drag_check_threshold(int(self.click_x - self.x), int(self.click_y - self.y), int(event.x), int(event.y)):
      if self.selections and (self.selection_x1 <= self.click_x <= self.selection_x2) and (self.selection_y1 <= self.click_y <= self.selection_y2) and not self.cursor:
        drag = self.drag_begin(self.drag_source_targets, gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY, 1, event)
        
        self.drag_start_x    = self.click_x
        self.drag_start_y    = self.click_y
        self.drag_selections = set(self.last_selections)
        
        width  = int(self.selection_x2 - self.selection_x1) + 2
        height = int(self.selection_y2 - self.selection_y1) + 2
        pixmap = gtk.gdk.Pixmap(self.window, width, height)
        ctx = pixmap.cairo_create()
        
        self.draw_drag_icon(ctx, self.selection_x1 - 1, self.selection_y1 - 1, width, height)
        pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, 1, 8, max(width, 100), height) # It seems that GTK doesn't like small drag icons !
        pixbuf.fill(0x00000000)
        pixbuf.get_from_drawable(pixmap, self.window.get_colormap(), 0, 0, 0, 0, width, height)
        pixbuf = pixbuf.add_alpha(1, chr(255), chr(255), chr(255))
        drag.set_icon_pixbuf(pixbuf, int(self.click_x - self.selection_x1), int(self.click_y - self.selection_y1))
        
      else:
        if self.selections: self.deselect_all()
        old_sel_x1 = self.selection_x1
        old_sel_y1 = self.selection_y1
        old_sel_x2 = self.selection_x2
        old_sel_y2 = self.selection_y2
        if   event.x <= self.start_x: self.hadjustment.value = max(0, self.hadjustment.value - 10)
        elif event.x >= self.width  : self.hadjustment.value = min(max(self.hadjustment.upper - self.width, 0), self.hadjustment.value + 10)
        if   event.y <= 0           : self.vadjustment.value = max(0, self.vadjustment.value - 10)
        elif event.y >= self.height : self.vadjustment.value = min(max(self.vadjustment.upper - self.height, 0), self.vadjustment.value + 10)
        self.selection_x1 = max(min(self.click_x, event.x + self.x), self.start_x)
        self.selection_y1 = min(self.click_y, event.y + self.y)
        self.selection_x2 = max(self.click_x, event.x + self.x)
        self.selection_y2 = max(self.click_y, event.y + self.y)
        self.render(min(old_sel_x1, self.selection_x1) - 1,
                    min(old_sel_y1, self.selection_y1) - 1,
                    max(old_sel_x2, self.selection_x2) - min(old_sel_x1, self.selection_x1) + 2,
                    max(old_sel_y2, self.selection_y2) - min(old_sel_y1, self.selection_y1) + 2)
        
  def on_drag_drop(self, widget, drag_context, x, y, timestamp): return True
  
  def on_drag_data_get(self, widget, drag_context, selection_data, info, timestamp):
    _xml    = StringIO()
    xml     = codecs.lookup("utf8")[3](_xml)
    context = model._XMLContext()
    xml.write("""<?xml version="1.0" encoding="utf-8"?>\n<notes click_x="%s">\n""" % (self.drag_start_x - self.selection_x1))
    
    for note in sorted(self.drag_selections):
      drawer = self.partition_2_drawer[note.partition]
      x1, y1, x2, y2 = drawer.note_dimensions(note)
      nb_char = len(drawer.note_text(note))
      x = x1 + (self.char_h_size * nb_char) // 2 - self.drag_start_x
      y = (y1 + y2) // 2 - self.drag_start_y + self.y
      label = drawer.strings[note.partition.view.note_string_id(note)].value_2_text(note)
      note.__xml__(xml, context, ' x="%r" y="%r" label="%s" view_type="%s"' % (x, y, label, note.partition.view.__class__.__name__[:-4].lower()))
    xml.write("</notes>")
    selection_data.set(selection_data.target, 8, xml.getvalue())
    
  def on_drag_data_received(self, widget, drag_context, x0, y0, selection_data, info, timestamp):
    xml = selection_data.data
    
    print xml
    from cStringIO import StringIO
    click_x, notes = stemml.parse(StringIO(xml))
    
    orig_time = click_x / self.zoom
    dest_time = self.x_2_time(x0)
    
    self.paste_notes(notes, dest_time, orig_time, y0)
    
  def on_note_paste(self):
    xml = CLIPBOARD2.wait_for_contents(CLIPBOARD2_NAME).data
    
    from cStringIO import StringIO
    click_x, notes = stemml.parse(StringIO(xml))
    
    if not self.selections: return
    note      = tuple(self.selections)[0]
    drawer    = self.partition_2_drawer[note.partition]
    y0        = drawer.string_id_2_y(drawer.note_string_id(note))
    dest_time = note.time
    orig_time = 0
    
    self.paste_notes(notes, dest_time, orig_time, y0)
    
    
  def paste_notes(self, notes, dest_time, orig_time, y0):
    orig_time += min([note.time for note in notes])
    
    clip_duration = ZOOM_2_CLIP_DURATION[self.zoom]
    if clip_duration ==  96:
      if (self.song.mesure_at(dest_time) or self.song.mesures[-1]).rythm2 == 8: clip_duration /= 2
    if clip_duration == 144:
      if (self.song.mesure_at(dest_time) or self.song.mesures[-1]).rythm2 == 4: clip_duration /= 3
    else:
      if clip_duration / 1.5 in model.DURATIONS.keys(): clip_duration /= 3
    
    dt = int(0.4 + float(abs(dest_time - orig_time)) / clip_duration) * clip_duration
    
    if dest_time < orig_time: dt = -dt
    
    notes_data     = []
    previous_notes = {}
    for note in notes:
      y = y0 + note.y
      drawer = self.y_2_drawer(y)
      if not isinstance(drawer, PartitionDrawer): continue
      time = note.time + dt
      if time < 0: continue
      
      if (note.view_type == drawer.partition.view.__class__.__name__[:-4].lower()) and drawer.partition.view.can_paste_note_by_string:
        # Paste by string
        string_id = drawer.y_2_string_id(y)
        if string_id is None: continue
        paste_by_string = 1
      else:
        # Paste by note
        string_id = drawer.partition.view.note_string_id(note)
        paste_by_string = 0
        
      notes_data.append((note, drawer, time, string_id, paste_by_string))
      for previous_note in drawer.partition.notes_at(time):
        if string_id == drawer.note_string_id(previous_note):
          drawer_previous_notes = previous_notes.get(drawer)
          if not drawer_previous_notes: drawer_previous_notes = previous_notes[drawer] = []
          drawer_previous_notes.append(previous_note)
          break
        
    saved_duration = {}
    def do_it(notes_data = notes_data):
      for drawer, notes in previous_notes.items():
        drawer.partition.remove(*notes)
        
      new_notes = {}
      for note, drawer, time, string_id, paste_by_string in notes_data:
        new_note = model.Note(drawer.partition, time, note.duration, note.value, note.volume)
        new_note.fx           = note.fx
        new_note.link_fx      = note.link_fx
        new_note.duration_fx  = note.duration_fx
        new_note.strum_dir_fx = note.strum_dir_fx
        if note.bend_pitch: new_note.bend_pitch = note.bend_pitch
        for attr in model.NOTE_ATTRS:
          value = getattr(note, attr)
          if not value is None: setattr(new_note, attr, value)
        
        if not drawer.partition.view.automatic_string_id:
          new_note.string_id = string_id
        if paste_by_string:
          #new_note.value = note.value - note.string_pitch + drawer.strings[string_id].base_note
          note.partition = drawer.partition # required for text_2_value
          new_note.value = drawer.strings[string_id].text_2_value(new_note, note.label)
          
          
        drawer_new_notes = new_notes.get(drawer)
        if not drawer_new_notes: drawer_new_notes = new_notes[drawer] = []
        drawer_new_notes.append(new_note)
        
      self.deselect_all()
      
      for drawer, notes in new_notes.items():
        drawer.partition.add_note(*notes)
        
        for note in notes:
          self.add_selection(note, render = 0, edit = 0, *drawer.note_dimensions(note))
          
        self.auto_update_duration(min(notes), saved_duration)
        self.auto_update_duration(drawer.partition.note_after(max(notes)))
      self.render_all()

    def undo_it(notes = notes):
      new_notes = {}
      for note, drawer, time, string_id, paste_by_string in notes_data:
        drawer_new_notes = new_notes.get(drawer)
        if not drawer_new_notes: drawer_new_notes = new_notes[drawer] = []
        for new_note in drawer.partition.notes_at(time):
          
          if paste_by_string:
            if string_id == drawer.note_string_id(new_note):
              drawer_new_notes.append(new_note)
              break
          else:
            if new_note.value == note.value:
              drawer_new_notes.append(new_note)
              break
            
      for drawer, notes in new_notes.items():
        drawer.partition.remove(*notes)
        
      for drawer, notes in previous_notes.items():
        drawer.partition.add_note(*notes)
        
      self.restore_saved_duration(saved_duration)
      self.render_all()
      
    UndoableOperation(do_it, undo_it, _(u"add %s note(s)") % len(notes), self.main.undo_stack)
    
    
  def on_drag_data_delete(self, widget, drag_context):
    # Some notes int the selection may have been already deleted, if the selection was pasted partly
    # over the selection itself.
    notes = [note for note in self.drag_selections if note.partition and note in note.partition.notes]
    self.delete_notes(notes)


  def round_time_to_current_duration(self, time, delta = 0):
    #duration = min(96, self.current_duration)
    duration = min(ZOOM_2_CLIP_DURATION[self.zoom], self.current_duration)
    
    if duration ==  96:
      if (self.song.mesure_at(time) or self.song.mesures[-1]).rythm2 == 8: duration /= 2
    if duration == 144:
      if (self.song.mesure_at(time) or self.song.mesures[-1]).rythm2 == 4: duration /= 3
    else:
      if duration / 1.5 in model.DURATIONS.keys(): duration /= 3
      
    return max(0, int((delta + (time // duration)) * duration))
    
  def on_key_press(self, obj, event):
    #print dir(event), event.keyval
    keyval = event.keyval
        
    if   keyval == keysyms.Left:
      if self.selections:
        sel = tuple(self.selections)[0]
        time = sel.time
        string_id = self.note_string_id(sel)
        note = sel.partition.note_before_pred(sel, lambda a: self.note_string_id(a) == string_id)
        time0 = self.round_time_to_current_duration(time, -1)
        #time0 = ((time - 1) // self.current_duration) * self.current_duration
        if note and note.time >= time0:
          self.deselect_all()
          self.partition_2_drawer[sel.partition].select_note(note)
        elif time > 0:
          self.deselect_all()
          self.partition_2_drawer[sel.partition].select_at(time0, string_id)
          
    elif keyval == keysyms.Right:
      if self.selections:
        sel = tuple(self.selections)[0]
        time = sel.time
        string_id = self.note_string_id(sel)
        note = sel.partition.note_after_pred(sel, lambda a: self.note_string_id(a) == string_id)
        time0 = self.round_time_to_current_duration(time, 1)
        if note and note.time <= time0:
          self.deselect_all()
          self.partition_2_drawer[sel.partition].select_note(note)
        else:
          self.deselect_all()
          self.partition_2_drawer[sel.partition].select_at(time0, string_id)
          
    elif keyval == keysyms.Up:
      if self.selections:
        sel = tuple(self.selections)[0]
        string_id = self.note_string_id(sel)
        if string_id > 0:
          self.deselect_all()
          self.partition_2_drawer[sel.partition].select_at(sel.time, string_id - 1)
        else:
          i = self.drawers.index(self.partition_2_drawer[sel.partition])
          if i > 0:
            drawer = self.drawers[i - 1]
            if isinstance(drawer, PartitionDrawer):
              self.deselect_all()
              drawer.select_at(sel.time, len(drawer.strings) - 1)
              
    elif keyval == keysyms.Down:
      if self.selections:
        sel = tuple(self.selections)[0]
        string_id = self.note_string_id(sel)
        if string_id < len(self.partition_2_drawer[sel.partition].strings) - 1:
          self.deselect_all()
          self.partition_2_drawer[sel.partition].select_at(sel.time, string_id + 1)
        else:
          i = self.drawers.index(self.partition_2_drawer[sel.partition])
          if i < len(self.drawers) - 1:
            drawer = self.drawers[i + 1]
            if isinstance(drawer, PartitionDrawer):
              self.deselect_all()
              drawer.select_at(sel.time, 0)
              
    elif keyval == keysyms.Home:
      if self.selections:
        note   = list(self.selections)[0]
        drawer = self.partition_2_drawer[note.partition]
        string_id = drawer.note_string_id(note)
        self.deselect_all()
        drawer.select_at(0, string_id)
        
    elif keyval == keysyms.End:
      if self.selections:
        note   = list(self.selections)[0]
        drawer = self.partition_2_drawer[note.partition]
        string_id = drawer.note_string_id(note)
        self.deselect_all()
        drawer.select_at(self.song.mesures[-1].end_time() - self.current_duration, string_id)
        
    elif (keyval == keysyms.slash) or (keyval == keysyms.asterisk) or (keyval == keysyms.colon) or (keyval == keysyms.KP_Divide) or (keyval == keysyms.KP_Multiply): # / or * or :
      if (keyval == keysyms.asterisk) or (keyval == keysyms.KP_Multiply): notes = [note for note in self.selections if note.base_duration() < 384]
      else:                                                               notes = [note for note in self.selections if note.base_duration() > 12 ]
      def decrease_duration(notes = notes):
        for note in notes: self.current_duration = note.duration = note.duration // 2
      def increase_duration(notes = notes):
        for note in notes: self.current_duration = note.duration = note.duration *  2
        
      if (keyval == keysyms.asterisk) or (keyval == keysyms.KP_Multiply): UndoableOperation(increase_duration, decrease_duration, _(u"increase note duration"), self.main.undo_stack)
      else:                                                               UndoableOperation(decrease_duration, increase_duration, _(u"decrease note duration"), self.main.undo_stack)
      
    elif (keyval == keysyms.period) or (keyval == keysyms.KP_Decimal): # .
      self.toggle_dotted()
      
    elif (keyval == keysyms.Delete) or (keyval == keysyms.BackSpace):
      if self.selections: self.delete_notes(self.selections)
      
    else:
      if self.selections:
        drawers = list(set([self.partition_2_drawer[note.partition] for note in self.selections]))
        if len(drawers) == 1:
          if drawers[0].on_key_press(keyval): return
          
      if   (keyval == keysyms.plus) or (keyval == keysyms.KP_Add) or (keyval == keysyms.equal): # + ou =
        self.shift_selections_values(1)
        
      elif (keyval == keysyms.minus) or (keyval == keysyms.KP_Subtract): # -
        self.shift_selections_values(-1)
        
      elif (keysyms._0 <= keyval <= keysyms._9) or (keysyms.KP_0 <= keyval <= keysyms.KP_9): # Numbers
        if keyval <= keysyms._9: nb = keyval - keysyms._0
        else:                    nb = keyval - keysyms.KP_0
        self.previous_text += str(nb)
        self.on_number_typed(self.previous_text)

      elif keyval == keysyms.agrave:
        self.previous_text += "0"
        self.on_number_typed(self.previous_text)

      elif (keyval == keysyms.asciicircum) or (keyval == keysyms.dead_circumflex): # ^
        if self.selections: self.set_selections_strum_dir_fx(u"up")

      elif keyval == keysyms.underscore: # _
        if self.selections: self.set_selections_strum_dir_fx(u"down")

      elif keyval == keysyms.comma: # ,
        if self.selections: self.set_selections_strum_dir_fx(u"down_thumb")

      elif keyval == keysyms.l:
        if self.selections: self.set_selections_link_fx(u"link")

      elif keyval == keysyms.p:
        if self.selections: self.set_selections_duration_fx(u"fermata")

      elif keyval == keysyms.h:
        if self.selections: self.set_selections_fx(u"harmonic")

      elif keyval == keysyms.d:
        if self.selections: self.set_selections_fx(u"dead")

      elif keyval == keysyms.t:
        if self.selections: self.set_selections_fx(u"tremolo")

      elif keyval == keysyms.b:
        if self.selections: self.set_selections_fx(u"bend")

      elif keyval == keysyms.s:
        if self.selections: self.set_selections_link_fx(u"slide")

      elif keyval == keysyms.r:
        if self.selections: self.set_selections_fx(u"roll")

      elif keyval == keysyms.n:
        if self.selections: self.remove_selections_fx()

      elif (keyval == keysyms.Return) or (keyval == keysyms.KP_Enter): # return
        self.toggle_accent()

      elif keyval == keysyms.q:
        self.main.on_close()

      elif keyval == keysyms.space:
        if player.is_playing(): player.stop()
        else: self.main.on_play_from_here()

      elif (keyval == keysyms.v) and (event.state & gtk.gdk.CONTROL_MASK): # C-V
        self.on_note_paste()

      elif (keyval == keysyms.a) and (event.state & gtk.gdk.CONTROL_MASK): # C-A
        self.select_all()

      elif keyval == keysyms.a: # a
        if self.selections: self.set_selections_duration_fx(u"appoggiatura")
        
    return 1
  
  def auto_update_duration(self, note, save = None):
    if globdef.config.AUTOMATIC_DURATION and note:
      previous_notes = note.partition.notes_before(note)

      appo = previous_notes and previous_notes[0].duration_fx == u"appoggiatura"
      for previous_note in previous_notes:
        next = previous_note.partition.note_after(previous_note)
        if not appo:
          while next and next.duration_fx == u"appoggiatura": next = previous_note.partition.note_after(next)
        if next:
          new_duration = int(next.time - previous_note.time)
          if new_duration in model.VALID_DURATIONS:
            if (not save is None) and (not previous_note in save): save[previous_note] = previous_note.duration
            previous_note.duration = new_duration
            
      if appo:
        self.auto_update_duration(previous_notes[0])
        
  def restore_saved_duration(self, save):
    for note, duration in save.items(): note.duration = duration
    save.clear()
    
  def on_number_typed(self, text):
    notes = list(self.selections)
    if notes:
      old_values = [note.value for note in notes]
      
      new_values = []
      for note in notes:
        drawer = self.partition_2_drawer[note.partition]
        new_values.append(drawer.strings[drawer.note_string_id(note)].text_2_value(note, text))
        
      drawer = self.partition_2_drawer[notes[0].partition]
      player.play_note(notes[0].partition.instrument,
                       drawer.strings[drawer.note_string_id(notes[0])].text_2_value(notes[0], text))
      
      saved_duration = {}
      
      def do_it(notes = notes, text = text, saved_duration = saved_duration):
        for i in range(len(notes)):
          if notes[i].value < 0:
            notes[i].partition.add_note(notes[i])
            self.auto_update_duration(notes[i], saved_duration)
          notes[i].value = new_values[i]
          self.auto_update_duration(notes[i].partition.note_after(notes[i]))
      def undo_it(notes = notes, old_values = old_values, saved_duration = saved_duration):
        for i in range(len(notes)):
          new_values[i]  = notes[i].value # new values may have been changed when adding a note by touching the screen and then dragging up or down
          notes[i].value = old_values[i]
          if notes[i].value < 0: notes[i].partition.remove(notes[i])
        self.restore_saved_duration(saved_duration)
      UndoableOperation(do_it, undo_it, _(u"note change"), self.main.undo_stack)
      
  def shift_selections_values(self, d):
      notes      = list(self.selections)
      old_values = [note.value for note in notes]
      def do_it(notes = notes):
        for note in notes:
          drawer = self.partition_2_drawer[note.partition]
          if note.value < 0: note.partition.add_note(note)
          
          current_value = note.value
          note.value = abs(note.value) + d
          while not drawer.note_value_possible(note, note.value):
            if (note.value < 2) or (note.value > 200):
              note.value = current_value
              break
            note.value += d
          if isinstance(drawer, TablatureDrawer) and (note.value < drawer.strings[drawer.note_string_id(note)].base_note):
            note.value = drawer.strings[drawer.note_string_id(note)].base_note
            
        self.main.set_selected_note(self.main.selected_note) # Changed !
        
      def undo_it(notes = notes, old_values = old_values):
        for i in range(len(notes)):
          notes[i].value = old_values[i]
          if notes[i].value < 0: notes[i].partition.remove(notes[i])
          
        self.main.set_selected_note(self.main.selected_note) # Changed !
        
      if d > 0: UndoableOperation(do_it, undo_it, _(u"increase notes pitch"), self.main.undo_stack)
      else:     UndoableOperation(do_it, undo_it, _(u"decrease notes pitch"), self.main.undo_stack)
      
  def set_selections_volume(self, volume):
    if self.selections:
      notes      = list(self.selections)
      old_values = [note.volume for note in notes]
      def do_it(notes = notes):
        for note in notes: note.volume = volume
      def undo_it(notes = notes):
        for i in range(len(notes)): notes[i].volume = old_values[i]
      UndoableOperation(do_it, undo_it, _(u"change of %s") % _(u"volume"), self.main.undo_stack)
      
  def toggle_dotted(self, *args):
    notes      = list(self.selections)
    old_values = [note.duration for note in notes]
    def do_it(notes = notes):
      dotted = not notes[0].is_dotted()
      for note in notes:
        if note.is_dotted() != dotted:
          if dotted: note.duration = int(note.duration * 1.5)
          else:      note.duration = int(note.duration / 1.5)
      self.current_duration = notes[-1].duration
    def undo_it(notes = notes, old_values = old_values):
      for i in range(len(notes)): notes[i].duration = old_values[i]
      self.current_duration = notes[-1].duration

    UndoableOperation(do_it, undo_it, _(u"dotted note"), self.main.undo_stack)
    
  def toggle_triplet(self, *args):
    notes      = list(self.selections)
    old_values = [note.duration for note in notes]
    def do_it(notes = notes):
      triplet = not notes[0].is_triplet()
      for note in notes:
        if note.is_triplet() != triplet:
          if triplet: note.duration = int(note.duration * 2 / 3)
          else:       note.duration = int(note.duration * 3 / 2)
      self.current_duration = notes[-1].duration
    def undo_it(notes = notes, old_values = old_values):
      for i in range(len(notes)): notes[i].duration = old_values[i]
      self.current_duration = notes[-1].duration
      
    UndoableOperation(do_it, undo_it, _(u"triplet note"), self.main.undo_stack)
    
  def toggle_accent(self, *args):
    if self.selections:
      notes = list(self.selections)
      save = {}
      for note in notes: save[note] = note.volume
      def stress(notes = notes):
        for note in notes: note.volume = 255
      def unstress(notes = notes):
        for note in notes: note.volume = 204
      def restore(save = save):
        for note, volume in save.items(): note.volume = volume
      if notes[0].volume == 255: UndoableOperation(unstress, restore, _(u"remove accent"), self.main.undo_stack)
      else:                      UndoableOperation(stress  , restore, _(u"accent"), self.main.undo_stack)
      
  def delete_notes(self, notes):
    if not notes: return
    notes = list(notes)
    if notes == [self.cursor]: return
    
    saved_duration = {}
    def do_it(notes = notes):
      sel = notes[0]
      drawer = self.partition_2_drawer[sel.partition]
      partition_2_notes = {}
      for note in notes:
        l = partition_2_notes.get(note.partition)
        if not l: partition_2_notes[note.partition] = [note]
        else: l.append(note)
        drawer.render_note(note)
      for partition, notes in partition_2_notes.items():
        partition.remove(*notes)
        for note in notes: self.auto_update_duration(note, saved_duration)
      if set(notes) & self.selections:
        self.deselect_all()
        drawer.select_at(sel.time, drawer.note_string_id(sel), 0)
    def undo_it(notes = notes):
      self.deselect_all()
      partition_2_notes = {}
      for note in notes:
        l = partition_2_notes.get(note.partition)
        if not l: partition_2_notes[note.partition] = [note]
        else: l.append(note)
      for partition, notes in partition_2_notes.items():
        partition.add_note(*notes)
        drawer = self.partition_2_drawer[partition]
        for note in notes:
          self.add_selection(note, render = 0, edit = 0, *drawer.note_dimensions(note))
          drawer.render_note(note)
      self.restore_saved_duration(saved_duration)
    UndoableOperation(do_it, undo_it, _(u"delete %s note(s)") % len(notes), self.main.undo_stack)

  def remove_selections_fx(self):
    notes       = list(self.selections)
    old_values  = [(note.fx, note.link_fx, note.duration_fx, note.strum_dir_fx) for note in notes]
    def do_it():
      for note in notes:
        note.set_fx          (u"")
        note.set_link_fx     (u"")
        note.set_duration_fx (u"")
        note.set_strum_dir_fx(u"")
    def undo_it():
      for i in range(len(notes)):
        notes[i].set_fx          (old_values[i][0])
        notes[i].set_link_fx     (old_values[i][1])
        notes[i].set_duration_fx (old_values[i][2])
        notes[i].set_strum_dir_fx(old_values[i][3])
    UndoableOperation(do_it, undo_it, _(u"Remove all effects"), self.main.undo_stack)
    
  def set_selections_fx(self, fx, bend_pitch = None):
    notes      = list(self.selections)
    old_values = [note.fx for note in notes]
    if not bend_pitch is None: old_bend_pitches = [note.bend_pitch for note in notes]
    def do_it():
      if fx == u"bend":
        if (notes[0].fx == fx) and (notes[0].bend_pitch == bend_pitch): new_fx = u""
        else:                                                           new_fx = fx
      else:
        if notes[0].fx == fx: new_fx = u""
        else:                 new_fx = fx
      for note in notes:
        note.set_fx(new_fx)
        if not bend_pitch is None: note.bend_pitch = bend_pitch
    def undo_it():
      for i in range(len(notes)):
        notes[i].set_fx(old_values[i])
        if not bend_pitch is None:
          if old_bend_pitches[i] == 0.0: del notes[i].bend_pitch
          else:                          notes[i].bend_pitch = old_bend_pitches[i]
    UndoableOperation(do_it, undo_it, _(u"set special effect %s") % _(fx), self.main.undo_stack)
    
  def set_selections_link_fx(self, fx, arg = None):
    notes      = list(self.selections)
    old_values = [note.link_fx for note in notes]
    def do_it():
      if notes[0].link_fx == fx: new_fx = u""
      else:                      new_fx = fx
      for note in notes:
        note.set_link_fx(new_fx)
    def undo_it():
      for i in range(len(notes)): notes[i].set_link_fx(old_values[i])
    UndoableOperation(do_it, undo_it, _(u"set special effect %s") % _(fx), self.main.undo_stack)
    
  def set_selections_duration_fx(self, fx, arg = None):
    notes      = list(self.selections)
    old_values = [note.duration_fx for note in notes]
    saved_duration = {}
    def do_it():
      if notes[0].duration_fx == fx: new_fx = u""
      else:                          new_fx = fx
      for note in notes: note.set_duration_fx(new_fx)
      self.auto_update_duration(min(notes), saved_duration)
      last = max(notes)
      self.auto_update_duration(last.partition.note_after(last), saved_duration)
    def undo_it():
      for i in range(len(notes)): notes[i].set_duration_fx(old_values[i])
      self.restore_saved_duration(saved_duration)
    UndoableOperation(do_it, undo_it, _(u"set special effect %s") % _(fx), self.main.undo_stack)
    
  def set_selections_strum_dir_fx(self, fx, arg = None):
    if self.selections:
      notes      = list(self.selections)
      old_values = [note.strum_dir_fx for note in notes]
      def do_it(notes = notes):
        if notes[0].strum_dir_fx == fx: new_fx = u""
        else:                           new_fx = fx
        for note in notes: note.strum_dir_fx = new_fx
      def undo_it(notes = notes):
        for i in range(len(notes)): notes[i].strum_dir_fx = old_values[i]
      UndoableOperation(do_it, undo_it, _(u"set special effect %s") % _(fx), self.main.undo_stack)
      
  def render_pixel(self, x, y, width, height):
    self.canvas.queue_draw_area(int(x), int(y), int(width), int(height))
    
  def render_all(self):
    self.canvas.queue_draw_area(0, 0, self.width, self.height)
    
  def render(self, x, y, width, height):
    self.canvas.queue_draw_area(int(x - self.x), int(y - self.y), int(width), int(height))
    
  def render_selection(self):
    self.canvas.queue_draw_area(int(self.selection_x1 - self.x) - 1, int(self.selection_y1 - self.y) - 1, int(self.selection_x2 - self.selection_x1) + 4, int(self.selection_y2 - self.selection_y1) + 4)
    
  def on_resized(self, obj, allocation):
    x, y, self.width, self.height = self.allocation
    self.canvas.set_size_request(self.width, self.height)
    
  def on_expose(self, obj, event):
    self.draw(event.area.x, event.area.y, event.area.width, event.area.height)
    
    if self.hadjustment.upper - self.hadjustment.lower < self.hadjustment.page_size:
      if self.hadjustment.value != 0: self.hadjustment.value = 0
      
  def draw(self, x, y, width, height):
    self.x = int(self.hadjustment.value)
    self.y = int(self.vadjustment.value)
    
    if self.need_update_selection:
      self.selection_x1     = 1000000
      self.selection_y1     = 1000000
      self.selection_x2     = -1
      self.selection_y2     = -1
      for note in self.selections: self.add_selection(note, render = 0, edit = 0, *self.partition_2_drawer[note.partition].note_dimensions(note))
      self.need_update_selection = 0
      
    if gtk.pygtk_version < (2,7,0): ctx = cairo.gtk.gdk_cairo_create(self.canvas.window)
    else:                           ctx = self.canvas.window.cairo_create()
    
    ctx = pangocairo.CairoContext(ctx)
    self.default_layout = new_layout(ctx, "Sans %s" % (self.default_font_size * self.scale_pango_2_cairo))
    ctx.select_font_face('sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(self.default_font_size)
    
    left, top, self.width, self.height = self.allocation
    
    if self.show_render_zone: ctx.set_source_rgb(1.0, 0.0, 0.0); self.show_render_zone = 0
    else:                     ctx.set_source_rgb(1.0, 1.0, 1.0)
    ctx.rectangle(x, y, width, height)
    ctx.fill()
    
    first_drawer = None
    if not self.drawers: # first time
      self.default_pango_font = pango.FontDescription(u"Sans %s" % (self.default_font_size * self.scale_pango_2_cairo))
      self.default_ascent, self.default_descent, self.default_line_height, max_x_advance, max_y_advance = ctx.font_extents()
      self.char_h_size = self.default_line_height // 2 # XXX
      
      self.drawers = [SongDrawer(self, self.song)]
      for partition in self.song.partitions:
        if   isinstance(partition     , model.Lyrics       ): drawer = LyricsDrawer   (self, partition)
        elif hasattr(partition.view, "get_drawer"):           drawer = partition.view.get_drawer(self)
        elif isinstance(partition.view, model.TablatureView): drawer = TablatureDrawer(self, partition)
        elif isinstance(partition.view, model.StaffView    ): drawer = StaffDrawer    (self, partition)
        elif isinstance(partition.view, model.DrumsView    ): drawer = DrumsDrawer    (self, partition)
        if drawer:
          self.drawers.append(drawer)
          if (not first_drawer) and self.first_time:
            first_drawer = drawer
            self.first_time = 0
      self.update_melody_lyrics()
      for drawer in self.drawers: drawer.drawers_changed()
      
    if self.selection_x2 != -1:
      ctx.save()
      ctx.rectangle(self.start_x - 1, 0, self.width, self.height)
      ctx.clip()
      ctx.set_line_width(2.0)
      draw_round_rect(ctx, self.selection_x1 - self.x, self.selection_y1 - self.y, self.selection_x2 - self.x, self.selection_y2 - self.y, 8)
      ctx.set_source_rgb(*SELECTION_COLOR)
      ctx.fill_preserve()
      if self.canvas.is_focus():
        ctx.set_source_rgb(*SELECTION_COLOR2)
      ctx.stroke()
      ctx.set_line_width(1.0)
      ctx.restore()
      
    dy = -self.y
    total_height = 0
    for drawer in self.drawers:
      drawer.y = dy
      drawer.draw(ctx, x, y, width, height)
      dy           += drawer.height + 10
      total_height += drawer.height + 10
      
    #self.hadjustment.upper          = (self.song.mesures[-1].end_time() + self.song.mesures[-1].duration) * self.zoom
    self.hadjustment.upper          = (self.song.mesures[-1].end_time() + self.song.mesures[-1].duration) * self.zoom + self.mesure_2_extra_x[self.song.mesures[-1]]
    self.hadjustment.page_increment = self.width // 2
    self.hadjustment.page_size      = self.width
    self.vadjustment.upper          = total_height
    self.vadjustment.page_increment = self.height // 2
    self.vadjustment.page_size      = self.height
    
    if first_drawer: first_drawer.select_at(0, 0, 0)
    
    if (total_height <= self.height) and (self.y != 0):
      self.vadjustment.set_value(0)
      self.render_all()
      
  def draw_drag_icon(self, ctx, x, y, width, height):
    _x = self.x
    _y = self.y
    self.x = x
    self.y = y
    
    ctx.set_source_rgb(1.0, 1.0, 1.0)
    ctx.rectangle(0, 0, width, height)
    ctx.fill()
    
    ctx.set_line_width(2.0)
    draw_round_rect(ctx, 1, 1, width - 2, height - 2, 8)
    ctx.set_source_rgb(1.0, 1.0, 1.0)
    ctx.fill_preserve()
    ctx.set_source_rgb(*SELECTION_COLOR2)
    ctx.stroke()
    ctx.set_line_width(1.0)
    
    dy = -self.y
    for drawer in self.drawers:
      ctx.new_path()
      _drawer_y = drawer.y
      drawer.y = dy
      drawer.draw(ctx, 0, dy, width, height, 1)
      drawer.y = _drawer_y
      dy      += drawer.height + 10
      
    self.x = _x
    self.y = _y
    
  def change_zoom(self, incr):
    i = zoom_levels.index(self.zoom) + incr
    if   i < 0:                    i = 0
    elif i > len(zoom_levels) - 1: i = len(zoom_levels) - 1
    self.set_zoom(zoom_levels[i])
    
  def on_before_scroll(self, obj, event):
    if event.state & gtk.gdk.CONTROL_MASK:
      if   (event.direction == gtk.gdk.SCROLL_DOWN) or (event.direction == gtk.gdk.SCROLL_LEFT):
        self.change_zoom(-1)
      else:
        self.change_zoom( 1)
      return 1
    
  def on_scroll(self, obj):
    self.render_pixel(0, 0, self.width, self.height)
    
    
    
class Drawer(object):
  def __init__(self, canvas):
    self.canvas = canvas
    self.y      = 0
    self.height = 0
    self.scale  = canvas.scale
    
  def draw(self, ctx, x, y, width, height, drag = 0):
    return (y < self.y + self.height) and (self.y < y + height)
  
  def destroy(self): pass

  def drawers_changed(self): pass
  
  def config_listener(self, obj, type, new, old): pass
  
class SongDrawer(Drawer):
  def __init__(self, canvas, song):
    Drawer.__init__(self, canvas)
    self.song = song
    self.title_layout   = None
    self.comment_layout = None
    
  def on_button_press(self, event):
    if   event.button == 3:
      self.canvas.context_menu_song.popup(None, None, None, event.button, event.time)
    elif event.type == gtk.gdk._2BUTTON_PRESS:
      self.canvas.main.on_song_prop()

  def draw(self, ctx, x, y, width, height, drag = 0):
    if self.song.authors: title = "%s (%s)" % (self.song.title, self.song.authors)
    else:                 title = self.song.title
    ctx.set_source_rgb(0,0,0)
    
    #ctx.select_font_face('sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    #ctx.set_font_size(self.canvas.default_font_size * 1.2)
    #x_bearing, y_bearing, width, height, x_advance, y_advance = ctx.text_extents(title)
    #draw_text(ctx, title, "Sans bold %s" % int(self.canvas.default_font_size * 1.2))
    #ctx.show_text(title)
    #ctx.set_font_size(self.canvas.default_font_size)
    #ctx.select_font_face('sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    
    if self.title_layout == None:
      self.title_layout = new_layout(ctx, "Sans bold %s" % int(self.canvas.default_font_size * 1.2 * self.canvas.scale_pango_2_cairo))
    self.title_layout.set_text(title)
    width, height = self.title_layout.get_pixel_size()
    ctx.move_to((self.canvas.width - width) / 2, self.y + 10 * self.scale)
    ctx.show_layout(self.title_layout)
    
    if self.song.comments:
      #self.height = draw_multiline_text(ctx, self.song.comments,
      #                                  20 * self.scale,
      #                                  height + 10 * self.scale + self.y,
      #                                  self.canvas.width - 20 * self.scale) + 10 * self.scale - self.y
      if self.comment_layout == None:
        self.comment_layout = new_layout(ctx, "Sans %s" % (self.canvas.default_font_size * self.canvas.scale_pango_2_cairo))
        self.comment_layout.set_wrap(pango.WRAP_WORD)
        
      self.comment_layout.set_width((self.canvas.width - int(20.0 * self.scale)) * pango.SCALE)
      self.comment_layout.set_text(self.song.comments)
      ctx.move_to(20 * self.scale, height + 10 * self.scale + self.y)
      ctx.show_layout(self.comment_layout)
      self.height = height + self.comment_layout.get_pixel_size()[1] + 30 * self.scale
    else:
      self.height = height + 20 * self.scale
      
    return 1
  
  
class PartitionDrawer(Drawer):
  show_header       = 1
  always_draw_stems = 0
  def __init__(self, canvas, partition):
    Drawer.__init__(self, canvas)
    self.partition = partition
    self.start_y   = 15 * self.scale
    self.stem_extra_height = 0
    self.stem_extra_height_bottom = 0
    self.canvas.partition_2_drawer[partition] = self
    self.note_offset_x = 0
    self.note_offset_y = 0
    
  def default_string_id(self, value): return 0
  
  def note_value_possible(self, note, value): return 1

  def mouse_motion_note(self, value, delta): return value + delta
  
  def partition_listener(self, partition, type, new, old): pass
  
  def notes_listener(self, obj, type, new, old):
    for lyrics_drawer in self.associated_lyrics:
      lyrics_drawer.delayed_update_melody()
      
  def note_listener(self, note, type, new, old):
    if type is object:
      if note.duration_fx != old.get("duration_fx", u""):
        for lyrics_drawer in self.associated_lyrics:
          lyrics_drawer.delayed_update_melody()
          
  def y_2_string_id(self, y, force = 0):
    string_id = int((y - self.y - self.stem_extra_height - self.start_y) // self.string_height)
    if not force:
      if   string_id < 0:                     return None
      elif string_id > len(self.strings) - 1: return None
    return string_id
  
  def string_id_2_y(self, string_id):
    return int(self.y + self.start_y + self.stem_extra_height + self.string_height * (string_id + 0.5))

  def on_key_press(self, keyval): return 0
  
  def on_button_press(self, event):
    string_id = self.y_2_string_id(event.y)
    if not string_id is None:
      time = self.canvas.x_2_time(event.x)
      self.select_at(time, string_id)
      
    if event.button == 3:
      self.canvas.context_menu_note.popup(None, None, None, event.button, event.time)
      
  def on_touchscreen_new_note(self, event):
    self.canvas.on_number_typed("0")
    return 1 # OK to change note by dragging up or down
  
  def select_at(self, time, string_id, fix_time = 1):
    if fix_time: time0 = self.canvas.round_time_to_current_duration(time)
    else:        time0 = time

    notes = self.partition.notes_at(time0, time)
    notes = [note for note in notes if self.note_string_id(note) == string_id]
    for note in notes:
      if note.end_time() > time:
        self.select_note(note)
        break
    else:
      for note in notes:
        if note.time == time0:
          self.select_note(note)
          break
      else:
        cursor = self.create_cursor(time0, self.canvas.current_duration, string_id, -self.strings[string_id].base_note)
        while cursor.time >= self.canvas.song.mesures[-1].end_time():
          mesure = self.canvas.song.add_mesure()
          self.canvas.render(self.canvas.time_2_x(mesure.time) - 10.0, 0, mesure.duration * self.canvas.zoom + 20.0, self.canvas.height)
        observe(cursor, self.canvas.note_listener)
        self.canvas.set_cursor(cursor, self)
        self.select_note(cursor)
        self.render_note(cursor)
        
  def destroy(self):
    self.destroy_cursor(render = 0)
    Drawer.destroy(self)

  def create_cursor(self, time, duration, string_id, value):
    cursor          = model.Note(self.partition)
    cursor.time     = time
    cursor.duration = duration
    cursor.value    = value
    #if isinstance(self, TablatureDrawer):
    #  cursor.string_id = string_id
    #if isinstance(self, StaffDrawer):
    #  cursor.value = -(self.strings[string_id].base_note + self.strings[string_id].alteration)
    #else:
    #  cursor.value = -self.strings[string_id].base_note
    return cursor
    
  def destroy_cursor(self, render = 1):
    cursor = self.canvas.cursor
    if cursor:
      unobserve(cursor)
      self.canvas.cursor        = None
      self.canvas.cursor_drawer = None
      if render: self.render_note(cursor)
      if cursor.linked_to: cursor.linked_to._link_from(None)
    
  def select_note(self, note):
    self.canvas.add_selection(note, *self.note_dimensions(note))
    
  def render_note(self, note):
    mesure = self.canvas.song.mesure_at(note)
    if mesure.rythm2 == 8: time1 = (note.link_start() // 144) * 144; time2 = max(note.link_end(), time1 + 144)
    else:                  time1 = (note.link_start() //  96) *  96; time2 = max(note.link_end(), time1 +  96)
    self.canvas.render_pixel(
      self.canvas.time_2_x(time1) - 10.0 * self.scale,
      self.y,
      (time2 - time1) * self.canvas.zoom + 20 * self.scale,
      self.height + self.canvas.default_line_height // 2 + self.canvas.default_ascent // 2,
      )
    
  def note_dimensions(self, note):
    x = self.canvas.time_2_x(note.time)
    y = self.string_id_2_y(self.note_string_id(note)) - self.string_height // 2
    return (
      x,
      y,
      x + max(note.duration * self.canvas.zoom, self.canvas.char_h_size * 1.5),
      y + self.string_height,
      )

  def note_width(self, note):
    return self.canvas.char_h_size * len(self.note_text(note))
  
  def draw_mesure(self, ctx, time, mesure, y, height):
    x       = self.canvas.time_2_x(time)
    if   time == 0:
      bar_x = int(x - 2.0 * self.scale)
      bold  = 1
    elif mesure == None:
      bar_x = int(x + 2.5 * self.scale)
      bold  = 1
    else:
      bar_x = int(x - 2.0 * self.scale)
      bold  = 0
    nheight = height
    symbols = self.partition.song.playlist.symbols.get(mesure)
    if symbols:
      start_repeat = end_repeat = 0
      for symbol in symbols:
        if symbol.startswith(r"\repeat"): start_repeat = 1
        elif (symbol == "} % end repeat") or (symbol == "} % end alternative"): end_repeat = 1
        elif symbol.startswith(r"{ % start alternative"):
          if not((self.canvas.__class__.__name__ == "PSCanvas") and (not isinstance(self, StaffDrawer)) and getattr(self.partition, "print_with_staff_too", 0)):
            alt = symbol[22:]
            ctx.move_to(x + 5 * self.scale, self.y + self.canvas.default_line_height * 0.85)
            ctx.show_text(alt)
            #self.canvas.draw_text_small(ctx, alt, x + 5 * self.scale, self.y + self.canvas.default_line_height * 0.25)
            ctx.move_to(int(x) - 0.5, self.y + 0.5 + 16.0 * self.scale)
            ctx.rel_line_to(0, -16.0 * self.scale)
            ctx.rel_line_to(60 * self.scale, 0)
            ctx.stroke()
      if   start_repeat and end_repeat:
        ctx.arc(x -  7 * self.scale, y + 0.35 * height, 3.0 * self.scale, 0, 2.0 * math.pi); ctx.fill()
        ctx.arc(x -  7 * self.scale, y + 0.65 * height, 3.0 * self.scale, 0, 2.0 * math.pi); ctx.fill()
        ctx.arc(x - 27 * self.scale, y + 0.35 * height, 3.0 * self.scale, 0, 2.0 * math.pi); ctx.fill()
        ctx.arc(x - 27 * self.scale, y + 0.65 * height, 3.0 * self.scale, 0, 2.0 * math.pi); ctx.fill()
        
        ctx.move_to(int(x - 16.0 * self.scale), y)
        ctx.set_line_width(4)
        ctx.rel_line_to(0, nheight)
        ctx.stroke()
        ctx.set_line_width(1)
        ctx.move_to(int(x - 12.0 * self.scale) + 0.5, y)
        ctx.rel_line_to(0, nheight)
        ctx.stroke()
        ctx.move_to(int(x - 20.0 * self.scale) - 0.5, y)
        ctx.rel_line_to(0, nheight)
        ctx.stroke()
        return
      elif start_repeat:
        ctx.arc(x - 6 * self.scale, y + 0.35 * height, 3.0 * self.scale, 0, 2.0 * math.pi); ctx.fill()
        ctx.arc(x - 6 * self.scale, y + 0.65 * height, 3.0 * self.scale, 0, 2.0 * math.pi); ctx.fill()
        
        ctx.move_to(int(x - 15.0 * self.scale), y)
        ctx.set_line_width(4)
        ctx.rel_line_to(0, nheight)
        ctx.stroke()
        ctx.set_line_width(1)
        ctx.move_to(int(x - 11.0 * self.scale) + 0.5, y)
        ctx.rel_line_to(0, nheight)
        ctx.stroke()
        return
      elif end_repeat:
        ctx.arc(x - 14 * self.scale, y + 0.35 * height, 3.0 * self.scale, 0, 2.0 * math.pi); ctx.fill()
        ctx.arc(x - 14 * self.scale, y + 0.65 * height, 3.0 * self.scale, 0, 2.0 * math.pi); ctx.fill()
        
        ctx.move_to(int(x - 3.0 * self.scale), y)
        ctx.set_line_width(4)
        ctx.rel_line_to(0, nheight)
        ctx.stroke()
        ctx.set_line_width(1)
        ctx.move_to(int(x - 7.0 * self.scale) - 0.5, y)
        ctx.rel_line_to(0, nheight)
        ctx.stroke()
        return
      
    if bold:
      ctx.move_to(bar_x, y)
      ctx.set_line_width(4)
      ctx.rel_line_to(0, nheight)
      ctx.stroke()
      ctx.set_line_width(1)
    else:
      ctx.set_line_width(1)
      ctx.move_to(bar_x + 0.5, y)
      ctx.rel_line_to(0, nheight)
      ctx.stroke()
      
  def draw_strings(self, ctx, x, y, width, height):
    string_x  = x
    string_x2 = x + width
    
    if (string_x < string_x2):
      i = 0
      for string in self.strings:
        string_y = self.string_id_2_y(i)
        i += 1
        if y - 2 < string_y < y + height + 2:
          w = string.width()
          if   w == -1: continue
          elif w == 8: pass
          else:
            ctx.set_line_width(1.0); string_y += 0.5
            ctx.set_source_rgb(0.0, 0.0, 0.0)
            ctx.move_to(string_x , string_y)
            ctx.line_to(string_x2, string_y)
            ctx.stroke()
      ctx.set_line_width(1.0)
    
  def draw(self, ctx, x, y, width, height, drag = 0, draw_icon = 1, start_y = 15):
    if x < self.canvas.start_x:
      width = width + x - self.canvas.start_x
      x = self.canvas.start_x
    if not drag:
      if self.show_header:
        self.canvas.draw_text_default(ctx, self.partition.header, 3.0 * self.scale, self.y + 2 * self.scale)
        self.start_y = start_y * self.scale + self.canvas.default_line_height
        #self.start_y = start_y * self.scale + draw_multiline_text(ctx, self.partition.header, 3.0 * self.scale, self.y + 2 * self.scale, self.canvas.width - 20) - self.y
      else:
        self.start_y = start_y * self.scale
        
    self.height = int(self.start_y + self.stem_extra_height + self.string_height * len(self.strings) + self.stem_extra_height_bottom + 1)
    
    if Drawer.draw(self, ctx, x, y, width, height, drag):
      ctx.save()
      if not drag:
        if draw_icon: # Draws the partition icon
          draw_bitmap(self.canvas, ctx,
                      description(self.partition.__class__).icon_filename_for(self.partition),
                      4 * self.scale,
                      int(self.y + self.start_y + self.stem_extra_height + (self.height - self.start_y - self.stem_extra_height - self.stem_extra_height_bottom) // 2 - (editor_gtk.SMALL_ICON_SIZE * self.scale) // 2),
                      0.5 * self.scale)
        
        self.draw_strings(ctx, x, y, width, height)
        
        ctx.rectangle(self.canvas.start_x - 1, 0, self.canvas.width, self.canvas.height)
        ctx.clip()
        
        bar_y      = self.y + self.start_y + self.stem_extra_height + self.string_height * 0.5
        bar_height = self.string_height * (len(self.strings) - 1)
        ctx.set_source_rgb(0, 0, 0)
        for mesure in self.partition.song.mesures:
          if x - 60.0 * self.scale <= self.canvas.time_2_x(mesure.time) <= x + width + 40.0 * self.scale:
            self.draw_mesure(ctx, mesure.time, mesure, bar_y, bar_height)
        if x - 60.0 * self.scale <= self.canvas.time_2_x(mesure.end_time()) <= x + width + 40.0 * self.scale:
          self.draw_mesure(ctx, mesure.end_time(), None, bar_y, bar_height)
          
      time1  = self.canvas.x_2_time(x - self.canvas.start_x)
      time2  = self.canvas.x_2_time(x + width)
      mesure = self.canvas.song.mesure_at(time2)
      if mesure:
        if mesure.rythm2 == 8:
          time1 = (    time1 // 144) * 144
          time2 = (1 + time2 // 144) * 144
        else:
          time1 = (    time1 //  96) *  96
          time2 = (1 + time2 //  96) *  96
          
      notes     = self.partition.notes_at(time1, time2)
      notes_set = set(notes)
      for note in notes:
        while note.linked_from:
          notes_set.add(note.linked_from)
          note = note.linked_from
      notes = list(notes_set)
      notes.sort()
      
      if self.canvas.cursor and (self.canvas.cursor.partition is self.partition):
        if time1 <= self.canvas.cursor <= time2:
          bisect.insort(notes, self.canvas.cursor)
          
      current_time = -1
      previous     = None
      notes_y = {}
      ctx.set_font_size(self.canvas.default_font_size)
      ctx.select_font_face('sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

      chords = []
      if drag and not self.always_draw_stems:
        for note in notes:
          string_id = self.note_string_id(note)
          note_y = notes_y[note] = self.string_id_2_y(string_id)
          ctx.set_source_rgb(0.0, 0.0, 0.0)
          self.draw_note(ctx, note, string_id, note_y)
          
      else:
        for note in notes:
          if note.duration_fx == u"appoggiatura":
            string_id = self.note_string_id(note)
            note_y = notes_y[note] = self.string_id_2_y(string_id)
            self.draw_note(ctx, note, string_id, note_y)
            self.draw_stem_and_beam_for_chord(ctx, [note], { note : note_y }, None, None, 1)
            continue
          
          string_id = self.note_string_id(note)
          note_y = notes_y[note] = self.string_id_2_y(string_id)
          
          if current_time != note.time:
            if (current_time != -1): chords.append(notes_at_time)
            current_time  = note.time
            notes_at_time = []
            
          notes_at_time.append(note)
          
          ctx.set_source_rgb(0.0, 0.0, 0.0)
          self.draw_note(ctx, note, string_id, note_y)
          
        if current_time != -1: chords.append(notes_at_time)
        
        for i in range(0, len(chords)):
          if   i == 0: previous = None
          elif len(chords[i - 1]) == 1: previous = chords[i - 1][0]
          else:
            min_duration = min([note.duration for note in chords[i - 1]])
            for previous in chords[i - 1]:
              if previous.duration == min_duration: break
          if   i == len(chords) - 1: next = None
          elif len(chords[i + 1]) == 1: next = chords[i + 1][0]
          else:
            min_duration = min([note.duration for note in chords[i + 1]])
            for next in chords[i + 1]:
              if next.duration == min_duration: break
          self.draw_stem_and_beam_for_chord(ctx, chords[i], notes_y, previous, next)

      
      ctx.restore()
      
  def draw_stem_and_beam_for_chord(self, ctx, notes, notes_y, previous, next, appo = 0):
    if len(notes) == 1:
      l = notes
    else:
      l = {}
      for note in notes: l[self.note_string_id(note)] = note
      l = l.items()
      l.sort()
      l = [note for (string_id, note) in l]
      
    x = self.canvas.time_2_x(l[0].time)
    
    mesure = self.canvas.song.mesure_at(l[0].time)
    
    if appo:
      y = notes_y[l[ 0]] - self.string_height // 2
      self.draw_stem_and_beam(ctx, x, l[ 0], y - 20 * self.scale, y, mesure, previous, next)
    else:
      self.draw_stem_and_beam(ctx, x, l[ 0], self.y + self.start_y, notes_y[l[ 0]] - self.string_height // 2, mesure, previous, next)
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    self.draw_strum_direction(ctx, notes)
      
  def draw_strum_direction(self, ctx, notes, offset_x = 0.0):
    for note in notes:
      if note.strum_dir_fx:
        x = int(self.canvas.time_2_x(note.time) + self.note_offset_x + offset_x) + 0.5
        if   note.strum_dir_fx == u"up":
          ctx.set_line_width(1)
          ctx.move_to(x, self.y + 10 * self.scale)
          ctx.rel_line_to(4 * self.scale,  12 * self.scale)
          ctx.rel_line_to(4 * self.scale, -12 * self.scale)
          ctx.stroke()
        elif note.strum_dir_fx ==  u"down":
          ctx.set_line_width(1)
          ctx.move_to(x, self.y + 10 * self.scale)
          ctx.rel_line_to(0, 12 * self.scale)
          ctx.stroke()
          ctx.set_line_width(4 * self.scale)
          ctx.move_to(x - 0.5, self.y + 10 * self.scale)
          ctx.rel_line_to(9 * self.scale, 0)
          ctx.stroke()
          ctx.set_line_width(1)
          ctx.move_to(x + 8 * self.scale, self.y + 10 * self.scale)
          ctx.rel_line_to(0,  12 * self.scale)
          ctx.stroke()
        elif note.strum_dir_fx ==  u"down_thumb":
          ctx.set_line_width(1)
          ctx.move_to(x, self.y + 22 * self.scale)
          ctx.rel_line_to(4 * self.scale, -12 * self.scale)
          ctx.rel_line_to(4 * self.scale,  12 * self.scale)
          ctx.stroke()
        return 1
      
  def note_color(self, ctx, note):
    if note.volume == 255:
      ctx.set_source_rgb(0.85, 0.0, 0.0)
    else:
      intensity = 0.7 - min(0.7, 0.7 * note.volume / 204.0)
      ctx.set_source_rgb(intensity, intensity, intensity)
      
  def draw_note(self, ctx, note, string_id, y):
    self.note_color(ctx, note)
    x  = self.canvas.time_2_x(note.time)
    y += self.note_offset_y
    #ctx.move_to(x + 3 * self.scale, y + self.canvas.default_ascent / 2 - self.canvas.default_descent / 2)
    #if note.duration_fx == u"appoggiatura": ctx.set_font_size(int(self.canvas.default_font_size * 0.75))
    #if note.is_dotted():                    ctx.show_text(self.note_text(note) + ".")
    #else:                                   ctx.show_text(self.note_text(note))
    #if note.duration_fx == u"appoggiatura": ctx.set_font_size(self.canvas.default_font_size)
    
    if note.is_dotted(): text = self.note_text(note) + "."
    else:                text = self.note_text(note)
    if note.duration_fx == u"appoggiatura":
      self.canvas.draw_text_at_size(ctx, text,
                                    x + 3.0 * self.scale,
                                    y - 0.35 * self.canvas.default_line_height,
                                    0.75)
    else:
      self.canvas.draw_text_default(ctx, text,
                                    x + 3.0 * self.scale,
                                    y - 0.48 * self.canvas.default_line_height)
      
    if note.fx     : getattr(self, "draw_note_fx_%s" % note.fx     )(ctx, note, string_id)
    if note.link_fx: getattr(self, "draw_note_fx_%s" % note.link_fx)(ctx, note, string_id)
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    
  def draw_note_fx_link(self, ctx, note, string_id):
    if note.linked_from: return
    ax1, ay1, ax2, ay2 = self.note_dimensions(note)
    
    if note.linked_to:
      final_note = note
      lower_y2 = ay2
      while final_note.linked_to:
        final_note = final_note.linked_to
        cx1, cy1, cx2, cy2 = self.note_dimensions(final_note)
        if lower_y2 < cy2: lower_y2 = cy2
      bx1, by1, bx2, by2 = self.note_dimensions(final_note)
      bx1 += self.note_width(note.linked_to)
      lower_y2 = ay2 + (lower_y2 - ay2) * 1.3
    else:
      bx1, by1, bx2, by2 = ax1 + note.duration, ay1, ax2 + note.duration, ay2
      lower_y2 = ay2
      
    ay2 += 4 * self.scale
    by2 += 3 * self.scale
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(2)
    ctx.move_to(ax1 + 2, ay2 - self.canvas.default_descent)
    ctx.curve_to(
      ax1 +  6 * self.scale, lower_y2 - self.canvas.default_descent + 12 * self.scale,
      bx1 -  6 * self.scale, lower_y2 - self.canvas.default_descent + 12 * self.scale,
      bx1 +  0 * self.scale, by2      - self.canvas.default_descent,
      )
    ctx.stroke()
    ctx.set_line_width(1)
    
  def draw_note_fx_slide(self, ctx, note, string_id):
    ax1, ay1, ax2, ay2 = self.note_dimensions(note)
    if note.linked_to: bx1, by1, bx2, by2 = self.note_dimensions(note.linked_to)
    else:              bx1, by1, bx2, by2 = ax1 + note.duration, ay1, ax2 + note.duration, ay2
    bx1 -= 3 * self.scale
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(2)
    ctx.move_to(ax1 + self.note_width(note), (ay1 + ay2) // 2 + self.canvas.default_descent)
    ctx.line_to(bx1 + 2 * self.scale, (by1 + by2) // 2 + self.canvas.default_descent)
    ctx.rel_line_to(-5 * self.scale, -5 * self.scale)
    ctx.rel_move_to( 5 * self.scale,  5 * self.scale)
    ctx.rel_line_to(-5 * self.scale,  5 * self.scale)
    ctx.stroke()
    ctx.set_line_width(1)
    
  def draw_note_fx_bend(self, ctx, note, string_id):
    x1, y1, x2, y2 = self.note_dimensions(note)
    x2 -= 3 * self.scale
    xx = x1 + 3 * self.scale + self.note_width(note)
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(2)
    ctx.move_to(xx, (y1 + y2) // 2 + self.canvas.default_descent)
    dx = min(x2 - x1, self.canvas.char_h_size * 3)
    ctx.rel_curve_to(
       12 * self.scale,  0,
       dx, -self.string_height // 2 + 5 * self.scale,
       dx, -self.string_height // 2,
      )
    ctx.rel_line_to(-5 * self.scale,      self.scale)
    ctx.rel_move_to( 5 * self.scale, -1 * self.scale)
    ctx.rel_line_to(     self.scale,  5 * self.scale)
    ctx.stroke()
    ctx.set_font_size(self.canvas.default_font_size * 0.7)
    ctx.move_to(xx + dx * 0.1, y1 + (y2 - y1) * 0.2)
    ctx.show_text(locale.str(note.bend_pitch))
    ctx.set_font_size(self.canvas.default_font_size)
    ctx.set_line_width(1)
    
  def draw_note_fx_tremolo(self, ctx, note, string_id):
    x1, y1, x2, ty2 = self.note_dimensions(note)
    tx = x1 + self.note_width(note)
    ty1 = (y1 + ty2) // 2 - 1 * self.scale
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(2)
    ctx.move_to(tx, ty1)
    while tx < x2 - 20 * self.scale:
      ctx.curve_to(
        tx + 10 * self.scale, ty1 - 5 * self.scale,
        tx + 10 * self.scale, ty1 + 5 * self.scale,
        tx + 20 * self.scale, ty1,
        )
      tx += 20 * self.scale
    ctx.stroke()
    ctx.set_line_width(1)
    
  def draw_note_fx_dead(self, ctx, note, string_id):
    x1, cy1, x2, cy2 = self.note_dimensions(note)
    anb_char = len(self.note_text(note))
    cx1 = x1
    cx2 = x1 + self.note_width(note)
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1.0)
    ctx.move_to(cx1, cy1)
    ctx.line_to(cx2, cy2)
    ctx.move_to(cx2, cy1)
    ctx.line_to(cx1, cy2)
    ctx.stroke()
    ctx.set_line_width(1)
    
  def draw_note_fx_roll(self, ctx, note, string_id):
    notes = note.chord_notes()
    min_string_id = 99999
    if notes:
      for other in notes:
        other_string_id = self.note_string_id(other)
        if other_string_id >     string_id: return
        if other_string_id < min_string_id: min_string_id = other_string_id
    else:
      min_string_id = self.note_string_id(note) - 1
    x1, y1, x2, y2 = self.note_dimensions(note)
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(2.0)
    ctx.move_to(x1 + self.note_width(note), y2)
    ctx.rel_curve_to(
       7 * self.scale,  0,
      10 * self.scale, -(string_id - min_string_id) * self.string_height + 20,
      10 * self.scale, -(string_id - min_string_id) * self.string_height,
      )
    ctx.rel_line_to(-5 * self.scale,  5 * self.scale)
    ctx.rel_move_to( 5 * self.scale, -5 * self.scale)
    ctx.rel_line_to( 5 * self.scale,  5 * self.scale)
    ctx.stroke()
    ctx.set_line_width(1.0)
    
  def draw_note_fx_harmonic(self, ctx, note, string_id): pass
    
  def _nothing(self, ctx, x, y1, y2, note, previous, next): pass
  _round = _nothing
  
  def _white(self, ctx, x, y1, y2, note, previous, next):
    ctx.set_source_rgb(0.8, 0.8, 0.8)
    ctx.set_line_width(2)
    ctx.move_to(x, y2)
    ctx.line_to(x, y1)
    ctx.stroke()
    ctx.set_line_width(1)
  
  def _black(self, ctx, x, y1, y2, note, previous, next):
    #d = cmp(y2, y1) * 3
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1)
    ctx.move_to(x, y2)
    #ctx.line_to(x, y1 + d)
    ctx.line_to(x, y1)
    ctx.stroke()
  
  def _quarter_appo(self, ctx, x, y1, y2, note, previous, next):
    self._quarter(ctx, x, y1, y2, note, previous, next)
    ctx.move_to(x - 4, y1 + 12)
    ctx.line_to(x + 7, y1)
    ctx.stroke()
    
  def _quarter(self, ctx, x, y1, y2, note, previous, next):
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1)
    ctx.move_to(x, y2)
    ctx.line_to(x, y1)
    ctx.stroke()
    
    dt           = note.time % 96
    has_next     = next     and (next.time + next.duration <= note.time - dt + 96) and (note.time + note.duration == next.time)
    has_previous = previous and (previous.time >= note.time - dt) and (previous.time + previous.duration >= note.time)
    if has_next:
      if note.time + note.duration < note.time - dt + 96:
        ctx.set_line_width(2 * self.scale)
        ctx.move_to(x, y1)
        ctx.line_to(x + note.duration * self.canvas.zoom, y1)
        ctx.stroke()
        ctx.set_line_width(1)
      return
    if has_previous:
      if previous.duration > 48 * 1.5:
        ctx.set_line_width(2 * self.scale)
        ctx.move_to(x, y1)
        ctx.line_to(x - (note.time - previous.time) * self.canvas.zoom, y1)
        ctx.stroke()
        ctx.set_line_width(1)
      return
    # Single
    sens = cmp(y2, y1)
    ctx.move_to(x, y1)
    ctx.curve_to(x + 0               , y1 +  3.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  3.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 14.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 10.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 +  6.0 * sens * self.scale,
                 x                   , y1 +  4.0 * sens * self.scale)
    #ctx.curve_to(x + 3, y1 + sens, x + 7, y1, x + 5, y1 + 14 * sens)
    #ctx.curve_to(x + 7, y1 + 5 * sens, x + 2, y1 + 3 * sens, x    , y1 + 2 * sens)
    ctx.stroke_preserve()
    ctx.fill()
    
  def _hquarter(self, ctx, x, y1, y2, note, previous, next):
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1)
    ctx.move_to(x, y2)
    ctx.line_to(x, y1)
    ctx.stroke()
    
    dt   = note.time % 96
    sens = cmp(y2, y1)
    has_next     = next     and (next.time + next.duration <= note.time - dt + 96) and (note.time + note.duration == next.time)
    has_previous = previous and (previous.time >= note.time - dt) and (previous.time + previous.duration == note.time)
    if has_next:
      if note.time + note.duration < note.time - dt + 96:
        ctx.set_line_width(2)
        ctx.move_to(x, y1)
        ctx.line_to(x + note.duration * self.canvas.zoom, y1)
        ctx.stroke()
        if   (next.duration <= 24 * 1.5):
          ctx.move_to(x, y1 + 3 * sens)
          ctx.line_to(x + note.duration * self.canvas.zoom, y1 + 3 * sens)
          ctx.stroke()
        elif not (has_previous and (previous.duration <= 24 * 1.5)):
          ctx.move_to(x, y1 + 3 * sens)
          ctx.line_to(x + note.duration // 2 * self.canvas.zoom, y1 + 3 * sens)
          ctx.stroke()
        ctx.set_line_width(1)
      return
    if has_previous:
      if (previous.duration > 24 * 1.5): # Else, previous will draw the stem
        ctx.set_line_width(2)
        ctx.move_to(x, y1 + 3 * sens)
        ctx.line_to(x - note.duration // 2 * self.canvas.zoom, y1 + 3 * sens)
        ctx.stroke()
        ctx.set_line_width(1)
      return
    
    # Single
    #ctx.curve_to(x + 3, y1 + sens, x + 7, y1, x + 5, y1 + 14 * sens)
    #ctx.curve_to(x + 7, y1 + 5 * sens, x + 2, y1 + 3 * sens, x, y1 + 2 * sens)
    #ctx.curve_to(x + 3, y1 +  7 * sens, x + 7, y1 +  6 * sens, x + 5, y1 + 20 * sens)
    #ctx.curve_to(x + 7, y1 + 11 * sens, x + 2, y1 +  9 * sens, x, y1 +  8 * sens)
    ctx.move_to(x, y1)
    ctx.curve_to(x + 0               , y1 +  3.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  3.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 14.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 10.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 +  6.0 * sens * self.scale,
                 x                   , y1 +  4.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    ctx.move_to(x, y1 + 6.0 * sens * self.scale)
    ctx.curve_to(x + 0               , y1 +  9.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  9.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 20.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 16.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 12.0 * sens * self.scale,
                 x                   , y1 + 10.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    
  def _hhquarter(self, ctx, x, y1, y2, note, previous, next):
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1)
    ctx.move_to(x, y2)
    ctx.line_to(x, y1)
    ctx.stroke()
    
    dt   = note.time % 96
    sens = cmp(y2, y1)
    has_next     = next     and (next.time + next.duration <= note.time - dt + 96) and (note.time + note.duration == next.time)
    has_previous = previous and (previous.time >= note.time - dt) and (previous.time + previous.duration == note.time)
    if has_next:
      if note.time + note.duration < note.time - dt + 96:
        ctx.set_line_width(2)
        ctx.move_to(x, y1)
        ctx.line_to(x + note.duration * self.canvas.zoom, y1)
        ctx.stroke()
        if (next.duration <= 24 * 1.5):
          ctx.move_to(x, y1 + 3 * sens)
          ctx.line_to(x + note.duration * self.canvas.zoom, y1 + 3 * sens)
          ctx.stroke()
        elif not (has_previous and (previous.duration <= 24 * 1.5)):
          ctx.move_to(x, y1 + 3 * sens)
          ctx.line_to(x + note.duration // 2 * self.canvas.zoom, y1 + 3 * sens)
          ctx.stroke()
        if (next.duration <= 12 * 1.5):
          ctx.move_to(x, y1 + 6 * sens)
          ctx.line_to(x + note.duration * self.canvas.zoom, y1 + 6 * sens)
          ctx.stroke()
        elif not (has_previous and (previous.duration <= 12 * 1.5)):
          ctx.move_to(x, y1 + 6 * sens)
          ctx.line_to(x + note.duration // 2 * self.canvas.zoom, y1 + 6 * sens)
          ctx.stroke()
        ctx.set_line_width(1)
      return
    if has_previous:
      if (previous.duration > 24 * 1.5): # Else, previous will draw the stem
        ctx.set_line_width(2)
        ctx.move_to(x, y1 + 3 * sens)
        ctx.line_to(x - note.duration // 2 * self.canvas.zoom, y1 + 3 * sens)
        ctx.stroke()
        ctx.set_line_width(1)
      if (previous.duration > 12 * 1.5): # Else, previous will draw the stem
        ctx.set_line_width(2)
        ctx.move_to(x, y1 + 6 * sens)
        ctx.line_to(x - note.duration // 2 * self.canvas.zoom, y1 + 6 * sens)
        ctx.stroke()
        ctx.set_line_width(1)
      return

    # Single
    ctx.move_to(x, y1)
    ctx.curve_to(x + 0               , y1 +  3.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  3.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 14.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 10.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 +  6.0 * sens * self.scale,
                 x                   , y1 +  4.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    ctx.move_to(x, y1 + 5.0 * sens * self.scale)
    ctx.curve_to(x + 0               , y1 +  8.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  8.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 19.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 15.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 11.0 * sens * self.scale,
                 x                   , y1 +  9.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    ctx.move_to(x, y1 + 10.0 * sens * self.scale)
    ctx.curve_to(x + 0               , y1 + 13.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 + 13.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 24.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 20.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 16.0 * sens * self.scale,
                 x                   , y1 + 14.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
#    ctx.move_to(x, y1)
#    ctx.curve_to(x + 3, y1 + sens, x + 7, y1, x + 5, y1 + 14 * sens)
#    ctx.curve_to(x + 7, y1 + 5 * sens, x + 2, y1 + 3 * sens, x, y1 + 2 * sens)
#    ctx.curve_to(x + 3, y1 +  7 * sens, x + 7, y1 +  6 * sens, x + 5, y1 + 20 * sens)
#    ctx.curve_to(x + 7, y1 + 11 * sens, x + 2, y1 +  9 * sens, x, y1 +  8 * sens)
#    ctx.curve_to(x + 3, y1 + 13 * sens, x + 7, y1 + 12 * sens, x + 5, y1 + 26 * sens)
#    ctx.curve_to(x + 7, y1 + 17 * sens, x + 2, y1 + 15 * sens, x, y1 + 14 * sens)
#    ctx.fill()
    
  def _black_triplet(self, ctx, x, y1, y2, note, previous, next):
    sens = cmp(y2, y1)
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1)
    ctx.move_to(x, y2)
    ctx.line_to(x, y1 + 3 * sens)
    ctx.stroke()
    
    dt = note.time % 192
    
    if dt == 64:
      if    y2 > y1: ctx.move_to(x - self.canvas.char_h_size // 2, y1 - self.canvas.default_descent)
      else:          ctx.move_to(x - self.canvas.char_h_size // 2, y1 + self.canvas.default_ascent)
      ctx.set_font_size(self.canvas.default_font_size // 2)
      ctx.show_text("3")
      ctx.set_font_size(self.canvas.default_font_size)
      
      ctx.move_to(x - 64 * self.canvas.zoom, y1 + 0.5)
      ctx.line_to(x + 64 * self.canvas.zoom, y1 + 0.5)
      ctx.stroke()
      
  def _quarter_triplet(self, ctx, x, y1, y2, note, previous, next):
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1)
    ctx.move_to(x, y2)
    ctx.line_to(x, y1)
    ctx.stroke()
    
    dt           = note.time % 96
    has_next     = next     and (next.time + next.duration <= note.time - dt + 96) and (note.time + note.duration == next.time)
    has_previous = previous and (previous.time >= note.time - dt) and (previous.time + previous.duration == note.time)
    
    if dt == 32:
      if    y2 > y1: ctx.move_to(x - self.canvas.char_h_size // 2, y1 - self.canvas.default_descent)
      else:          ctx.move_to(x - self.canvas.char_h_size // 2, y1 + self.canvas.default_ascent)
      ctx.set_font_size(self.canvas.default_font_size // 2)
      ctx.show_text("3")
      ctx.set_font_size(self.canvas.default_font_size)
      
    if has_next:
      if note.time + note.duration < note.time - dt + 96:
        ctx.set_line_width(2)
        ctx.move_to(x, y1)
        ctx.line_to(x + note.duration * self.canvas.zoom, y1)
        ctx.stroke()
        ctx.set_line_width(1)
      return
    if has_previous:
      return
    # Single
    sens = cmp(y2, y1)
    ctx.move_to(x, y1)
    ctx.curve_to(x + 0               , y1 +  3.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  3.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 14.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 10.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 +  6.0 * sens * self.scale,
                 x                   , y1 +  4.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    
  def _hquarter_triplet(self, ctx, x, y1, y2, note, previous, next):
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1)
    ctx.move_to(x, y2)
    ctx.line_to(x, y1)
    ctx.stroke()
    
    if (note.time % 48) == 16:
      if    y2 > y1: ctx.move_to(x - self.canvas.char_h_size // 2, y1 - self.canvas.default_descent)
      else:          ctx.move_to(x - self.canvas.char_h_size // 2, y1 + self.canvas.default_ascent)
      ctx.set_font_size(self.canvas.default_font_size // 2)
      ctx.show_text("3")
      ctx.set_font_size(self.canvas.default_font_size)
      
    dt   = note.time % 96
    sens = cmp(y2, y1)
    has_next     = next     and (next.time + next.duration <= note.time - dt + 96) and (note.time + note.duration == next.time)
    has_previous = previous and (previous.time >= note.time - dt) and (previous.time + previous.duration == note.time)
    if has_next:
      if note.time + note.duration < note.time - dt + 96:
        ctx.set_line_width(2)
        ctx.move_to(x, y1)
        ctx.line_to(x + note.duration * self.canvas.zoom, y1)
        ctx.stroke()
        if   (next.duration <= 24 * 1.5):
          ctx.move_to(x, y1 + 3 * sens)
          ctx.line_to(x + note.duration * self.canvas.zoom, y1 + 3 * sens)
          ctx.stroke()
        elif not (has_previous and (previous.duration <= 24 * 1.5)):
          ctx.move_to(x, y1 + 3 * sens)
          ctx.line_to(x + note.duration // 2 * self.canvas.zoom, y1 + 3 * sens)
          ctx.stroke()
        ctx.set_line_width(1)
      return
    if has_previous:
      if (previous.duration > 24 * 1.5): # Else, previous will draw the stem
        ctx.set_line_width(2)
        ctx.move_to(x, y1 + 3 * sens)
        ctx.line_to(x - note.duration // 2 * self.canvas.zoom, y1 + 3 * sens)
        ctx.stroke()
        ctx.set_line_width(1)
      return
    
    # Single
    ctx.move_to(x, y1)
    ctx.curve_to(x + 0               , y1 +  3.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  3.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 14.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 10.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 +  6.0 * sens * self.scale,
                 x                   , y1 +  4.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    ctx.move_to(x, y1 + 6.0 * sens * self.scale)
    ctx.curve_to(x + 0               , y1 +  9.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  9.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 20.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 16.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 12.0 * sens * self.scale,
                 x                   , y1 + 10.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    
  def _hhquarter_triplet(self, ctx, x, y1, y2, note, previous, next):
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1)
    ctx.move_to(x, y2)
    ctx.line_to(x, y1)
    ctx.stroke()
    
    if (note.time % 24) == 8:
      if    y2 > y1: ctx.move_to(x - self.canvas.char_h_size // 2, y1 - self.canvas.default_descent)
      else:          ctx.move_to(x - self.canvas.char_h_size // 2, y1 + self.canvas.default_ascent)
      ctx.set_font_size(self.canvas.default_font_size // 2)
      ctx.show_text("3")
      ctx.set_font_size(self.canvas.default_font_size)
      
    dt   = note.time % 96
    sens = cmp(y2, y1)
    has_next     = next     and (next.time + next.duration <= note.time - dt + 96) and (note.time + note.duration == next.time)
    has_previous = previous and (previous.time >= note.time - dt) and (previous.time + previous.duration == note.time)
    if has_next:
      if note.time + note.duration < note.time - dt + 96:
        ctx.set_line_width(2)
        ctx.move_to(x, y1)
        ctx.line_to(x + note.duration * self.canvas.zoom, y1)
        ctx.stroke()
        if (next.duration <= 24 * 1.5):
          ctx.move_to(x, y1 + 3 * sens)
          ctx.line_to(x + note.duration * self.canvas.zoom, y1 + 3 * sens)
          ctx.stroke()
        elif not (has_previous and (previous.duration <= 24 * 1.5)):
          ctx.move_to(x, y1 + 3 * sens)
          ctx.line_to(x + note.duration // 2 * self.canvas.zoom, y1 + 3 * sens)
          ctx.stroke()
        if (next.duration <= 12 * 1.5):
          ctx.move_to(x, y1 + 6 * sens)
          ctx.line_to(x + note.duration * self.canvas.zoom, y1 + 6 * sens)
          ctx.stroke()
        elif not (has_previous and (previous.duration <= 12 * 1.5)):
          ctx.move_to(x, y1 + 6 * sens)
          ctx.line_to(x + note.duration // 2 * self.canvas.zoom, y1 + 6 * sens)
          ctx.stroke()
        ctx.set_line_width(1)
      return
    if has_previous:
      if (previous.duration > 24 * 1.5): # Else, previous will draw the stem
        ctx.set_line_width(2)
        ctx.move_to(x, y1 + 3 * sens)
        ctx.line_to(x - note.duration // 2 * self.canvas.zoom, y1 + 3 * sens)
        ctx.stroke()
        ctx.set_line_width(1)
      if (previous.duration > 12 * 1.5): # Else, previous will draw the stem
        ctx.set_line_width(2)
        ctx.move_to(x, y1 + 6 * sens)
        ctx.line_to(x - note.duration // 2 * self.canvas.zoom, y1 + 6 * sens)
        ctx.stroke()
        ctx.set_line_width(1)
      return

    # Single
    ctx.move_to(x, y1)
    ctx.curve_to(x + 0               , y1 +  3.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  3.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 14.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 10.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 +  6.0 * sens * self.scale,
                 x                   , y1 +  4.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    ctx.move_to(x, y1 + 5.0 * sens * self.scale)
    ctx.curve_to(x + 0               , y1 +  8.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  8.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 19.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 15.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 11.0 * sens * self.scale,
                 x                   , y1 +  9.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    ctx.move_to(x, y1 + 10.0 * sens * self.scale)
    ctx.curve_to(x + 0               , y1 + 13.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 + 13.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 24.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 20.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 16.0 * sens * self.scale,
                 x                   , y1 + 14.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
  
  def _quarter8(self, ctx, x, y1, y2, note, previous, next):
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1)
    ctx.move_to(x, y2)
    ctx.line_to(x, y1)
    ctx.stroke()
    
    dt           = note.time % 144
    has_next     = next     and (next    .duration <= 48 * 1.5) and (next.time + next.duration <= note.time - dt + 144) and (note.time + note.duration == next.time)
    has_previous = previous and (previous.duration <= 48 * 1.5) and (previous.time >= note.time - dt) and (previous.time + previous.duration == note.time)
    if has_next:
      if note.time + note.duration < note.time - dt + 144:
        ctx.set_line_width(2)
        ctx.move_to(x, y1)
        ctx.line_to(x + note.duration * self.canvas.zoom, y1)
        ctx.stroke()
        ctx.set_line_width(1)
      return
    if has_previous:
      return
    # Single
    sens = cmp(y2, y1)
    ctx.move_to(x, y1)
    ctx.curve_to(x + 0               , y1 +  3.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  3.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 14.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 10.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 +  6.0 * sens * self.scale,
                 x                   , y1 +  4.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    
  def _hquarter8(self, ctx, x, y1, y2, note, previous, next):
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1)
    ctx.move_to(x, y2)
    ctx.line_to(x, y1)
    ctx.stroke()
    
    sens = cmp(y2, y1)
    dt           = note.time % 144
    has_next     = next     and (next    .duration <= 48 * 1.5) and (next.time + next.duration <= note.time - dt + 144) and (note.time + note.duration == next.time)
    has_previous = previous and (previous.duration <= 48 * 1.5) and (previous.time >= note.time - dt) and (previous.time + previous.duration == note.time)
    if has_next:
      if note.time + note.duration < note.time - dt + 144:
        ctx.set_line_width(2)
        ctx.move_to(x, y1)
        ctx.line_to(x + note.duration * self.canvas.zoom, y1)
        ctx.stroke()
        if (next.duration <= 24 * 1.5):
          ctx.move_to(x, y1 + 3 * sens)
          ctx.line_to(x + note.duration * self.canvas.zoom, y1 + 3 * sens)
          ctx.stroke()
        elif not (has_previous and (previous.duration <= 24 * 1.5)):
          ctx.move_to(x, y1 + 3 * sens)
          ctx.line_to(x + note.duration // 2 * self.canvas.zoom, y1 + 3 * sens)
          ctx.stroke()
        ctx.set_line_width(1)
      return
    if has_previous:
      if (previous.duration > 24 * 1.5): # Else, previous will draw the stem
        ctx.set_line_width(2)
        ctx.move_to(x, y1 + 3 * sens)
        ctx.line_to(x - note.duration // 2 * self.canvas.zoom, y1 + 3 * sens)
        ctx.stroke()
        ctx.set_line_width(1)
      return
    
    # Single
    ctx.move_to(x, y1)
    ctx.curve_to(x + 0               , y1 +  3.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  3.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 14.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 10.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 +  6.0 * sens * self.scale,
                 x                   , y1 +  4.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    ctx.move_to(x, y1 + 6.0 * sens * self.scale)
    ctx.curve_to(x + 0               , y1 +  9.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  9.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 20.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 16.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 12.0 * sens * self.scale,
                 x                   , y1 + 10.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
  
  def _hhquarter8(self, ctx, x, y1, y2, note, previous, next):
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1)
    ctx.move_to(x, y2)
    ctx.line_to(x, y1)
    ctx.stroke()
    
    sens = cmp(y2, y1)
    dt           = note.time % 144
    has_next     = next     and (next    .duration <= 48 * 1.5) and (next.time + next.duration <= note.time - dt + 144) and (note.time + note.duration == next.time)
    has_previous = previous and (previous.duration <= 48 * 1.5) and (previous.time >= note.time - dt) and (previous.time + previous.duration == note.time)
    if has_next:
      if note.time + note.duration < note.time - dt + 144:
        ctx.set_line_width(2)
        ctx.move_to(x, y1)
        ctx.line_to(x + note.duration * self.canvas.zoom, y1)
        ctx.stroke()
        if (next.duration <= 24 * 1.5):
          ctx.move_to(x, y1 + 3 * sens)
          ctx.line_to(x + note.duration * self.canvas.zoom, y1 + 3 * sens)
          ctx.stroke()
        elif not (has_previous and (previous.duration <= 24 * 1.5)):
          ctx.move_to(x, y1 + 3 * sens)
          ctx.line_to(x + note.duration // 2 * self.canvas.zoom, y1 + 3 * sens)
          ctx.stroke()
        if (next.duration <= 12 * 1.5):
          ctx.move_to(x, y1 + 6 * sens)
          ctx.line_to(x + note.duration * self.canvas.zoom, y1 + 6 * sens)
          ctx.stroke()
        elif not (has_previous and (previous.duration <= 12 * 1.5)):
          ctx.move_to(x, y1 + 6 * sens)
          ctx.line_to(x + note.duration // 2 * self.canvas.zoom, y1 + 6 * sens)
          ctx.stroke()
        ctx.set_line_width(1)
      return
    if has_previous:
      if (previous.duration > 24 * 1.5): # Else, previous will draw the stem
        ctx.set_line_width(2)
        ctx.move_to(x, y1 + 3 * sens)
        ctx.line_to(x - note.duration // 2 * self.canvas.zoom, y1 + 3 * sens)
        ctx.stroke()
        ctx.set_line_width(1)
      if (previous.duration > 12 * 1.5): # Else, previous will draw the stem
        ctx.set_line_width(2)
        ctx.move_to(x, y1 + 6 * sens)
        ctx.line_to(x - note.duration // 2 * self.canvas.zoom, y1 + 6 * sens)
        ctx.stroke()
        ctx.set_line_width(1)
      return
    
    # Single
    ctx.move_to(x, y1)
    ctx.curve_to(x + 0               , y1 +  3.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  3.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 14.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 10.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 +  6.0 * sens * self.scale,
                 x                   , y1 +  4.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    ctx.move_to(x, y1 + 5.0 * sens * self.scale)
    ctx.curve_to(x + 0               , y1 +  8.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 +  8.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 19.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 15.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 11.0 * sens * self.scale,
                 x                   , y1 +  9.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()
    ctx.move_to(x, y1 + 10.0 * sens * self.scale)
    ctx.curve_to(x + 0               , y1 + 13.0 * sens * self.scale,
                 x + 8.0 * self.scale, y1 + 13.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 24.0 * sens * self.scale)
    ctx.curve_to(x + 7.0 * self.scale, y1 + 20.0 * sens * self.scale,
                 x + 5.0 * self.scale, y1 + 16.0 * sens * self.scale,
                 x                   , y1 + 14.0 * sens * self.scale)
    ctx.stroke_preserve()
    ctx.fill()

    
  _drawers = { # Maps durations to the corresponding drawer function
    576 : _round,
    288 : _white,
    144 : _black,
    72  : _quarter,
    36  : _hquarter,
    18  : _hhquarter,

    384 : _round,
    192 : _white,
    96  : _black,
    48  : _quarter,
    24  : _hquarter,
    12  : _hhquarter,

    64  : _black_triplet,
    32  : _quarter_triplet,
    16  : _hquarter_triplet,
    8   : _hhquarter_triplet,
    }
  _drawers8 = { # Maps durations to the corresponding drawer function for x/8 rythms
    576 : _round,
    288 : _white,
    144 : _black,
    72  : _quarter8,
    36  : _hquarter8,
    18  : _hhquarter8,
    
    384 : _round,
    192 : _white,
    96  : _black,
    48  : _quarter8,
    24  : _hquarter8,
    12  : _hhquarter8,
    
    # Does triplets make sense in 6/8 rythms ???
    64  : _black_triplet,
    32  : _quarter_triplet,
    16  : _hquarter_triplet,
    8   : _hhquarter_triplet,
    }
  
  def draw_stem_and_beam(self, ctx, x, note, y1, y2, mesure = None, previous = None, next = None):
    x = int(x + self.note_offset_x) + 0.5
    if   note.duration_fx == u"appoggiatura": return self._quarter_appo(ctx, x, y1, y2, note, previous, next)
    elif note.duration_fx == u"fermata":      self.draw_fermata(ctx, x)
    elif note.duration_fx == u"breath":       self.draw_breath (ctx, x)
    if mesure and (mesure.rythm2 == 8):       return (PartitionDrawer._drawers8.get(note.duration) or PartitionDrawer._nothing)(self, ctx, x, y1, y2, note, previous, next)
    else:                                     return (PartitionDrawer._drawers .get(note.duration) or PartitionDrawer._nothing)(self, ctx, x, y1, y2, note, previous, next)

  def draw_fermata(self, ctx, x):
    ctx.save() # When draw_fermata, the current color is the one for the stem !
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.arc(x, self.y + 20.0 * self.scale, 2.0 * self.scale, 0, 2.0 * math.pi)
    ctx.fill()
    ctx.arc(x, self.y + 20.0 * self.scale, 10.0 * self.scale, math.pi, 2.0 * math.pi)
    ctx.stroke()
    ctx.set_line_width(2)
    ctx.arc(x, self.y + 20.0 * self.scale, 10.0 * self.scale, 1.25 * math.pi, 1.75 * math.pi)
    ctx.stroke()
    ctx.restore() # Restore color and line width
    

  def draw_breath(self, ctx, x):
    #ctx.save() # When draw_breath, the current color is the one for the stem !
    draw_bitmap(self.canvas, ctx, os.path.join(globdef.DATADIR, "effet_breath.png"), x, self.y + 7.0 * self.scale, 0.18 * self.scale)
    
    #ctx.restore() # Restore color and line width
    
    
    
class TablatureDrawer(PartitionDrawer):
  def __init__(self, canvas, partition):
    PartitionDrawer.__init__(self, canvas, partition)
    self.height = 300
    self.strings = partition.view.strings
    self.string_height = canvas.default_line_height + 2 * self.scale
    self.stem_extra_height = self.string_height
    self.stem_extra_height_bottom = self.string_height * 0.6
    self.note_offset_x = 8.0 * self.scale
    self.drawing_drag_icon = 0
    
  def create_cursor(self, time, duration, string_id, value):
    cursor = PartitionDrawer.create_cursor(self, time, duration, string_id, value)
    cursor.string_id = string_id
    return cursor
  
  def partition_listener(self, partition, type, new, old):
    if type is object:
      if new.get("capo", 0) != old.get("capo", 0):
        self.canvas.render_all()
        
    PartitionDrawer.partition_listener(self, partition, type, new, old)
    
  def mouse_motion_note(self, value, delta): return value + abs(delta)
  
  def note_string_id(self, note): return self.partition.view.note_string_id(note)
  
  def note_text(self, note):
    if note.fx == u"harmonic":
      if note is self.canvas.cursor: return "_♢"
      return self.strings[self.note_string_id(note)].value_2_text(note) + u"♢"
    if note is self.canvas.cursor: return "_"
    return self.strings[self.note_string_id(note)].value_2_text(note)
  
  def note_width(self, note):
    return self.canvas.char_h_size * len(self.note_text(note)) + 6 * self.scale
  
  def draw(self, ctx, x, y, width, height, drag = 0, draw_icon = 1, start_y = 15):
    self.drawing_drag_icon = drag
    return PartitionDrawer.draw(self, ctx, x, y, width, height, drag, draw_icon, start_y)
    
  def draw_note(self, ctx, note, string_id, y):
    x  = self.canvas.time_2_x(note.time)
    y += self.note_offset_y
    xx = x + 3 * self.scale
    yy = y + self.canvas.default_ascent / 2 - self.canvas.default_descent / 2
    if note.duration_fx == u"appoggiatura": ctx.set_font_size(int(self.canvas.default_font_size * 0.75))
    
    text = self.note_text(note)
    if note.is_dotted(): text += u"."
    if (not self.drawing_drag_icon) and (note in self.canvas.selections): ctx.set_source_rgb(*SELECTION_COLOR)
    else:                                                                 ctx.set_source_rgb(1.0, 1.0, 1.0)
    x_bearing, y_bearing, width, height, x_advance, y_advance = ctx.text_extents(text)
    ctx.rectangle(xx + 1, yy + y_bearing, width, height)
    ctx.fill()
    self.note_color(ctx, note)
    ctx.move_to(xx, yy)
    ctx.show_text(text)
    
    #yy = y - self.canvas.default_line_height / 2.0
    #width, height = self.canvas.text_extents_default(text)
    #ctx.rectangle(xx, yy + 1, width, height - 2)
    #ctx.fill()
    #self.note_color(ctx, note)
    #self.canvas.draw_text_default(ctx, text, xx, yy)
    
    if note.duration_fx == u"appoggiatura": ctx.set_font_size(self.canvas.default_font_size)
    
    if note.fx     : getattr(self, "draw_note_fx_%s" % note.fx     )(ctx, note, string_id)
    if note.link_fx: getattr(self, "draw_note_fx_%s" % note.link_fx)(ctx, note, string_id)
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    
  def draw_note_fx_link(self, ctx, note, string_id):
    ax1, ay1, ax2, ay2 = self.note_dimensions(note)
    if note.linked_to: bx1, by1, bx2, by2 = self.note_dimensions(note.linked_to)
    else:              bx1, by1, bx2, by2 = ax1 + note.duration, ay1, ax2 + note.duration, ay2
    anb_char = len(self.note_text(note))
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.set_line_width(1)
    ctx.move_to(ax1 + 5 + self.canvas.char_h_size * anb_char, (ay1 + ay2) // 2 + self.canvas.default_descent)
    ctx.curve_to(
      ax1 + 8 + self.canvas.char_h_size * anb_char, (ay1 + ay2) // 2 + self.canvas.default_descent + 4,
      bx1 - 1                                     , (by1 + by2) // 2 + self.canvas.default_descent + 4,
      bx1 + 2                                     , (by1 + by2) // 2 + self.canvas.default_descent,
      )
    ctx.stroke()
    if note.linked_to:
      if   note.value < note.linked_to.value:
        ctx.move_to((ax1 + self.canvas.char_h_size * anb_char + bx1) // 2, (ay1 + ay2 + by1 + by2) // 4 + self.canvas.default_descent)
        ctx.show_text("h")
      elif note.value > note.linked_to.value:
        ctx.move_to((ax1 + self.canvas.char_h_size * anb_char + bx1) // 2, (ay1 + ay2 + by1 + by2) // 4 + self.canvas.default_descent)
        ctx.show_text("p")
     
#  def draw_stem_and_beam_for_chord(self, ctx, notes, notes_y, previous, next, appo = 0):
#    PartitionDrawer.draw_stem_and_beam_for_chord(self, ctx, notes, notes_y, previous, next)
        
  def draw_strum_direction(self, ctx, notes, offset_x = 0.0):
    return PartitionDrawer.draw_strum_direction(self, ctx, notes, -4.0 * self.scale)
    
class DrumsDrawer(PartitionDrawer):
  def __init__(self, canvas, partition):
    PartitionDrawer.__init__(self, canvas, partition)
    self.height = 300
    self.strings = partition.view.strings
    self.string_height = canvas.default_line_height + 2
    self.stem_extra_height = self.string_height
    
  def mouse_motion_note(self, value, delta): return value
  
  def note_string_id(self, note):
    return self.partition.view.note_string_id(note)
    
  def note_text(self, note):
    if note is self.canvas.cursor: return "_"
    return "O"
  
  def on_touchscreen_new_note(self, event):
    PartitionDrawer.on_touchscreen_new_note(self, event)
    return 0 # No change note by dragging up or down
  
  def draw(self, ctx, x, y, width, height, drag = 0):
    PartitionDrawer.draw(self, ctx, x, y, width, height, drag)
    if not drag:
      ctx.set_source_rgb(0.4, 0.4, 0.4)
      ctx.set_font_size(self.canvas.default_font_size * 0.8)
      for i in range(len(self.strings)):
        ctx.move_to(self.canvas.start_x + 3, self.string_id_2_y(i))
        ctx.show_text(model.DRUM_PATCHES[self.strings[i].base_note])
        
      ctx.set_source_rgb(0.0, 0.0, 0.0)
      ctx.set_font_size(self.canvas.default_font_size)
      
  def draw_stem_and_beam(self, ctx, x, note, y1, y2, mesure = None, previous_time = -32000, next_time = 32000):
    x = x + self.string_height // 2.5
    PartitionDrawer.draw_stem_and_beam(self, ctx, x, note, y1, y2, mesure, previous_time, next_time)


STAFF_STRING_PREVIOUS = { 0 : -1, 2 : 0, 4 : 2, 5 : 4, 7 : 5, 9 :  7, 11 :  9 }
STAFF_STRING_NEXT     = { 0 :  2, 2 : 4, 4 : 5, 5 : 7, 7 : 9, 9 : 11, 11 : 12 }

class StaffDrawer(PartitionDrawer):
  def __init__(self, canvas, partition, compact = 0):
    PartitionDrawer.__init__(self, canvas, partition)
    self.compact = compact
    if compact:
      self.string_height     = canvas.default_line_height / 3.5
      self.stem_extra_height =  5 * self.scale + self.string_height
    else:
      self.string_height     = int(canvas.default_line_height / 2.5)
      self.stem_extra_height = 15 * self.scale + self.string_height
      
    self.stem_extra_height_bottom =  3 * self.scale + self.string_height
    self.height         = 300
    self.strings        = []
    self.value_2_string = {}
    string_values_and_line_styles = []
    
    g_key = getattr(self.partition, "g_key", 1)
    f_key = getattr(self.partition, "f_key", 0)
    if g_key or (not f_key):
      #string_values_and_line_styles += [(67, 0, 0), (65, 2, 0), (64, 0, 0), (62, 2, 0), (60, 0, 0), (59, 2, 0), (57, 0, 0), (55, 2, 0), (53, 0, 0), (52, 2, 0), (50, 0, 0)]
      #if f_key: string_values_and_line_styles += [(48, 1, 1)]
      string_values_and_line_styles += [(79, 0, 0), (77, 2, 0), (76, 0, 0), (74, 2, 0), (72, 0, 0), (71, 2, 0), (69, 0, 0), (67, 2, 0), (65, 0, 0), (64, 2, 0), (62, 0, 0)]
      #if f_key: string_values_and_line_styles += [(60, 1, 1), (59, 0, 1), (57, 1, 1), (55, 0, 1), (53, 0, -1), (52, 1, -1), (50, 0, -1), (48, 1, -1)]
      if f_key: string_values_and_line_styles += [(60, 1, 1)]
    if f_key:
      #string_values_and_line_styles += [(47, 0, 0), (45, 2, 0), (43, 0, 0), (41, 2, 0), (40, 0, 0), (38, 2, 0), (36, 0, 0), (35, 2, 0), (33, 0, 0), (31, 2, 0), (29, 0, 0)]
      string_values_and_line_styles += [(59, 0, 0), (57, 2, 0), (55, 0, 0), (53, 2, 0), (52, 0, 0), (50, 2, 0), (48, 0, 0), (47, 2, 0), (45, 0, 0), (43, 2, 0), (41, 0, 0)]
      
    if getattr(partition, "g8", 0):
      string_values_and_line_styles = [(v - 12, d, p) for (v, d, p) in string_values_and_line_styles]

    alterations = model.TONALITIES[partition.tonality]
    if alterations:
      if alterations[0] == model.DIESES[0]: self.alteration_type =  1 # diese
      else:                                 self.alteration_type = -1 # bemol
    else:                                   self.alteration_type =  0
    self.alterations  = set(alterations)
    alterations2      = set(alterations)
    
    for note_value, line_style, pos in string_values_and_line_styles:
      alteration      = 0
      draw_alteration = 0
      if (note_value % 12) in self.alterations:
        alteration = self.alteration_type
        if (note_value % 12) in alterations2:
          alterations2.remove(note_value % 12)
          draw_alteration = 1
      StaffString(self, note_value, line_style, alteration, draw_alteration, pos)
    self._sort_strings()
    
  def create_cursor(self, time, duration, string_id, value):
    return PartitionDrawer.create_cursor(self, time, duration, string_id, value - self.strings[string_id].alteration)
  
  def mouse_motion_note(self, value, delta):
    v = value + delta
    unaltered_value, alteration = model.TONALITY_NOTES[self.partition.tonality][v % 12]
    string = self.get_string(v - alteration)
    return string.base_note + string.alteration
  
  def get_orig_string(self, value):
    if getattr(self.partition, "g8", 0): value -= 12
    return self.value_2_string[value + offset]
    
  def get_orig_string_by_pos(self, pos, key = u""):
    if not key:
      if   self.partition.g_key: key = u"g"
      elif self.partition.f_key: key = u"f"
      else:                      key = u"g"
    #if   key == u"g": value = (65, 62, 59, 55, 52)[pos]
    #elif key == u"f": value = (45, 41, 38, 35, 31)[pos]
    if   key == u"g": value = (77, 74, 71, 67, 64)[pos]
    elif key == u"f": value = (57, 53, 50, 47, 43)[pos]
    if getattr(self.partition, "g8", 0): value -= 12
    return self.value_2_string[value]
    
  def partition_listener(self, partition, type, new, old):
    if (old["g_key"] != new["g_key"]) or (old["f_key"] != new["f_key"]): # Key changed
      self.__init__(self.canvas, self.partition, self.compact)
      self.canvas.render_all()
      
    PartitionDrawer.partition_listener(self, partition, type, new, old)
    
  def draw_strings(self, ctx, x, y, width, height):
    if getattr(self.partition, "g8", 0): offset = -12
    else:                                offset =  0
    scale = self.string_height * 2.5 / 14.6666666667
    
    if self.partition.g_key:
      key_y = int(self.string_id_2_y(self.get_orig_string_by_pos(3).id) - 120.0 * scale * 0.4)
      draw_bitmap(self.canvas, ctx, os.path.join(globdef.DATADIR, "clef_de_sol2.png"), 2, key_y, scale * 0.4)
      if self.partition.g8:
        ctx.move_to(26.0 * self.scale, key_y + 13.0 * self.string_height)
        ctx.show_text(u"8")
        
    if self.partition.f_key:
      draw_bitmap(self.canvas, ctx,
                  os.path.join(globdef.DATADIR, "clef_de_fa2.png"),
                  2,
                  int(self.string_id_2_y(self.get_orig_string_by_pos(1, "f").id) - 29.0 * scale * .4),
                  scale * 0.4)
      
    PartitionDrawer.draw_strings(self, ctx, 0, y, width + x, height)
    
  def draw(self, ctx, x, y, width, height, drag = 0):
    PartitionDrawer.draw(self, ctx, x, y, width, height, drag, 0)
    if not drag:
      if len(self.canvas.song.mesures) > 1: mesure = self.canvas.song.mesures[1]
      else:                                 mesure = self.canvas.song.mesures[0]
      font_size = self.string_height * 2.3 * 2
      ctx.select_font_face('serif', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
      t = unicode(mesure.rythm1)
      if len(t) == 1:
        ctx.set_font_size(font_size)
        ctx.move_to(self.canvas.start_x - self.string_height * 3.4, self.string_id_2_y(self.get_orig_string_by_pos(2).id) - self.string_height / 5)
        ctx.show_text(t)
      else:
        ctx.set_font_size(font_size * 0.7)
        ctx.move_to(self.canvas.start_x - self.string_height * 4.4, self.string_id_2_y(self.get_orig_string_by_pos(2).id) - self.string_height / 2)
        ctx.show_text(t)
        ctx.set_font_size(font_size)
      ctx.move_to(self.canvas.start_x - self.string_height * 3.4, self.string_id_2_y(self.get_orig_string_by_pos(4).id) - self.string_height / 5)
      ctx.show_text(unicode(mesure.rythm2))
      ctx.select_font_face('sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
      ctx.set_font_size(self.canvas.default_font_size)
      
      y = self.y + self.start_y + self.stem_extra_height + self.string_height * 0.38
      for string in self.strings:
        y += self.string_height
        if string.draw_alteration:
          if string.alteration == -1:
            #ctx.move_to(self.canvas.start_x * 0.5 + self.canvas.char_h_size * 0.35 * model.BEMOLS.index(string.base_note % 12), y - self.string_height * 0.4)
            #ctx.show_text(u"♭")
            self.canvas.draw_text_default(ctx, u"♭",
                                          self.canvas.start_x * 0.5 + self.canvas.char_h_size * 0.35 * model.BEMOLS.index(string.base_note % 12),
                                          y - 18.0 * self.canvas.scale)
          else:
            #ctx.move_to(self.canvas.start_x * 0.5 + self.canvas.char_h_size * 0.35 * model.DIESES.index(string.base_note % 12), y)
            #ctx.show_text(u"♯")
            self.canvas.draw_text_default(ctx, u"♯",
                                          self.canvas.start_x * 0.5 + self.canvas.char_h_size * 0.35 * model.DIESES.index(string.base_note % 12),
                                          y - 15.0 * self.canvas.scale)
            
      if self.compact: self.draw_pauses(ctx, x, width)
      
  def _sort_strings(self):
    self.strings.sort(lambda a, b: cmp(b.base_note, a.base_note))
    for i, string in enumerate(self.strings): string.id = i
    self.mesure_ys = []
    
  def get_string(self, note_value, create = 1):
    if note_value > self.strings[0].base_note:
      if create:
        new_string_value = STAFF_STRING_NEXT[self.strings[0].base_note % 12] + (self.strings[0].base_note // 12) * 12
        if self.strings[0].line_style == 0: new_string_line_style = 1
        else:                               new_string_line_style = 0
        if (new_string_value % 12) in self.alterations: alteration = self.alteration_type
        else:                                           alteration = 0
        string = StaffString(self, new_string_value, new_string_line_style, alteration, 0, -1)
        self._sort_strings()
        self.canvas.render_all()
        return self.get_string(note_value, create)
      else:
        return None
      
    string = self.value_2_string.get(note_value)
    if string: return string
    
    if create:
      new_string_value = STAFF_STRING_PREVIOUS[self.strings[-1].base_note % 12] + (self.strings[-1].base_note // 12) * 12
      if self.strings[-1].line_style == 0: new_string_line_style = 1
      else:                                new_string_line_style = 0
      if (new_string_value % 12) in self.alterations: alteration = self.alteration_type
      else:                                           alteration = 0
      string = StaffString(self, new_string_value, new_string_line_style, alteration, 0, 1)
      self._sort_strings()
      self.canvas.render_all()
      return self.get_string(note_value, create)
    
  def note_string_id(self, note):
    unaltered_value, alteration = note.unaltered_value_and_alteration()
    return self.get_string(unaltered_value, 1).id
  
  def note_text(self, note):
    if note is self.canvas.cursor: return "-"
    return self.get_string(note.unaltered_value_and_alteration()[0]).value_2_text(note)
  
  def note_dimensions(self, note):
    string_id = self.note_string_id(note)
    x = self.canvas.time_2_x(note.time)
    y = self.string_id_2_y(string_id) - self.string_height
    return (
      x,
      y,
      x + max(note.duration * self.canvas.zoom, self.string_height * 2.5),
      y + self.string_height * 2,
      )
  
  def note_width(self, note):
    if note.duration_fx == u"appoggiatura": return 1.4 * self.string_height
    return 2.5 * self.string_height
  
  def note_previous(self, note):
    string_id = self.note_string_id(note)
    while 1:
      note = note.previous()
      if not note: return None
      if self.note_string_id(note) == string_id: return note
      
  def render_note(self, note):
    mesure = self.canvas.song.mesure_at(note)
    if mesure.rythm2 == 8: time1 = (note.link_start() // 144) * 144; time2 = max(note.link_end(), time1 + 144)
    else:                  time1 = (note.link_start() //  96) *  96; time2 = max(note.link_end(), time1 +  96)
    
    # Required for updating sharp / natural / flat symbol correctly
    if self.partition.notes:
      time2 = max(time2, self.partition.notes[-1].end_time())
      
    extra_width = 15.0 * self.scale # for # and b
    self.canvas.render_pixel(
      self.canvas.time_2_x(time1) - extra_width,
      self.y,
      (time2 - time1) * self.canvas.zoom + 10 * self.scale + extra_width,
      self.height,
      )
    
  def calc_mesure_ys(self):
    self.mesure_ys = []
    if self.partition.g_key:
      y1 = self.string_id_2_y(self.strings.index(self.get_orig_string_by_pos(0, u"g")))
      y2 = self.string_id_2_y(self.strings.index(self.get_orig_string_by_pos(4, u"g")))
      self.mesure_ys.append((y1 - self.y, y2 - y1))
    if self.partition.f_key:
      y1 = self.string_id_2_y(self.strings.index(self.get_orig_string_by_pos(0, u"f")))
      y2 = self.string_id_2_y(self.strings.index(self.get_orig_string_by_pos(4, u"f")))
      self.mesure_ys.append((y1 - self.y, y2 - y1))
      
  def draw_mesure(self, ctx, time, mesure, y, height):
    if not self.mesure_ys:
      if self.partition.g_key:
        y1 = self.string_id_2_y(self.strings.index(self.get_orig_string_by_pos(0, u"g")))
        y2 = self.string_id_2_y(self.strings.index(self.get_orig_string_by_pos(4, u"g")))
        self.mesure_ys.append((y1 - self.y, y2 - y1))
      if self.partition.f_key:
        y1 = self.string_id_2_y(self.strings.index(self.get_orig_string_by_pos(0, u"f")))
        y2 = self.string_id_2_y(self.strings.index(self.get_orig_string_by_pos(4, u"f")))
        self.mesure_ys.append((y1 - self.y, y2 - y1))
        
    for y, height in self.mesure_ys:
      PartitionDrawer.draw_mesure(self, ctx, time, mesure, self.y + y, height)
      
  def draw_note(self, ctx, note, string_id, y):
    x      = self.canvas.time_2_x(note.time)
    string = self.strings[string_id]
    
    if string.pos != 0:
      i = string_id
      ctx.set_line_width(0.6)
      while self.strings[i].pos != 0:
        if self.strings[i].line_style > 0:
          ctx.move_to(x - 3, self.string_id_2_y(i) + .3)
          ctx.rel_line_to(19.0 * self.scale, 0.0)
          ctx.stroke()
        i -= string.pos
      ctx.set_line_width(1.0)
      
    if   note.fx == "harmonic":
      ctx.move_to(x + 2.5, y + 0.5)
      ctx.rel_line_to( 5.0,  5.0)
      ctx.rel_line_to( 5.0, -5.0)
      ctx.rel_line_to(-5.0, -5.0)
      ctx.rel_line_to(-5.0,  5.0)
      
      ctx.stroke_preserve()
      if not note.base_duration() in (192, 384): ctx.fill()
      
    elif note.fx != "dead":
      ctx.translate(x + self.string_height * 1.3, y + 0.5)
      ctx.rotate(-0.3)
      ctx.scale(1.0, 0.7)
      if note.value < 0: ctx.set_source_rgb(0.7, 0.7, 0.7)
      else: self.note_color(ctx, note)
      
      white = note.base_duration() in (192, 384)
      if note.duration_fx == u"appoggiatura":
        # White appoggiatura should never exist !
        ctx.arc(1.65, 0, 3.5 * self.string_height / 6.0, 0, 2.0 * math.pi)
        ctx.fill()
      else:
        if white:
          ctx.arc(0, 0, 6.5 * self.string_height / 6.0 - 1, 0, 2.0 * math.pi)
          ctx.set_line_width(2.0)
          ctx.stroke()
          ctx.set_line_width(1.0)
        else:
          ctx.arc(0, 0, 6.5 * self.string_height / 6.0, 0, 2.0 * math.pi)
          ctx.fill()
      ctx.identity_matrix()
      
    alteration = abs(note.value) - string.base_note
    
    previous = self.note_previous(note)
    if previous:
      previous_alteration = abs(previous.value) - string.base_note
      if self.partition.song.mesure_at(previous) is not self.partition.song.mesure_at(note):
        if previous_alteration != string.alteration:
          previous_alteration = -99 # force the drawing of the alteration mark
    else:
      previous_alteration = string.alteration
      
    if alteration != previous_alteration:
      ctx.move_to(x - self.canvas.char_h_size, y + self.string_height)
      #if   alteration == -2: ctx.show_text(u"♭♭")
      #elif alteration == -1: ctx.show_text(u"♭")
      #elif alteration ==  0: ctx.show_text(u"♮")
      #elif alteration ==  1: ctx.show_text(u"♯")
      #elif alteration ==  2: ctx.show_text(u"♯♯")
      
      if   alteration == -2: t = u"♭♭"
      elif alteration == -1: t = u"♭"
      elif alteration ==  0: t = u"♮"
      elif alteration ==  1: t = u"♯"
      elif alteration ==  2: t = u"♯♯"
      self.canvas.draw_text_default(ctx, t,
                                    x - self.canvas.char_h_size,
                                    y - self.string_height * 1.2)
      
      ctx.new_path()
      
    if note.is_dotted():
      ctx.arc(x + 15 * self.scale, y + self.string_height / 2 + 2 * self.scale, 1.5 * self.scale, 0, 2.0 * math.pi)
      ctx.fill()
      
    if note.fx     : getattr(self, "draw_note_fx_%s" % note.fx     )(ctx, note, string_id)
    if note.link_fx: getattr(self, "draw_note_fx_%s" % note.link_fx)(ctx, note, string_id)
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    
  def draw_stem_and_beam(self, ctx, x, note, y1, y2, mesure = None, previous_time = -32000, next_time = 32000):
    if note.duration_fx == u"appoggiatura": x  += int(2.05  * self.string_height)
    else:                                   x  += int(2.34 * self.string_height)
    if note.duration_fx == u"fermata": self.draw_fermata(ctx, x)
    y2 += self.string_height // 2
    PartitionDrawer.draw_stem_and_beam(self, ctx, x, note, y1, y2, mesure, previous_time, next_time)
    
  def draw_strum_direction(self, ctx, notes, offset_x = 0.0):
    return PartitionDrawer.draw_strum_direction(self, ctx, notes, 4.0 * self.scale)
    
  def draw_pauses(self, ctx, x, width):
    t1 = max(0, self.canvas.x_2_time(x))
    t2 = max(0, self.canvas.x_2_time(x + width))
    
    import bisect
    mesure_id = bisect.bisect_right(self.partition.song.mesures, t1) - 1
    mesure = self.partition.song.mesures[mesure_id]
    t = mesure.time

    bitmap_scale = self.string_height / 30.0
    
    def advance_t(old_t, t):
      new_t = t
      for note2 in self.partition.notes_at(old_t, t):
        if new_t < note2.end_time(): new_t = note2.end_time()
      if new_t != t:
        return advance_t(t, new_t)
      return new_t
    
    
    def draw_pause(mesure, t1, t2):
      if t1 == t2: return
      t = t1 - mesure.time
      if t % 96 == 0:
        if t2 >= t1 + 384:
          ctx.rectangle(self.canvas.time_2_x((t1 + t2) // 2) - 10, self.string_id_2_y(self.get_orig_string_by_pos(1).id), 20, 5)
          ctx.fill()
          if (t1 == mesure.time) and (t2 == mesure.end_time()): return
          return draw_pause(mesure, t1 + 384, t2)
        
        if t2 >= t1 + 192:
          ctx.rectangle(self.canvas.time_2_x((t1 + t2) // 2) - 9, self.string_id_2_y(self.get_orig_string_by_pos(2).id) - 5, 18, 5)
          ctx.fill()
          return draw_pause(mesure, t1 + 192, t2)
        
      if t2 >= t1 + 144:
        x = self.canvas.time_2_x(t1) + 2
        y = self.string_id_2_y(self.get_orig_string_by_pos(0).id) + self.string_height
        draw_bitmap(self.canvas, ctx, os.path.join(globdef.DATADIR, "rest_96.png"), x, y, bitmap_scale)
        ctx.arc(x + 15, y + 20, 2.0, 0, 2.0 * math.pi)
        ctx.fill()
        return draw_pause(mesure, t1 + 144, t2)
      
      if t2 >= t1 + 96:
        draw_bitmap(self.canvas, ctx,
                    os.path.join(globdef.DATADIR, "rest_96.png"),
                    self.canvas.time_2_x(t1) + 2,
                    self.string_id_2_y(self.get_orig_string_by_pos(0).id) + self.string_height,
                    bitmap_scale)
        return draw_pause(mesure, t1 + 96, t2)
      
      if t2 >= t1 + 72:
        x = self.canvas.time_2_x(t1) + 2
        y = self.string_id_2_y(self.get_orig_string_by_pos(0).id) + 2.5 * self.string_height
        draw_bitmap(self.canvas, ctx, os.path.join(globdef.DATADIR, "rest_48.png"), x, y, bitmap_scale)
        ctx.arc(x + 13, y + 16, 1.5, 0, 2.0 * math.pi)
        ctx.fill()
        return draw_pause(mesure, t1 + 72, t2)

      if t2 >= t1 + 48:
        draw_bitmap(self.canvas, ctx,
                    os.path.join(globdef.DATADIR, "rest_48.png"),
                    self.canvas.time_2_x(t1) + 2,
                    self.string_id_2_y(self.get_orig_string_by_pos(0).id) + 2.5 * self.string_height,
                    bitmap_scale)
        return draw_pause(mesure, t1 + 48, t2)

      if t2 >= t1 + 36:
        x = self.canvas.time_2_x(t1) + 2
        y = self.string_id_2_y(self.get_orig_string_by_pos(0).id) + 2.5 * self.string_height
        draw_bitmap(self.canvas, ctx, os.path.join(globdef.DATADIR, "rest_24.png"), x, y, bitmap_scale)
        ctx.arc(x + 11, y + 16, 1.5, 0, 2.0 * math.pi)
        ctx.fill()
        return draw_pause(mesure, t1 + 36, t2)

      if t2 >= t1 + 24:
        draw_bitmap(self.canvas, ctx,
                    os.path.join(globdef.DATADIR, "rest_24.png"),
                    self.canvas.time_2_x(t1) + 2,
                    self.string_id_2_y(self.get_orig_string_by_pos(0).id) + 2.5 * self.string_height,
                    bitmap_scale)
        return draw_pause(mesure, t1 + 24, t2)

      if t2 >= t1 + 18:
        x = self.canvas.time_2_x(t1) + 2
        y = self.string_id_2_y(self.get_orig_string_by_pos(0).id) + 2.5 * self.string_height
        ctx.arc(x + 9, y + 16, 1.5, 0, 2.0 * math.pi)
        ctx.fill()
        draw_bitmap(self.canvas, ctx, os.path.join(globdef.DATADIR, "rest_12.png"), x, y, bitmap_scale)
        return draw_pause(mesure, t1 + 18, t2)
      
      if t2 >= t1 + 12:
        draw_bitmap(self.canvas, ctx,
                    os.path.join(globdef.DATADIR, "rest_12.png"),
                    self.canvas.time_2_x(t1) + 2,
                    self.string_id_2_y(self.get_orig_string_by_pos(0).id) + 2.5 * self.string_height,
                    bitmap_scale)
        return draw_pause(mesure, t1 + 12, t2)
        
    while mesure.time < t2:
      while t < mesure.end_time():
        note = self.partition.note_before(t + 1)
        if note and (t < note.end_time()):
          t = advance_t(t, note.end_time())
          
        end_pause = mesure.end_time()
        next = self.partition.note_after(t)
        if next and (end_pause > next.time): end_pause = next.time
        if end_pause > t:
          draw_pause(mesure, t, end_pause)
          t = end_pause
          
      mesure_id += 1
      if mesure_id >= len(self.partition.song.mesures): break
      mesure = self.partition.song.mesures[mesure_id]
      
      
      
class StaffString(object):
  def __init__(self, drawer, base_note, line_style, alteration, draw_alteration, pos):
    self.drawer              = drawer
    self.base_note           = base_note
    self.line_style          = line_style
    self.alteration          = alteration
    self.draw_alteration     = draw_alteration
    self.pos                 = pos
    
    drawer.value_2_string[base_note] = self
    drawer.strings.append(self)
    
  def value_2_text(self, note):        return u"o"
  def text_2_value(self, note, text):  return self.base_note + self.alteration
  
  def __unicode__(self): return _(self.__class__.__name__) % note_label(self.base_note, 1)
  
  def width(self):
    if   self.line_style == 0: return -1
    elif self.line_style == 1: return 8
    return 9
  

class LyricsDrawer(Drawer):
  def __init__(self, canvas, lyrics):
    Drawer.__init__(self, canvas)
    
    self.last_undoable = None
    self.lyrics  = lyrics
    self.x0      = canvas.start_x + 2
    self.start_y = 0
    self.melody  = None
    self.timeout_set_text_size = None
    self.timeout_update_melody = None
    self.text    = gtk.TextView()
    self.text.get_buffer().set_text(lyrics.text)
    self.update_melody()
    self.canvas.partition_2_drawer[lyrics] = self
    
    self.fixed = gtk.Fixed()
    self.fixed.set_has_window(1)
    self.fixed.connect("button_press_event", self.on_button_press)
    self.fixed.put(self.text, 0, 1)
    canvas.put(self.fixed, canvas.start_x + 2, 0)
    
    self.text.modify_font(pango.FontDescription("Sans %s" % (self.canvas.default_font_size / pangocairo.cairo_font_map_get_default().get_resolution() * 72.0)))
    self.text.connect("focus-in-event" , self.on_text_focus)
    self.text.connect("key_press_event", self.on_text_key_press)
    self.text.connect_after("move_cursor"    , self.on_move_cursor)
    self.text_changed_handler = self.text.get_buffer().connect("changed", self.on_text_changed)
    self.text.show_all()
    canvas   .show_all()
    
  #def partition_listener(self, partition, type, new, old): pass
    
  def on_move_cursor(self, text, step, count, extend_selection):
    self.scroll_if_needed()
    
  def scroll_if_needed(self):
    if self.text.is_focus():
      cursor_x = self.text.get_iter_location(self.text.get_buffer().get_iter_at_mark(self.text.get_buffer().get_insert())).x + self.fixed.child_get_property(self.text, "x")
      if   cursor_x < 20:
        self.canvas.hadjustment.value = max(self.canvas.hadjustment.lower, self.canvas.hadjustment.value + (cursor_x - 20))
      elif cursor_x > self.canvas.width - self.canvas.start_x - 40:
        self.canvas.hadjustment.value = min(self.canvas.hadjustment.upper, self.canvas.hadjustment.value + (cursor_x - (self.canvas.width - self.canvas.start_x - 40)))
        
  def on_text_changed(self, buffer):
    old_text = self.lyrics.text
    new_text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter())
    
    size_changed = old_text.count(u"\n") != new_text.count(u"\n")
    
    def set_text(text):
      current = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter())
      self.lyrics.text = text
      if current != text:
        buffer.handler_block(self.text_changed_handler)
        buffer.set_text(text)
        buffer.handler_unblock(self.text_changed_handler)
        self.set_text_size() # Not delayed, because the set_text remove all the precendent text tags !
      else:
        self.delayed_set_text_size()
      if size_changed: self.canvas.render_all()
        
    def do_it  (): set_text(new_text)
    def undo_it(): set_text(old_text)
    
    if self.last_undoable and self.canvas.main.undo_stack.undoables and (self.last_undoable is self.canvas.main.undo_stack.undoables[-1]):
      self.last_undoable.do_func = do_it
      do_it()
    else:
      self.last_undoable = UndoableOperation(do_it, undo_it, _(u"edit lyrics"), self.canvas.main.undo_stack)

    self.scroll_if_needed()
    
  def on_text_focus(self, text, event):
    if getattr(self.canvas.main, "notebook", None):
      self.canvas.main.notebook.edit(-3, self.lyrics)
    self.canvas.main.selected_partition = self.lyrics
    
  def on_text_key_press(self, text, event):
    if event.state & gtk.gdk.CONTROL_MASK:
      if    event.keyval == keysyms.space:
        text.get_buffer().insert_at_cursor(" ")
        return 1
    else:
      if    event.keyval == keysyms.space:
        text.get_buffer().insert_at_cursor("\t")
        return 1
      elif (event.keyval == keysyms.minus) or (event.keyval == keysyms.KP_Subtract):
        text.get_buffer().insert_at_cursor("-\t")
        return 1
      
  def partition_listener(self, partition, type, new, old): pass
    
  def melody_note_listener(self, obj, type, new, old):
    self.update_melody()
    
  def update_melody(self):
    melody = self.melody = self.lyrics.get_melody()
    
    self.sizes = []
    if melody and melody.notes:
      x0 = int(2 + self.canvas.time_2_x(melody.notes[0].time) - self.canvas.start_x + self.canvas.x)
      
      tabs = pango.TabArray(len(melody.notes) - 1, 1)
      previous_time = melody.notes[0].time
      i = 0
      x = 0
      for note in melody.notes[1:]:
        if note.time == previous_time: continue
        if note.duration_fx == u"appoggiatura": continue
        note_x = self.canvas.time_2_x(note.time) - self.canvas.start_x + self.canvas.x
        if i == 0: self.sizes.append(note_x - x - x0)
        else:      self.sizes.append(note_x - x)
        tabs.set_tab(i, pango.TAB_LEFT, int(note_x - x0))
        x = note_x
        i += 1
        previous_time = note.time
      self.text.set_tabs(tabs)
      
      if self.x0 != x0:
        self.x0 = x0
        self.canvas.render_all()
        
    self.delayed_set_text_size()
    
  def delayed_set_text_size(self):
    if self.timeout_set_text_size: gobject.source_remove(self.timeout_set_text_size)
    self.timeout_set_text_size = gobject.timeout_add(120, self.set_text_size)
    
  def delayed_update_melody(self):
    if self.timeout_update_melody: gobject.source_remove(self.timeout_update_melody)
    self.timeout_update_melody = gobject.timeout_add(120, self.update_melody)
    
  def set_text_size(self):
    b = self.text.get_buffer()
    b.remove_all_tags(b.get_start_iter(), b.get_end_iter())
    
    font_size = (self.canvas.default_font_size / pangocairo.cairo_font_map_get_default().get_resolution() * 72.0)
    
    reduced_layouts = []
    while font_size > 3:
      l = pango.Layout(self.text.get_pango_context())
      l.set_font_description(pango.FontDescription("Sans %s" % font_size))
      l.font_size = font_size
      reduced_layouts.append(l)
      font_size -= 1
      
    line_id = 0
    for line in self.lyrics.text.split(u"\n"):
      i      = 0
      offset = 0
      for piece in line.split(u"\t")[:-1]:
        if i >= len(self.sizes): continue
        
        max_width = self.sizes[i] - 7.0 * self.scale
        
        for reduced_layout in reduced_layouts:
          reduced_layout.set_text(piece)
          width = reduced_layout.get_pixel_extents()[1][2] or 1
          if width < max_width: break

        if not reduced_layout is reduced_layouts[0]:
          tag = b.create_tag(size_points = reduced_layout.font_size)
          b.apply_tag(tag, b.get_iter_at_line_offset(line_id, offset), b.get_iter_at_line_offset(line_id, offset + 1 + len(piece)))
          
        offset += 1 + len(piece)
        i      += 1
        
      line_id += 1
      
  def draw(self, ctx, x, y, width, height, drag = 0):
    if Drawer.draw(self, ctx, x, y, width, height, drag):
      #self.start_y = draw_multiline_text(ctx, self.lyrics.header, 3.0 * self.scale, self.y + 2 * self.scale, self.canvas.width - 20) - self.y + 7 * self.scale
      self.canvas.draw_text_default(ctx, self.lyrics.header, 3.0 * self.scale, self.y + 5 * self.scale)
      self.start_y = self.canvas.default_line_height + 7 * self.scale
      
      text_w, text_h = self.text.size_request()
      self.height = self.start_y + max(editor_gtk.SMALL_ICON_SIZE * self.scale, text_h + 2 * self.scale)
      if self.canvas.x == 0:
        ctx.set_source_rgb(0.0, 0.0, 0.0)
        ctx.set_line_width(2)
        ctx.move_to(self.canvas.start_x - self.canvas.x + 1, self.y + self.start_y)
        ctx.rel_line_to(0, self.height - self.start_y)
        ctx.stroke()
        ctx.set_line_width(1)
        
      # Draws the icon
      draw_bitmap(self.canvas, ctx,
                  description(self.lyrics.__class__).icon_filename_for(self.lyrics),
                  4 * self.scale,
                  int(self.y + self.start_y // 2 + self.height // 2 - (editor_gtk.SMALL_ICON_SIZE * self.scale) // 2),
                  0.5 * self.scale)
        
      
    if self.canvas.child_get_property(self.fixed, "y") != self.y + self.start_y:
      self.canvas.child_set_property(self.fixed, "y", self.y + self.start_y)
      
    if self.fixed.child_get_property(self.text, "x") != self.x0 - self.canvas.x:
      self.fixed.child_set_property(self.text, "x", self.x0 - self.canvas.x)
      
    self.fixed.set_size_request(self.canvas.width, int(self.height - self.start_y))
    
  def on_button_press(self, *args): self.text.grab_focus()
  
  def destroy(self):
    self.fixed.destroy()
    Drawer.destroy(self)

    
def draw_round_rect(ctx, x1, y1, x2, y2, round):
  round = min(round, (x2 - x1) // 2, (y2 - y1) // 2)
  round2 = round / 5
  ctx.move_to(x2 - round, y1        ); ctx.curve_to(x2 - round2, y1         , x2         , y1 + round2, x2        , y1 + round)
  ctx.line_to(x2        , y2 - round); ctx.curve_to(x2         , y2 - round2, x2 - round2, y2         , x2 - round, y2        )
  ctx.line_to(x1 + round, y2        ); ctx.curve_to(x1 + round2, y2         , x1         , y2 - round2, x1        , y2 - round)
  ctx.line_to(x1        , y1 + round); ctx.curve_to(x1         , y1 + round2, x1 + round2, y1         , x1 + round, y1        )
  ctx.close_path()
  

def draw_multiline_text(ctx, text, x, y, max_width):
  ascent, descent, font_height, max_x_advance, max_y_advance = ctx.font_extents()
  lines = text.split(u"\n")
  for line in lines:
    x_bearing, y_bearing, width, height, x_advance, y_advance = ctx.text_extents(line)
    if width > max_width:
      words = line.split()
      words_ok = []
      line = u""
      for word in words:
        if line:
          line2 = line + u" " + word
          x_bearing, y_bearing, width, height, x_advance, y_advance = ctx.text_extents(line2)
          if width > max_width:
            y += font_height
            ctx.move_to(x, y)
            ctx.show_text(line)
            line = word
          else:
            line = line2
        else:
          line = word
          
      if line:
        y += font_height
        ctx.move_to(x, y)
        ctx.show_text(line)
        
    else:
      y += font_height
      ctx.move_to(x, y)
      ctx.show_text(line)
  return y



def new_layout(ctx, font = "Sans 12"):
  layout = ctx.create_layout()
  layout.set_font_description(pango.FontDescription(font))
  ctx.update_layout(layout)
  return layout
  


# layout = pangoctx.create_layout()
# layout.set_text(u"bla bla")
# layout.set_font_description(pango.FontDescription(u"Sans 12"))
## pangoctx.update_layout(layout)  # Needed only if changing color ???
# pangoctx.show_layout(layout)


_BITMAP_CACHE = {}

def draw_bitmap(canvas, ctx, bitmap_filename, x, y, scale = 1.0):
  image = _BITMAP_CACHE.get(bitmap_filename)
  if not image:
    image = _BITMAP_CACHE[bitmap_filename] = cairo.ImageSurface.create_from_png(bitmap_filename)
  ctx.scale(scale, scale)
  ctx.set_source_surface(image, x / scale, y / scale)
  ctx.get_source().set_filter(cairo.FILTER_GOOD)
  ctx.paint()
  ctx.identity_matrix()
  ctx.set_source_rgb(0.0, 0.0, 0.0) # Required, is it a bug in GTK / Cairo ?
  
#def draw_bitmap(canvas, ctx, bitmap_filename, x, y, scale = 1.0):
#  import editobj2
#  pixbuf = editobj2.editor_gtk.load_big_icon(bitmap_filename)
#  if scale != 1.0: pixbuf = pixbuf.scale_simple(int(round(pixbuf.get_width() * scale)), int(round(pixbuf.get_height() * scale)), gtk.gdk.INTERP_BILINEAR)
#  ctx.set_source_pixbuf(pixbuf, x, y)
#  ctx.paint()
#  ctx.set_source_rgb(0.0, 0.0, 0.0) # Required, is it a bug in GTK / Cairo ?
  
