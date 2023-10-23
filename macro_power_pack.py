# Macro power pack
#
# Copyright (C) 2023 Adam Makswiej <vertexbz@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import types, configfile, ast, json, jinja2, hashlib
from . import gcode_macro


def hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


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
        self.script = hash(script)


def get_variabales(print, config):
    variables = {}
    prefix = 'variable_'

    for option in config.get_prefix_options(prefix):
        try:
            literal = ast.literal_eval(config.get(option))
            json.dumps(literal, separators=(',', ':'))
            variables[option[len(prefix):]] = literal
        except (SyntaxError, TypeError, ValueError) as e:
            print("Option '%s' in section '%s' is not a valid literal: %s" % (option, config.get_name(), e))

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

    def update(self, gcmd, config):
        name_filter = gcmd.get('NAME', None)

        for section_config in config.get_prefix_sections(self.section):
            key = section_config.get_name()

            if not name_filter is None and key.split()[1].lower() != name_filter.lower():
                continue

            current = self.printer.lookup_object(key, None)
            if current is None:
                self._add(gcmd, key, config, section_config)
            elif not self._compare(gcmd, current, section_config):
                self._update(gcmd, key, config, current, section_config)

        for key, current in self.printer.lookup_objects(self.section):
            if key == self.section:
                continue

            if not name_filter is None and key.split()[1].lower() != name_filter.lower():
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
        vars_mode = gcmd.get_int('VARIABLES', 1)
        if vars_mode > 0:
            new_vars = get_variabales(gcmd.respond_info, section_config)

            if vars_mode == 1:
                new_vars.update(current.variables)

            if current.variables != new_vars:
                return False

        return current.template.script == hash(section_config.get('gcode')) and current.cmd_desc == section_config.get(
            "description", "G-Code macro") and current.rename_existing == section_config.get("rename_existing", None)

    def _add(self, gcmd, key, config, section_config):
        try:
            self.gcode_macro.env.parse(section_config.get('gcode'))

            obj = self.printer.load_object(config, key)
            if not obj.rename_existing is None:
                obj.handle_connect()

            gcmd.respond_info("Added {}".format(key))
        except jinja2.exceptions.TemplateSyntaxError as e:
            gcmd.respond_info('Skipped {} - template error: {}'.format(key, e))

    def _update(self, gcmd, key, config, current, section_config):
        vars_mode = gcmd.get_int('VARIABLES', 1)
        try:
            self.gcode_macro.env.parse(section_config.get('gcode'))

            current.template = self.gcode_macro.load_template(section_config, 'gcode')
            current.cmd_desc = section_config.get("description", "G-Code macro")

            new_vars = get_variabales(gcmd.respond_info, section_config)
            if vars_mode > 0:

                if vars_mode == 1:
                    new_vars.update(current.variables)

                current.variables = new_vars

            rename_existing = section_config.get("rename_existing", None)
            if current.rename_existing is None and not rename_existing is None:
                current.handle_connect()  # this shouldn't happen
            elif not current.rename_existing is None and rename_existing is None:
                gcmd.respond_info("Warning: rename_existing {} removed from config, not updating!".format(
                    key))  # this shouldn't happen
            elif current.rename_existing != rename_existing:
                orig = self.gcode.register_command(current.rename_existing, None)
                self.gcode.register_command(rename_existing, orig)

                if current.rename_existing in self.gcode.gcode_help:
                    self.gcode.gcode_help[rename_existing] = self.gcode.gcode_help[current.rename_existing]
                    del self.gcode.gcode_help[current.rename_existing]

            current.rename_existing = rename_existing

            gcmd.respond_info("Updated {}".format(key))
        except jinja2.exceptions.TemplateSyntaxError as e:
            gcmd.respond_info('Skipped {} - template error: {}'.format(key, e))

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

        if not current.rename_existing is None:
            orig = self.gcode.register_command(current.rename_existing, None)
            self.gcode.register_command(current.alias, orig)

        # remove from printer configuration
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
        try:
            self.gcode_macro.env.parse(section_config.get('template'))

            self.printer.load_object(config, key)
            gcmd.respond_info("Added {}".format(key))
        except jinja2.exceptions.TemplateSyntaxError as e:
            gcmd.respond_info('Skipped {} - template error: {}'.format(key, e))

    def _update(self, gcmd, key, config, current, section_config):
        try:
            self.gcode_macro.env.parse(section_config.get('template'))

            current.template = section_config.get('template')
            gcmd.respond_info("Updated {}".format(key))
        except jinja2.exceptions.TemplateSyntaxError as e:
            gcmd.respond_info('Skipped {} - template error: {}'.format(key, e))

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

        self.gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self.gcode_macro.load_template = types.MethodType(self.load_template, self.gcode_macro)
        self.gcode_macro.create_template_context = types.MethodType(self.create_template_context, self.gcode_macro)
        self.gcode_macro.env.loader = MacroTemplateLoader(self.printer)

        if config.getboolean('enable_jinja_do', default=False):
            self.gcode_macro.env.add_extension('jinja2.ext.do')
        if config.getboolean('enable_jinja_loopcontrols', default=False):
            self.gcode_macro.env.add_extension('jinja2.ext.loopcontrols')
        if config.getboolean('enable_jinja_filter_bool', default=False):
            self.gcode_macro.env.filters['bool'] = filter_bool
        if config.getboolean('enable_jinja_filter_yesno', default=False):
            self.gcode_macro.env.filters['yesno'] = filter_yesno
        if config.getboolean('enable_jinja_filter_onoff', default=False):
            self.gcode_macro.env.filters['onoff'] = filter_onoff
        if config.getboolean('enable_jinja_filter_fromjson', default=False):
            self.gcode_macro.env.filters['fromjson'] = filter_fromjson

        self.config = {
            'power_printer': config.getboolean('enable_power_printer', default=False),
            'jinja_print': config.getboolean('enable_jinja_print', default=False)
        }

        self._load_vars(config)

        self.updater_gcode_macro = GCodeMacroUpdater(self.printer)
        self.updater_macro_template = MacroTemplateUpdater(self.printer)

        self.gcode.register_command(
            'MACRO_RELOAD',
            self.cmd_MACRO_RELOAD,
            desc="Reloads macros from config files"
        )

    def _unwrap_variable(self, value):
        return self.gcode_macro.env.compile_expression(value)(
            gcode_macro.PrinterGCodeMacro.create_template_context(self.gcode_macro))

    def _load_vars(self, config):
        self.variables = ProxyDict(get_variabales(self.gcode.respond_info, config), unwrap=self._unwrap_variable)

    def cmd_MACRO_RELOAD(self, gcmd):
        config = PrinterConfig(self.printer).read_main_config()

        self._load_vars(config.getsection('macro_power_pack'))

        self.updater_gcode_macro.update(gcmd, config)
        self.updater_macro_template.update(gcmd, config)

        gcmd.respond_info("Reload complete")

    def load_template(self, gSelf, config, option, default=None):
        name = "%s:%s" % (config.get_name(), option)
        if default is None:
            script = config.get(option)
        else:
            script = config.get(option, default)
        return TemplateWrapper(gSelf.printer, gSelf.env, name, script)

    def create_template_context(self, gSelf, eventtime=None):
        ctx = gcode_macro.PrinterGCodeMacro.create_template_context(gSelf, eventtime)

        if self.config['jinja_print']:
            ctx['print'] = ctx['action_respond_info']

        ctx['pp'] = {'vars': self.variables}
        if self.config['power_printer']:
            ctx['pp']['printer'] = self.printer

        return ctx


class ProxyDict(dict):
    def __init__(self, *args, **kwargs):
        self._parent = kwargs.pop('parent', self)
        self._unwrap = kwargs.pop('unwrap', None)
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if isinstance(value, dict):
            return ProxyDict(value, parent=self._parent)
        elif isinstance(value, list):
            return ProxyList(value, parent=self._parent)
        elif isinstance(value, tuple):
            return ProxyTuple(value, parent=self._parent)
        elif isinstance(value, str):
            return self._parent._unwrap(value)
        return value

    def __repr__(self):
        d = {}
        for key in self:
            d[key] = self.__getitem__(key)

        return str(d)

    def __str__(self):
        return self.__repr__()


class ProxyTuple(tuple):
    def __init__(self, *args, **kwargs):
        self._parent = kwargs.pop('parent', self)
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if isinstance(value, dict):
            return ProxyDict(value, parent=self._parent)
        elif isinstance(value, list):
            return ProxyList(value, parent=self._parent)
        elif isinstance(value, tuple):
            return ProxyTuple(value, parent=self._parent)
        elif isinstance(value, str):
            return self._parent._unwrap(value)
        return value

    def __repr__(self):
        t = ()
        for key in range(len(self)):
            t = t + (self.__getitem__(key),)

        return str(t)

    def __str__(self):
        return self.__repr__()


class ProxyList(list):
    def __init__(self, *args, **kwargs):
        self._parent = kwargs.pop('parent', self)
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if isinstance(value, dict):
            return ProxyDict(value, parent=self._parent)
        elif isinstance(value, list):
            return ProxyList(value, parent=self._parent)
        elif isinstance(value, tuple):
            return ProxyTuple(value, parent=self._parent)
        elif isinstance(value, str):
            return self._parent._unwrap(value)
        return value

    def __repr__(self):
        l = []
        for key in range(len(self)):
            l.append(self.__getitem__(key))

        return str(l)

    def __str__(self):
        return self.__repr__()


def load_config(config):
    return MacroPowerPack(config)
