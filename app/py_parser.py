#/usr/bin/env python3

import ast
from typing import Optional

from docs_parser import Parser


class PythonParser(Parser):
    @property
    def target_file_extensions(self):
        # targeting python files
        return [".py"]


    def parse_file(self, full_path: str) -> dict:
        """parses specified python file for signatures and docstrings of classes and functions

        Parameters
        ----------
        full_path: str
                   absolute path to target file

        Returns
        -------
        dict
            signatures and docstrings of parsed functions and classes
        """
        with open(full_path, "r") as f:
            source = f.read()

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {"functions": [], "classes": []}

        functions = []
        classes = []

        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                signature, decorators = self.__get_signature_and_decorators(source, node)

                sig = {
                    "name": node.name,
                    "lineno_start": node.lineno,
                    "lineno_end": node.end_lineno,
                    "args": [arg.arg for arg in node.args.args],
                    "type_hints": ast.unparse(node.args) if hasattr(ast, "unparse") else None,
                    "decorators": decorators,
                    "signature": signature,
                    "docstring": ast.get_docstring(node)
                }
                functions.append(sig)

            elif isinstance(node, ast.ClassDef):
                bases = [ast.unparse(base) if hasattr(ast, "unparse") else getattr(base, "id", str(base)) for base in node.bases]

                signature, decorators = self.__get_signature_and_decorators(source, node)

                class_info = {
                    "name": node.name,
                    "lineno_start": node.lineno,
                    "lineno_end": node.end_lineno,
                    "bases": bases,
                    "decorators": decorators,
                    "signature": signature,
                    "docstring": ast.get_docstring(node),
                    "methods": []
                }

                for child in node.body:
                    if isinstance(child, ast.FunctionDef):
                        method_signature, method_decorators = self.__get_signature_and_decorators(source, child)
                        method_info = {
                            "name": child.name,
                            "lineno_start": child.lineno,
                            "lineno_end": child.end_lineno,
                            "args": [arg.arg for arg in child.args.args],
                            "type_hints": ast.unparse(child.args) if hasattr(ast, "unparse") else None,
                            "decorators": method_decorators,
                            "signature": method_signature,
                            "docstring": ast.get_docstring(child)
                        }
                        class_info["methods"].append(method_info)

                classes.append(class_info)

        return {"functions": functions, "classes": classes}


    def __get_signature_and_decorators(self, source, node):
        """docs_exclude"""
        # get full signature as written in the code
        code_segment = ast.get_source_segment(source, node)
        signature_lines = []

        for line in code_segment.splitlines():
            line_wo_comment = line.split("#", 1)[0].rstrip() # remove inline comments
            signature_lines.append(line)
            if line_wo_comment.endswith(":"):
                break  # end of signature

        signature = '\n'.join(signature_lines)

        decorators = []
        for dec in node.decorator_list:
            try:
                decorators.append("@" + ast.unparse(dec).strip())
            except Exception:
                decorators.append("<unparseable decorator>")

        full_signature = '\n'.join(decorators + [signature])

        return full_signature, decorators


    def make_docs(self):
        """parses python files for function and class signatures and docstrings and generates AsciiDoc documentation from them

        add keyword 'docs_exclude' to each docstring of each function / method or class you want to exclude from the documentation output
        """
        combined_ast = self.get_combined_ast()

        dir_tree_str = self.make_dir_tree(combined_ast)
        list_of_files = self.combined_ast_to_list_of_files(combined_ast)

        if self.args.output == None:
            print(dir_tree_str)
        else:
            data = {
                "dir_tree": dir_tree_str,
                "list_of_files": list_of_files
            }
            self.render_file_template(self.args.template_dir, self.args.template, data)


    def create_arg_parser(self):
        parser = super().create_arg_parser()
        parser.set_defaults(template="python.adoc")
        return parser


    def combined_ast_to_list_of_files(self, combined_ast: dict, flattened: Optional[list]=None) -> list:
        """recursively converts combined abstract syntaxt tree to flattened list of files

        Parameters
        ----------
        node:      dict
                   (part of) combined abstract syntax tree to process
        flattened: list, optional
                   holds new contents already assembled by previous recursion steps

        Returns
        -------
        list
            flattened list of files
        """
        if flattened is None:
            flattened = []

        unpacked = list(combined_ast.values())[0]
        basename = list(combined_ast.keys())[0]

        if unpacked["type"] == "file":
            file = {"basename": basename}
            file.update(unpacked)
            file.update(unpacked["contents"])
            del file["contents"]

            for k in ["functions", "classes"]:
                for elem in file[k][:]:
                    # iterate over copy of list to avoid skipping elements when removing one
                    if elem["docstring"] != None and self.matches_any_regex(elem["docstring"], ["docs_exclude"]):
                        file[k].remove(elem)

                    if self.matches_any_regex(elem["name"], ["^__\\w+__$"]):
                        # excape double underscore for AsciiDoc
                        elem["name"] = f"\\\\{elem['name']}"

                    if k == "classes":
                        for method in elem["methods"][:]:
                            # iterate over copy of list to avoid skipping elements when removing one
                            if method["docstring"] != None and self.matches_any_regex(method["docstring"], ["docs_exclude"]):
                                elem["methods"].remove(method)

                            if self.matches_any_regex(method["name"], ["^__\\w+__$"]):
                                # excape double underscore for AsciiDoc
                                method["name"] = f"\\\\{method['name']}"

            flattened.append(file)

        if unpacked["type"] == "directory":
            children = unpacked["contents"].keys()
            for c in children:
                self.combined_ast_to_list_of_files({c: unpacked["contents"][c]}, flattened)

        return flattened


if __name__ == "__main__":
    python_parser = PythonParser()
    python_parser.make_docs()
    print("Done.")
