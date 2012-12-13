# -*- coding: utf-8 -*-

# Songwrite 2
# Copyright (C) 2001-2011 Jean-Baptiste LAMY -- jibalamy@free.fr
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

# Semintone / interval
#  0 base
#  1 nine_flat
#  2 nine
#  3 three_minor
#  4 three_major
#  5 four
#  6 five_flat
#  7 five
#  8 five_sharp
#  9 six
# 10 seven_minor
# 11 seven_major

import sys
import songwrite2
import songwrite2.globdef as globdef
import songwrite2.model   as model

class Chord(object):
  def __init__(self, base, identified_notes, type, tonality = u"C"):
    self.base             = base
    self.identified_notes = identified_notes
    self.type             = type
    if len(identified_notes) == 1: # Bass
      self.name           = u"%s %s" % (songwrite2.model.note_label(base, 0, tonality, globdef.config.ENGLISH_CHORD_NAME).upper(), type)
    else: # Chord
      self.name           = u"%s %s" % (songwrite2.model.note_label(base, 0, tonality, globdef.config.ENGLISH_CHORD_NAME), type)
      
class ChordManager(object):
  def __init__(self, partition, reverse_penality = -65):
    self.partition        = partition
    self.reverse_penality = reverse_penality
    self.caches           = {}
    self.default_thirds   = None
    
  def _identify_relative_notes(self, relative_notes):
    if   0 in relative_notes: first = 0; relative_notes.remove(0)
    else:                     first = None
    
    if   4 in relative_notes: third = 4; relative_notes.remove(4) # Major
    elif 3 in relative_notes: third = 3; relative_notes.remove(3) # Minor
    else:                     third = None
    
    if   7 in relative_notes: fifth = 7; relative_notes.remove(7) # Fifth
    elif 8 in relative_notes: fifth = 8; relative_notes.remove(8) # Sharp fifth / augmented
    elif 6 in relative_notes: fifth = 6; relative_notes.remove(6) # Flat fifth / diminished
    else:                     fifth = None
    
    seventh = None
    if   10 in relative_notes: seventh = 10; relative_notes.remove(10) # Minor seventh
    elif 11 in relative_notes: seventh = 11; relative_notes.remove(11) # Major seventh
    elif  9 in relative_notes:
      if (third == 3) and (fifth == 6): # Only with minor third and diminished fifth
        seventh = 9; relative_notes.remove(9) # Diminished seventh
        
    if   5 in relative_notes: fourth = 5; relative_notes.remove(5) # Sus4 / Eleventh
    else:                     fourth = None
    
    if   2 in relative_notes: second = 2; relative_notes.remove(2) # Sus2 / Nineth
    elif 1 in relative_notes: second = 1; relative_notes.remove(1) # Flat nineth
    else:                     second = None
    
    if   9 in relative_notes: sixth = 9; relative_notes.remove(9) # Sixth
    else:                     sixth = None
    
    return first, second, third, fourth, fifth, sixth, seventh
  
  
  def _name_identified_notes(self, base, first, second, third, fourth, fifth, sixth, seventh):
    if first is None: return 0, u""
    t0 = t2 = t3 = t4 = t5 = t6 = t7 = t9 = t11 = u""
    lik = 0

    # 3th
    if   third == 4: t0 = u"M"; t3= u""; lik += 30
    elif third == 3: t0 = u"m"; t3= u""; lik += 30
    else:            t3 = u"omit3"

    # 5th
    if   fifth == 6: t5 = u"5♭" ; lik += 10
    elif fifth == 7:
      lik += 50
      if t3 == u"omit3": t5 = u"5"; t3 = u""
      else:              t5 = u""
    elif fifth == 8: t5 = u"5♯"; lik += 10
    else:            t5 = u"omit5"

    if (t0 == u"M") and (t5 == u"5♯"): t0 = u"aug" ; t5 = u""; lik += 15
    if (t0 == u"m") and (t5 == u"5♭" ): t0 = u"dim"; t5 = u""; lik += 10

    # 7th
    if   seventh ==  9: t7 = u"7dim"
    elif seventh == 10: t7 = u"7m"     ; lik += 20
    elif seventh == 11: t7 = u"7M"     ; lik += 10

    if   (t0 == u"M"  ) and (t7 == u"7M"  ): t0 = u"7M"      ; t7 = u""; lik += 10
    elif (t0 == u"m"  ) and (t7 == u"7m"  ): t0 = u"m 7"     ; t7 = u""; lik += 10
    elif (t0 == u"M"  ) and (t7 == u"7m"  ): t0 = u"7"       ; t7 = u""; lik += 10
    elif (t0 == u"dim") and (t7 == u"7m"  ): t0 = u"half dim"; t7 = u""
    elif (t0 == u"dim") and (t7 == u"7dim"): t0 = u"dim 7"   ; t7 = u""
    elif (t0 == u"m"  ) and (t7 == u"7M"  ): t0 = u"m 7M"    ; t7 = u""
    elif (t0 == u"aug") and (t7 == u"7M"  ): t0 = u"aug 7M"  ; t7 = u""
    elif (t0 == u"aug") and (t7 == u"7m"  ): t0 = u"aug 7"   ; t7 = u""
    elif (t0 == u""   ) and (t7 == u"7m"  ): t0 = u"7"       ; t7 = u""
    elif (t0 == u""   ) and (t7 == u"7M"  ): t0 = u"7M"      ; t7 = u""

    # 9th and 11th
    if not third:
      if   second == 2: t2 = u"sus2" ; t3 = u""; lik += 10
      elif second == 1: t2 = u"sus2♭"; t3 = u""; lik -= 20
      if   fourth == 5: t4 = u"sus4" ; t3 = u""; lik += 20
    else:
      if   second == 2: t9  = u"add9" ; lik += 20
      elif second == 1: t9  = u"add9♭"; lik +=  0
      if   fourth == 5: t11 = u"add11"; lik += 10

    if (t0 == u"7M"    ) and (t9  == u"add9" ): t0 = u"9M"    ; t9 = u""
    if (t0 == u"m 7"   ) and (t9  == u"add9" ): t0 = u"m 9"   ; t9 = u""
    if (t0 == u"7"     ) and (t9  == u"add9" ): t0 = u"9"     ; t9 = u""
    if (t0 == u"aug 7" ) and (t9  == u"add9" ): t0 = u"aug 9" ; t9 = u""
    if (t0 == u"aug 7M") and (t9  == u"add9" ): t0 = u"aug 9M"; t9 = u""
    if (t0 == u"m 7M"  ) and (t9  == u"add9" ): t0 = u"m 9M"  ; t9 = u""

    if (t0 == u"7M"    ) and (t11 == u"add11"): t0 = u"11M"   ; t11 = u""; lik += 5
    if (t0 == u"m 7"   ) and (t11 == u"add11"): t0 = u"m 11"  ; t11 = u""; lik += 5
    if (t0 == u"7"     ) and (t11 == u"add11"): t0 = u"11"    ; t11 = u""; lik += 5
    if (t0 == u"m 7M"  ) and (t11 == u"add11"): t0 = u"m 11M" ; t11 = u""; lik += 5

    if (t0 == u"9M"    ) and (t11 == u"add11"): t0 = u"11M"   ; t11 = u""; lik += 5
    if (t0 == u"m 9"   ) and (t11 == u"add11"): t0 = u"m 11"  ; t11 = u""; lik += 5
    if (t0 == u"9"     ) and (t11 == u"add11"): t0 = u"11"    ; t11 = u""; lik += 5
    if (t0 == u"m 9M"  ) and (t11 == u"add11"): t0 = u"m 11M" ; t11 = u""; lik += 5

    # 6th
    if sixth == 9: t6 = u"add6"; lik -= 20
    
    if (t0 == u"m") and (t6 == u"add6"): t0 = u"m 6"; t6 = u""; lik += 10
    
    if self.default_thirds:
      default = self.default_thirds.get(base % 12)
      if default:
        if   t0 == default:                   t0 = u""
        elif t0.startswith(u"%s " % default): t0 = t0[len(default) + 1:]
    else:
      if t0 == u"M": t0 = u""
      
    name = u" ".join([_(x) for x in [t0, t2, t3, t4, t5, t6, t7, t9, t11] if x])

    if name.count(_(u"omit")) > 1: return 0, u""

    return lik, name


  def identify(self, values):
    if values in self.caches:
      return self.caches[values]
    else:
      chord = self.caches[values] = self._identify(values)
      return chord
    
  def _identify(self, values):
    lower_value = min(values)
    best_lik    = 0
    best_base   = None
    best_name   = u""
    best_notes  = None
    for base in values:
      relative_notes = set([(value - base) % 12 for value in values])
      identified_notes = self._identify_relative_notes(relative_notes)
      lik, name = self._name_identified_notes(base, *identified_notes)
      if name is not None:
        if base != lower_value:
          lik += self.reverse_penality
        if lik > best_lik:
          best_lik   = lik
          best_base  = base
          best_name  = name
          best_notes = identified_notes
    if best_base is None:
      print >> sys.stderr, "XXX pas d'accord pour", values
      return None
    return Chord(best_base, best_notes, best_name, self.partition.tonality)
  
  def create(self, base, second = 0, third = 4, fourth = 0, fifth = 7, sixth = 0, seventh = 0):
    pass
  
  def choose_third(self, partition, base):
    if ((base + 4 - model.OFFSETS[partition.tonality]) % 12) in model.NOTES: return 4
    else:                                                                    return 3
    
class TablatureChordManager(ChordManager):
  def __init__(self, partition):
    ChordManager.__init__(self, partition)
    
  def create(self, base, second = 0, third = 4, fourth = 0, fifth = 7, sixth = 0, seventh = 0, barred = 0):
    if barred >= 14: return None
    base = base % 12
    allowed_values = set([base, (base + second) % 12, (base + third) % 12, (base + fourth) % 12, (base + fifth) % 12, (base + sixth) % 12, (base + seventh) % 12])
    needed_values  = set(allowed_values)
    values         = []
    frets          = []
    base_placed    = 0
    strings        = list(reversed(self.partition.view.strings))
    max_string_id  = len(strings) - 1
    for i in range(len(strings)):
      if not base_placed:
        value = self._relative_note_on_string(strings[i].base_note, base, barred)
        fret = value - strings[i].base_note
        if fret < strings[i + 1].base_note - strings[i].base_note + barred:
          values.append((value, max_string_id - i))
          frets .append(fret)
          needed_values.discard(base)
          base_placed = 1
      else:
        value = min([self._relative_note_on_string(strings[i].base_note, allowed_value, barred) for allowed_value in allowed_values])
        values.append((value, max_string_id - i))
        needed_values.discard(value % 12)
        frets .append(value - strings[i].base_note)
        
    barred = min(frets)
    if needed_values or self._frets_impossible(frets, barred): return self.create(base, second, third, fourth, fifth, sixth, seventh, barred + 1)
    
    frets = u"".join([unicode(fret) for fret in frets])
    frets = u"X" * (len(strings) - len(frets)) + frets
    return values, frets
  
  def _frets_impossible(self, frets, barred = 0):
    if len(frets) - frets.count(barred) > 4: return 1
    if barred and (max(frets) - barred > 2): return 1
    if (not barred) and (max(frets) - barred > 3): return 1
    if (frets.count(barred + 3) >= 2) and (frets.count(barred + 1) >= 2): return 1
    if (frets.count(barred + 4) >= 2) and (frets.count(barred + 2) >= 2): return 1
    if (frets.count(barred + 1) >= 4): return 1
    if (frets.count(barred + 2) >= 4): return 1
    if (frets.count(barred + 3) >= 4): return 1
    if (frets.count(barred + 4) >= 4): return 1
    if len(frets) < 3: return 1
    
  def _relative_note_on_string(self, string_base_note, relative_note, barred = 0):
    while relative_note < string_base_note + barred: relative_note += 12
    return relative_note

class PianoChordManager(ChordManager):
  def __init__(self, partition):
    ChordManager.__init__(self, partition)
    
  def create(self, base, second = 0, third = 4, fourth = 0, fifth = 7, sixth = 0, seventh = 0):
    base   = ((base + 7) % 12) + 41
    values = list(set([(base          , -1),
                       (base + second , -1),
                       (base + third  , -1),
                       (base + fourth , -1),
                       (base + fifth  , -1),
                       (base + sixth  , -1),
                       (base + seventh, -1),
                       (base +      12, -1),
                       ]))
    return values, u""

class AccordionChordManager(ChordManager):
  def __init__(self, partition, instrument_tonality = u"G/C"):
    ChordManager.__init__(self, partition)
    self.instrument_tonality = instrument_tonality
    if   instrument_tonality == u"G/C": delta = 0
    elif instrument_tonality == u"A/D": delta = 2
    self.default_thirds = {
      ( 0 + delta) % 12 : u"M", # Do
      ( 2 + delta) % 12 : u"M", # Ré
      ( 4 + delta) % 12 : u"m", # Mi
      ( 5 + delta) % 12 : u"M", # Fa
      ( 7 + delta) % 12 : u"M", # Sol
      ( 9 + delta) % 12 : u"m", # La
      }
    
  def _identify(self, values):
    if len(values) == 1:
      return Chord(tuple(values)[0], [0], u"", self.partition.tonality)
    else:
      chord = ChordManager._identify(self, values)
      words = chord.name.split(None, 1)
      if len(words) == 1: chord.name = chord.name.lower()
      else:               chord.name = u"%s %s" % (words[0].lower(), words[1])
      return chord
    
  def create(self, base, second = 0, third = 4, fourth = 0, fifth = 7, sixth = 0, seventh = 0):
    if (second == 0) and (third == 0) and (fourth == 0) and (fifth == 0) and (sixth == 0) and (seventh == 0):
      base   = ((base + 7) % 12) + 41
      values = [(base, -1)]
    else:
      base   = ((base + 7) % 12) + 41
      values = list(set([(base          , -1),
                         (base + second , -1),
                         (base + third  , -1),
                         (base + fourth , -1),
                         (base + fifth  , -1),
                         (base + sixth  , -1),
                         (base + seventh, -1),
                         ]))
    return values, u""
  
  def choose_third(self, partition, base):
    default = self.default_thirds.get(base % 12)
    if   default == u"M": return 4
    elif default == u"m": return 3
    if ((base + 4 - model.OFFSETS[partition.tonality]) % 12) in model.NOTES: return 4
    else:                                                                    return 3
    return ChordManager.choose_third(self, partition, base)
    

class LyreChordManager(ChordManager):
  def __init__(self, partition):
    ChordManager.__init__(self, partition, reverse_penality = 0)
    
  def create(self, base, second = 0, third = 4, fourth = 0, fifth = 7, sixth = 0, seventh = 0):
    base           = base % 12
    allowed_values = set([base, (base + second) % 12, (base + third) % 12, (base + fourth) % 12, (base + fifth) % 12, (base + sixth) % 12, (base + seventh) % 12])
    values         = []
    frets          = u""
    strings        = list(reversed(self.partition.view.strings))
    max_string_id  = len(strings) - 1
    for i in range(len(strings)):
      if strings[i].base_note % 12 in allowed_values:
        values.append((strings[i].base_note, max_string_id - i))
        frets += u"0"
      else:
        frets += u"X"
    return values, frets
    


if __name__ == "__main__":
  import songwrite2, songwrite2.model, songwrite2.plugins.lyre
  partition = songwrite2.model.Partition(None)
  partition.set_view_type(songwrite2.model.GuitarView)
  manager = TablatureChordManager(partition)
  #partition.set_view_type(songwrite2.plugins.lyre.SevenStringLyreView)
  #manager = LyreChordManager(partition)
  #notes = frozenset([
  #  36,
  #  36 + 2,
  #  36 + 4,
  #  36 + 7,
  #  ])
  notes = frozenset([64, 52, 60, 48, 55])
  chord = manager.identify(notes)
  print chord.name
  print
  #for i in range(12):
  #  print songwrite2.model.note_label(i) + u"  \t" + manager.create(i)[1], manager.create(i, third = 3)[1], manager.create(i, seventh = 10)[1], manager.create(i, third = 3, seventh = 10)[1]

  
