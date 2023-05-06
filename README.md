# klipper-macro-power-pack

Reload all your macros without restarting Klipper!

# Installation

```
cd ~
git clone https://github.com/vertexbz/klipper-macro-power-pack.git
cd ~/klipper/klippy/extras/
ln -s ~/klipper-macro-power-pack/macro_power_pack.py .
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

## Usage

```
MACRO_RELOAD      - reloads macros

```