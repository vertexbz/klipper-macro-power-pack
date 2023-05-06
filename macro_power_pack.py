# Macro power pack
#
# Copyright (C) 2023 Adam Makswiej <vertexbz@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import types, configfile, ast, json
from . import gcode_macro

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

class MacroPowerPack:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')

        gm = self.printer.load_object(config, 'gcode_macro')
        gm.load_template = types.MethodType(power_load_template, gm)

        self.gcode.register_command(
            'MACRO_RELOAD', 
            self.cmd_MACRO_RELOAD,
            desc="Reloads macros from config files"
        )

    def cmd_MACRO_RELOAD(self, gcmd):
        gcode_macro = self.printer.lookup_object('gcode_macro')
        config = PrinterConfig(self.printer).read_main_config()

        for section_config in config.get_prefix_sections('gcode_macro'):
            key = section_config.get_name()

            current = self.printer.lookup_object(key, None)
            if current is None:
                self.printer.load_object(config, key)
                gcmd.respond_info("Added {}".format(key))
            else:
                new_vars = get_variabales(gcmd, section_config)
                new_desc = section_config.get("description", "G-Code macro")

                if current.template.script != section_config.get('gcode') or current.cmd_desc != new_desc or current.variables != new_vars:
                    current.template = gcode_macro.load_template(section_config, 'gcode')
                    current.cmd_desc = new_desc
                    current.variables = new_vars
                
                    gcmd.respond_info("Updated {}".format(key))

        for key, _ in self.printer.lookup_objects('gcode_macro')[1:]:
            if not config.has_section(key):
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

        gcmd.respond_info("Reload complete")

def load_config(config):
    return MacroPowerPack(config)
