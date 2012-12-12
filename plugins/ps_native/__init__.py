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

import os, atexit

import songwrite2.plugins as plugins
import songwrite2.model   as model
import songwrite2.globdef as globdef


PREVIEW_TMP_FILE = ""

def remove_preview_tmp_file():
  global PREVIEW_TMP_FILE
  if PREVIEW_TMP_FILE:
    os.unlink(PREVIEW_TMP_FILE)
    PREVIEW_TMP_FILE = ""
atexit.register(remove_preview_tmp_file)

class ExportPlugin(plugins.ExportPlugin):
  def __init__(self):
    plugins.ExportPlugin.__init__(self, "PostScript", ["ps"], 1, 1)
    
  def export_to_string(self, song):
    import songwrite2.plugins.ps_native.ps_latex as ps_latex
    return ps_latex.psify(song)
    
  def print_preview(self, song):
    import songwrite2.plugins.ps_native.ps_latex as ps_latex
    global PREVIEW_TMP_FILE
    
    if PREVIEW_TMP_FILE: remove_preview_tmp_file()
      
    pdf = ps_latex.psify(song, pdf = 1)
    if "%s" in globdef.config.PREVIEW_COMMAND_PDF:
      import tempfile, popen2
      fid, PREVIEW_TMP_FILE = tempfile.mkstemp(suffix = ".pdf", text = 0)
      open(PREVIEW_TMP_FILE, "w").write(pdf)
      command = globdef.config.PREVIEW_COMMAND_PDF % PREVIEW_TMP_FILE
      print "Running '%s'" % command
      popen2.popen4(command)
    else:
      import popen2
      print "Running '%s'" % globdef.config.PREVIEW_COMMAND_PDF
      output, input = popen2.popen4(globdef.config.PREVIEW_COMMAND_PDF)
      input.write(pdf)
      input.close()
      
ExportPlugin()


class ExportPluginPDF(plugins.ExportPlugin):
  def __init__(self):
    plugins.ExportPlugin.__init__(self, "PDF", ["pdf"], 1, 1)
    
  def export_to_string(self, song):
    import songwrite2.plugins.ps_native.ps_latex as ps_latex
    return ps_latex.psify(song, pdf = 1)
    
ExportPluginPDF()
