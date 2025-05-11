#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import Optional
import argparse
import os

from helpers import misc, render, dir_tree


class Parser(ABC):
    def __init__(self):
        """docs_exclude"""
        # enforce list of str type in target_file_extensions
        ext = self.target_file_extensions
        if not isinstance(ext, list) or not all(isinstance(e, str) for e in ext):
            raise TypeError("target_file_extensions must be a list of str")

        # argparse init
        self.args = self.create_arg_parser().parse_args()


    @property
    @abstractmethod
    def target_file_extensions(self):
        """subclasses must specify list of file extensions they can parse"""
        pass


    @abstractmethod
    def parse_file(self, full_path):
        """subclasses must implement parse_file method to parse a targeted file"""
        pass


    @abstractmethod
    def make_docs(self):
        """subclasses must implement make_docs method with all steps required to generate AsciiDoc output"""
        pass


    def create_arg_parser(self):
        parser = argparse.ArgumentParser(description="Generate AsciiDoc documentation from source code")

        search_opts = parser.add_argument_group('Source Collection Options')
        search_opts.add_argument("search_dir", help="root directory for recursive search of targeted files")
        search_opts.add_argument("-e", "--exclude", nargs="*", default=None, help="[regex] exclude matching files and directories from search")
        search_opts.add_argument("--max-depth", type=int, default=None, help="max search depth (num of directories)")

        adoc_opts = parser.add_argument_group('AsciiDoc Options')
        adoc_opts.add_argument("-o", "--output", default=None, help="path/to/output.adoc")
        adoc_opts.add_argument("--template-dir", default="templates", help="path of jinja2 template(s)")
        adoc_opts.add_argument("--template", default=None, help="filename of main jinja2 template")
        adoc_opts.add_argument("-i", "--include", nargs="*", default=None, help="[regex] include only matching files and directories in generated output")
        adoc_opts.add_argument("--adoc-links", action="store_true", help="dir_tree: render relative links instead of bare filenames")
        adoc_opts.add_argument("--adoc-anchors", action="store_true", help="dir_tree: add link to anchor of details section for each included file")

        return parser


    def get_combined_ast(self):
        """gets combined abstract syntax tree including directory structure for all found files"""
        root_path = os.path.abspath(self.args.search_dir)
        root_path_basename = os.path.basename(self.args.search_dir)

        exclude_filters = self.args.exclude if self.args.exclude != None else []
        max_depth = self.args.max_depth

        result = {
            f"{root_path_basename}": {
                    "type": "directory",
                    "rel_path": ".",
                    "contents": self.__scan_directory(root_path, root_path, exclude_filters, max_depth)
                }
            }

        result_pruned = self.__prune_ast(result)
        result_w_idx = self.__add_file_idx(result_pruned)

        return result_w_idx


    def __scan_directory(self, base_path: str, root_path: str, exclude_filters: Optional[list[str]]=None, max_depth: Optional[int]=None, current_depth: int=0):
        """recursively scans directory and assembles combined abstract syntax tree with dir_structure and file contents; docs_exclude

        Parameters
        ----------
        base_path:       str
                         base path of current recursion step
        root_path:       str
                         root_path of search
        exclude_filters: list of str, optional
                         list of exclude filters (regex) to exclude files/paths from search
        max_depth:       int, optional
                         maximum recursion depth
        current_depth:   int, default=0
                         used to track current depth during recursion

        Returns
        -------
        dict
            contents of currently parsed node (dir or file)
        """
        if max_depth is not None and current_depth > max_depth:
            return {}

        result = {}
        try:
            entries = os.listdir(base_path)
        except PermissionError:
            return {}

        for entry in entries:
            full_path = os.path.join(base_path, entry)
            rel_path = os.path.relpath(full_path, root_path)
            basename = os.path.basename(full_path)

            if self.matches_any_regex(rel_path, exclude_filters):
                continue

            if os.path.isdir(full_path):
                result[basename] = {
                    "type": "directory",
                    "rel_path": rel_path,
                    "contents": self.__scan_directory(full_path, root_path, exclude_filters, max_depth, current_depth + 1)
                }
            else:
                for ext in self.target_file_extensions:
                    if entry.endswith(ext):
                        result[basename] = {
                            "type": "file",
                            "rel_path": rel_path,
                            "contents": self.parse_file(full_path)
                        }

        return result


    def __prune_ast(self, combined_ast: dict) -> dict | None:
        """docs_exclude"""
        return dir_tree.prune_ast(combined_ast, self.args.include)


    def __add_file_idx(self, combined_ast: dict) -> dict:
        """docs_exclude"""
        return dir_tree.add_file_idx(combined_ast)


    def render_file_template(self, template_dir: str, template: str, data: dict) -> None:
        render.render_file_template(template_dir, template, data, self.args.output)


    def make_dir_tree(self, combined_ast: dict) -> str:
        return dir_tree.make_dir_tree(combined_ast, adoc_links=self.args.adoc_links, adoc_anchors=self.args.adoc_anchors)


# attach helper functions so they can be used by subclasses
Parser.matches_any_regex = staticmethod(misc.matches_any_regex)
