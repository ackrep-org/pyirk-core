import datetime
from jinja2 import Environment, PackageLoader, select_autoescape, FileSystemLoader
from ipydex import IPS

from . import settings


def generate_report():

    jin_env = Environment(loader=FileSystemLoader(settings.TEMPLATE_PATH))
    template_doc = jin_env.get_template('report-template.tex')

    context = {
        "date": datetime.datetime.today().strftime(r"%Y-%m-%d"),
        "nodes": 10,
        "edges": 22,
    }
    res = template_doc.render(c=context)
    # IPS()

    fname = "report.tex"
    with open(fname, "w") as resfile:
        resfile.write(res)
    print(fname, "written.")
