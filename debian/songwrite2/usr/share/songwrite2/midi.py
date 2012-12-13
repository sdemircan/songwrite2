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

# More info on Rich Tablature Midi format here:
# http://www.tabledit.com/midi/rich_midi_tablature_format.html

# MIDI info:
# http://wearcam.org/ece516/MIDIspec.htm

import sys, struct, math
import songwrite2.model as model

def apply_syncope(mesure, time):
  if (mesure.rythm1 == 6) and (mesure.rythm2 == 8): # Jig
    t = (time - mesure.time) % 144
    if   t < 48: t = t * 1.2      # First  half, longer
    elif t < 96: t = t * 0.8 + 19.2 # Second half, shorter
                                          # Third  half is normal
    return mesure.time + ((time - mesure.time) // 144) * 144 + int(t)
  
  else: # Ternary syncope
    t = (time - mesure.time) % 96
    if t < 48: t = t * 1.333333333      # First  half, longer
    else:      t = t * 0.666666666 + 32 # Second half, shorter
    return mesure.time + ((time - mesure.time) // 96) * 96 + int(t)
  

class TooManyChannelError(model.SongwriteError): pass

class MidiBaseChannel(object): # A midi channel, for internal use
  def __init__(self, midi, id):
    if id >= 16: raise TooManyChannelError
    self.midi       = midi
    self.special_id = self.id = id
    
  def set_init_events(self, init_events):
    self.init_events = init_events
    self.midi.events.extend(init_events)
    
  def __int__(self): return self.id
  
class MidiChannel(MidiBaseChannel): # A normal midi channel, for internal use
  def __init__(self, midi):
    MidiBaseChannel.__init__(self, midi, midi.next_channel_id)
    midi.next_channel_id += 1
    if midi.next_channel_id == 9: # Channel 9 is reserved for Drums !
      midi.next_channel_id += 1
      
  def fork_for_special_notes(self):
    self.special_id = self.midi.next_channel_id
    if self.special_id >= 16: raise TooManyChannelError
    self.midi.next_channel_id += 1
    
    self.midi.events.extend(map( # Transpose the initing events so it apply to the new channel -- the special channel must be initialized as the normal was !
      lambda data: (data[0], data[1], chr(ord(data[2][0]) - self.id + self.special_id) + data[2][1:]),
      self.init_events,
      ))
    
class Midi(object): # A midifier, for internal use
  def __init__(self, rich_midi_tablature = 0):
    self.next_channel_id     = 0
    self.events              = []
    self.drums_channel       = MidiBaseChannel(self, 9) # Play drums on channel 9 (10 if we start counting at 1)
    self.rich_midi_tablature = rich_midi_tablature
    self.partition_2_channel = {}
    
  def data(self, mesures, playlist = None, trackable = 0):
    self.events.sort()
    
    lasttime = 0
    events2  = []
    
    time_factor = 1.0
    old_tempo   = mesures[0].tempo
    
    real_time = 0
    
    if playlist and playlist.playlist_items:
      events1 = []
      mesure2events = dict(map(lambda mesure: (mesure, []), mesures))
      
      for time_event in self.events:
        # Before event is a Midi meta-event that be stay JUST BEFORE event (this is for the Rich Tablature Midi Format)
        if len(time_event) == 3:
          time, mesure, event  = time_event
          source = None
        else: time, mesure, event, source = time_event
        
        if mesure is None:
          events2.append(varLength(0) + event)
          continue
          
        if time < 0: time = 0
        
        if mesure.syncope: time = apply_syncope(mesure, time)
        
        mesure2events[mesure].append((time, event, source))
        lasttime = time
        
      mesuretime = 0
      lasttime   = 0
      for item in playlist.playlist_items:
        for mesure in mesures[item.from_mesure : item.to_mesure + 1]:
          if mesure.tempo != old_tempo:
            time_factor = time_factor * old_tempo / mesure.tempo
            old_tempo = mesure.tempo
            
          for time_event in mesure2events[mesure]:
            time2, event, source = time_event
            time = time2 - mesure.time + mesuretime
            
            delta_time = (time - lasttime) * time_factor
            real_time += delta_time
            
            if self.rich_midi_tablature and source: # Add the rich midi tablature note event JUST BEFORE the event
              if isinstance(source, model.Partition): rich_midi_event = partition_2_rich_midi_events(source, self)
              else:                                   rich_midi_event = note_2_rich_midi_events(source)
              if rich_midi_event: events1.append((real_time, rich_midi_event))
              
            events1.append((real_time, event))
            
            if trackable and isinstance(source, model.Note):
              if 144 <= ord(event[0]) < 160:
                label = str(int(source.time))
                events1.append((real_time, struct.pack(">BB", 0xFF, 0x05) + varLength(1+len(label)) + label + "\n"))
                
            lasttime = time
            
          mesuretime += mesure.duration
          
      events1.sort()
      lasttime = time
      for time, event in events1:
        events2.append(varLength(int(time - lasttime)) + event)
        lasttime = time
        
    else:
      for time_event in self.events:
        # Before event is a Midi meta-event that be stay JUST BEFORE event (this is for the Rich Tablature Midi Format)
        if len(time_event) == 3:
          time, mesure, event  = time_event
          source = None
        else: time, mesure, event, source = time_event
        
        if time < 0: time = 0
        
        if mesure:
          if mesure.syncope: time = apply_syncope(mesure, time)
            
          if mesure.tempo != old_tempo:
            time_factor = time_factor * old_tempo / mesure.tempo
            old_tempo = mesure.tempo
            
        delta_time = (time - lasttime) * time_factor
        real_time += delta_time
        
        if self.rich_midi_tablature and source: # Add the rich midi tablature note event JUST BEFORE the event
          if isinstance(source, model.Partition): rich_midi_event = partition_2_rich_midi_events(source, self)
          else:                                   rich_midi_event = note_2_rich_midi_events(source)
          
          if rich_midi_event:
            events2.append(varLength(int(delta_time)) + rich_midi_event)
            lasttime = time
            delta_time = 0
        events2.append(varLength(int(delta_time)) + event)
        
        if trackable and isinstance(source, model.Note):
          label = str(int(source.time))
          events2.append(varLength(0) + struct.pack(">BB", 0xFF, 0x05) + varLength(1+len(label)) + label + "\n")
          
        lasttime = time
        
    if trackable:
      events2.append(varLength(0) + struct.pack(">BB", 0xFF, 0x05) + varLength(3) + "-1\n")
    events2.append(varLength(0) + END_TRACK)
    
    return chunk("MThd", struct.pack(">hhh", 0, 1, mesures[0].tempo)) + chunk("MTrk", "".join(events2))
    
    

def song_2_midi(self, start_time = 0, end_time = sys.maxint, rich_midi_tablature = 0, trackable = 0):
  midi = Midi(rich_midi_tablature)
  
  for partition in self.partitions:
    if isinstance(partition, model.Partition):
      #delta = getattr(partition, "capo", 0)
      delta = 0
      for note in partition.notes:
        note._real_value = note.value + delta
  
  for partition in self.partitions:
    if isinstance(partition, model.Partition):
      partition_2_midi(partition, midi, start_time, end_time)
  if start_time != 0:
    return midi.data(self.mesures, (), trackable)
  else:
    return midi.data(self.mesures, self.playlist, trackable)
    ME_SYSEX_GS_LSB
def partition_2_midi(self, midi, start_time, end_time):
  if not self.muted:
    if self.instrument == 128: # 128 means Drums
      channel = midi.partition_2_channel[self] = midi.drums_channel
      channel.set_init_events((
        (-1, None, struct.pack(">BBB", 0xB0 + channel.id, 0x5B, self.reverb    )), # Reverb
        (-1, None, struct.pack(">BBB", 0xB0 + channel.id, 0x5D, self.chorus    )), # Chorus
        (-1, None, struct.pack(">BBB", 0xB0 + channel.id, 0x07, self.volume / 2)), # Volume
        ))
    else:
      channel = midi.partition_2_channel[self] = MidiChannel(midi)
      channel.set_init_events((
        (-1, None, struct.pack(">BB" , 0xC0 + channel.id, self.instrument), self), # Instrument selection
        (-1, None, struct.pack(">BBB", 0xB0 + channel.id, 0x5B, self.reverb    )), # Reverb
        (-1, None, struct.pack(">BBB", 0xB0 + channel.id, 0x5D, self.chorus    )), # Chorus
        (-1, None, struct.pack(">BBB", 0xB0 + channel.id, 0x07, self.volume / 2)), # Volume
        ))
      
    # Check if some "special notes" (hammer, ...) are played at the same time that normal notes, and if so, play them on a different channel.
    fx_notes = filter(lambda note: note.fx or note.link_fx, self.notes)
    if fx_notes and not midi.rich_midi_tablature:
      # We must ALWAYS fork since we don't know when a note really ends...
      channel.fork_for_special_notes()
      
    mesure    = self.song.mesures[0]
    mesure_id = 0
    
    if midi.rich_midi_tablature: note_2_events = note_2_midi_events_without_special_effect
    else:                        note_2_events = note_2_midi_events
    
    for note in self.notes:
      while note.time >= mesure.end_time():
        mesure_id += 1
        mesure = self.song.mesures[mesure_id]
        
      midi.events.extend(note_2_events(note, channel, mesure, start_time, end_time))
      
def partition_2_rich_midi_events(self, midi):
  if not hasattr(self.view, "strings"): return None
  channel = midi.partition_2_channel[self]
  return "\xff\x10%s%s%s%s" % (struct.pack(">B", len(self.view.strings) + 2),
                               struct.pack(">B", channel.id + 1),
                               struct.pack(">B", getattr(self, "capo", 0)),
                               "".join(map(lambda string: struct.pack(">B", string.base_note), self.view.strings)))



def note_2_midi_events_without_special_effect(self, channel, mesure, start_time, end_time):
  if start_time <= self.time <= end_time:
    return (
      (self.time - start_time                , mesure, struct.pack(">BBB", 0x90 + channel.id, self._real_value, self.volume), self),
      (self.time - start_time + self.duration, mesure, struct.pack(">BBB", 0x80 + channel.id, self._real_value, self.volume)),
      )
  return ()

def note_2_midi_events(self, channel, mesure, start_time, end_time):
  if start_time <= self.time <= end_time:
    if   self.link_fx:
      func = globals().get("_note_2_midi_events_%s" % self.link_fx)
      if func: return func(self, channel, mesure, start_time, end_time)
    elif self.fx:
      func = globals().get("_note_2_midi_events_%s" % self.fx)
      if func: return func(self, channel, mesure, start_time, end_time)
    if self.linked_from: return ()
    real_time = self.real_time()
    if getattr(self.partition, "let_ring", 0):
      next = self.next()
      if next: duration = min(next.time - self.time, 384)
      else:    duration = 384
    else: duration = self.duration
    return (
      (real_time - start_time           , mesure, struct.pack(">BBB", 0x90 + channel.id, self._real_value, self.volume), self),
      (real_time - start_time + duration, mesure, struct.pack(">BBB", 0x80 + channel.id, self._real_value, self.volume)),
      )
  return ()

def _note_2_midi_events_link(self, channel, mesure, start_time, end_time):
  real_time   = self.real_time()
  first_value = self.link_first_real_value()
  _min, _max  = self.link_min_max_real_values()
  delta = max(first_value - _min, _max - first_value)

  midi_events = [] # Here we'll use the "special ID" channel, and not the channel normal ID, to avoid to change other notes played in parallel on the normal channel
  
  duration = self.link_duration()
  if getattr(self.partition, "let_ring", 0):
    next = self.next()
    while next and next.time < self.time + duration:
      next = next.next()
    if next: duration = min(next.time - self.time, 384)
    else:    duration = 384

  if not self.linked_from:
    if delta:
      midi_set_pitch_bend_delta(midi_events, real_time - start_time, mesure, channel.special_id, delta)
      
    if self.fx == u"harmonic":
      midi_events.append((real_time - start_time,            mesure, struct.pack(">BBB", 0x90 + channel.special_id, self._real_value - 12, self.volume), self))
      midi_events.append((real_time - start_time + duration, mesure, struct.pack(">BBB", 0x80 + channel.special_id, self._real_value - 12, self.volume)))
      midi_events.append((real_time - start_time,            mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, int(63.0 + 63.0 * 12.0 / delta)))) # Reset initial pitch bend
    else:
      midi_events.append((real_time - start_time,            mesure, struct.pack(">BBB", 0x90 + channel.special_id, self._real_value, self.volume), self))
      midi_events.append((real_time - start_time + duration, mesure, struct.pack(">BBB", 0x80 + channel.special_id, self._real_value, self.volume)))
      midi_events.append((real_time - start_time,            mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, 63))) # Reset initial pitch bend
      
  midi_events.append((real_time - start_time + duration - 1, mesure, struct.pack(">BBB", 0xB0 + channel.special_id, 0x7B, 127))) # Stop all sound on the special channel, because we are going to modify the pitch bend !
  
  if delta:
    if self.linked_to.fx == u"harmonic":
      midi_events.append((self.linked_to.real_time() - start_time, mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, int(63.0 + 63.0 * (self.linked_to._real_value + 12.0 - self.link_first_real_value()) / delta)))) # Pitch bend
    else:
      midi_events.append((self.linked_to.real_time() - start_time, mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, int(63.0 + 63.0 * (self.linked_to._real_value - self.link_first_real_value()) / delta)))) # Pitch bend
      
  return tuple(midi_events)


def _note_2_midi_events_slide(self, channel, mesure, start_time, end_time):
  real_time   = self.real_time()
  first_value = self.link_first_real_value()
  _min, _max  = self.link_min_max_real_values()
  delta = max(first_value - _min, _max - first_value)
  
  midi_events = [] # Here we'll use the "special ID" channel, and not the channel normal ID, to avoid to change other notes played in parallel on the normal channel
  
  if not self.linked_from:
    if delta:
      midi_set_pitch_bend_delta(midi_events, real_time - start_time, mesure, channel.special_id, delta)
      
    midi_events.append((real_time - start_time                       , mesure, struct.pack(">BBB", 0x90 + channel.special_id, self._real_value, self.volume), self))
    midi_events.append((real_time - start_time + self.link_duration(), mesure, struct.pack(">BBB", 0x80 + channel.special_id, self._real_value, self.volume)))
    midi_events.append((real_time - start_time                       , mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, 63))) # Reset initial pitch bend
    
  delta_time  = self.linked_to.real_time() - real_time
  delta_value = self.linked_to._real_value - self.link_first_real_value()
  for i in xrange(1, 11):
    value = (i / 10.0) * self.linked_to._real_value + ((10 - i) / 10.0) * self._real_value
    f = i / 10.0
    midi_events.append((real_time + int(f * delta_time) - start_time,  mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, int(63.0 + 63.0 * (value - self.link_first_real_value()) / delta)))) # Pitch bend
    
  return tuple(midi_events)

def _note_2_midi_events_bend(self, channel, mesure, start_time, end_time):
  real_time   = self.real_time()
  midi_events = [] # Here we'll use the "special ID" channel, and not the channel normal ID, to avoid to change other notes played in parallel on the normal channel
  
  midi_events.append((real_time - start_time                       , mesure, struct.pack(">BBB", 0x90 + channel.special_id, self._real_value, self.volume), self))
  midi_events.append((real_time - start_time + self.link_duration(), mesure, struct.pack(">BBB", 0x80 + channel.special_id, self._real_value, self.volume)))
  midi_events.append((real_time - start_time                       , mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, 63))) # Reset initial pitch bend
  
  delta_time  = self.duration
  delta_value = 2.0 * self.bend_pitch
  for i in xrange(10):
    f = i / 10.0
    midi_events.append((real_time + int(f * delta_time) - start_time, mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, int(31.5 * (f * delta_value + 2))))) # Pitch bend
    
  return tuple(midi_events)

def _note_2_midi_events_tremolo(self, channel, mesure, start_time, end_time):
  real_time   = self.real_time()
  midi_events = [] # Here we'll use the "special ID" channel, and not the channel normal ID, to avoid to change other notes played in parallel on the normal channel
  
  midi_events.append((real_time - start_time,                        mesure, struct.pack(">BBB", 0x90 + channel.special_id, self._real_value, self.volume), self))
  midi_events.append((real_time - start_time + self.link_duration(), mesure, struct.pack(">BBB", 0x80 + channel.special_id, self._real_value, self.volume)))
  midi_events.append((real_time - start_time,                        mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, 63))) # Reset initial pitch bend
  
  val = 0.0
  for time in xrange(int(real_time - start_time), int(real_time - start_time + self.duration), 2):
    midi_events.append((time, mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, int(31.5 * (math.sin(val) * 0.3 + 2))))) # Pitch bend
    val += 0.3
    
  return tuple(midi_events)

def _note_2_midi_events_dead(self, channel, mesure, start_time, end_time):
  real_time   = self.real_time()
  midi_events = [] # Here we'll use the "special ID" channel, and not the channel normal ID, to avoid to change other notes played in parallel on the normal channel

  midi_events.append((real_time - start_time,                        mesure, struct.pack(">BBB", 0x90 + channel.special_id, self._real_value, self.volume), self))
  midi_events.append((real_time - start_time + self.link_duration(), mesure, struct.pack(">BBB", 0x80 + channel.special_id, self._real_value, self.volume)))
  midi_events.append((real_time - start_time,                        mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, 63))) # Reset initial pitch bend

  midi_events.append((real_time - start_time + 16,                   mesure, struct.pack(">BBB", 0xB0 + channel.special_id, 120, 0))) # Stop all sounds
  
  return tuple(midi_events)

def _note_2_midi_events_harmonic(self, channel, mesure, start_time, end_time):
  if self.linked_from: return ()
  real_time   = self.real_time()
  if getattr(self.partition, "let_ring", 0):
    next = self.next()
    if next: duration = min(next.time - self.time, 384)
    else:    duration = 384
  else: duration = self.duration
  midi_events = [] # Here we'll use the "special ID" channel, and not the channel normal ID, to avoid to change other notes played in parallel on the normal channel
  
  midi_set_pitch_bend_delta(midi_events, real_time - start_time, mesure, channel.special_id, 12)
  midi_events.append((real_time - start_time           , mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, 127)))
  
  midi_events.append((real_time - start_time + duration, mesure, struct.pack(">BBB", 0xE0 + channel.special_id, 63, 63))) # Reset pitch bend
  
  midi_events.append((real_time - start_time           , mesure, struct.pack(">BBB", 0x90 + channel.special_id, self._real_value - 12, self.volume), self))
  midi_events.append((real_time - start_time + duration, mesure, struct.pack(">BBB", 0x80 + channel.special_id, self._real_value - 12, self.volume)))
  
  return tuple(midi_events)

def midi_set_pitch_bend_delta(midi_events, time, mesure, channel_id, delta):
  if time >= 1:
    midi_events.append((time - 1, mesure, struct.pack(">BBB", 0xB0 + channel_id, 0x7B, 120))) # Stop all sound on the special channel, because we are going to modify the pitch bend !
  midi_events.append  ((time    , mesure, struct.pack(">BBB", 0xB0 + channel_id, 0x64, 0x00)))
  midi_events.append  ((time    , mesure, struct.pack(">BBB", 0xB0 + channel_id, 0x65, 0x00)))
  midi_events.append  ((time    , mesure, struct.pack(">BBB", 0xB0 + channel_id, 0x06, delta)))
  


def note_2_rich_midi_events(self):
  if not hasattr(self, "string_id"): return None
  if self.fx: return globals()["_note_2_rich_midi_events_%s" % self.fx](self)
  return "\xff\x11\x01%s" % struct.pack(">b", self.string_id)

def _note_2_rich_midi_events_link(self):
  dif = cmp(self._real_value, self.linked_to._real_value)
  if   dif < 0: return "\xff\x11\x02%s\x01" % struct.pack(">b", self.string_id)
  elif dif > 0: return "\xff\x11\x02%s\x02" % struct.pack(">b", self.string_id)
  else:         return "\xff\x11\x02%s\x01" % struct.pack(">b", self.string_id) # Not supported by Rich Tablature Midi ???

def _note_2_rich_midi_events_slide(self):
  if self._real_value < self.linked_to._real_value: return "\xff\x11\x02%s\x03" % struct.pack(">b", self.string_id)
  else:                                             return "\xff\x11\x02%s\x04" % struct.pack(">b", self.string_id)

def _note_2_rich_midi_events_bend(self):
  return "\xff\x11\x03%s\x0C%s" % (struct.pack(">b", self.string_id), struct.pack(">b", int(round(self.bend_pitch / 0.25))))

def _note_2_rich_midi_events_tremolo(self):
  return "\xff\x11\x02%s\x0A" % struct.pack(">b", self.string_id)

def _note_2_rich_midi_events_dead(self):
  return "\xff\x11\x02%s\x0E" % struct.pack(">b", self.string_id)

def _note_2_rich_midi_events_roll(self):
  notes = self.chord_notes()
  if (not notes) or (self._real_value is min([note._real_value for note in notes])):
    return "\xff\x11\x02%s\x06" % struct.pack(">b", self.string_id)
  else:
    return "\xff\x11\x01" + struct.pack(">b", self.string_id) # Same as normal notes
  
def _note_2_rich_midi_events_harmonic(self):
  return "\xff\x11\x02%s\x07" % struct.pack(">b", self.string_id)



def chunk(name, data): return struct.pack(">4si", name, len(data)) + data

def varLength(i):
  array = [i & 0x7F]
  while i >= 128:
    i = i >> 7
    array.append((i & 0x7F) | 0x80)
    
  array.reverse()
  return struct.pack(">" + "B" * len(array), *array)

def readVarLength(file):
  result = 0
  while 1:
    b = struct.unpack(">B", file.read(1))[0]
    
    result = result | (b & 0x7F)
    if (b & 0x80) != 0x80: break
    result = result << 7
    
  return result

END_TRACK = "\xff\x2f\x00"

