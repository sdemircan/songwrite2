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

import os, os.path
import editobj2, editobj2.introsp as introsp, editobj2.field as field
import songwrite2.globdef as globdef, songwrite2.model as model

INSTRUMENTS = []
for i in _("__instru__").split("\n"): INSTRUMENTS.append(i.split(None, 1)[1])

INSTRUMENTS_2_ID = dict([(instrument, i) for (i, instrument) in enumerate(INSTRUMENTS)])

editobj2.TRANSLATOR = _


if editobj2.GUI == "Gtk":
  import gtk, editobj2.field_gtk as field_gtk, editobj2.editor_gtk as editor_gtk
  
  editor_gtk.SMALL_ICON_SIZE = 48
  
  # class GtkNoteValueField(field_gtk.GtkField, gtk.VBox):
  #   def __init__(self, gui, master, obj, attr, undo_stack):
  #     gtk.VBox.__init__(self)
  #     super(GtkNoteValueField, self).__init__(gui, master, obj, attr, undo_stack)
      
  #     self.label = gtk.Label()
  #     self.label.set_alignment(0.0, 0.5)
  #     self.pack_start(self.label, 0, 1)
      
  #     self.adjustment = gtk.Adjustment(1, 1, 90, 1, 12)
  #     self.scale = gtk.HScale(self.adjustment)
  #     self.scale.set_digits(0)
  #     self.pack_end(self.scale, 1, 1)
  #     self.update()
  #     self.scale.connect("value_changed", self.validate)
      
  #   def get_value(self):
  #     v = field.Field.get_value(self)
  #     if v is introsp.NonConsistent: return 0
  #     return v
    
  #   def validate(self, *args):
  #     v = int(round(self.adjustment.get_value()))
  #     if self.get_value() < 0: v = -v
  #     if isinstance(self.o, model.Note): self.label.set_text(unicode(self.o))
  #     else:                              self.label.set_text(model.note_label(v))
  #     self.set_value(v)

  #   def update(self):
  #     self.updating = 1
  #     try:
  #       v = abs(self.get_value())
  #       if isinstance(self.o, model.Note): self.label.set_text(unicode(self.o))
  #       else:                              self.label.set_text(model.note_label(v))
  #       self.adjustment.set_value(v)
  #     finally:
  #       self.updating = 0

  class GtkNoteValueField(field_gtk.GtkField, gtk.HBox):
    def __init__(self, gui, master, obj, attr, undo_stack):
      gtk.HBox.__init__(self)
      super(GtkNoteValueField, self).__init__(gui, master, obj, attr, undo_stack)
      
      self.octavo = gtk.combo_box_new_text()
      for i in range(0, 10):
        self.octavo.append_text(_(u"octavo %s") % i)
      self.pack_start(self.octavo, 1, 1)
      
      if hasattr(obj, "partition"): tonality = obj.partition.tonality
      else:                         tonality = "C"
      
      self.note = gtk.combo_box_new_text()
      for i in range(0, 12):
        self.note.append_text(model.note_label(i, False, tonality))
      self.pack_end(self.note, 1, 1)
      
      self.update()
      self.octavo.connect("changed", self.validate)
      self.note  .connect("changed", self.validate)
      
    def get_value(self):
      v = field.Field.get_value(self)
      if v is introsp.NonConsistent: return 0
      return v
    
    def validate(self, *args):
      if not self.updating:
        v = self.octavo.get_active() * 12 + self.note.get_active()
        if self.get_value() < 0: v = -v
        self.set_value(v)
        
    def update(self):
      self.updating = 1
      try:
        v = abs(self.get_value())
        self.octavo.set_active(v // 12)
        self.note  .set_active(v %  12)
      finally:
        self.updating = 0
        
        
  class GtkDurationField(field_gtk.GtkField, gtk.VBox):
    def __init__(self, gui, master, obj, attr, undo_stack):
      gtk.VBox.__init__(self)
      super(GtkDurationField, self).__init__(gui, master, obj, attr, undo_stack)
      self.options = []

      box  = gtk.HBox()
      box2 = gtk.HBox()
      box3 = gtk.HBox()

      for i in [1, 2, 3, 4, 5, 6]:
        #option = gtk.RadioButton((self.options and self.options[0]) or None, model.duration_label(6 * 2 ** i))
        option = gtk.RadioButton((self.options and self.options[0]) or None)
        image = gtk.Image()
        image.set_from_pixbuf(editor_gtk.load_small_icon(os.path.join(globdef.DATADIR, "note_%s.png" % (6 * 2 ** i))))
        option.set_image(image)
        self.options.append(option)


      self.pack_start(box , 0, 1)
      self.pack_start(box2, 0, 1)
      self.pack_start(box3, 0, 1)

      self.doted   = gtk.CheckButton(_("Doted"))
      self.triplet = gtk.CheckButton(_("Triplet"))
      box3.pack_start(self.doted  , 0, 1)
      box3.pack_start(self.triplet, 0, 1)

      self.update()

      self.doted  .connect("toggled", self.validate)
      self.triplet.connect("toggled", self.validate)
      for option in self.options[::-1]:
        option.set_property("draw-indicator", 0)
        option.set_property("relief"        , gtk.RELIEF_NONE)
        option.connect("toggled", self.validate)
        
      box .pack_start(self.options[5], 0, 1)
      box .pack_start(self.options[4], 0, 1)
      box2.pack_start(self.options[3], 0, 1)
      box2.pack_start(self.options[2], 0, 1)
      box2.pack_start(self.options[1], 0, 1)
      box2.pack_start(self.options[0], 0, 1)

    def get_value(self):
      v = field.Field.get_value(self)
      if v is introsp.NonConsistent: return 0
      return v
      
    def validate(self, *args):
      for i, option in enumerate(self.options):
        if option.get_active():
          v = 6 * 2 ** (i + 1)
          break
      else: v = 0
      if   self.doted  .get_active(): v = int(v * 1.5)
      elif self.triplet.get_active(): v = int(v / 1.5)
      self.set_value(v)

      if not self.updating:
        import songwrite2.main
        songwrite2.main.APPS[self.o.partition.song].canvas.current_duration = v
        
    def update(self):
      self.updating = 1
      try:
        v = self.get_value()

        if v in (9, 18, 36, 72, 144, 288, 576):
          v = int(v / 1.5)
          self.doted.set_active(1)
        else:
          self.doted.set_active(0)

        if v in (4,  8, 16, 32,  64, 128, 256):
          v = int(v * 1.5)
          self.triplet.set_active(1)
        else:
          self.triplet.set_active(0)

        i = { 12 : 0, 24: 1, 48 : 2, 96 : 3, 192 : 4, 384 : 5 }.get(v)
        if not i is None:
          self.options[i].set_active(1)
      finally:
        self.updating = 0
        
  NoteValueField = GtkNoteValueField
  DurationField  = GtkDurationField
  
else: # Qt
  import qt
  if editobj2.GUI == "Qt":
    import editobj2.field_qt as field_qt, editobj2.editor_qt as editor_qt
  else:
    import editobj2.field_qtopia as field_qt, editobj2.editor_qtopia as editor_qt
  
  editor_qt.SMALL_ICON_SIZE = 48
  
  choices = {}
  for octavo in range(8):
    for note in range(12):
      x = note + 12 * octavo
      choices[model.note_label(x)] = x
      
  NoteValueField = editobj2.field.EnumField(choices, long_list = 1, translate = 0)
  
  DurationField = NoteValueField
  
        
introsp.set_field_for_attr("details"      , None)
introsp.set_field_for_attr("icon_filename", None)

descr = introsp.description(globdef.Config)
descr.set_label  (_("Preferences"))
descr.set_details(_("__config_preamble__"))
descr.set_field_for_attr("MIDI_USE_TEMP_FILE", None)
descr.set_field_for_attr("PREVIOUS_FILES", None)
descr.set_field_for_attr("ASK_FILENAME_ON_EXPORT", field.BoolField)
descr.set_field_for_attr("PAGE_FORMAT", field.EnumField({ _("A3") : "a3paper", _("A4") : "a4paper", _("A5") : "a5paper", _("letter") : "letterpaper" }))
#descr.set_field_for_attr("SIDE_BAR_POSITION", field.EnumField(["left", "right", "top", "bottom", "floating_horizontal", "floating_vertical", "none"]))
descr.set_field_for_attr("SIDE_BAR_POSITION", None)
descr.set_field_for_attr("PLAY_AS_TYPING", field.BoolField)
descr.set_field_for_attr("DISPLAY_PLAY_BAR", field.BoolField)
descr.set_field_for_attr("NUMBER_OF_PREVIOUS_FILES", field.IntField)
descr.set_field_for_attr("AUTOMATIC_DURATION", field.BoolField)
descr.set_field_for_attr("FONTSIZE", field.IntField)
descr.set_field_for_attr("ENGLISH_CHORD_NAME", field.BoolField)


def ask_new_song_ref(songbook):
  import songwrite2.main     as main
  filename = main.APPS[songbook].prompt_open_filename(".sw.xml")
  if not filename: return None
  song_ref = model.SongRef(songbook)
  song_ref.set_filename(filename)
  return song_ref

descr = introsp.description(model.Songbook)
descr.set_icon_filename(os.path.join(globdef.DATADIR, "songbook.png"))
descr.set_children_getter("song_refs", None, ask_new_song_ref, "insert_song_ref", "remove_song_ref", 1)
#descr.set_field_for_attr("song_refs", field.ObjectHEditorField)
descr.set_field_for_attr("title"    , field.StringField)
descr.set_field_for_attr("authors"  , field.StringField)
descr.set_field_for_attr("comments" , field.TextField)
descr.set_field_for_attr("version"  , None)
descr.set_field_for_attr("filename" , None)

descr = introsp.description(model.SongRef)
descr.set_icon_filename(os.path.join(globdef.DATADIR, "song.png"))
descr.set_field_for_attr("filename", field.FilenameField)
descr.set_field_for_attr("title"   , None)
descr.set_field_for_attr("songbook", None)


class PartitionCategory(object):
  def __init__(self, name, details, children = None):
    self.name          = name
    self.details       = details
    self.icon_filename = os.path.join(globdef.DATADIR, "no_icon.png") #icon_filename
    self.children      = children or []
  def __unicode__(self): return self.name
descr = introsp.description(PartitionCategory)
descr.set_field_for_attr("name", None)

def ask_new_partition(song):
  next_strophe_number = len([lyrics for lyrics in song.partitions if isinstance(lyrics, model.Lyrics) and _(u"Strophe #%s").replace(u"%s", u"") in lyrics.header]) + 1
  
  categories = []
  for category in model.VIEW_CATEGORIES:
    view_types = model.VIEWS[category]
    categories.append(
      PartitionCategory(_(category), u"", [model.Partition(None, view_type.default_instrument, view_type) for view_type in view_types])
      )
  categories.append(PartitionCategory(_(u"Lyrics"), u"", [
    model.Lyrics(None, header = _(u"Chorus")),
    model.Lyrics(None, header = _(u"Strophe #%s") % next_strophe_number),
    ]))
  categories = PartitionCategory(_(u"__add_partition__"), _(u"__add_partition_details__"), categories)

  r = [None]
  def on_validate(choice):
    if choice:
      if isinstance(choice, introsp.ObjectPack): r[0] = choice.objects[0]
      else:                                      r[0] = choice
    if not isinstance(r[0], model.TemporalData): r[0] = None
    else:                                        r[0].song = song
    
  editobj2.edit(categories, on_validate = on_validate, height = 680, expand_tree_at_level = 2)
  
  return r[0]


import songwrite2.plugins.ps_native.ps_latex

descr = introsp.description(model.Song)
descr.set_icon_filename(os.path.join(globdef.DATADIR, "song.png"))
descr.set_children_getter("partitions", None, ask_new_partition, "insert_partition", "remove_partition", 1)
descr.set_field_for_attr("title"    , field.StringField)
descr.set_field_for_attr("authors"  , field.StringField)
descr.set_field_for_attr("copyright", field.StringField)
descr.set_field_for_attr("comments" , field.TextField)
descr.set_field_for_attr("filename" , None)
descr.set_field_for_attr("playlist" , None)
descr.set_field_for_attr("version"  , None)
descr.set_field_for_attr("lang"     , field.EnumField(dict((_(u"__lang__%s" % code), code) for code in songwrite2.plugins.ps_native.ps_latex.lang_iso2latex.keys()), long_list = 0))
descr.set_field_for_attr("print_nb_mesures_per_line", field.RangeField(1, 20))
descr.set_field_for_attr("printfontsize", field.RangeField(6, 28))
descr.set_field_for_attr("print_with_staff_too", field.BoolField)

def partition_2_icon_filename(self):
  return os.path.join(globdef.DATADIR, self.view.get_icon_filename())


VIEW_TYPE_NAMES = dict([(_(view_type.__name__), view_type) for view_types in model.VIEWS.values() for view_type in view_types])

def view_value_2_enum(partition, view_type):
  if hasattr(view_type, "__name__"): return _(view_type.__name__)
  return u""

def view_enum_2_value(partition, view_type_name):
  return VIEW_TYPE_NAMES[view_type_name]

class Tuning(object):
  def __init__(self, strings):
    self.strings = strings
    self._string_class = strings[0].__class__

  def __unicode__(self): return _(u"Tuning")
  
  def insert(self, index, string):
    self.strings.insert(index, string)
    
  def remove(self, string):
    self.strings.remove(string)
    
  def new_child(self):
    return self._string_class()

def get_tuning(partition):
  if hasattr(partition.view, "strings"):
    return Tuning(partition.view.strings)
  return None

descr = introsp.description(Tuning)
descr.set_icon_filename(os.path.join(globdef.DATADIR, "guitar.png"))
descr.set_children_getter("strings", None, "new_child", "insert", "remove", 1)

def nb_sharp_or_bemol(tonality):
  alterations = model.TONALITIES[tonality]
  if not alterations: return u""
  if alterations[0] is model.DIESES[0]: return u"\t(%s ♯)" % len(alterations)
  return u"\t(%s ♭)" % len(alterations)

descr = introsp.description(model.Partition)
descr.set_icon_filename(partition_2_icon_filename)
#descr.set_children_getter(lambda partition: getattr(partition.view, "strings", None))
descr.set_field_for_attr("header"    , field.TextField)
descr.set_field_for_attr("instrument", field.EnumField(INSTRUMENTS_2_ID))
descr.set_field_for_attr("tonality"           , field.EnumField(dict([(_("tonality_%s" % tonality) + nb_sharp_or_bemol(tonality), tonality) for tonality in model.TONALITIES.keys()])))
descr.set_field_for_attr("instrument_tonality", field.EnumField(dict([(_("tonality_%s" % tonality), tonality) for tonality in model.TONALITIES.keys()])))
descr.set_field_for_attr("view"      , None)
descr.set_field_for_attr("view_type" , field.EnumField(VIEW_TYPE_NAMES.keys(), value_2_enum = view_value_2_enum, enum_2_value = view_enum_2_value))
descr.set_field_for_attr("capo"      , field.IntField)
descr.set_field_for_attr("g_key"     , field.BoolField)
descr.set_field_for_attr("f_key"     , field.BoolField)
descr.set_field_for_attr("g8"        , field.BoolField)
descr.set_field_for_attr("print_with_staff_too", field.BoolField)
descr.set_field_for_attr("volume"    , field.RangeField(0, 255))
descr.set_field_for_attr("muted"     , field.BoolField)
descr.set_field_for_attr("chorus"    , field.RangeField(0, 127))
descr.set_field_for_attr("reverb"    , field.RangeField(0, 127))
descr.set_field_for_attr("let_ring"  , field.BoolField)
#descr.set_field_for_attr("visible"   , field.BoolField)
descr.set_field_for_attr("visible"   , None)
descr.set_field_for_attr("tuning"    , field.EditButtonField)
descr.add_attribute(introsp.Attribute("visible", lambda partition: partition.view.visible, lambda partition, visible: setattr(partition.view, "visible", visible)))
descr.add_attribute(introsp.Attribute("tuning" , get_tuning))


def string_2_icon_filename(self):
  return os.path.join(globdef.DATADIR, "string_%s.png" % self.width())
  
descr = introsp.description(model.TablatureString)
descr.set_icon_filename(string_2_icon_filename)
descr.set_field_for_attr("base_note"   , NoteValueField)
#descr.set_field_for_attr("notation_pos", field.EnumField({_("Upper") : -1, _("Lower") : 1}))
descr.set_field_for_attr("notation_pos", None)

descr = introsp.description(model.DrumString)
descr.set_icon_filename(os.path.join(globdef.DATADIR, "tamtam.png"))
descr.set_field_for_attr("base_note"   , NoteValueField)
#descr.set_field_for_attr("notation_pos", field.EnumField({_("Upper") : -1, _("Lower") : 1}))
descr.set_field_for_attr("notation_pos", None)


def note_2_icon_filename(self):
  filename = os.path.join(globdef.DATADIR, "note_%s.png" % self.duration)
  if os.path.exists(filename): return filename
  return os.path.join(globdef.DATADIR, "note_96.png")
  
descr = introsp.description(model.Note)
descr.set_icon_filename(note_2_icon_filename)
descr.set_field_for_attr("string_id"   , None)
descr.set_field_for_attr("time"        , None)
descr.set_field_for_attr("duration"    , DurationField)
descr.set_field_for_attr("fx"          , field.EnumField(dict((_(fx or u"(none)"), fx) for fx in model.FXS)))
descr.set_field_for_attr("link_fx"     , field.EnumField(dict((_(fx or u"(none)"), fx) for fx in model.LINK_FXS)))
descr.set_field_for_attr("duration_fx" , field.EnumField(dict((_(fx or u"(none)"), fx) for fx in model.DURATION_FXS)))
descr.set_field_for_attr("strum_dir_fx", field.EnumField(dict((_(fx or u"(none)"), fx) for fx in model.STRUM_DIR_FXS)))
descr.set_field_for_attr("volume"      , field.RangeField(0, 255))
descr.set_field_for_attr("value"       , NoteValueField)
descr.set_field_for_attr("strum_dir"   , field.EnumField({_("(none)") : 0, "up" : -1, "down" : 1, "down_thumb" : 2, "down_fingers" : 3}))
descr.set_field_for_attr("button_rank" , None)
descr.set_field_for_attr("bellows_dir" , None)

descr = introsp.description(model.Mesure)
descr.set_icon_filename(os.path.join(globdef.DATADIR, "bar.png"))
descr.set_field_for_attr("number"   , None)
descr.set_field_for_attr("time"     , None)
descr.set_field_for_attr("duration" , None)
descr.set_field_for_attr("rythm1"   , field.EnumField([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]))
descr.set_field_for_attr("rythm2"   , field.EnumField([4, 8]))
descr.set_field_for_attr("tempo"    , field.IntField)
descr.set_field_for_attr("syncope"  , field.BoolField)

def new_playlist_item(playlist):
  import songwrite2.main as main
  app = main.APPS[playlist.song]
  mesure = app.selected_mesure
  if isinstance(mesure, model.Mesure): start = end = mesure.get_number()
  else:
    mesure_numbers = [mesure.get_number() for mesure in mesure.objects]
    start = min(mesure_numbers)
    end   = max(mesure_numbers)
  return model.PlaylistItem(playlist, start, end)

descr = introsp.description(model.Playlist)
descr.set_icon_filename(os.path.join(globdef.DATADIR, "playlist.png"))
descr.set_children_getter("playlist_items", None, new_playlist_item, "insert", "remove", 1)

descr = introsp.description(model.PlaylistItem)
descr.set_icon_filename(os.path.join(globdef.DATADIR, "playlist.png"))
descr.set_field_for_attr("playlist", None)
descr.set_field_for_attr("from_mesure", None)
descr.set_field_for_attr("to_mesure", None)
def get_from_mesure1(o)   : return o.from_mesure + 1
def get_to_mesure1  (o)   : return o.to_mesure   + 1
def set_from_mesure1(o, x): o.from_mesure = x - 1
def set_to_mesure1  (o, x): o.to_mesure   = x - 1
descr.add_attribute(introsp.Attribute("from_mesure1", get_from_mesure1, set_from_mesure1))
descr.add_attribute(introsp.Attribute("to_mesure1"  , get_to_mesure1  , set_to_mesure1  ))

descr = introsp.description(model.Lyrics)
descr.set_icon_filename(os.path.join(globdef.DATADIR, "lyrics.png"))
descr.set_field_for_attr("text"  , None)
descr.set_field_for_attr("melody", None)
descr.set_field_for_attr("header", field.TextField)
descr.set_field_for_attr("show_all_lines_on_melody"  , field.BoolField)
descr.set_field_for_attr("show_all_lines_after_score", field.BoolField)

