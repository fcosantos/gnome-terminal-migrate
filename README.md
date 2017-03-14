# Gnome Terminal migrate tool

Recover Gnome Terminal profiles from gconf directories and export to a dconf load script.
Useful when recovering profiles from Ubuntu 14.04 or less.

Depends on python2.7. The script does the best effort to recover all options, some of them don't have sense anymore in newest versions of gterminal. For more information you can check <https://github.com/GNOME/gnome-terminal/blob/master/src/migration.c>.

## Usage
```
usage: gterminal_tool.py [-h] [--load-current-profiles]
                         [--load-gconf-profiles-from GCONF_PATH]
                         [--skip-duplicate-names]
                         [--set-backup-profile-default] [--set [SET]]
                         [--execute-action] [--execute-delete]

Gnome Terminal config restore

optional arguments:
  -h, --help            show this help message and exit
  --load-current-profiles
                        Load current dconf profiles
  --load-gconf-profiles-from GCONF_PATH
                        Load gconf profiles from path
  --skip-duplicate-names
                        Skip restoring already existent profile names
  --set-backup-profile-default
                        Set new default profile to GConf default
  --set [SET]           Set all profile option to value. For ex:
                        --set="font='Consolas 13'" --set="default-size-
                        columns=136" --set="default-size-rows=44"
  --execute-action      Run command that updates dconf with command result, by
                        default we just print new dconf to console, and you
                        can manually load with "dconf load"
  --execute-delete      Delete previous existing profiles
```


## Examples
Add old profiles to current list, ignore if same name exist, print to stdout:
```Bash
python gterminal_tool.py --load-current-profiles --skip-duplicate-names \
    --load-gconf-profiles-from homefolder_backup/.gconf/apps/gnome-terminal \
    > new_dconf_profiles
```

You can now review `new_dconf_profiles` and then load it with:
```Bash
/usr/bin/dconf load /org/gnome/terminal/legacy/profiles:/ < new_dconf_profiles
```

Update current profiles properties at once:
```Bash
python gterminal_tool.py --load-current-profiles --set="font='Consolas 13'" \
    --set="default-size-columns=170" --set="default-size-rows=50" \
    --execute-delete --execute-action
```

## Other information

### Gconf file structure:
```
apps/
├── gnome-terminal
│   ├── %gconf.xml
│   ├── global
│   │   └── %gconf.xml
│   └── profiles
│       ├── Default
│       │   └── %gconf.xml
│       ├── %gconf.xml
│       ├── Profile1
│       │   └── %gconf.xml
│       ├── Profile10
│       │   └── %gconf.xml
│       ├── Profile11
│       │   └── %gconf.xml
```

### Dconf editor
Run it and navigate to `/org/gnome/terminal/legacy/profiles:/` to see current profiles.
```
$ sudo apt-get install dconf-editor
$ dconf-editor
```