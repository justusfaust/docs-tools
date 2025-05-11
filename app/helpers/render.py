#!/usr/bin/env python3

from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from tzlocal import get_localzone


def render_file_template(templates_dir: str, template: str, data: dict, outfile: str) -> None:
    """renders provided jinja2 file template with given data

    Parameters
    ----------
    templates_dir: str
                   search path for jinja2 templates
    template:      str
                   filename of template
    data:          dict
                   template variables
    outfile:       str
                   filename and path of output
    """
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        trim_blocks=True,
        lstrip_blocks=True
    )
    template = env.get_template(template)

     # make 'now' available in jinja templates
    template.globals["now"] = datetime.now(get_localzone()).strftime('%d.%m.%Y %H:%M:%S %z')

    output = template.render(**data)

    with open(outfile, "w") as f:
        f.write(output)
