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

from songwrite2.main import *
from songwrite2.canvas import Canvas

import gobject, gtk

mainloop = gtk.main

sw_xml_filter = gtk.FileFilter()
sw_xml_filter.set_name(_(u"__songwrite_file_format__"))
sw_xml_filter.add_pattern(u"*.sw.xml")

MENU_LABEL_2_IMAGE = {
  u"Open..."        : gtk.STOCK_OPEN,
  u"Save"           : gtk.STOCK_SAVE,
  u"Save as..."     : gtk.STOCK_SAVE_AS,
  u"Close"          : gtk.STOCK_CLOSE,
  u"Undo"           : gtk.STOCK_UNDO,
  u"Redo"           : gtk.STOCK_REDO,
  u"Paste"          : gtk.STOCK_PASTE,
  u"Preferences..." : gtk.STOCK_PREFERENCES,
  }

icon_factory = gtk.IconFactory()
icon_factory.add_default()

class App(BaseApp, gtk.Window):
  def menu_image(self, filename):
    image = editobj2.editor_gtk.load_big_icon(os.path.join(globdef.DATADIR, filename))
    return image
  
  def append_to_menu(self, menu, has_submenu, label, command = None, arg = None, accel = "", accel_enabled = 1, image = None, type = u"button"):
    if isinstance(menu, gtk.MenuItem):
      m = menu.get_submenu()
      if not m:
        m = gtk.Menu()
        menu.set_submenu(m)
      menu = m
    stock = MENU_LABEL_2_IMAGE.get(label)
    if stock:
      menu_item = gtk.ImageMenuItem(stock)
    elif image:
      gtk.stock_add([(label, _(label).replace("_", "__"), gtk.gdk.SHIFT_MASK, 46, "")])
      icon_factory.add(label, gtk.IconSet(image))
      menu_item = gtk.ImageMenuItem(label)
    elif type == "check":
      menu_item = gtk.CheckMenuItem(_(label).replace("_", "__"))
    elif type == "radio":
      menu_item = gtk.RadioMenuItem(self.current_radio_group, _(label).replace("_", "__"))
      self.current_radio_group = menu_item
    else:
      menu_item = gtk.MenuItem(_(label).replace("_", "__"))
    if command:
      if arg: menu_item.connect("activate", command, arg)
      else:   menu_item.connect("activate", command)
    menu.append(menu_item)
    
    if accel:
      mod = 0
      if isinstance(accel, basestring):
        if u"C-" in accel: mod |= gtk.gdk.CONTROL_MASK
        if u"S-" in accel: mod |= gtk.gdk.SHIFT_MASK
        key = ord(accel[-1])
      else: key = accel
      menu_item.add_accelerator("activate", self.accel_group, key, mod, gtk.ACCEL_VISIBLE)
      if not accel_enabled:
        menu_item.connect("can-activate-accel", self.can_activate_accel)
    return menu_item
  
  def can_activate_accel(self, widget, signal):
    widget.stop_emission("can-activate-accel")
    return False
  
  def append_separator_to_menu(self, menu):
    menu.get_submenu().append(gtk.SeparatorMenuItem())
    self.current_radio_group = None

  def create_menubar(self):
    return gtk.MenuBar()
  
  def __init__(self, song = None):
    gtk.Window.__init__(self)

    self.instrument_chooser_pane = None
    self.current_radio_group     = None
    self.set_icon(editobj2.editor_gtk.load_big_icon(os.path.join(globdef.DATADIR, "songwrite2_64x64.png")))
    
    self.accel_group = gtk.AccelGroup()
    self.add_accel_group(self.accel_group)
    self.set_role("main")
    
    self.vbox = gtk.VBox()
    self.add(self.vbox)

    BaseApp.__init__(self, None)

    toolbar = self.toolbar = gtk.Toolbar()
    toolbar.set_style(gtk.TOOLBAR_ICONS)
    toolbar.set_show_arrow(0)

    def add_toolbar_button(label, command, image = None, ButtonClass = gtk.ToolButton):
      if image:
        gtk.stock_add([(label, _(label).replace("_", "__"), gtk.gdk.SHIFT_MASK, 46, "")])
        icon_factory.add(label, gtk.IconSet(self.menu_image(image)))
      if ButtonClass is gtk.RadioToolButton:
        b = ButtonClass(add_toolbar_button.radio_group, label)
        add_toolbar_button.radio_group = b
      else:
        b = ButtonClass(label)
      tooltip = _(label)
      tooltip = tooltip[0].upper() + tooltip[1:]
      b.set_tooltip_text(tooltip)
      b.connect("clicked", command)
      toolbar.insert(b, -1)
      return b
    def add_toolbar_separator():
      toolbar.insert(gtk.SeparatorToolItem(), -1)
      add_toolbar_button.radio_group = None

    add_toolbar_button(gtk.STOCK_SAVE      , self.on_save)
    add_toolbar_button(gtk.STOCK_PRINT     , self.on_preview_print)
    add_toolbar_button(gtk.STOCK_MEDIA_PLAY, self.on_play_from_here)
    add_toolbar_button(gtk.STOCK_MEDIA_STOP, self.on_stop_playing)
    add_toolbar_separator()

    for duration in [384, 192, 96, 48, 24, 12]:
      setattr(self, "toolbar_duration_%s" % duration, add_toolbar_button(model.DURATIONS[duration], getattr(self, "set_duration_%s" % duration), "note_%s.png" % duration, ButtonClass = gtk.RadioToolButton))

    self.toolbar_dotted  = add_toolbar_button(u"Dotted"     , self.toggle_dotted , "note_144.png"    , ButtonClass = gtk.ToggleToolButton)
    self.toolbar_triplet = add_toolbar_button(u"Triplet"    , self.toggle_triplet, "note_64.png"     , ButtonClass = gtk.ToggleToolButton)
    add_toolbar_separator()
    self.toolbar_accent  = add_toolbar_button(u"Accentuated", self.toggle_accent , "effet_accent.png", ButtonClass = gtk.ToggleToolButton)

    self.toolbar_buttons = {}
    for type, fxs in model.ALL_FXS:
      for fx in fxs:
        if not fx: continue
        if fx == u"bend": func = self.set_fx_bend05
        else:             func = getattr(self, "set_fx_%s" % fx)
        self.toolbar_buttons[fx] = add_toolbar_button(fx, func, "effet_%s.png" % fx, ButtonClass = gtk.ToggleToolButton)
          
    zoom_menubar = gtk.MenuBar()
    
    def change_zoom(menu_item, incr):
      gobject.timeout_add(100, zoom_menubar.cancel)
      self.canvas.change_zoom(incr)
      
    def set_zoom(menu_item, zoom):
      self.canvas.set_zoom(zoom)
      
    zoom_out_menu = self.append_to_menu(zoom_menubar, 0, u" ‒ ")
    zoom_menu  = self.zoom_menu = self.append_to_menu(zoom_menubar, 1, u"100%")
    for zoom in songwrite2.canvas.zoom_levels: self.append_to_menu(zoom_menu, 0, u"%s%%" % int(zoom * 100.0), set_zoom, arg = zoom)
    zoom_in_menu  = self.append_to_menu(zoom_menubar, 0, u" + ")
    
    zoom_out_menu.connect("select", change_zoom, -1)
    zoom_in_menu .connect("select", change_zoom,  1)
    
    menu_box = gtk.HBox()
    self.vbox.pack_start(menu_box, 0, 1)
    
    menu_box.pack_start(self.menubar, 1, 1)
    menu_box.pack_end  (zoom_menubar, 0, 1)
    
    self.vbox.pack_start(toolbar, 0, 1)
      
    self.connect("delete-event", self.on_close)
    
    if song: self.set_song(song)
    
    self.show_all()
    observe(globdef.config, self.config_listener)
    
  def set_selected_note(self, note):
    BaseApp.set_selected_note(self, note)
    if isinstance(note, introsp.ObjectPack):
      mesure_ids   = set([self.song.mesure_at(n).get_number() + 1 for n in note.objects])
      if len(mesure_ids) == 1:
        mesure_label = self.song.mesure_at(note.objects[0])
      else:
        mesure_label = _(u"Bars #%s to #%s") % (min(mesure_ids), max(mesure_ids))
      if len(note.objects) == 2:
        delta = abs(note.objects[0].value - note.objects[1].value)
        note_label = _(u"__interval__%s" % delta)
        if note_label.startswith(u"_"): note_label = u"2 %s" % _("notes")
      else:
        note_label = unicode(len(note.objects)) + u" " + _("notes")
      note = note.objects[-1]
    else:
      mesure_label = self.song.mesure_at(note)
      note_label = unicode(note)
      
    self.updating_duration = 1
    self.updating_volume_fx = 1
    getattr(self, "toolbar_duration_%s" % note.base_duration()).set_active(1)
    self.toolbar_dotted .set_active(note.is_dotted())
    self.toolbar_triplet.set_active(note.is_triplet())
    self.toolbar_accent .set_active(note.volume == 255)
    
    fxs = set([note.fx, note.link_fx, note.duration_fx, note.strum_dir_fx])
    for key, button in self.toolbar_buttons.iteritems():
      button.set_active(key in fxs)
      
    self.updating_duration = 0
    self.updating_volume_fx = 0
    
    self.set_title(u"Songwrite2 -- %s -- %s -- %s" % (self.song.title, mesure_label, note_label))
    
  def config_listener(self, obj, type, new, old):
    self.canvas.config_listener(obj, type, new, old)
    #if type is object:
    #  if new["SIDE_BAR_POSITION"] != old["SIDE_BAR_POSITION"]: self.create_content()
    pass
    
  def create_content(self):
    if   self.floating: self.floating.destroy()
    if   self.paned:    self.paned   .destroy()
    elif self.scrolled: self.scrolled.destroy()
    
    # if   (globdef.config.SIDE_BAR_POSITION == "left") or (globdef.config.SIDE_BAR_POSITION == "right") or (globdef.config.SIDE_BAR_POSITION == "floating_vertical"):
    #   self.notebook = EditNotebook(self.undo_stack, gtk.POS_TOP)
    #   self.notebook.set_current_page(self.notebook.get_n_pages() - 1)
    # elif (globdef.config.SIDE_BAR_POSITION == "top") or (globdef.config.SIDE_BAR_POSITION == "bottom") or (globdef.config.SIDE_BAR_POSITION == "floating_horizontal"):
    #   self.notebook = EditNotebook(self.undo_stack, gtk.POS_LEFT)
    #   self.notebook.set_size_request(-1, 310)
    # else:
    #   self.notebook = None
      
    # if   (globdef.config.SIDE_BAR_POSITION == "left") or (globdef.config.SIDE_BAR_POSITION == "right"):
    #   self.paned    = gtk.HPaned()
    #   self.floating = None
    # elif (globdef.config.SIDE_BAR_POSITION == "top") or (globdef.config.SIDE_BAR_POSITION == "bottom"):
    #   self.paned    = gtk.VPaned()
    #   self.floating = None
    # elif (globdef.config.SIDE_BAR_POSITION == "floating_horizontal") or (globdef.config.SIDE_BAR_POSITION == "floating_vertical"):
    #   self.paned    = None
    #   self.floating = gtk.Window()
    #   self.floating.set_role("toolbox")
    #   self.floating.set_transient_for(self)
    #   self.floating.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_UTILITY)
    #   self.floating.set_destroy_with_parent(1)
    # else:
    #   self.paned    = None
    #   self.floating = None
    self.paned    = None
    self.floating = None
    self.notebook = None
     
    if self.notebook:
      if self.songbook:
        self.songbook_pane = SongbookPane(self, self.undo_stack)
        self.notebook.add_tab(self.songbook, self.songbook_pane)
        self.songbook_pane.set_songbook(self.songbook)
        
      self.notebook.add_tab(self.song)
      
      self.partitions_pane = PartitionsPane(self, self.undo_stack)
      self.notebook.add_tab(self.song.partitions[0], self.partitions_pane, 0)
      self.playlist_pane = PlaylistPane(self, self.undo_stack)
      self.playlist_pane.set_playlist(self.song.playlist)
      self.notebook.add_tab(self.song.mesures[0], self.playlist_pane)
      self.notebook.add_tab(None)
      self.notebook.show_all()
      self.notebook.set_current_page(-1)
      
      
    self.scrolled = gtk.ScrolledWindow()
    self.scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    self.scrolled.set_size_request(800, 400)

    self.canvas = Canvas(self, model.Song(), self.scrolled)
    self.instrument_chooser_pane = InstrumentChooserPane(self)
    self.scrolled.add(self.instrument_chooser_pane)
    self.set_title(u"Songwrite2")
    
    # if   globdef.config.SIDE_BAR_POSITION == "left":
    #   self.paned.pack1(self.notebook, 0, 1)
    #   self.paned.pack2(self.scrolled, 1, 1)
    # elif globdef.config.SIDE_BAR_POSITION == "right":
    #   self.paned.pack2(self.notebook, 0, 1)
    #   self.paned.pack1(self.scrolled, 1, 1)
    # elif globdef.config.SIDE_BAR_POSITION == "top":
    #   self.paned.pack1(self.notebook, 0, 1)
    #   self.paned.pack2(self.scrolled, 1, 1)
    # elif globdef.config.SIDE_BAR_POSITION == "bottom":
    #   self.paned.pack2(self.notebook, 0, 1)
    #   self.paned.pack1(self.scrolled, 1, 1)
    # elif (globdef.config.SIDE_BAR_POSITION == "floating_horizontal") or (globdef.config.SIDE_BAR_POSITION == "floating_vertical"):
    #   self.floating.add(self.notebook)
    #   self.floating.show_all()
    #   self.vbox.pack_end(self.scrolled, 1, 1)
    # else:
    #   self.vbox.pack_end(self.scrolled, 1, 1)
    self.vbox.pack_end(self.scrolled, 1, 1)
      
    #if self.paned:
    #  self.paned.set_border_width(3)
    #  self.vbox.pack_end(self.paned, 1, 1)
      
    self.show_all()
    
  def on_new(self, *args):
    if self.check_save(): return
    
    self.set_songbook(None)
    
    if self.instrument_chooser_pane:
      self.scrolled.remove(self.instrument_chooser_pane)
      self.instrument_chooser_pane = None
    if getattr(self, "canvas", None): self.canvas.destroy()
    
    self.canvas = Canvas(self, model.Song(), self.scrolled)
    self.instrument_chooser_pane = InstrumentChooserPane(self)
    self.scrolled.add(self.instrument_chooser_pane)
    self.instrument_chooser_pane.show_all()
    self.set_title(u"Songwrite2")
    
  def set_song(self, song):
    BaseApp.set_song(self, song)

    zoom = 1.0
    if self.instrument_chooser_pane:
      self.scrolled.remove(self.instrument_chooser_pane)
      self.instrument_chooser_pane = None
      
    elif getattr(self, "canvas", None):
      zoom = self.canvas.zoom
      self.canvas.destroy()
      
    self.canvas = songwrite2.canvas.Canvas(self, self.song, self.scrolled, zoom)
    self.scrolled.add(self.canvas)
    self.set_focus(self.canvas.canvas)
      
    #self.set_title(u"Songwrite2 -- %s" % song.title)
    if hasattr(self, "notebook"):
      self.show_all()

  def set_menu_enable(self, menu, enable): menu.set_sensitive(enable)
  def set_menu_label (self, menu, label ): menu.get_child().set_text(label)
    
  def prompt_open_filename(self, exts, format = u""):
    if exts == "sw.xml": filter = sw_xml_filter
    else:
      filter = gtk.FileFilter()
      filter.set_name(format)
      if isinstance(exts, basestring): exts = [exts]
      for ext in exts:
        filter.add_pattern(u"*" + ext)
        
    dialog = gtk.FileChooserDialog(_(u"Open..."), self, gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
    dialog.set_default_response(gtk.RESPONSE_OK)
    dialog.add_filter(filter)
    dialog.set_filename(os.path.join(globdef.config.LAST_DIR, u"DOES_NOT_EXIST"))
    response = dialog.run()
    filename = dialog.get_filename()
    dialog.destroy()
    if response != gtk.RESPONSE_OK: return
    return filename
  
  def prompt_save_filename(self, exts, format = u""):
    if not self.filename: self.filename = self.song.title.lower().replace(u" ", u"_").replace(u"'", u"").replace(u"/", u"_").replace(u"é", u"e").replace(u"è", u"e").replace(u"ê", u"e").replace(u"ë", u"e").replace(u"à", u"a").replace(u"â", u"a").replace(u"ù", u"u").replace(u"û", u"u").replace(u"î", u"i").replace(u"ï", u"i")
    
    if exts == "sw.xml": filter = sw_xml_filter
    else:
      filter = gtk.FileFilter()
      filter.set_name(format)
      if isinstance(exts, basestring): exts = [exts]
      for ext in exts:
        filter.add_pattern(u"*" + ext)
        
    dialog = gtk.FileChooserDialog(_(u"Save as..."), self, gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_OK))
    dialog.set_property("do-overwrite-confirmation", 1)
    dialog.set_default_response(gtk.RESPONSE_OK)
    
    if isinstance(exts, basestring): ext0 = exts
    else:                            ext0 = exts[0]
    
    dialog.add_filter(filter)
    dialog.set_current_folder(os.path.dirname(self.filename) or globdef.config.LAST_DIR)
    dialog.set_current_name(os.path.basename(self.filename).replace("sw.xml", ext0))
    response = dialog.run()
    filename = dialog.get_filename()
    dialog.destroy()
    if response != gtk.RESPONSE_OK: return
    return filename
  
  def on_open(self, event = None):
    if self.check_save(): return
    
    filename = self.prompt_open_filename("sw.xml")
    if not filename: return
    self.open_filename(filename, do_check_save = 0) # check_save has already been done before asking the filename
    
  def check_save(self):
    if not self.song: return 0
    
    if self.undo_stack.undoables != self.last_undoables:
      # The undoable actions have changed => the song need to be saved.
      dialog = gtk.MessageDialog(self, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING, message_format = _(u"Save the modification before closing?"))
      dialog.add_buttons(
        _(u"Close without saving"), 0,
        gtk.STOCK_CANCEL, 1,
        gtk.STOCK_SAVE, 2,
        )
      dialog.set_default_response(1)
      response = dialog.run()
      dialog.destroy()
      if   response == 0: return 0
      if   response == 1: return 1
      elif response == 2:
        self.on_save()
        return self.check_save() # The user may have canceled the save as dialog box !
      
    else: return 0
    
          
    



      

class EditNotebook(gtk.Notebook):
  def __init__(self, undo_stack, tab_pos, *objs):
    gtk.Notebook.__init__(self)
    self.undo_stack      = undo_stack
    self.set_tab_pos(tab_pos)
    self.current         = 0
    self.tab_width       = 0
    self.objs            = []
    self.icon_panes      = []
    self.attribute_panes = []
    self.extra_widgets   = []
    for obj in objs: self.add_tab(obj)
    
    self.connect("switch-page", self.on_switch_page)
    
  def delete_tab(self, i):
    self.remove_page(i)
    del self.objs           [i]
    del self.icon_panes     [i]
    del self.attribute_panes[i]
    del self.extra_widgets  [i]
    
  def add_tab(self, obj = None, widget = None, widget_extend = 1):
    self.insert_tab(len(self.objs), obj, widget, widget_extend)
    
  def insert_tab(self, i, obj = None, widget = None, widget_extend = 1):
    label          = gtk.Label()
    icon_pane      = editor.IconPane     ("Gtk", self, 1, 1, 0)
    attribute_pane = editor.AttributePane("Gtk", self, None, self.undo_stack)
    self.objs           .insert(i, None)
    self.icon_panes     .insert(i, icon_pane)
    self.attribute_panes.insert(i, attribute_pane)
    self.extra_widgets  .insert(i, widget)
    
    scroll = gtk.ScrolledWindow()
    scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
    scroll.add_with_viewport(attribute_pane)
    scroll.get_child().set_shadow_type(gtk.SHADOW_NONE)
    scroll.set_border_width(5)
    
    if widget:
      if self.get_tab_pos() in (gtk.POS_LEFT, gtk.POS_RIGHT): page = gtk.HBox()
      else:                                                   page = gtk.VBox()
      page.pack_start(scroll, 1, 1)
      if self.get_tab_pos() in (gtk.POS_LEFT, gtk.POS_RIGHT): page.pack_start(gtk.VSeparator(), 0, 0)
      else:                                                   page.pack_start(gtk.HSeparator(), 0, 0)
      page.pack_end  (widget, widget_extend, 1)
    else:
      page = scroll
      
    self.insert_page(page, icon_pane, i)
    self.set_tab_label_packing(page, 1, 0, gtk.PACK_START)
    
    if obj: self.edit(i, obj)
    
    if (i <= self.current) and (self.current < len(self.objs) - 1): self.current += 1
    
    self.show_all()
    
  def edit(self, i, obj, force = 0):
    if i < 0: i = len(self.objs) + i
    
    if not self.objs[i] is obj:
      self.objs[i] = obj
      self.icon_panes[i].edit(obj)
      if self.extra_widgets[i]: self.extra_widgets[i].edit(obj)
      
      self.icon_pane_changed(self.icon_panes[i])
      if (i == self.current) or force:
        self.attribute_panes[i].edit(obj)
      if (i == len(self.objs) - 2): self.check_mesures()
      
      
  def check_mesures(self):
    if isinstance(self.objs[-2], introsp.ObjectPack):
      numbers = [m.get_number() for m in self.objs[-2].objects]
      if numbers:
        label = _(u"Bars #%s to #%s") % (min(numbers) + 1, max(numbers) + 1)
        if self.current == len(self.objs) - 2: label = u"<b>%s</b>" % label
        self.icon_panes[-2].label.set_markup(label)
        
  def on_switch_page(self, notebook, page, i):
    self.icon_pane_changed(self.icon_panes[self.current])
    self.icon_panes[self.current].config(1, 1, 0)
    self.icon_panes[i           ].config(0, 1, 1)
    self.icon_pane_changed(self.icon_panes[self.current])
    old_current = self.current
    self.current = i
    if (self.current == len(self.objs) - 2) or (old_current == len(self.objs) - 2): self.check_mesures()
    self.attribute_panes[i].edit(self.objs[i])
    self.attribute_panes[i].queue_resize()
    self.icon_panes[i].show_all()
    self.icon_pane_changed(self.icon_panes[i])
    
  def icon_pane_changed(self, icon_pane):
    if self.get_tab_pos() in (gtk.POS_LEFT, gtk.POS_RIGHT):
      icon_pane.set_size_request(-1, -1)
      tab_width = icon_pane.size_request()[0]
      if tab_width > self.tab_width: self.tab_width = tab_width
      for icon_pane in self.icon_panes: icon_pane.set_size_request(self.tab_width, -1)
    else:
      try:
        icon_pane.label.set_property("visible", 0)
        icon_pane.image.set_alignment(0.5, 0.5)
      except: pass



class SongbookPane(gtk.HBox):
  def __init__(self, main, undo_stack = None):
    gtk.HBox.__init__(self, 0, 0)
    
    self.main           = main
    self.hierarchy_pane = editor.HierarchyPane("Gtk", self, self.on_song_selected, undo_stack)
    self.childhood_pane = editor.ChildhoodPane("Gtk", self,                        undo_stack)
    
    self.hierarchy_pane.set_childhood_pane(self.childhood_pane)
    
    scroll = gtk.ScrolledWindow()
    scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
    scroll.set_shadow_type(gtk.SHADOW_IN)
    scroll.add(self.hierarchy_pane)
    self.set_border_width(5)
    
    self.pack_start(scroll, 1, 1)
    self.pack_start(self.childhood_pane, 0, 0)
    
  def on_song_selected(self, song_ref):
    if isinstance(song_ref, introsp.ObjectPack): song_ref = song_ref.objects[0]
    if isinstance(song_ref, model.SongRef):
      if self.main.check_save(): return
      self.main.set_song(song_ref.get_song())
      
      
  def set_songbook(self, songbook):
    self.hierarchy_pane.edit(songbook)
    
  def edit(self, o): pass
  
App.SongbookPane = SongbookPane


class PlaylistPane(gtk.HBox):
  def __init__(self, main, undo_stack = None):
    gtk.HBox.__init__(self, 0, 0)
    
    self.main           = main
    self.hierarchy_pane = editor.HierarchyPane("Gtk", self, lambda o: None, undo_stack)
    self.childhood_pane = editor.ChildhoodPane("Gtk", self,                 undo_stack)
    
    self.hierarchy_pane.set_childhood_pane(self.childhood_pane)
    
    scroll = gtk.ScrolledWindow()
    scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
    scroll.set_shadow_type(gtk.SHADOW_IN)
    scroll.add(self.hierarchy_pane)
    self.set_border_width(5)
    
    self.pack_start(scroll, 1, 1)
    self.pack_start(self.childhood_pane, 0, 0)
    
  def set_playlist(self, playlist):
    self.hierarchy_pane.edit(playlist)
    
  def edit(self, o): pass
  


class PartitionsPane(gtk.HBox):
  def __init__(self, main, undo_stack = None):
    gtk.HBox.__init__(self)
    
    self.main           = main
    self.childhood_pane = editor.ChildhoodPane("Gtk", self, undo_stack)
    
    self.pack_start(self.childhood_pane, 0, 0)
    self.set_border_width(5)
    
  def edit(self, partition):
    self.childhood_pane.edit(partition.song, partition)
    


class InstrumentChooserPane(gtk.VBox):
  def __init__(self, main):
    gtk.VBox.__init__(self, 0, 20)
    
    self.main = main
    label     = gtk.Label(_(u"Choose an instrument:"))
    ebox      = gtk.EventBox()
    image     = gtk.Image()
    
    pixbuf = main.menu_image("instruments.png")
    self.pixbuf_width = pixbuf.get_width()
    image.set_from_pixbuf(pixbuf)
    #ebox.add_events(gtk.gdk.BUTTON_PRESS_MASK)
    #ebox.set_flags(gtk.CAN_FOCUS)
    ebox.connect('button_release_event', self.on_click)
    ebox.add(image)
    ebox.set_visible_window(1)
    self.pack_start(gtk.Label(), 1, 1)
    self.pack_start(label, 0, 0)
    self.pack_start(ebox , 0, 0)
    #self.pack_start(gtk.Label(), 1, 1)

    self.image = image
    
  def on_click(self, obj, event):
    x = event.x - (self.image.allocation.width - self.pixbuf_width) // 2
    if not(0 <= x < self.pixbuf_width): return
    
    s = model.Song()
    s.authors   = unicode(getpass.getuser().title(), "latin")
    s.title     = _(u"%s's song") % s.authors
    s.copyright = u"Copyright %s by %s" % (time.localtime(time.time())[0], s.authors)
    
    p = model.Partition(s)
    s.partitions.append(p)
    if   x < 100:
      p.view = model.GuitarView(p)
      sound_file = "son_guitare.mid"
    elif x < 168:
      from songwrite2.plugins.lyre import SevenStringLyreView
      p.view = SevenStringLyreView(p)
      sound_file = "son_lyre.mid"
    elif x < 255:
      p.view = model.VocalsView(p)
      sound_file = "son_chant.mid"
    elif x < 362:
      from songwrite2.plugins.accordion import AccordionView
      from songwrite2.plugins.chord     import AccordionChordView
      p.view = AccordionView(p)
      p2 = model.Partition(s)
      s.partitions.append(p2)
      p2.view = AccordionChordView(p2)
      p2.volume = 128
      sound_file = "son_accordeon.mid"
    else:
      from songwrite2.plugins.fingering import TinWhistleView
      p.view = TinWhistleView(p)
      sound_file = "son_flute.mid"
      
    player.play(open(os.path.join(globdef.DATADIR, sound_file)).read())
    
    for p in s.partitions: p.instrument = p.view.default_instrument
    self.main.filename = None
    self.main.set_song(s)
