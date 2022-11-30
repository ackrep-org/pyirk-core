import datetime
from jinja2 import Environment, PackageLoader, select_autoescape, FileSystemLoader
from ipydex import IPS
import addict

from . import erkloader
import pyerk as p

try:
    # this will be part of standard library for python >= 3.11
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from . import settings


def generate_report(reportconf_path: str):

    rg = ReportGenerator(reportconf_path)

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


class ReportGenerator:
    """
    Omnipotent class that manages the report-generation. Assumend to be a singleton.
    """

    def __init__(self, reportconf_path: str):

        self.reportconf = self.load_report_conf(reportconf_path)
        self.mods = self.load_modules()
        self.authors = None
        self.content = None
        self.resolve_entities()

    @staticmethod
    def load_report_conf(reportconf_path: str) -> dict:
        """

        """

        try:
            with open(reportconf_path, "rb") as fp:
                conf = tomllib.load(fp)
        except FileNotFoundError:
            raise

        return conf

    def load_modules(self) -> list:

        res = []
        if not (lmdict := self.reportconf.get("load_modules")):
            return res

        assert isinstance(lmdict, dict)

        for prefix, path in lmdict.items():
            mod = erkloader.load_mod_from_path(path, prefix=prefix)
            res.append(mod)

        return res

    def resolve_entities(self):
        self.authors = self.reportconf.get("authors")
        self.content = self.reportconf.get("content")
        assert len(self.authors) > 0
        assert len(self.content) > 0

        IPS()


def resolve_entities_in_nested_data(data):
    assert isinstance(data, (dict, str, list, int, float))

    if isinstance(data, (int, float)):
        return data

    if isinstance(data, str):
        if data.startswith(":"):
            erk_key_str = data[1:]
            entity = p.ds.get_entity_by_key_str(erk_key_str)
            assert entity is not None, f"unknown key_str: {erk_key_str}"
            return entity
        else:
            return data

    if isinstance(data, list):
        return [resolve_entities_in_nested_data(d) for d in data]

    assert isinstance(data, dict)

    res = {}
    for key, value in data.items():
        res[key] = resolve_entities_in_nested_data(value)
        IPS(key == ":I1")

    return res
