# klipper-macro-power-pack

Reload all your macros without restarting Klipper! 

And get more from jinja templates?

## Installation

```
cd ~
git clone https://github.com/vertexbz/klipper-macro-power-pack.git
cd ~/klipper/klippy/extras/
ln -s ~/klipper-macro-power-pack/macro_power_pack.py .
ln -s ~/klipper-macro-power-pack/macro_template.py .
```


### Moonraker
To add the extension to the update manager you can use following config

```
[update_manager macro_power_pack]
type: git_repo
path: ~/klipper-macro-power-pack
origin: https://github.com/vertexbz/klipper-macro-power-pack.git
primary_branch: master
is_system_service: False
```


### Klipper Configuration

Finally to enable the extension, add floowing block (preferably) on the top of your config
```
[macro_power_pack]
enable_jinja_do: True
enable_jinja_loopcontrols: True
enable_jinja_filter_bool: True
enable_jinja_filter_yesno: True
enable_jinja_filter_onoff: True
enable_jinja_filter_fromjson: True
enable_jinja_print: True
enable_power_printer: True
```

## Features

### Macro reload
G-Code command `MACRO_RELOAD [VARIABLES=1] [NAME=<template/macro name>]` reads configuration files again and reloads macros. 
By default it also adds new variables, to disable this behavior add `VARIABLES=0` parameter, or to replace variable sets with those from file use `VARIABLES=2`. You can also restrict reload by macro/template name using `NAME=...` parameter.

### Templates
To define macros for use in [`include`s](https://jinja.palletsprojects.com/en/2.10.x/templates/#include) or [`import`s](https://jinja.palletsprojects.com/en/2.10.x/templates/#import) define `macro_template` section

```
[macro_template my_test_template]
template:
    {% macro hello(name) -%}
      Hello { name }!
    {%- endmacro %}

```

usage:

```
[gcode_macro TEST_HELLO]
gcode:
  {% import 'my_test_template' as t %}
  M117 {t.hello('world')}

```

### Template filters
- `bool` - converts "yes", "true", "on" (case insensitive) and positive numeric values to boolean _True_ and the rest to _False_
- `yesno` - converts boolean _True_ to string `yes` and _False_ to `no`
- `onoff` - converts boolean _True_ to string `on` and _False_ to `off`
- `fromjson` - parses json string into dict

### `do` statement
Enables `jinja2.ext.do` jinja extension that provides `do` statement as a wrapper for any calls from template and ignores return value

```
[gcode_macro TEST_DO]
gcode:
  {% set dict = '{"a":"foo"}'|fromjson %}
  {% do dict.update({'a':'bar'}) %}
  M117 {dict['a']}
```

### `break` and `continue` statements
Enables `jinja2.ext.loopcontrols`  jinja extension that adds support for break and continue in loops

### `pp.printer`
Global variable `pp.printer` proivdes full access to the main [printer](https://github.com/Klipper3d/klipper/blob/master/klippy/klippy.py) object
