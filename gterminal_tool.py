#!/usr/bin/python2.7

from __future__ import print_function
import argparse
import subprocess
import pprint
import os
import uuid
import xml.etree.ElementTree
import sys


_DCONF_SAVE_CMD = '/usr/bin/dconf load /org/gnome/terminal/legacy/profiles:/'
_DCONF_DUMP_CMD = '/usr/bin/dconf dump /org/gnome/terminal/legacy/profiles:/'
_DCONF_DELETE_CMD = (
    '/usr/bin/dconf reset -f /org/gnome/terminal/legacy/profiles:/')


def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)


class GConfTerminalProfiles(object):

  _IGNORE_LIST = (  # Not direct translation found
      'alternate_screen_scroll',
      'background_image',
      'background_type',
      'cursor_blink_mode',
      'cursor_shape',
      'default_show_menubar',
      'scroll_background',
      'scrollback_unlimited',
      'scrollbar_position',
      'title',
      'title_mode',
      'update_records',
      'use_custom_default_size',
      'word_chars',
  )
  _WHITE_LIST = (  # unused
      'use_system_font',
      'font',
      'visible_name',
      'silent_bell',
      'use_theme_colors',
      'allow_bold',
      'palette',
      'scrollback_lines',
      'use_custom_command',
      'custom_command',
      'background_color',
      'background_darkness',
      'bold_color_same_as_fg',
      'login_shell',
      'scroll_on_keystroke',
      'scroll_on_output',
      'default_size_columns',
      'default_size_rows',
      'bold_color',
      'backspace_binding',
      'foreground_color',
      'delete_binding',
      'exit_action',
  )

  def __init__(self, gnome_terminal_gconf_path):
    self._gnome_terminal_gconf_path = gnome_terminal_gconf_path
    self._profiles_path = os.path.join(gnome_terminal_gconf_path, 'profiles')

    self._default_profile_name = None
    self._profile_names = []

    self._load_global_configuration()

  def _load_global_configuration(self):
    gconf_global_xml = os.path.join(self._gnome_terminal_gconf_path,
                                    'global/%gconf.xml')

    default_profile = None
    e = xml.etree.ElementTree.parse(gconf_global_xml).getroot()
    for entry in e.findall('entry'):
      if entry.attrib.get('name') == 'default_profile':
        self._default_profile_name = entry[0].text

      if entry.attrib.get('name') == 'profile_list':  # Read profiles in order
        for list_element in entry.findall('li'):
          profile = list_element[0].text
          self._profile_names.append(profile)

  def _color_16bits_hex_to_8bits_rgb(self, hexatext):
    return 'rgb(%s,%s,%s)' % (int(hexatext[0:4], 16) / 16 / 16,
                              int(hexatext[4:8], 16) / 16 / 16,
                              int(hexatext[8:12], 16) / 16 / 16)

  def extract_gconf_xml_values(self, profile_name):
    xml_filename = os.path.join(self._profiles_path, profile_name, '%gconf.xml')
    profile_settings = {}

    e = xml.etree.ElementTree.parse(xml_filename).getroot()
    for entry in e.findall('entry'):
      name = entry.attrib.get('name')
      if name in self._IGNORE_LIST:
        continue

      value = entry.attrib.get('value')

      if not value:
        value = entry[0].text

      if name == 'silent_bell':
        name = 'audible-bell'
        value = str(not bool(value)).lower()

      elif name == 'background_darkness':
        name = 'background-transparency-percent'
        value = int(float(value) * 100)

      elif name == 'visible_name':
        value = '\'%s\'' % value

      elif name in ('font', 'custom_command', 'exit_action'):
        value = '\'%s\'' % value

      elif name in ('background_color', 'foreground_color', 'bold_color'):
        value = '\'%s\'' % (self._color_16bits_hex_to_8bits_rgb(value[1:]))

      elif name == 'palette':
        value = str(
            [self._color_16bits_hex_to_8bits_rgb(v[1:])
             for v in value.split(':')])

      elif name == 'backspace_binding':
        value = '\'%s\'' % value.replace('ascii-del', 'ascii-delete')

      elif name == 'delete_binding':
        value = '\'%s\'' % value.replace('escape-sequence', 'delete-sequence')

      name = name.replace('_', '-')
      profile_settings[name] = value
    return profile_settings

  def default_profile_name(self):
    return self._default_profile_name

  def profiles(self):
    for profile_name in self._profile_names:
      yield self.extract_gconf_xml_values(profile_name)


class DConfTerminalProfiles(object):

  def __init__(self, skip_duplicate_names=False):
    self._skip_duplicate_names = skip_duplicate_names

    self._order_list = []  # (name, uuid) pairs
    self._default_profile = None
    self._profiles = {}

  def add(self, profile_uuid, profile_dict):
    profile_name = profile_dict['visible-name'].strip('\'')
    current_names = [name for name, _ in self._order_list]
    if self._skip_duplicate_names and profile_name in current_names:
      eprint('Skipping duplicated profile "%s"' % profile_name)
      return

    self._order_list.append((profile_name, profile_uuid))
    self._profiles[profile_uuid] = profile_dict

  def set_default_profile(self, profile_uuid):
    # print 'Setting default profile to:', profile_uuid
    self._default_profile = profile_uuid

  def _dconf_properties_to_entry(self, id, properties):
    items = properties.items()
    items.sort()
    return (('[%s]\n' % id) +
            '\n'.join(['%s=%s' % (k, v) for k, v in items]))

  def as_dconf_load(self):
    entries = []

    current_uuids = [profile_uuid for _, profile_uuid in self._order_list]
    global_conf = {'list': str(current_uuids)}
    if not self._default_profile is None:
      global_conf['default'] = '\'%s\'' % self._default_profile

    entries.append(self._dconf_properties_to_entry('/', global_conf))

    for profile_uuid in self._profiles:
      entries.append(
          self._dconf_properties_to_entry(
              ':' + profile_uuid, self._profiles[profile_uuid]))

    return '\n\n'.join(entries)

  def as_resume(self):
    lines = []
    lines.append('Default profile: "%s"' % self._default_profile)
    lines.append('')

    current_order = list(self._order_list)  # copy
    sorted_order = sorted(current_order, key=lambda pairs: pairs[0].lower())

    for profile_name, profile_uuid in sorted_order:
      is_default = self._default_profile == profile_uuid
      lines.append(' %s  %s: %s' %
          ('*' if is_default else ' ', profile_uuid, profile_name))
    return '\n'.join(lines)

  def _dconf_entries_to_dict(self, dump_value):
    dconf_dict = {}
    title = ''
    for line in dump_value.split('\n'):
      if not line:
        continue

      if line.startswith('['):
        title = line.partition('[')[2].rpartition(']')[0]
        continue

      if not title in dconf_dict:
        dconf_dict[title] = {}

      param, _, value = line.partition('=')
      dconf_dict[title][param] = value

    return dconf_dict

  def from_dump(self, dump_value):
    current_profiles = self._dconf_entries_to_dict(dump_value)

    if '/' in current_profiles:
      global_config = current_profiles.pop('/')
      profiles_as_list = global_config.get(
          'list').replace(' ', '').strip('[]\'').split('\',\'')

      self.set_default_profile(global_config.get('default').strip('\''))
      for profile_uuid in profiles_as_list:
        self.add(profile_uuid, current_profiles[':' + profile_uuid])

  def set_param(self, param, value):
    """Set all profiles param to value."""
    for profile in self._profiles:
      self._profiles[profile][param] = value


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Gnome Terminal config restore')
  parser.add_argument('--load-current-profiles',
                      dest='load_current_profiles',
                      help='Load current dconf profiles',
                      action='store_true',
                      default=False)
  parser.add_argument('--load-gconf-profiles-from',
                      dest='gconf_path',
                      help='Load gconf profiles from path',
                      action='store')
  parser.add_argument('--skip-duplicate-names',
                      dest='skip_duplicate_names',
                      help='Skip restoring already existent profile names',
                      action='store_true',
                      default=False)
  parser.add_argument('--set-backup-profile-default',
                      dest='set_backup_profile_default',
                      help='Set new default profile to GConf default',
                      action='store_true',
                      default=False)
  parser.add_argument('--set',
                      nargs='?',
                      help=(
      'Set all profile option to value. For ex: --set="font=\'Consolas 13\'" '
      '--set="default-size-columns=136" --set="default-size-rows=44"'),
                      action='append')
  parser.add_argument('--execute-action',
                      dest='execute_action',
                      help=(
      'Run command that updates dconf with command result, by default we just '
      'print new dconf to console, and you can manually load with "dconf load"'
      ),
                      action='store_true',
                      default=False)
  parser.add_argument('--execute-delete',
                      dest='execute_delete',
                      help='Delete previous existing profiles',
                      action='store_true',
                      default=False)
  args = parser.parse_args()

  # Main
  dconf_profiles = DConfTerminalProfiles(args.skip_duplicate_names)

  if args.load_current_profiles:
    dconf_profiles_dump = subprocess.check_output(_DCONF_DUMP_CMD.split(' '))
    dconf_profiles.from_dump(dconf_profiles_dump)

  if args.gconf_path:
    gconf_obj = GConfTerminalProfiles(args.gconf_path)
    default_profile_name = gconf_obj.default_profile_name()

    for profile in gconf_obj.profiles():
      new_uuid = str(uuid.uuid4())
      dconf_profiles.add(new_uuid, profile)

      if (args.set_backup_profile_default and
          default_profile_name == profile.get('visible-name').strip('\'')):
        dconf_profiles.set_default_profile(new_uuid)

  if args.set:
    for param in args.set:
      if not '=' in param:
        continue
      name, _, value = param.partition('=')
      eprint('Setting all profiles preference "%s" to "%s"' % (name, value))
      dconf_profiles.set_param(name, value)

  load_result = dconf_profiles.as_dconf_load()
  if args.execute_action:
    if args.execute_delete:
      eprint('Deleting all gnome terminal entries')
      subprocess.check_output(_DCONF_DELETE_CMD.split(' '))

    eprint('Loading new gnome terminal entries')
    process = subprocess.Popen(_DCONF_SAVE_CMD.split(' '),
                               stdin=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    process.stdin.write(load_result)
    process.stdin.close()
    if process.stdout:
      print(process.stdout)

  else:
    print(load_result)

  eprint(dconf_profiles.as_resume())
