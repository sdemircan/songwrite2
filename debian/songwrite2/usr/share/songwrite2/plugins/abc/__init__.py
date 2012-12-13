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

import songwrite2.plugins as plugins


class ABCImportPlugin(plugins.ImportPlugin):
  def __init__(self):
    plugins.ImportPlugin.__init__(self, "ABC", ["abc", "txt"])
    
  def import_from_string(self, data):
    import songwrite2.plugins.abc.abc
    return songwrite2.plugins.abc.abc.parse(data)
    
ABCImportPlugin()


