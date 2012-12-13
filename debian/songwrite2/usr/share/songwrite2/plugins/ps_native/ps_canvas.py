# -*- coding: utf-8 -*-

# Songwrite 2
# Copyright (C) 2007-2010 Jean-Baptiste LAMY -- jibalamy@free.fr
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

from __future__ import division
import sys, math, bisect, locale, codecs
from cStringIO import StringIO

import gobject, gtk, cairo, pango, pangocairo
if gtk.pygtk_version < (2, 7, 0): import cairo.gtk

import editobj2.editor_gtk as editor_gtk

import songwrite2.model  as model
from   songwrite2.canvas import *


def guess_zoom(song):
  min_duration = 1000000
  for partition in song.partitions:
    if isinstance(partition, model.Partition):
      for note in partition.notes:
        if note.duration < min_duration: min_duration = note.duration
  return 0.3 + 0.075 * 96.0 / min_duration


class PSAdditionalStaffDrawer(StaffDrawer):
  def draw(self, ctx, x, y, width, height, drag = 0):
    view = self.partition.view
    try:
      self.partition.view = model.GuitarStaffView(self.partition, 0)
      
      StaffDrawer.draw(self, ctx, x, y, width, height, drag)
    finally:
      self.partition.view = view
    
class PSLyricsDrawer(Drawer):
  def __init__(self, canvas, lyrics, melody):
    Drawer.__init__(self, canvas)
    
    self.lyrics  = lyrics
    self.melody  = melody
    self.x0      = canvas.start_x + 2
    self.start_y = 0
    
  def draw(self, ctx, x, y, width, height, drag = 0):
    if Drawer.draw(self, ctx, x, y, width, height, drag):
      text_y = self.y + self.start_y + 1 + self.canvas.default_line_height / 2 + self.canvas.default_ascent / 2 - self.canvas.default_descent / 2
      lignes = self.lyrics.text.split(u"\n")
      
      nb_ligne = 1
      
      ctx.set_source_rgb(0, 0, 0)
      cur_x = 0
      for ligne in lignes:
        syllabes = ligne.replace(u"\\\\", u"").replace(u"--", u"-").split(u"\t")
        
        melody_notes0 = [note for note in self.melody.notes if not note.duration_fx == u"appoggiatura"]
        melody_notes = []
        previous_time = -1000
        for note in melody_notes0:
          if note.time == previous_time: continue
          melody_notes.append(note)
          previous_time = note.time
          
        nb_skip = 0
        for i in range(min(len(melody_notes), len(syllabes))):
          if nb_skip:
            nb_skip -= 1
            continue
          note    = melody_notes[i]
          if not (self.canvas.time1 <= note.time < self.canvas.time2):
            continue
          
          syllabe = syllabes[i]
          if not syllabe: continue
          
          text_x = self.canvas.time_2_x(note.time) + 1
          if text_x < x: continue
          if text_x > x + width: break
          
          max_text_width = note.duration * self.canvas.zoom - 3 * self.scale
          if text_x <= cur_x: # Need breakline !
            nb_ligne += 1
            text_y   += self.canvas.default_line_height
            
          cur_x = text_x
          
          #font_size = self.canvas.default_font_size
          #ctx.move_to(text_x, text_y)
          #x_bearing, y_bearing, text_width, text_height, x_advance, y_advance = ctx.text_extents(syllabe)
          #while text_width > max_text_width:
          #  try: syl = syllabes[i + nb_skip + 1]
          #  except IndexError: syl = u""
          #  if syl in (u"_", u"_-"):
          #    nb_skip += 1
          #    duration = 0
          #    for j in range(nb_skip + 1): duration += melody_notes[i + j].duration
          #    max_text_width = duration * self.canvas.zoom - 3 * self.scale
          #    
          #  else:
          #    font_size -= 1.0
          #    ctx.set_font_size(font_size)
          #    x_bearing, y_bearing, text_width, text_height, x_advance, y_advance = ctx.text_extents(syllabe)
              
          #ctx.show_text(syllabe)
          #ctx.set_font_size(self.canvas.default_font_size)
          
          self.canvas.draw_text_max_width(ctx, syllabe,
                                          text_x, text_y - 0.77* self.canvas.default_line_height,
                                          max_text_width)
          
          
      self.height = self.start_y + nb_ligne * self.canvas.default_line_height + 1

    
class PSCanvas(BaseCanvas):
  is_gui_interface = 0
  def __init__(self, song, filename, x, width, time1, time2, zoom):
    BaseCanvas.__init__(self, song)
    
    self.set_default_font_size(song.printfontsize)
    self.update_mesure_size()
    
    self.filename = filename
    self.time1    = time1
    self.time2    = time2
    self.zoom     = zoom #or guess_zoom(self.song)
    
    self.drawers = []
    
    self.x        = x
    self.width    = width
    self.height   = 10000
    
    self.draw() # First  pass for   computing size
    self.draw() # Second pass for recomputing size
    self.draw()
    
  def render_all(self): pass
  
  def draw(self):
    drawer = None
    surface = cairo.PSSurface(self.filename, self.width, self.height)
    ctx = cairo.Context(surface)
    ctx = pangocairo.CairoContext(ctx)
    self.default_layout = new_layout(ctx, "Sans %s" % (self.default_font_size * self.scale_pango_2_cairo))
    
    ctx.select_font_face('sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(self.default_font_size)
    self.default_ascent, self.default_descent, self.default_line_height, max_x_advance, max_y_advance = ctx.font_extents()
    self.char_h_size = self.default_line_height // 2
    
    lyricss = []
    def add_lyrics():
      text = u"\n".join([lyrics.text for lyrics in lyricss if lyrics.show_all_lines_on_melody])
      if text:
        cumulated_lyrics = model.Lyrics(self.song, text, _(u"Lyrics"))
        drawer = PSLyricsDrawer(self, cumulated_lyrics, melody)
        self.drawers.append(drawer)
        
      else:
        syllabess = [line.split(u"\t") for lyrics in lyricss for line in lyrics.text.split(u"\n") if not lyrics.show_all_lines_on_melody]
        
        if syllabess:
          cummulated_syllabes = [u""] * len([note for note in melody.notes if not note.duration_fx == u"appoggiatura"])
          for i in range(len(cummulated_syllabes)):
            for syllabes in syllabess:
              if (i < len(syllabes)) and syllabes[i]:
                cummulated_syllabes[i] = syllabes[i]
                break
          cumulated_lyrics = model.Lyrics(self.song, u"\t".join(cummulated_syllabes), _(u"Lyrics"))
          drawer = PSLyricsDrawer(self, cumulated_lyrics, melody)
          self.drawers.append(drawer)
          
      lyricss.__imul__(0)
      
    if not self.drawers:
      self.default_pango_font = pango.FontDescription(u"Sans %s" % (self.default_font_size * self.scale_pango_2_cairo))
      for partition in self.song.partitions:
        if   isinstance(partition, model.Partition):
          add_lyrics()
          melody = partition
          if not partition.notes_at(self.time1, self.time2 - 1): continue
          
        if   getattr(partition, "print_with_staff_too", 0) and not isinstance(partition.view, model.StaffView):
          drawer = PSAdditionalStaffDrawer(self, partition, compact = 1)
          self.drawers.append(drawer)
          
        if   isinstance(partition     , model.Lyrics       ): lyricss.append(partition)
        elif hasattr(partition.view, "get_drawer"):           drawer = partition.view.get_drawer(self)
        elif isinstance(partition.view, model.TablatureView): drawer = TablatureDrawer(self, partition)
        elif isinstance(partition.view, model.StaffView    ): drawer = StaffDrawer    (self, partition, compact = 1)
        elif isinstance(partition.view, model.DrumsView    ): drawer = DrumsDrawer    (self, partition)
        if drawer:
          if   getattr(partition, "print_with_staff_too", 0):
            drawer.show_header = 0
            
          self.drawers.append(drawer)
          drawer = None
      add_lyrics()
      
      for drawer in self.drawers: drawer.drawers_changed()
      
    x     = self.start_x
    width = self.width
    y     = 0
    dy    = 0
    total_height = 0
    for drawer in self.drawers:
      drawer.y = dy
      drawer.draw(ctx, x, y, width, self.height)
      dy           += drawer.height
      total_height += drawer.height
      
    if self.drawers and isinstance(self.drawers[0], PartitionDrawer):
      # Show mesure number at the beginning
      mesure_number = str(1 + self.song.mesures.index(self.song.mesure_at(self.time1)))
      ctx.set_font_size(self.default_font_size * 0.7)
      x_bearing, y_bearing, text_width, text_height, x_advance, y_advance = ctx.text_extents(mesure_number)
      ctx.move_to(
        self.start_x - text_width - x_bearing - 2,
        self.drawers[0].y + self.drawers[0].start_y + self.drawers[0].stem_extra_height - text_height // 2,
        )
      ctx.show_text(mesure_number)
      ctx.set_font_size(self.default_font_size)
      
    ctx.show_page()
    surface.finish()
    self.height = total_height
