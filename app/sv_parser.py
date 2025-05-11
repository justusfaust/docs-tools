#/usr/bin/env python3

from typing import Optional
import regex

from docs_parser import Parser


class SystemVerilogParser(Parser):
    @property
    def target_file_extensions(self):
        # targeting systemverilog files
        return [".sv"]


    def parse_file(self, full_path: str) -> dict:
        """parses specified systemverilog file for modules and docs_description comments

        Parameters
        ----------
        full_path: str
                   absolute path to target file

        Returns
        -------
        dict
            module definitions and docs_description comments of parsed file
        """
        with open(full_path, "r") as f:
             source = f.read()

        modules_list = []

        # extract global comments containing "docs_description" keyword
        inline_comments = regex.findall(r"(?:\/\/\s*docs_description\s*(.*))", source)
        block_comments = regex.findall(r"(?:\/\*\s*docs_description\s*([^*]+|\*(?!\/))*+\*\/)", source)
        comments = inline_comments + block_comments
        if comments == []:
            comments = None
        else:
            comments = "\n".join(comments)

        # extract all module definitions from file
        modules = regex.findall(r"module[\s\S]*?endmodule", source)

        for module in modules:
            mod_dict = {}

            # extract header section of module
            header = regex.search(r"(module(?:.|\n)*\);)", module).groups()[0]

            # extract name of module
            mod_dict["name"] = regex.search(r"(?:module\s+(\w+))", header).groups()[0]

            # extract param and port declarations
            parenthesized_sections = regex.findall(r"\((?:[^)(]+|(?R))*+\)", header)
            param_declarations = None
            port_declarations = None

            if len(parenthesized_sections) == 1:
                # only port declarations, no params
                port_declarations = parenthesized_sections[0]
            elif len(parenthesized_sections) > 1:
                # param and port declarations
                param_declarations = parenthesized_sections[0]
                port_declarations = parenthesized_sections[1]

            if param_declarations != None:
                param_list = []
                # parse params (name, default_value, comment)
                params = regex.findall(r"(?:\s*parameter\s+)(?:\w+\s+)?(\w+)\s*(?:=\s*(.+?(?=(?:,|\s*\/\/|[\r\n\v]))))?\s*,?[\r\t\f ]*(\/\/.*)?", param_declarations)

                for line in params:
                    param_list.append({
                        "name": line[0],
                        "default_val": line[1] if line[1] else None,
                        "comment": line[2] if line[2] else None
                    })

                mod_dict["params"] = param_list
            else:
                mod_dict["params"] = None

            if port_declarations != None:
                port_list = []
                # parse ports (type, name_and_range, comment)
                ports = regex.findall(r"(?:(input|output|inout)\s+(?:wire|reg|logic)\s+)(.+?(?=(?:,|\s*\/\/|[\r\n\v]))),?\s*(\/\/.*)?", port_declarations)

                for line in ports:
                    # remove port ranges if present to get name
                    name_wo_range = regex.sub(r"\s*\[[^][]*\]\s*", "", line[1])

                    port_list.append({
                        "type": line[0],
                        "name": name_wo_range,
                        "name_and_ranges": line[1],
                        "comment": line[2] if line[2] else None
                    })

                mod_dict["ports"] = port_list
            else:
                mod_dict["ports"] = None

            modules_list.append(mod_dict)

        return {"modules": modules_list, "docs": comments}


    def make_docs(self):
        """parses systemverilog files for modules and docs_description comments and generates AsciiDoc documentation from them

        inline comments or comment blocks starting with keyword 'docs_description' are included in the documentation
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
        parser.set_defaults(template="systemverilog.adoc")
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

            for module in file["modules"]:
                module["instance"] = self.make_instance(module)

            flattened.append(file)

        if unpacked["type"] == "directory":
            children = unpacked["contents"].keys()
            for c in children:
                self.combined_ast_to_list_of_files({c: unpacked["contents"][c]}, flattened)

        return flattened


    def make_instance(self, module: dict) -> str:
        """converts extracted module info to instance template str

        Parameters
        ----------
        module: dict
                module data

        Returns
        -------
        str
            instance template (str) of module
        """
        lines = []

        # if no params and ports (i.e. testbenches) -> "module <name> ();"
        if not module.get("params") and not module.get("ports"):
            return f"module {module['name']} ();"

        # params
        param_lines = []
        if module.get("params"):
            max_name_len = max(len(p["name"]) for p in module["params"])
            default_strings = [f"// = {p['default_val']}" for p in module["params"]]
            max_default_len = max(len(s) for s in default_strings)

            for param in module["params"]:
                name = param["name"]
                default_str = f"// = {param['default_val']}"
                line = f"    .{name.ljust(max_name_len)}()  {default_str.ljust(max_default_len)}"
                if param.get("comment"):
                    line += f"  {param['comment']}"
                param_lines.append(line)

        # ports
        port_lines = []
        if module.get("ports"):
            max_name_len = max(len(p["name"]) for p in module["ports"])
            range_strings = []
            for p in module["ports"]:
                if p.get("name_and_ranges"):
                    range_strings.append(f"// {p['name_and_ranges']}")
                else:
                    range_strings.append("")
            max_range_len = max(len(s) for s in range_strings)

            for port in module["ports"]:
                name = port["name"]
                range_str = f"// {port['name_and_ranges']}" if port.get("name_and_ranges") else ""
                line = f"    .{name.ljust(max_name_len)}()  {range_str.ljust(max_range_len)}"
                if port.get("comment"):
                    line += f"  {port['comment']}"
                port_lines.append(line)

        # combine everything
        if param_lines:
            lines.append(f"{module['name']} (")
            lines.extend(param_lines)
            lines.append(f") i_{module['name']} (")
        else:
            lines.append(f"{module['name']} i_{module['name']} (")

        if port_lines:
            lines.extend(port_lines)
            lines.append(");")
        else:
            lines.append(");")

        return "\n".join(lines)


if __name__ == "__main__":
    systemverilog_parser = SystemVerilogParser()
    systemverilog_parser.make_docs()
    print("Done.")
