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

import sys, os, cStringIO as StringIO, tempfile, shutil
#import string as string_module # not a guitar string !

import songwrite2.globdef  as globdef
import songwrite2.model    as model
import songwrite2.plugins  as plugins
from   songwrite2.plugins.ps_native.ps_canvas import BaseCanvas, PSCanvas

def escape_latex(s):
  return s.replace(u"°", u"\\symbol{6}").replace(u"#", u"\\#").replace(u"_", u"\\_").replace(u"~", u"\\~").replace(u"&", u"\\&").replace(u"%", u"\\%").replace(u"$", u"\\$").replace(u"^", u"\\^")

lang_iso2latex = { # Languages supported by LaTeX with Babel
  u"" : u"\\usepackage[]{babel}",
  }
lang_iso2latex = { # Languages supported by LaTeX with Babel
  u"ar" : u"arabic",
  u"hy" : u"armenian",
  u"eu" : u"basque",
  u"bg" : u"bulgarian",
  u"ca" : u"catalan",
  u"hr" : u"croatian",
  u"cs" : u"czech",
  u"da" : u"danish",
  u"nl" : u"dutch",
  u"en" : u"english",
  u"eo" : u"esperanto",
  u"et" : u"estonian",
  u"fa" : u"farsi",
  u"fi" : u"finnish",
  u"fr" : u"french",
  u"gl" : u"galician",
  u"de" : u"german",
  u"el" : u"greek",
  u"hu" : u"hungarian",
  u"is" : u"icelandic",
  u"as" : u"assamese",
  u"bn" : u"bengali",
  u"gu" : u"gujarati",
  u"hi" : u"hindi",
  u"kn" : u"kannada",
  u"ml" : u"malayalam",
  u"mr" : u"marathi",
  u"or" : u"oriya",
  u"pa" : u"panjabi",
  u"ta" : u"tamil",
  u"te" : u"telugu",
  u"id" : u"indonesian",
  u"ia" : u"interlingua",
  u"ga" : u"irish",
  u"it" : u"italian",
  u"ku" : u"kurmanji",
  u"lo" : u"lao",
  u"la" : u"latin",
  u"lv" : u"latvian",
  u"lt" : u"lithuanian",
  u"mn" : u"mongolian",
  u"nb" : u"bokmal",
  u"nn" : u"nynorsk",
  u"pl" : u"polish",
  u"pt" : u"portuguese",
  u"ro" : u"romanian",
  u"ru" : u"russian",
  u"sa" : u"sanskrit",
  u"sr" : u"serbian",
  u"sk" : u"slovak",
  u"sl" : u"slovenian",
  u"es" : u"spanish",
  u"sv" : u"swedish",
  u"tr" : u"turkish",
  u"tk" : u"turkmen",
  u"uk" : u"ukrainian",
  u"cy" : u"welsh",
  u"--" : u"",
  }

def latexify_songbook(tmp_dir, songbook):
  latexes = []
  lang    = None
  
  for song_ref in songbook.song_refs:
    song = song_ref.get_song()
    latexes.append(latexify_song(tmp_dir, song, 1))
    if not lang: lang = song.lang

  lang_latex = lang_iso2latex[lang]
  babel_code = u"\\usepackage[%s]{babel}" % lang_latex
  open(os.path.join(tmp_dir, "main.latex"), "w").write((u"""
\\documentclass[%s,10pt]{article}
\\usepackage[T1]{fontenc}
\\usepackage[utf8]{inputenc}
\\usepackage[lmargin=1.0cm,rmargin=1.0cm,tmargin=1.0cm,bmargin=2.0cm]{geometry}
\\usepackage{graphicx}
\\usepackage{ae,aecompl}
%s

\\begin{document}

\\sloppy

\\title {%s}
\\author{%s}
\\date  {}
\\maketitle
\\vfill
%s
\\tableofcontents
\\pagebreak

%s


\\end{document}
""" % (globdef.config.PAGE_FORMAT,
       babel_code,
       escape_latex(songbook.title),
       escape_latex(songbook.authors),
       escape_latex(songbook.comments),
       u"""
\\pagebreak
""".join(latexes),
       )).encode("utf8"))


PSID = 0
def latexify_song(tmp_dir, song, songbook = 0):
  global PSID

  song.remove_unused_mesures()
  
  latex = StringIO.StringIO()
  
  partitions = song.partitions
  
  lang = lang_iso2latex.get(song.lang, None)
  if lang: babel_code = u"\\usepackage[%s]{babel}" % lang
  else:    babel_code = u""
  
  # Use literal string r"..." because of the backslash !!!
  if songbook:
    latex.write(u"""
\\addcontentsline{toc}{subsection}{%s}

""" % escape_latex(song.title))
    
  else:
    latex.write(u"""
\\documentclass[%s,10pt]{article}
\\usepackage[T1]{fontenc}
\\usepackage[utf8]{inputenc}
\\usepackage[lmargin=1.0cm,rmargin=1.0cm,tmargin=1.0cm,bmargin=2.0cm,headheight=0cm,headsep=0cm]{geometry}
\\usepackage{graphicx}
\\usepackage{ae,aecompl}
%s
\\setlength{\\topskip}{0pt}

\\begin{document}

\\sloppy

""" % (globdef.config.PAGE_FORMAT,
       babel_code,
       ))

  if song.title:
    latex.write(u"""
\\begin{center}\\begin{LARGE} %s \\end{LARGE}\\end{center}
""" % escape_latex(song.title))
    
  if song.authors:
    latex.write(u"""
\\begin{center}\\begin{large} %s \\end{large}\\end{center}
""" % escape_latex(song.authors))
    
  if song.date():
    latex.write(u"""
\\begin{center}\\begin{large} %s \\end{large}\\end{center}
""" % escape_latex(song.date()))
    
  if song.comments:
    latex.write(u"""
%s

\\smallskip{}
""" % escape_latex(song.comments).replace(u"\\n", u"\\n\\n"))

  max_time = max([10] + [partition.end_time() for partition in song.partitions if isinstance(partition, model.Partition)])
  max_width = {
    "a3paper"    : 1468,
    "a4paper"    : 1080,
    "a5paper"    : 681,
    "letterpaper": 1010,
    }[globdef.config.PAGE_FORMAT]
  
  max_mesures_width = 0
  mesuress = []
  selected_mesures = []
  canvas = BaseCanvas(song)
  canvas.set_default_font_size(song.printfontsize)
  canvas.update_mesure_size()
  width = canvas.start_x
  
  zoom = (max_width - canvas.start_x - 1) / float(song.mesures[min(song.print_nb_mesures_per_line, len(song.mesures)) - 1].end_time() )
  for mesure in song.mesures:
    if len(selected_mesures) >= song.print_nb_mesures_per_line:
      mesuress.append(selected_mesures)
      selected_mesures = []
    selected_mesures.append(mesure)
  if selected_mesures:
    mesuress.append(selected_mesures)
    
  def mesure_2_repeat(mesure):
    start_repeat = end_repeat = 0
    for symbol in song.playlist.symbols.get(mesure) or []:
      if   symbol.startswith(r"\repeat"):    start_repeat = 1
      elif symbol == r"} % end alternative": end_repeat   = 1
      elif symbol == r"} % end repeat":      end_repeat   = 1
    return start_repeat, end_repeat
    
  def mesures_2_x_width_zoom(mesures, is_last, previous_mesures, previous_zoom):
    if mesures[0] is song.mesures[0]:
      x   = 0
      dx  = 0
      start_repeat, end_repeat = mesure_2_repeat(mesures[0])
      if start_repeat:                  x +=0.3 * canvas.scale; dx -=0.3 * canvas.scale
    else:
      x   = canvas.time_2_x(mesures[0].time) - canvas.start_x
      dx  = x  - mesures[ 0].time
      
      start_repeat, end_repeat = mesure_2_repeat(mesures[0])
      if   start_repeat and end_repeat: x -= 17 * canvas.scale; dx -= 17 * canvas.scale
      elif start_repeat:                x -= 16 * canvas.scale; dx -= 16 * canvas.scale
      elif end_repeat:                  x -=  2 * canvas.scale; dx -=  2 * canvas.scale
      else:                             x -=  2 * canvas.scale; dx -=  2 * canvas.scale
      
    x2    = canvas.time_2_x(mesures[-1].end_time()) - canvas.start_x
    dx2   = x2 - mesures[-1].end_time()
    
    try:    next_mesure = song.mesures[mesures[-1].get_number() + 1]
    except: next_mesure = None
    start_repeat, end_repeat = mesure_2_repeat(next_mesure)
    if   start_repeat and end_repeat: x2 -= 15 * canvas.scale; dx2 -= 15 * canvas.scale
    elif start_repeat:                x2 -= 16 * canvas.scale; dx2 -= 16 * canvas.scale
    elif end_repeat:                  x2 -=  2 * canvas.scale; dx2 -=  2 * canvas.scale
    else:                             x2 -=1.1 * canvas.scale; dx2 -=1.1 * canvas.scale
    
    if is_last and not (len(mesures) < len(previous_mesures)):
      x2 +=  5 * canvas.scale; dx2 +=  5 * canvas.scale
      
    width = x2 - x
    
    if is_last and (len(mesures) < len(previous_mesures)):
      zoom = previous_zoom
      width = (dx2 - dx) + (width - (dx2 - dx)) * zoom + canvas.start_x
      if not end_repeat: width += 5 * canvas.scale
    else:
      zoom  = (max_width - canvas.start_x - (dx2 - dx)) / float(width - (dx2 - dx))
      width = max_width
      
    x = dx + (x - dx) * zoom
    return x, width, zoom

  previous_mesures = []
  previous_zoom    = 0.0
  for mesures in mesuress:
    x, width, zoom = mesures_2_x_width_zoom(mesures, mesures is mesuress[-1], previous_mesures, previous_zoom)
    ps_filename = os.path.join(tmp_dir, "ps_file_%s.ps" % PSID)
    PSCanvas(song, ps_filename, x, width, mesures[0].time, mesures[-1].end_time(), zoom)
    previous_mesures = mesures
    previous_zoom    = zoom
  
    latex.write(u"""
\\noindent \\begin{flushleft}
\\includegraphics[clip,scale=0.5]{ps_file_%s.ps}
\\par\\end{flushleft}
""" % PSID)
    PSID += 1
    
  latex.write(u"""
\\vfill{}
""")
  
  for partition in partitions:
    if isinstance(partition, model.Lyrics):
      if not partition.show_all_lines_after_score: continue
      if partition.header: latex.write(u"""
\\subsection*{%s}
""" % escape_latex(partition.header))
      
      latex.write(u"""
\\begin{verse}
""")
      latex.write(escape_latex(partition.text.replace(u"_-\t", u"").replace(u"_\t", u" ").replace(u"-\t", u"").replace(u"\t", u" ").replace(u"_", u"").replace(u" ,", u",").replace(u" ,", u",")))
      latex.write(u"""
\\end{verse}
""")
      

  if not songbook:
    latex.write(u"""
\\end{document}
""")

  if songbook:
    return latex.getvalue()
  else:
    open(os.path.join(tmp_dir, "main.latex"), "w").write(latex.getvalue().encode("utf8"))


PDF_PAGE_FORMATS = {
  "a3paper"     : "a3",
  "a4paper"     : "a4",
  "a5paper"     : "a5",
  "letterpaper" : "letter",
  }

def do(command):
  print >> sys.stderr
  print >> sys.stderr, "Running '%s'..." % command
  os.system(command)
  
def psify(song, pdf = 0):
  tmp_dir = tempfile.mkdtemp()
  print >> sys.stderr
  print >> sys.stderr, "Using temporary directory '%s'..." % tmp_dir
  
  if isinstance(song, model.Songbook):
    latexify_songbook(tmp_dir, song)
  else:
    latexify_song    (tmp_dir, song)
    
  do("cd %s; latex -interaction=nonstopmode main.latex" % tmp_dir)
  do("cd %s; latex -interaction=nonstopmode main.latex" % tmp_dir) # For table of content
  do("cd %s; dvips -o main.ps main.dvi" % tmp_dir)
  if pdf:
    do("cd %s; ps2pdf -sDEFAULTPAPERSIZE=%s main.ps" % (tmp_dir, PDF_PAGE_FORMATS[globdef.config.PAGE_FORMAT]))
    r = open(os.path.join(tmp_dir, "main.pdf")).read()
  else:
    r = open(os.path.join(tmp_dir, "main.ps")).read()
    
  shutil.rmtree(tmp_dir)
  return r
