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

from StringIO import StringIO

import songwrite2.plugins as plugins
import songwrite2.midi    as midi


class MidiExportPlugin(plugins.ExportPlugin):
  def __init__(self):
    plugins.ExportPlugin.__init__(self, "MIDI", ["mid", "midi"])
    
  def export_to_string(self, song):
    return midi.song_2_midi(song)
    
MidiExportPlugin()


class MidiImportPlugin(plugins.ImportPlugin):
  def __init__(self):
    plugins.ImportPlugin.__init__(self, "MIDI", ["mid", "midi"])
    
  def import_from_string(self, data):
    import songwrite2.plugins.midi.importer as importer
    return importer.parse(StringIO(data))
    
MidiImportPlugin()


class RichMidiExportPlugin(plugins.ExportPlugin):
  def __init__(self):
    plugins.ExportPlugin.__init__(self, "RichMIDI", ["mid", "midi"])
    
  def export_to_string(self, song):
    return midi.song_2_midi(song, rich_midi_tablature = 1)
    
RichMidiExportPlugin()


class RichMidiImportPlugin(plugins.ImportPlugin):
  def __init__(self):
    plugins.ImportPlugin.__init__(self, "RichMIDI", ["mid", "midi"])
    
  def import_from_string(self, data):
    import songwrite2.plugins.midi.importer as importer
    return importer.parse(StringIO(data), rich_midi_tablature = 1)
    
RichMidiImportPlugin()
