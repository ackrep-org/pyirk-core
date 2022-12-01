import datetime
import os

import addict
from jinja2 import Environment, PackageLoader, select_autoescape, FileSystemLoader
from ipydex import IPS

try:
    # this will be part of standard library for python >= 3.11
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


from . import erkloader
import pyerk as p
from pyerk.erkloader import preserve_cwd

from . import settings




def generate_report(reportconf_path: str):

    rg = ReportGenerator(reportconf_path)
    rg.generate_report()


class ReportGenerator:
    """
    Omnipotent class that manages the report-generation. Assumend to be a singleton.
    """

    @preserve_cwd
    def __init__(self, reportconf_path: str, write_file: bool = True):

        self.write_file = write_file
        self.reportconf_raw = self.load_report_conf(reportconf_path)
        self.mods = self.load_modules()
        self.authors = None
        self.content = None
        self.reportconf = resolve_entities_in_nested_data(self.reportconf_raw)
        self.resolve_entities()

    @staticmethod
    def load_report_conf(reportconf_path: str) -> dict:
        """

        """

        os.chdir(p.aux.startup_workdir)
        try:
            with open(reportconf_path, "rb") as fp:
                conf = tomllib.load(fp)
        except FileNotFoundError:
            raise

        return conf

    def load_modules(self) -> list:

        res = []
        if not (lmdict := self.reportconf_raw.get("load_modules")):
            return res

        assert isinstance(lmdict, dict)

        for prefix, path in lmdict.items():
            if path.startswith("$"):
                path = path[1:].replace("__erk-root__", p.aux.get_erk_root_dir())
            mod = erkloader.load_mod_from_path(path, prefix=prefix)
            res.append(mod)

        return res

    def resolve_entities(self):
        self.authors = self.reportconf.get("authors").values()
        self.content = self.reportconf.get("content")
        assert len(self.authors) > 0
        assert len(self.content) > 0

    def generate_report(self):
        jin_env = Environment(loader=FileSystemLoader(settings.TEMPLATE_PATH))
        template_doc = jin_env.get_template('report-template.tex')

        # WIP!
        affiliations = []
        af_counter = 1
        for at in self.authors:

            af_list = at.get("affiliation", [])
            if not isinstance(af_list, list):
                assert isinstance(af_list, p.Entity)
                af_list = [af_list]

            for af in af_list:
                affiliations.append((af_counter, af.R1))
                af_counter += 1

        authors = [f"{a['item'].R1} ({a['item'].short_key})" for a in self.authors]

        context = {
            "date": datetime.datetime.today().strftime(r"%Y-%m-%d"),
            "authors": authors,
            "content": self.content,
            "nodes": 10,
            "edges": 22,
        }
        res = template_doc.render(c=context)

        if self.write_file:
            fname = "report.tex"
            with open(fname, "w") as resfile:
                resfile.write(res)
            print(os.path.abspath(fname), "written.")

        return res


# this is a function to be easier testable
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
