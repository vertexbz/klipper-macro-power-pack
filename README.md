# klipper-macro-power-pack

Reload all your macros without restarting Klipper! 

And get more from jinja templates?

# Installation

```
cd ~
git clone https://github.com/vertexbz/klipper-macro-power-pack.git
cd ~/klipper/klippy/extras/
ln -s ~/klipper-macro-power-pack/macro_power_pack.py .
ln -s ~/klipper-macro-power-pack/macro_template.py .
```


## Moonraker
To add the extension to the update manager you can use following config

```
[update_manager macro_power_pack]
type: git_repo
path: ~/klipper-macro-power-pack
origin: https://github.com/vertexbz/klipper-macro-power-pack.git
primary_branch: master
is_system_service: False
```


## Klipper Configuration

Add this (preferably) on top of your config
```
[macro_power_pack]
```

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


## Usage

```
MACRO_RELOAD      - reloads macros

```