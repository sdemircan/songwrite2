#! /usr/bin/env python

# Songwrite 2
# Copyright (C) 2001-2007 Jean-Baptiste LAMY -- jibalamy@free.fr
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

import os, os.path, sys, glob, distutils.core

#HERE = os.path.dirname(sys.argv[0]) or "."
#if "install" in sys.argv: installing = 1
#else:                     installing = 0

if "--no-lang" in sys.argv:
  sys.argv.remove("--no-lang")
  no_lang = 1
else: no_lang = 0

data_files = [
  (os.path.join("songwrite2", "data"),
  [os.path.join("data", file) for file in os.listdir("data") if (file != "CVS") and (file != ".svn") and (file != ".arch-ids")]),
  (os.path.join("man", "man1"),
  [os.path.join("manpage", "man1", "songwrite2.1")]),
  ]
if not no_lang:
  data_files = data_files + [
    (os.path.join(os.path.dirname(mo_file)), [mo_file])
    for mo_file
    in  glob.glob(os.path.join(".", "locale", "*", "LC_MESSAGES", "*"))
    ]

for doc_lang in ["fr", "en"]:
  data_files.append(
    (os.path.join("doc", "songwrite2", doc_lang),
     glob.glob(os.path.join(".", "doc", doc_lang, "doc.pdf"))),
    )

a = distutils.core.setup(name         = "Songwrite2",
                     version      = "0.4",
                     license      = "GPL",
                     description  = "Tablature editor in Python with Gtk 2, Cairo, EditObj 2, Timidity",
                     author       = "Lamy Jean-Baptiste",
                     author_email = "jibalamy@free.fr",
                     url          = "http://home.gna.org/oomadness/en/songwrite/index.html",
                     
                     package_dir  = {"songwrite2" : ""},
                     packages     = ["songwrite2",
                                     "songwrite2.plugins",
                                     "songwrite2.plugins.abc",
                                     "songwrite2.plugins.additional_instruments",
                                     "songwrite2.plugins.fingering",
                                     "songwrite2.plugins.guitar_pro",
                                     "songwrite2.plugins.lilypond",
                                     "songwrite2.plugins.lyre",
                                     "songwrite2.plugins.midi",
                                     "songwrite2.plugins.ps_native",
                                     "songwrite2.plugins.songwrite",
                                     "songwrite2.plugins.texttab",
                                     "songwrite2.plugins.chord",
                                     "songwrite2.plugins.accordion",
                                    ],
                     
                     scripts      = ["songwrite2"],
                     
                     data_files   = data_files,
                     )
