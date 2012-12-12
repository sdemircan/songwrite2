# -*- coding: utf-8 -*-

# Songwrite 2
# Copyright (C) 2007 Jean-Baptiste LAMY -- jibalamy@free.fr
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

import sys, os, os.path

import songwrite2.globdef as globdef
import songwrite2.model   as model

PLUGINS = {}
class Plugin(object):
  def __init__(self, name):
    print >> sys.stderr, "Registering %s plugin..." % name
    
    self.name = name
    
    PLUGINS[name] = self
    
  def create_ui(self, app):
    pass

#  def app_from_widget(self, widget):
#    while not isinstance(widget, main.App):
#      widget = widget.get_parent()
#    return widget

EXPORT_FORMATS = []
class ExportPlugin(Plugin):
  def __init__(self, format, exts, can_export_song = 1, can_export_songbook = 0):
    self.format              = format
    self.exts                = exts
    self.can_export_song     = can_export_song
    self.can_export_songbook = can_export_songbook
    EXPORT_FORMATS.append(format)
    Plugin.__init__(self, "%s exporter" % format.lower())
    
  def create_ui(self, app):
    if self.can_export_song:
      app.append_to_menu(app.export_menu, 0, _(u"Export to %s") % self.format + u"..." * int(globdef.config.ASK_FILENAME_ON_EXPORT), self.on_menu_click, arg = app)
    if self.can_export_songbook:
      app.append_to_menu(app.export_songbook_menu, 0, _(u"Export songbook to %s") % self.format + u"..." * int(globdef.config.ASK_FILENAME_ON_EXPORT), self.on_songbook_menu_click, arg = app)
      
  def on_menu_click(self, widget, app):
    if globdef.config.ASK_FILENAME_ON_EXPORT or (not app.filename):
      filename = app.prompt_save_filename(self.exts, self.format)
    else:
      filename = app.filename.replace(".sw.xml", "") + "." + self.exts[0]
    if filename: self.export_to(app.song, filename)
    
  def on_songbook_menu_click(self, widget, app):
    if globdef.config.ASK_FILENAME_ON_EXPORT or (not app.songbook.filename):
      filename = app.prompt_save_filename(self.exts, self.format)
    else:
      filename = app.songbook.filename.replace(".sw.xml", "") + "." + self.exts[0]
    if filename: self.export_to(app.songbook, filename)
    
  def export_to(self, song, filename):
    data = self.export_to_string(song)
    if filename == "-": print data
    else: open(filename, "w").write(data)
    
  def export_to_string(self, song):
    pass
  
  
IMPORT_FORMATS = []
class ImportPlugin(Plugin):
  def __init__(self, format, exts):
    self.format = format
    self.exts   = exts
    IMPORT_FORMATS.append(format)
    Plugin.__init__(self, "%s importer" % format.lower())
    
  def create_ui(self, app):
    app.append_to_menu(app.import_menu, 0, _(u"Import from %s") % self.format + u"...", self.on_menu_click, arg = app)
    
  def on_menu_click(self, widget, app):
    if app.check_save(): return
    
    filename = app.prompt_open_filename(self.exts, self.format)
    
    if filename:
      song = self.import_from(filename)
      app.set_song(song)
      
  def import_from(self, filename):
    if filename == "-":
      return self.import_from_string(sys.stdin.read())
    else:
      return self.import_from_string(open(filename).read())
    
  def import_from_string(self, data): pass


PLUGINS_VIEWS = {}
class ViewPlugin(Plugin):
  def __init__(self, View, String, code_name, category):
    PLUGINS_VIEWS[code_name] = View, String
    Plugin.__init__(self, "%s view" % code_name)
    
    if category: model.VIEWS.setdefault(category, []).append(View)
    
    #model.VIEW_TYPES.append(View)
    
    
def create_plugins_ui(app):
  for plugin in PLUGINS.values(): plugin.create_ui(app)
  
def load_all_plugins():
  plugins_dir = os.path.dirname(__file__)
  for file in [
    "songwrite",
    "abc",
    "texttab",
    "guitar_pro",
    "lilypond",
    "midi",
    "ps_native",
    "fingering",
    "additional_instruments",
    "lyre",
    "chord",
    "accordion",
    ]:
    try:
      __import__("songwrite2.plugins.%s" % file)
    except:
      print >> sys.stderr, "Error while loading plugin 'songwrite2.plugins.%s'!" % file
      sys.excepthook(*sys.exc_info())
  print >> sys.stderr
  
def get_importer(format):
  return PLUGINS["%s importer" % format.lower()]

def get_exporter(format):
  return PLUGINS["%s exporter" % format.lower()]

def load_view(partition, attrs):
  View, String = PLUGINS_VIEWS[attrs["type"]]
  view = View(partition, "")
  view.load_attrs(attrs)
  return view, String
  
