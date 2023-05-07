# Macro power pack
#
# Copyright (C) 2023 Adam Makswiej <vertexbz@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import types, configfile, ast, json, jinja2
from . import gcode_macro



class MacroTemplateLoader(jinja2.BaseLoader):
    def __init__(self, printer):
        self.printer = printer

    def get_source(self, environment, template):
        obj = self.printer.lookup_object('macro_template ' + template, None)
        if obj is None:
            raise TemplateNotFound(template)

        return obj.template, template, lambda: False


class TemplateWrapper(gcode_macro.TemplateWrapper):
    def __init__(self, printer, env, name, script):
        gcode_macro.TemplateWrapper.__init__(self, printer, env, name, script)
        self.script = script

def power_load_template(self, config, option, default=None):
    name = "%s:%s" % (config.get_name(), option)
    if default is None:
        script = config.get(option)
    else:
        script = config.get(option, default)
    return TemplateWrapper(self.printer, self.env, name, script)

def get_variabales(gcmd, config):
    variables = {}
    prefix = 'variable_'

    for option in config.get_prefix_options(prefix):
        try:
            literal = ast.literal_eval(config.get(option))
            json.dumps(literal, separators=(',', ':'))
            variables[option[len(prefix):]] = literal
        except (SyntaxError, TypeError, ValueError) as e:
            gcmd.respond_info(
                "Option '%s' in section '%s' is not a valid literal: %s" % (
                    option, config.get_name(), e))

    return variables

class PrinterConfig(configfile.PrinterConfig): 
    def __init__(self, printer):
        self.printer = printer
        self.deprecated = {}
        self.status_raw_config = {}
        self.status_save_pending = {}
        self.status_settings = {}
        self.status_warnings = []

    def log_config(self, config):
        pass
    def check_unused_options(self, config):
        pass
    def cmd_SAVE_CONFIG(self, gcmd):
        pass

class SectionUpdater:
    def __init__(self, printer, section):
        self.section = section
        self.printer = printer

    def update(self, gcmd):
        config = PrinterConfig(self.printer).read_main_config()

        for section_config in config.get_prefix_sections(self.section):
            key = section_config.get_name()

            current = self.printer.lookup_object(key, None)
            if current is None:
                self._add(gcmd, key, config, section_config)
            elif not self._compare(gcmd, current, section_config):
                self._update(gcmd, key, config, current, section_config)

        for key, current in self.printer.lookup_objects(self.section):
            if key == self.section:
                continue
            if not config.has_section(key):
                self._remove(gcmd, key, current)

    def _compare(self, gcmd, current, section_config):
        return True

    def _add(self, gcmd, key, config, section_config):
        pass

    def _update(self, gcmd, key, config, current, section_config):
        pass

    def _remove(self, gcmd, key, current):
        pass

class GCodeMacroUpdater(SectionUpdater): 
    def __init__(self, printer):
        SectionUpdater.__init__(self, printer, 'gcode_macro')
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode_macro = self.printer.lookup_object('gcode_macro')

    def _compare(self, gcmd, current, section_config):
        new_vars = get_variabales(gcmd, section_config)
        new_desc = section_config.get("description", "G-Code macro")
        return current.template.script == section_config.get('gcode') and current.cmd_desc == new_desc and current.variables == new_vars


    def _add(self, gcmd, key, config, section_config):
        self.printer.load_object(config, key)
        gcmd.respond_info("Added {}".format(key))

    def _update(self, gcmd, key, config, current, section_config):
        current.template = self.gcode_macro.load_template(section_config, 'gcode')
        current.cmd_desc = section_config.get("description", "G-Code macro")
        current.variables = get_variabales(gcmd, section_config)
        gcmd.respond_info("Updated {}".format(key))

    def _remove(self, gcmd, key, current):
        name = key.split()[1]
        cmd = name.upper()

        # remove variable access
        prev_key, prev_values = self.gcode.mux_commands.get("SET_GCODE_VARIABLE")
        del prev_values[name]

        # remove gcode
        if cmd in self.gcode.ready_gcode_handlers:
            del self.gcode.ready_gcode_handlers[cmd]
        if cmd in self.gcode.base_gcode_handlers:
            del self.gcode.base_gcode_handlers[cmd]
        if cmd in self.gcode.gcode_help:
            del self.gcode.gcode_help[cmd]

        if key in self.printer.objects:
            del self.printer.objects[key]

        gcmd.respond_info("Removed {}".format(key))

class MacroTemplateUpdater(SectionUpdater): 
    def __init__(self, printer):
        SectionUpdater.__init__(self, printer, 'macro_template')
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode_macro = self.printer.lookup_object('gcode_macro')

    def _compare(self, gcmd, current, config):
        return current.template == config.get('template')

    def _add(self, gcmd, key, config, section_config):
        self.printer.load_object(config, key)
        gcmd.respond_info("Added {}".format(key))

    def _update(self, gcmd, key, config, current, section_config):
        current.template = section_config.get('template')
        gcmd.respond_info("Updated {}".format(key))

    def _remove(self, gcmd, key, current):
        if key in self.printer.objects:
            del self.printer.objects[key]

        gcmd.respond_info("Removed {}".format(key))

def filter_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        value = value.strip().lower()
        if value == 'true' or value == 'on' or value == 'yes':
            return True

    try:
        return int(value) > 0
    except ValueError:
        return False

def filter_yesno(value):
    return "yes" if filter_bool(value) else "no"

def filter_onoff(value):
    return "on" if filter_bool(value) else "off"

def filter_fromjson(value):
    return json.loads(value)

class MacroPowerPack:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')

        gm = self.printer.load_object(config, 'gcode_macro')
        gm.load_template = types.MethodType(power_load_template, gm)
        gm.env.add_extension('jinja2.ext.do')
        gm.env.add_extension('jinja2.ext.loopcontrols')
        gm.env.loader = MacroTemplateLoader(self.printer)
        gm.env.filters['bool'] = filter_bool
        gm.env.filters['yesno'] = filter_yesno
        gm.env.filters['onoff'] = filter_onoff
        gm.env.filters['fromjson'] = filter_fromjson

        self.updater_gcode_macro = GCodeMacroUpdater(self.printer)
        self.updater_macro_template = MacroTemplateUpdater(self.printer)

        self.gcode.register_command(
            'MACRO_RELOAD', 
            self.cmd_MACRO_RELOAD,
            desc="Reloads macros from config files"
        )

    def cmd_MACRO_RELOAD(self, gcmd):
        self.updater_gcode_macro.update(gcmd)
        self.updater_macro_template.update(gcmd)

        gcmd.respond_info("Reload complete")

def load_config(config):
    return MacroPowerPack(config)
