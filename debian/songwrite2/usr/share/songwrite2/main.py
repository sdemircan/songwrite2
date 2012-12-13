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

import sys, time, getpass, copy, string, os, os.path, thread, codecs, locale
from StringIO import StringIO

import songwrite2, songwrite2.globdef as globdef, songwrite2.model as model, songwrite2.player as player
import songwrite2.__editobj2__
import songwrite2.midi
import editobj2, editobj2.undoredo as undoredo, editobj2.editor as editor, editobj2.introsp as introsp
from editobj2.observe import *

APPS = {}

class BaseApp(object):
  def __init__(self, song = None):
    self.undo_stack = undoredo.Stack(globdef.config.NUMBER_OF_UNDO)
    
    self.menubar = self.create_menubar()
    
    file_menu = self.append_to_menu(self.menubar, 1, u"File", self.on_file_menu)
    if editobj2.GUI !="Qtopia": # QTopia app can have onely one main window
      self.append_to_menu(file_menu, 0, u"New window..."      , self.on_new_app)
    self.append_to_menu(file_menu, 0, u"New song"           , self.on_new         , accel = u"C-N")
    self.append_to_menu(file_menu, 0, u"New songbook"       , self.on_new_songbook)
    self.append_to_menu(file_menu, 0, u"Open..."            , self.on_open        , accel = u"C-O")
    self.append_to_menu(file_menu, 0, u"Save"               , self.on_save        , accel = u"C-S")
    self.append_to_menu(file_menu, 0, u"Save as..."         , self.on_save_as     , accel = u"C-S-S")
    self.save_as_songbook_menu = self.append_to_menu(file_menu, 0, u"Save songbook as...", self.on_save_as_songbook)
    self.append_separator_to_menu(file_menu)
    
    self.import_menu          = self.append_to_menu(file_menu, 1, u"Import")
    self.export_menu          = self.append_to_menu(file_menu, 1, u"Export")
    self.export_songbook_menu = self.append_to_menu(file_menu, 1, u"Export songbook")
    
    self.append_to_menu(file_menu, 0, u"preview_print"         , self.on_preview_print)
    self.preview_print_songbook_menu = self.append_to_menu(file_menu, 0, u"preview_print_songbook", self.on_preview_print_songbook)
    self.append_separator_to_menu(file_menu)
    self.append_to_menu(file_menu, 0, u"Close", self.on_close)
    
    self.append_separator_to_menu(file_menu)
    for file in globdef.config.PREVIOUS_FILES:
      if not isinstance(file, unicode): file = file.decode("utf8")
      self.append_to_menu(file_menu, 0, file, lambda obj, file = file: self.open_filename(file))
      
    edit_menu = self.append_to_menu(self.menubar, 1, u"Edit", self.on_edit_menu)
    self.undo_menu = self.append_to_menu(edit_menu, 0, u"Undo", self.on_undo, accel = u"C-Z")
    self.redo_menu = self.append_to_menu(edit_menu, 0, u"Redo", self.on_redo, accel = u"C-Y")
    self.append_separator_to_menu(edit_menu)
    self.append_to_menu(edit_menu, 0, u"Select all"              , self.on_select_all, accel = u"C-A", accel_enabled = 0) # Disabled these accels,
    self.append_to_menu(edit_menu, 0, u"Paste last selection"    , self.on_note_paste, accel = u"C-V", accel_enabled = 0) # because they block C-A and C-V in lyrics editor
    self.append_to_menu(edit_menu, 0, u"Insert/remove beats..."  , self.on_insert_times)
    self.append_to_menu(edit_menu, 0, u"Insert/remove bars..."   , self.on_insert_bars)
    self.append_separator_to_menu(edit_menu)
    self.append_to_menu(edit_menu, 0, u"Rhythm and bars..."     , self.on_bars_prop)
    self.append_to_menu(edit_menu, 0, u"Repeats and playlist...", self.on_playlist_prop)
    self.append_to_menu(edit_menu, 0, u"Song and instruments...", self.on_song_prop)
    self.append_to_menu(edit_menu, 0, u"Songbook..."            , self.on_songbook_prop)
    self.append_separator_to_menu(edit_menu)
    self.append_to_menu(edit_menu, 0, u"Preferences...", self.on_preferences)
    
    play_menu = self.append_to_menu(self.menubar, 1, "Play")
    self.append_to_menu(play_menu, 0, u"Play from the beginning"        , self.on_play)
    self.append_to_menu(play_menu, 0, u"Play from here"                 , self.on_play_from_here, accel = u" ", accel_enabled = 0)
    self.append_to_menu(play_menu, 0, u"Play from the beginning in loop", self.on_play_in_loop)
    self.append_to_menu(play_menu, 0, u"Play from here in loop"         , self.on_play_from_here_in_loop)
    self.append_to_menu(play_menu, 0, u"Stop playing"                   , self.on_stop_playing)
    
    instru_menu = self.append_to_menu(self.menubar, 1, u"Instrument")
    self.append_to_menu(instru_menu, 0, u"Add..."       , self.on_add_instrument)
    self.append_to_menu(instru_menu, 0, u"Dupplicate"   , self.on_dupplicate_instrument)
    self.append_to_menu(instru_menu, 0, u"Remove"       , self.on_remove_instrument)
    self.append_to_menu(instru_menu, 0, u"Move up"      , self.on_move_instrument_up)
    self.append_to_menu(instru_menu, 0, u"Move down"    , self.on_move_instrument_down)
    self.append_separator_to_menu(instru_menu)
    self.append_to_menu(instru_menu, 0, u"Edit..."      , self.on_instrument_prop)
    
    note_menu = self.append_to_menu(self.menubar, 1, u"Note")
    self.append_to_menu(note_menu, 0, u"One octavo above", lambda *args: self.canvas.shift_selections_values( 12))
    self.append_to_menu(note_menu, 0, u"One pitch above" , lambda *args: self.canvas.shift_selections_values( 1), accel = u"+", accel_enabled = 0)
    self.append_to_menu(note_menu, 0, u"One pitch below" , lambda *args: self.canvas.shift_selections_values(-1), accel = u"-", accel_enabled = 0)
    self.append_to_menu(note_menu, 0, u"One octavo below", lambda *args: self.canvas.shift_selections_values(-12))
    self.append_separator_to_menu(note_menu)
    self.append_to_menu(note_menu, 0, u"Delete"                  , lambda *args: self.canvas.delete_notes(self.canvas.selections), accel = 65535, accel_enabled = 0)
    self.append_to_menu(note_menu, 0, u"Arrange notes at fret...", self.on_note_arrange)
    self.append_to_menu(note_menu, 0, u"Edit..."                 , self.on_note_prop)
    
    def set_duration(duration):
      def on_set_duration(*args):
        if self.updating_duration: return
        if self.canvas.selections:
          self.canvas.current_duration = duration
          notes = list(self.canvas.selections)
          old_durations = [note.duration for note in notes]
          
          def do_it(notes = notes):
            for note in notes:
              dotted  = note.is_dotted()
              triplet = note.is_triplet()
              note.duration = duration
              if dotted : note.duration *= 1.5
              if triplet: note.duration  = (note.duration * 2) // 3
              
          def undo_it(notes = notes):
            for i in range(len(notes)): notes[i] = old_durations[i]
            
          editobj2.undoredo.UndoableOperation(do_it, undo_it, _(u"change of %s") % _(u"duration"), self.undo_stack)
          
      return on_set_duration

    self.set_duration_384 = set_duration(384)
    self.set_duration_192 = set_duration(192)
    self.set_duration_96  = set_duration(96 )
    self.set_duration_48  = set_duration(48 )
    self.set_duration_24  = set_duration(24 )
    self.set_duration_12  = set_duration(12 )
    
    def toggle_dotted(*args):
      if not self.updating_duration: self.canvas.toggle_dotted()
    def toggle_triplet(*args):
      if not self.updating_duration: self.canvas.toggle_triplet()
    def toggle_accent(*args):
      if not self.updating_duration: self.canvas.toggle_accent()
    self.toggle_dotted  = toggle_dotted
    self.toggle_triplet = toggle_triplet
    self.toggle_accent  = toggle_accent 
    
    self.updating_duration = 0
    def on_duration_menu_cliked(*args):
      if self.canvas.selections:
        self.updating_duration = 1
        note = tuple(self.canvas.selections)[0]
        dotted .set_active(note.is_dotted())
        triplet.set_active(note.is_triplet())
        self.updating_duration = 0
        
        
    duration_menu = self.append_to_menu(self.menubar, 1, u"Duration", on_duration_menu_cliked)
    self.append_to_menu(duration_menu, 0, u"Whole"        , self.set_duration_384, image = self.menu_image("note_384.png"), accel = u"*", accel_enabled = 0)
    self.append_to_menu(duration_menu, 0, u"Half"         , self.set_duration_192, image = self.menu_image("note_192.png"))
    self.append_to_menu(duration_menu, 0, u"Quarter"      , self.set_duration_96 , image = self.menu_image("note_96.png"))
    self.append_to_menu(duration_menu, 0, u"Eighth"       , self.set_duration_48 , image = self.menu_image("note_48.png"))
    self.append_to_menu(duration_menu, 0, u"Sixteenth"    , self.set_duration_24 , image = self.menu_image("note_24.png"))
    self.append_to_menu(duration_menu, 0, u"Thirty-second", self.set_duration_12 , image = self.menu_image("note_12.png"), accel = u"/", accel_enabled = 0)
    self.append_separator_to_menu(duration_menu)
    dotted  = self.append_to_menu(duration_menu, 0, u"Dotted"       , toggle_dotted , type = "check", accel = u".", accel_enabled = 0)
    triplet = self.append_to_menu(duration_menu, 0, u"Triplet"      , toggle_triplet, type = "check")
    
    self.updating_volume_fx = 0
    def on_volume_fx_menu_cliked(*args):
      if self.canvas.selections:
        self.updating_volume_fx = 1
        note = tuple(self.canvas.selections)[0]
        if   note.volume == 255: volume_menus[0].set_active(1)
        elif note.volume >  190: volume_menus[1].set_active(1)
        elif note.volume >  100: volume_menus[2].set_active(1)
        else:                    volume_menus[3].set_active(1)
        
        fxs = set([note.link_fx, note.duration_fx, note.strum_dir_fx])
        if note.fx == u"bend": fxs.add(u"bend%s" % note.bend_pitch)
        else:                  fxs.add(note.fx)
        for key, menu in fx_menus.iteritems():
          menu.set_active(key in fxs)
          
        self.updating_volume_fx = 0

    for type, fxs in model.ALL_FXS:
      if type: type += "_"
      for fx in fxs:
        if not fx: continue
        for arg in model.FXS_ARGS.get(fx, [None]):
          def f(widegt, type = type, fx = fx, arg = arg):
            if not self.updating_volume_fx: getattr(self.canvas, "set_selections_%sfx" % type)(fx, arg)
          if arg: setattr(self, "set_fx_%s%s" % (fx, str(arg).replace(".", "")), f)
          else:   setattr(self, "set_fx_%s"   %  fx, f)
          
    effect_menu = self.append_to_menu(self.menubar, 1, u"Effect", on_volume_fx_menu_cliked)
    volume_menus = [
      self.append_to_menu(effect_menu, 0, u"Accentuated"            , self.set_volume_255, type = "radio", accel = 65293, accel_enabled = 0),
      self.append_to_menu(effect_menu, 0, u"Normal"                 , self.set_volume_204, type = "radio"),
      self.append_to_menu(effect_menu, 0, u"Low"                    , self.set_volume_120, type = "radio"),
      self.append_to_menu(effect_menu, 0, u"Very low"               , self.set_volume_50 , type = "radio"),
      ]
    self.append_separator_to_menu(effect_menu)
    self.append_to_menu(effect_menu, 0, u"Remove all effects"       , self.set_fx_none   , accel = u"n", accel_enabled = 0)
    
      
    self.append_separator_to_menu(effect_menu)
    fx_menus = {
      u"bend0.5" : self.append_to_menu(effect_menu, 0, u"Bend " + locale.str(0.5), self.set_fx_bend05  , type = "check", accel = u"b", accel_enabled = 0),
      u"bend1.0" : self.append_to_menu(effect_menu, 0, u"Bend 1"                 , self.set_fx_bend10  , type = "check"),
      u"bend1.5" : self.append_to_menu(effect_menu, 0, u"Bend " + locale.str(1.5), self.set_fx_bend15  , type = "check"),
      u"tremolo" : self.append_to_menu(effect_menu, 0, u"Tremolo"                , self.set_fx_tremolo , type = "check", accel = u"t", accel_enabled = 0),
      u"dead"    : self.append_to_menu(effect_menu, 0, u"Dead note"              , self.set_fx_dead    , type = "check", accel = u"g", accel_enabled = 0),
      u"roll"    : self.append_to_menu(effect_menu, 0, u"Roll"                   , self.set_fx_roll    , type = "check", accel = u"r", accel_enabled = 0),
      u"harmonic": self.append_to_menu(effect_menu, 0, u"Harmonic"               , self.set_fx_harmonic, type = "check", accel = u"h", accel_enabled = 0),
      }
    self.append_separator_to_menu(effect_menu)
    fx_menus.update({
      u"appoggiatura": self.append_to_menu(effect_menu, 0, u"Appoggiatura", self.set_fx_appoggiatura, type = "check", accel = u"a", accel_enabled = 0),
      u"fermata"     : self.append_to_menu(effect_menu, 0, u"Fermata"     , self.set_fx_fermata     , type = "check", accel = u"p", accel_enabled = 0),
      u"breath"      : self.append_to_menu(effect_menu, 0, u"Breath"      , self.set_fx_breath      , type = "check"),
      })
    self.append_separator_to_menu(effect_menu)
    fx_menus.update({
      u"link"  : self.append_to_menu(effect_menu, 0, u"Hammer / pull / legato" , self.set_fx_link   , type = "check", accel = u"l", accel_enabled = 0),
      u"slide" : self.append_to_menu(effect_menu, 0, u"Slide"                  , self.set_fx_slide  , type = "check", accel = u"s", accel_enabled = 0),
    })
    self.append_separator_to_menu(effect_menu)
    fx_menus.update({
      u"up"         : self.append_to_menu(effect_menu, 0, u"Strum direction up"          , self.set_fx_up        , type = "check", accel = u"^", accel_enabled = 0),
      u"down"       : self.append_to_menu(effect_menu, 0, u"Strum direction down"        , self.set_fx_down      , type = "check", accel = u"_", accel_enabled = 0),
      u"down_thumb" : self.append_to_menu(effect_menu, 0, u"Strum direction down (thumb)", self.set_fx_down_thumb, type = "check", accel = u",", accel_enabled = 0),
    })
    
    help_menu = self.append_to_menu(self.menubar, 1, u"Help")
    self.append_to_menu(help_menu, 0, u"About..."         , self.on_about)
    self.append_to_menu(help_menu, 0, u"Manual..."        , self.on_manual, accel = 65470)
    self.append_separator_to_menu(help_menu)
    self.append_to_menu(help_menu, 0, u"Dump"             , self.on_dump)
    self.append_to_menu(help_menu, 0, u"GC"               , self.on_gc)
    
    
    songwrite2.plugins.create_plugins_ui(self)
    
    self.song     = None
    self.songbook = None
    if   isinstance(song, model.Song)    : self.set_song    (song)
    elif isinstance(song, model.Songbook): self.set_songbook(song)
    #else:                                  self.on_new()
    
    self.floating = None
    self.paned    = None
    self.scrolled = None
    self.canvas   = None
    self.selected_partition = None
    self.selected_mesure    = None
    self.selected_note      = None
    self.create_content()

  def set_volume_255(self, *args):
    if not self.updating_volume_fx: self.canvas.set_selections_volume(255)
  def set_volume_204(self, *args):
    if not self.updating_volume_fx: self.canvas.set_selections_volume(204)
  def set_volume_120(self, *args):
    if not self.updating_volume_fx: self.canvas.set_selections_volume(120)
  def set_volume_50(self, *args):
    if not self.updating_volume_fx: self.canvas.set_selections_volume(50 )

  def set_fx_none(self, *args):
    if not self.updating_volume_fx: self.canvas.remove_selections_fx()

  def set_selected_partition(self, partition): self.selected_partition = partition
  def set_selected_mesure   (self, mesure   ): self.selected_mesure    = mesure
  def set_selected_note     (self, note     ): self.selected_note      = note
    
  def partition_categories(self):
    next_strophe_number = len([lyrics for lyrics in self.song.partitions if isinstance(lyrics, model.Lyrics) and _(u"Strophe #%s").replace(u"%s", u"") in lyrics.header]) + 1
    
    return PartitionCategory(_(u"Available partition views"), _(u"Select the partition and partition's view you want to add."),
        [model.Partition(None, view_type.default_instrument, view_type) for view_type in [model.GuitarView, model.BassView]] +
        [PartitionCategory(_(u"More tablatures..."), _(u"Tablature (for guitar-like instruments)"),
          [model.Partition(None, view_type.default_instrument, view_type) for view_type in model.VIEWS[u"tab"] if not view_type is model.GuitarView and not view_type is model.BassView])
        ] +
        [model.Partition(None, view_type.default_instrument, view_type) for view_type in [model.PianoView, model.GuitarStaffView, model.VocalsView]] +
        [PartitionCategory(_(u"More staffs..."), _(u"Staff (for any instrument)"),
          [model.Partition(None, view_type.default_instrument, view_type) for view_type in model.VIEWS[u"staff"] if not view_type is model.PianoView and not view_type is model.VocalsView and not view_type is model.GuitarStaffView])
        ] +
        [model.Partition(None, model.TomView.default_instrument, model.TomView)] +
        [PartitionCategory(_(u"More drums..."), _(u"Drum tablatures (for battery)"),
          [model.Partition(None, view_type.default_instrument, view_type) for view_type in model.VIEWS[u"drums"] if not view_type is model.TomView])
        ] +
        [
        model.Lyrics(None, header = _(u"Chorus")),
        model.Lyrics(None, header = _(u"Strophe #%s") % next_strophe_number),
        ])

  def edit(self, o, *args, **kargs):
    editobj2.edit(o, undo_stack = self.undo_stack, *args, **kargs)
    
  def on_new_app(self, *args): self.__class__()
  def on_close(self, *args):
    if self.check_save(): return 1

    if self.song:     del APPS[self.song]
    if self.songbook: del APPS[self.songbook]
    self.destroy()
    
    if len(APPS) == 0:
      globdef.config.save()
      sys.exit()
      
  def set_song(self, song):
    if self.song:
      del APPS[self.song]
      if self.filename: model.unload_song(self.filename)
      
    APPS[song] = self
    self.undo_stack.clear()
    self.last_undoables = []
    
    self.song = song
    self.filename = song.filename
    if getattr(self, "notebook", None):
      self.notebook.edit(-4, song, force = 1)
      if song.partitions:
        self.notebook.edit(-3, song.partitions[0], force = 1)
        if song.partitions[0].notes: self.notebook.edit(-1, song.partitions[0].notes[0], force = 1)
      if song.mesures:
        self.notebook.edit(-2, song.mesures[0], force = 1)
      
      self.playlist_pane.set_playlist(song.playlist)
      
  def set_songbook(self, songbook):
    if self.songbook:
      del APPS[self.songbook]
      
      if getattr(self, "notebook", None):
        self.notebook.delete_tab(0)
        
    self.songbook = songbook
    
    if self.songbook:
      APPS[self.songbook] = self
      if self.songbook.song_refs: self.set_song(self.songbook.song_refs[0].get_song())
      
      if getattr(self, "notebook", None):
        self.songbook_pane = self.SongbookPane(self, self.undo_stack)
        self.notebook.insert_tab(0, self.songbook, self.songbook_pane)
        self.songbook_pane.set_songbook(self.songbook)
        
        
  def on_playlist_changed(self, obj, type, new, old):
    self.song.playlist.analyse()
    self.rythm_changed()
    
  def on_file_menu(self, *args):
    if self.songbook:
      self.set_menu_enable(self.save_as_songbook_menu      , 1)
      self.set_menu_enable(self.preview_print_songbook_menu, 1)
      self.set_menu_enable(self.export_songbook_menu       , 1)
    else:
      self.set_menu_enable(self.save_as_songbook_menu      , 0)
      self.set_menu_enable(self.preview_print_songbook_menu, 0)
      self.set_menu_enable(self.export_songbook_menu       , 0)
    
  def on_edit_menu(self, *args):
    undo = self.undo_stack.can_undo()
    redo = self.undo_stack.can_redo()
    if undo: self.set_menu_enable(self.undo_menu, 1); self.set_menu_label(self.undo_menu, "%s '%s'" % (_(u"Undo"), undo.name))
    else:    self.set_menu_enable(self.undo_menu, 0); self.set_menu_label(self.undo_menu, _(u"Undo"))
    if redo: self.set_menu_enable(self.redo_menu, 1); self.set_menu_label(self.redo_menu, "%s '%s'" % (_(u"Redo"), redo.name))
    else:    self.set_menu_enable(self.redo_menu, 0); self.set_menu_label(self.redo_menu, _(u"Redo"))
    
  def on_undo(self, *args):
    if self.undo_stack.can_undo(): self.undo_stack.undo()
  def on_redo(self, *args):
    if self.undo_stack.can_redo(): self.undo_stack.redo()
    
  def on_new(self, *args):
    if self.check_save(): return
    
    self.set_songbook(None)
    
    s = model.Song()
    s.authors   = unicode(getpass.getuser().title(), "latin")
    s.title     = _(u"%s's song") % s.authors
    s.copyright = u"Copyright %s by %s" % (time.localtime(time.time())[0], s.authors)
    
    p = model.Partition(s)
    p.view = model.GuitarView(p)
    s.partitions.append(p)
    
    self.filename = None
    self.set_song(s)
    
  def on_new_songbook(self, *args):
    if self.check_save(): return

    songbook = model.Songbook()
    songbook.authors   = unicode(getpass.getuser().title(), "latin")
    songbook.title     = _(u"%s's songbook") % songbook.authors
    
    self.set_songbook(songbook)
    self.on_songbook_prop()
    
  def on_open(self, event = None):
    if self.check_save(): return
    
    filename = self.prompt_open_filename("sw.xml")
    if not filename: return
    self.open_filename(filename, do_check_save = 0) # check_save has already been done before asking the filename
    
  def open_filename(self, filename, do_check_save = 1):
    globdef.config.LAST_DIR = os.path.dirname(filename)
    
    if do_check_save and self.check_save(): return
    
    if not os.path.exists(filename):
      editobj2.edit(_(u"File does not exist!"), on_validate = lambda o: None)
    else:
      self.filename = filename
      song = model.get_song(filename)
      if isinstance(song, model.Song):
        self.set_songbook(None)
        self.set_song    (song)
      else:
        self.set_songbook(song)
        self.on_songbook_prop()
      globdef.config.add_previous_file(filename)
      
  def on_save_as(self, event = None):
    filename = self.prompt_save_filename("sw.xml")
    if not filename: return
    if not filename.endswith(u".sw.xml"): filename += u".sw.xml"
    self.filename = self.song.filename = filename
    self.on_save(save_song = 1, save_songbook = 0)
    
  def on_save_as_songbook(self, event = None):
    filename = self.prompt_save_filename("sw.xml")
    if not filename: return
    if not filename.endswith(u".sw.xml"): filename += u".sw.xml"
    self.songbook.set_filename(filename)
    self.on_save(save_song = 0, save_songbook = 1)
    
  def on_save(self, event = None, save_song = 1, save_songbook = 1):
    if save_song:
      ok_song = 0
      
      if not self.filename: self.on_save_as()
      if self.filename:
        self.song.__xml__(codecs.lookup("utf8")[3](open(self.filename, "w"))) #.getvalue()
        ok_song = 1
        
        if not self.songbook: globdef.config.add_previous_file(self.filename)
        
    else: ok_song = 1
    
    
    if save_songbook and self.songbook:
      ok_songbook = 0
      
      if not self.songbook.filename: self.on_save_as_songbook()
      if self.songbook.filename:
        self.songbook.__xml__(codecs.lookup("utf8")[3](open(self.songbook.filename, "w"))) #.getvalue()
        ok_songbook = 1
        
        globdef.config.add_previous_file(self.songbook.filename)
        
    else: ok_songbook = 1
    
    
    if ok_song and ok_songbook: self.last_undoables = self.undo_stack.undoables[:]
    
  def on_preview_print(self, event = None):
    try:
      songwrite2.plugins.get_exporter("postscript").print_preview(self.song)
    except:
      self._treat_export_error()
      
  def on_preview_print_songbook(self, event = None):
    try:
      songwrite2.plugins.get_exporter("postscript").print_preview(self.songbook)
    except:
      self._treat_export_error()
      
  def _treat_export_error(self):
    error_class, error, trace = sys.exc_info()
    sys.excepthook(error_class, error, trace)
    print
    
    if isinstance(error, model.SongwriteError):
      editobj2.edit(error)
      if isinstance(error, model.TimeError):
        self.canvas.deselect_all()
        if   error.note:
          self.canvas.partition_2_drawer[error.note.partition].select_note(error.note)
        elif error.partition and error.time:
          self.canvas.partition_2_drawer[error.partition].select_at(error.time, 0, 0)
        elif error.time:
          self.canvas.partition_2_drawer[self.song.partitions[0]].select_at(error.time, 0, 0)
    else:
      editobj2.edit(_(error.__class__.__name__) + "\n\n" + unicode(error))
      
      
  def on_about(self, *args):
    class About(object):
      def __init__(self):
        self.details       = _(u"__about__")
        self.icon_filename = os.path.join(globdef.DATADIR, "songwrite_about.png")
        self.url           = u"http://home.gna.org/oomadness/en/songwrite/index.html"
        self.licence       = u"GPL"
        self.authors       = "Jean-Baptiste 'Jiba' Lamy <jibalamy@free.fr>"
        
      def __unicode__(self): return "Songwrite 2 version %s" % model.VERSION
      
    descr = introsp.description(About)
    descr.set_field_for_attr("details"      , None)
    descr.set_field_for_attr("icon_filename", None)
    self.edit(About())
    
  def on_manual(self, *args):
    import locale
    
    DOCDIR = os.path.join(globdef.APPDIR, "doc")
    if not os.path.exists(DOCDIR):
      import glob
      DOCDIR = glob.glob(os.path.join(globdef.APPDIR, "..", "doc", "songwrite2*"))[0]
      
      if not os.path.exists(DOCDIR):
        DOCDIR = glob.glob("/usr/share/doc/songwrite2*")[0]
      
        if not os.path.exists(DOCDIR):
          DOCDIR = glob.glob("/usr/share/local/doc/songwrite2*")[0]
          
          if not os.path.exists(DOCDIR):
            DOCDIR = glob.glob("/usr/doc/songwrite2")[0]
            
    DOC = os.path.join(DOCDIR, locale.getdefaultlocale()[0][:2], "doc.pdf")
    if not os.path.exists(DOC):
      DOC = os.path.join(DOCDIR, "en", "doc.pdf")
      
    DOC = os.path.abspath(DOC)
    if "%s" in globdef.config.PREVIEW_COMMAND_PDF:
      os.system(globdef.config.PREVIEW_COMMAND_PDF % DOC)
    else:
      command = globdef.config.PREVIEW_COMMAND_PDF
      if command.endswith("-"): command = command[-1]
      os.system(command + " " + DOC)
      
  def on_add_instrument(self, event = None):
    try:
      if isinstance(self.selected_partition, introsp.ObjectPack): selected_partition = self.selected_partition.objects[-1]
      else:                                                       selected_partition = self.selected_partition
      insert_at = self.song.partitions.index(selected_partition) + 1
    except:
      insert_at = len(self.song.partitions)
    new_child = introsp.description(self.song.__class__).do_action(introsp.ACTION_ADD, self.undo_stack, self.song, insert_at)
    
  def on_dupplicate_instrument(self, event = None):
    if isinstance(self.selected_partition, introsp.ObjectPack):
      partitions = self.selected_partition.objects
    else: partitions = [self.selected_partition]
    
    insert_at = max([self.song.partitions.index(partition) for partition in partitions])
    
    xml = StringIO()
    xml.write(u"<song>\n")
    context = model._XMLContext()
    for partition in partitions: partition.__xml__(xml, context)
    xml.write(u"</song>")
    
    import songwrite2.stemml as stemml
    xml.seek(0)
    song = stemml.parse(xml)
    
    def do_it(song = song):
      for partition in song.partitions:
        self.song.insert_partition(insert_at, partition)
        partition.song = self.song
    def undo_it(song = song):
      for partition in song.partitions:
        self.song.remove_partition(partition)
    undoredo.UndoableOperation(do_it, undo_it, _(u"dupplicate instrument"), self.undo_stack)
    
  def on_remove_instrument(self, event = None):
    introsp.description(self.song.__class__).do_action(introsp.ACTION_REMOVE, self.undo_stack, self.song, self.selected_partition)
    
  def on_move_instrument_up(self, event = None):
    introsp.description(self.song.__class__).do_action(introsp.ACTION_MOVE_UP, self.undo_stack, self.song, self.selected_partition)
    
  def on_move_instrument_down(self, event = None):
    introsp.description(self.song.__class__).do_action(introsp.ACTION_MOVE_DOWN, self.undo_stack, self.song, self.selected_partition)
    
  def on_song_prop(self, event = None):
    self.edit(self.song)
    
  def on_instrument_prop(self, event = None):
    self.edit(self.selected_partition or self.song.partitions[0])
    
  def on_note_prop(self, event = None):
    self.edit(self.selected_note)
    
  def on_songbook_prop(self, event = None):
    if not self.songbook:
      self.on_new_songbook()
      return
    
    def on_edit_child(song_ref):
      if isinstance(song_ref, model.SongRef):
        self.set_song(song_ref.get_song())
        
    self.edit(self.songbook, on_edit_child = on_edit_child)
    
  def on_bars_prop(self, event = None):
    mesures = self.canvas.get_selected_mesures()
    if mesures:
      if len(mesures) == 1: mesures = mesures[0]
      else:                 mesures = introsp.ObjectPack(mesures)
      self.edit(mesures)
      
  def on_playlist_prop(self, event = None):
    self.edit(self.song.playlist)
    
  def on_preferences(self, *args):
    globdef.config.edit()
    
  def on_play          (self, *args):
    player.play(songwrite2.midi.song_2_midi(self.song, trackable = 1), 0, self.canvas.play_tracker)
  def on_play_in_loop  (self, *args):
    player.play(songwrite2.midi.song_2_midi(self.song, trackable = 1), 1, self.canvas.play_tracker)
  def on_play_from_here(self, *args):
    player.play(songwrite2.midi.song_2_midi(self.song, self.canvas.get_selected_time(), trackable = 1), 0, self.canvas.play_tracker)
  def on_play_from_here_in_loop(self, *args):
    player.play(songwrite2.midi.song_2_midi(self.song, self.canvas.get_selected_time(), trackable = 1), 1, self.canvas.play_tracker)
  def on_stop_playing  (self, *args): player.stop()
  
  def on_space(self, *args): # space : play from the current position
    if player.is_playing(): player.stop()
    else: self.on_play_from_here()
    
          
  def on_select_all(self, *args):
    self.canvas.select_all()
    
  def on_note_paste(self, *args):
    self.canvas.on_note_paste()
      
  def on_insert_times(self, *args):
    class InsertTimesOptions(object):
      def __init__(self):
        self.nb_time       = 1
        self.details       = _(u"""Use negative values for deleting beats.""")
        self.icon_filename = os.path.join(globdef.DATADIR, "song.png")
      def __unicode__(self): return _(u"Insert/remove beats...")
    
    o = InsertTimesOptions()
    
    def on_validate(o):
      if (not o) or (not o.nb_time): return
      at = self.canvas.get_selected_time()
      delta = o.nb_time * 96
      removed = []
      
      def shift(delta):
        old_removed = removed[:]
        del removed[:]

        for partition in self.song.partitions:
          if isinstance(partition, model.Partition):
            i = 0
            while i < len(partition.notes):
              note = partition.notes[i]
              if note.time >= at:
                if (delta < 0) and note.time < at - delta:
                  #del partition.notes[i]
                  partition.remove(partition.notes[i])
                  removed.append((partition, note))
                  continue
                else: note.time += delta
              i += 1
              
        for partition, note in old_removed: partition.add_note(note)
        
        self.song.rythm_changed()
        
        self.canvas.render_all()
        self.canvas.update_time()
        
      def do_it  (): shift( delta)
      def undo_it(): shift(-delta)

      if o.nb_time > 0: name = _(u"insert %s beat(s)") %  o.nb_time
      else:             name = _(u"delete %s beat(s)") % -o.nb_time
      undoredo.UndoableOperation(do_it, undo_it, name, self.undo_stack)
      
    editobj2.edit(o, on_validate = on_validate)
    
  def on_insert_bars(self, *args):
    class InsertBarsOptions(object):
      def __init__(self):
        self.nb_bar        = 1
        self.details       = _(u"""Use negative values for deleting bars.""")
        self.icon_filename = os.path.join(globdef.DATADIR, "song.png")
      def __unicode__(self): return _(u"Insert/remove bars...")
    
    o = InsertBarsOptions()

    def on_validate(o):
      if (not o) or (not o.nb_bar): return
    
      mesures = self.canvas.get_selected_mesures()
      if mesures: mesure = mesures[0]
      else:       mesure = self.song.mesures[0]
      
      mesure_pos = self.song.mesures.index(mesure)
      at = mesure.time
      removed = []
      playlist_items_values = []
      
      def shift(nb_bar):
        # Add / remove mesures
        time = self.song.mesures[mesure_pos].time
        if nb_bar > 0:
          for i in range(mesure_pos, mesure_pos + nb_bar):
            self.song.mesures.insert(i, model.Mesure(self.song, time, mesure.tempo, mesure.rythm1, mesure.rythm2, mesure.syncope))
            time += mesure.duration
        else:
          del self.song.mesures[mesure_pos : mesure_pos - nb_bar]
          i = mesure_pos
          
        # Shift playlist
        if playlist_items_values:
          for item, from_mesure, to_mesure in playlist_items_values:
            item.from_mesure = from_mesure
            item.to_mesure   = to_mesure
          del playlist_items_values[:]
        else:
          for item in self.song.playlist.playlist_items:
            playlist_items_values.append((item, item.from_mesure, item.to_mesure))
            if   item.from_mesure >= mesure_pos:
              if item.from_mesure <  mesure_pos - nb_bar: item.from_mesure  = mesure_pos
              else:                                       item.from_mesure += nb_bar
            if   item.to_mesure   >= mesure_pos - 1:
              if item.to_mesure   <  mesure_pos-1-nb_bar: item.to_mesure   = mesure_pos - 1
              else:                                       item.to_mesure  += nb_bar
              
        # Shift notes
        old_removed = removed[:]
        del removed[:]

        delta = nb_bar * mesure.duration
        for partition in self.song.partitions:
          if isinstance(partition, model.Partition):
            i = 0
            while i < len(partition.notes):
              note = partition.notes[i]
              if note.time >= at:
                if (delta < 0) and note.time < at - delta:
                  partition.remove(partition.notes[i])
                  removed.append((partition, note))
                  continue
                else: note.time += delta
              i += 1
              
        for partition, note in old_removed: partition.add_note(note)

        self.song.rythm_changed() # AFTER moving the notes !!!
        
        self.canvas.render_all()
        self.canvas.update_time()
        
      def do_it  (): shift( o.nb_bar)
      def undo_it(): shift(-o.nb_bar)
      
      if o.nb_bar > 0: name = _(u"insert %s bar(s)") %  o.nb_bar
      else:            name = _(u"delete %s bar(s)") % -o.nb_bar
      undoredo.UndoableOperation(do_it, undo_it, name, self.undo_stack)
      
    editobj2.edit(o, on_validate = on_validate)
    
  def on_note_arrange(self, *args):
    class ArrangeAtFretOptions(object):
      def __init__(self):
        self.fret          = 0
        self.details       = _(u"Arrange selected notes at fret?")
        self.icon_filename = os.path.join(globdef.DATADIR, "song.png")
      def __unicode__(self): return _(u"Arrange notes at fret...")
    
    o = ArrangeAtFretOptions()
    
    def on_validate(o):
      if o:
        self.canvas.arrange_selection_at_fret(o.fret)
        
    editobj2.edit(o, on_validate = on_validate)
    
    
  def rythm_changed(self):
    self.song.rythm_changed()
    
  def on_dump(self, *args):
    print self.song.__xml__().getvalue()
    
  def on_gc(self, *args):
    import gc
    print gc.collect(), "object(s) collected"
    for o in gc.garbage: print "Garbage:", o
    print
    
    #import memtrack, weakref
    #ref = weakref.ref(self.songbook.song_refs[0].get_song())
    #if ref(): memtrack.reverse_track(ref())
    
    scan()
    


  


