from ruamel.yaml import YAML, yaml_object

yaml = YAML()


@yaml_object(yaml)
class Section:
    yaml_tag = u"!section"

    def __init__(self, name, alignment, spacing="double"):
        self.name = name
        self.alignment = alignment
        self.spacing = spacing

    @classmethod
    def to_yaml(cls, representer, node):
        return representer.represent_scalar(
            cls.yaml_tag, u"{.name}~{.alignment}~{.spacing}".format(node, node, node)
        )

    @classmethod
    def from_yaml(cls, constructor, node):
        return cls(*node.value.split("~"))


@yaml_object(yaml)
class Subsection:
    yaml_tag = u"!subsection"

    def __init__(self, name):
        self.name = name

    @classmethod
    def to_yaml(cls, representer, node):
        return representer.represent_scalar(cls.yaml_tag, u"{.name}".format(node))

    @classmethod
    def from_yaml(cls, constructor, node):
        return cls(node.value)


class ReadMeStyle(object):
    def __init__(
        self,
        header,
        header_alignment,
        subheader,
        line_buffer,
        line_length,
        line_div_char,
        line_div_percent,
        line_div_alignment,
        line_start_char,
        line_end_char,
        section_pre,
        section_post,
        section_alignment,
        subsection_pre,
        subsection_post,
        subsection_alignment,
        credits_primary_thx,
        credits_secondary_thx,
        credits_additional_thx,
        credits_team_thx,
        credits_pre,
        credits_post,
        credits_offset,
        footer,
        footer_alignment,
        subfooter,
        contact_us,
    ):
        self.header = header
        self.header_alignment = header_alignment
        self.subheader = subheader
        self.line_buffer = line_buffer
        self.line_length = line_length
        self.line_div_char = line_div_char
        self.line_div_percent = line_div_percent
        self.line_div_alignment = line_div_alignment
        self.line_start_char = line_start_char
        self.line_end_char = line_end_char
        self.section_pre = section_pre
        self.section_post = section_post
        self.section_alignment = section_alignment
        self.subsection_pre = subsection_pre
        self.subsection_post = subsection_post
        self.subsection_alignment = subsection_alignment
        self.credits_primary_thx = credits_primary_thx
        self.credits_secondary_thx = credits_secondary_thx
        self.credits_additional_thx = credits_additional_thx
        self.credits_team_thx = credits_team_thx
        self.credits_pre = credits_pre
        self.credits_post = credits_post
        self.credits_offset = credits_offset
        self.footer = footer
        self.footer_alignment = footer_alignment
        self.subfooter = subfooter
        self.contact_us = contact_us


yaml.register_class(ReadMeStyle)
