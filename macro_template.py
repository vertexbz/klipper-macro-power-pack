class MacroTemplate:
    def __init__(self, config):
        if len(config.get_name().split()) > 2:
            raise config.error(
                    "Name of section '%s' contains illegal whitespace"
                    % (config.get_name()))
        self.name = config.get_name().split()[1]
        self.template = config.get("template", None)
       
def load_config_prefix(config):
    return MacroTemplate(config)
