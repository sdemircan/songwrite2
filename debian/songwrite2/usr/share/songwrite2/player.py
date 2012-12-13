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

import sys, popen2, os, select
import editobj2
import songwrite2, songwrite2.globdef as globdef

_p            = None
_midi         = ""
_loop         = 0
_tracker      = None
_last_tracker = None

def is_playing(): return _p and (_p.poll() == -1)

def stop():
  global _p, _tracker
  if not _p is None:
    if _tracker:
      _tracker(-1)
      _tracker = None
    
    try: os.kill(_p.pid, 9)
    except OSError: pass
    _p  = None
    
def play(midi, loop = 0, tracker = None):
  global _p, _midi, _loop, _tracker, _last_tracker
  
  stop()
  
  if not globdef.config.DISPLAY_PLAY_BAR: tracker = None
  _midi    = midi
  _loop    = loop
  _tracker = _last_tracker = tracker
  
  _play()
  
def _play():
  global _p, _midi, _loop, _tracker
  if globdef.config.MIDI_USE_TEMP_FILE:
    import tempfile
    file = tempfile.mktemp(".midi")
    open(file, "w").write(_midi)
    _p = p = popen2.Popen4(globdef.config.MIDI_COMMAND % file)
  else:
    _p = p = popen2.Popen4(globdef.config.MIDI_COMMAND)
    _p.tochild.write(_midi)
    _p.tochild.flush()
    
  if editobj2.GUI == "Gtk":
    import gobject
    if _tracker: gobject.timeout_add(  3, timer)
    else:        gobject.timeout_add(300, timer)
  else:
    import qt
    try: _play.qt_timer.stop()
    except: pass
    _play.qt_timer = qt.QTimer(songwrite2.main_qt.app)
    _play.qt_timer.connect(_play.qt_timer, qt.SIGNAL("timeout()"), timer_qt)
    _play.qt_timer.start(3, 0)
    if _tracker: _play.qt_timer.start(  3, 0)
    else:        _play.qt_timer.start(300, 0)
    
  

def timer():
  global _tracker
  
  if _p is None: return 0 # Stop was called
  r = _p.poll()
  if r == -1:
    if _tracker:
      line = ""
      while 1:
        s = select.select([_p.fromchild], [], [], 0)
        if not s[0]: break
        line = _p.fromchild.readline()
      if line:
        try:
          if ":" in line: t = int(line[line.find(":") + 3 :])
          else:           t = int(line)
        except: return 1
        _tracker(t)
        if t == -1:
          _tracker = None # Tracking has reached its end !
          stop()
          if _loop:
            _tracker = _last_tracker
            _play()
            
    return 1

  if (globdef.config.MIDI_COMMAND.find("timidity") != -1) and (_p.fromchild.read().find("Couldn't open Arts device") != -1):
    # We are using the KDE / aRts version of Timidity
    # This fucking version can only play with aRts,
    # until we provide another config file for it.
    #
    # BTW am I alone to think that aRts is a pain ?
    
    # Get the default config file
    import re, tempfile
    timidity_verbose = os.popen4("timidity -idvvv")[1].read()
    timidity_cfg = re.findall(r"\S*\.cfg", timidity_verbose)
    if timidity_cfg:
      timidity_cfg = timidity_cfg[0]

      cfg = open(timidity_cfg).read()
      cfg = re.sub("-O\s+A", "# No longer use fucking aRts", cfg)

      temp_cfg = tempfile.mktemp(".timidity.noarts.cfg")
      open(temp_cfg, "w").write(cfg)

      globdef.config.MIDI_COMMAND += " -c %s" % temp_cfg

      import gtk
      dialog = gtk.MessageDialog(self, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING, message_format = _("__fucking-arts__") % temp_cfg)
      dialog.add_buttons(gtk.STOCK_OK, gtk.RESPONSE_OK)
      dialog.run()
      dialog.destroy()
      
  if (r == 0) and _loop:
    _tracker = _last_tracker
    _play()
  
  return 0

def timer_qt():
  if not timer():
    if _play.qt_timer:
      _play.qt_timer.stop()
      _play.qt_timer = None
    

noteplayer = None

def play_note(instrument, value):
  if not globdef.config.PLAY_AS_TYPING: return
  
  stop()
  
  import songwrite2.model as model
  import songwrite2.midi  as midi
  
  global noteplayer
  if not noteplayer:
    noteplayer = model.Song()
    noteplayer.partitions.append(model.Partition(noteplayer))
    noteplayer.partitions[0].notes.append(model.Note(noteplayer.partitions[0], 0, 48, 0))
  noteplayer.partitions[0].instrument = instrument
  noteplayer.partitions[0].notes[0].value = value
  
  play(midi.song_2_midi(noteplayer))
