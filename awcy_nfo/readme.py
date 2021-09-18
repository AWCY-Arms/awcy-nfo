import io
import shutil
import logging
import pkgutil

from enum import Enum
from errno import ENOENT
from datetime import datetime
from pathlib import PurePath, Path
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .helpers import ProcLogFileFormatter, temp_filename
from .serializable import yaml, ReadMeStyle, Section, Subsection

app_name = "AWCY?NFO"  # stylized display name
def_style = "classic.yaml"  # default fallback style

# when imported as a module: default null handler
logger = logging.getLogger(__package__)
logger.addHandler(logging.NullHandler())


class LineType(Enum):
    TEXT = 1
    SPACER = 2
    DIVIDER = 3
    SECTION = 4
    SUBSECTION = 5


class ReadMe(object):
    def __init__(
        self,
        yamlfile,
        output=None,
        filename=None,
        header=None,
        style=None,
        log_to_file=False,
        log_verbosity=logging.INFO,
    ):
        self._yamlfile = self.clean_str(yamlfile)
        self._output = self.clean_str(output)
        self._filename = self.check_ext(self.clean_str(filename), ".txt")
        self._header = self.clean_str(header)
        self._style = self.clean_str(style)
        self.log_to_file = log_to_file
        self.log_verbosity = log_verbosity
        self.doc_lines = []
        self.comp_sects = []
        self.init_lc_col = 0
        self.used_lc_col = 0
        self.curr_lc_col = 0
        self.undent_count = 0
        self.indent_count = 0
        self.indent_is_init = False

    @property
    def yamlfile(self):
        return self._yamlfile

    @property
    def output(self):
        return self._output

    @property
    def filename(self):
        return self._filename

    @property
    def header(self):
        return self._header

    @property
    def style(self):
        return self._style

    @property
    def log_to_file(self):
        return self._log_to_file

    @log_to_file.setter
    def log_to_file(self, val):
        self._log_to_file = val

    @property
    def log_verbosity(self):
        return self._log_verbosity

    @log_verbosity.setter
    def log_verbosity(self, val):
        self._log_verbosity = val

    @property
    def doc_lines(self):
        return self._doc_lines

    @doc_lines.setter
    def doc_lines(self, val):
        self._doc_lines = val

    @staticmethod
    def check_ext(file, ext):
        if file is not None:
            if PurePath(file).suffix != ext:
                return file + ext
        return file

    @staticmethod
    def check_req(req, msg):
        # verify a required section or attribute exists
        if req is None:
            raise KeyError(msg)
        return req

    @staticmethod
    def abs_path(ppath):
        # get absolute path of a purepath
        if ppath.is_absolute:
            return Path(ppath)
        else:
            return Path(ppath).resolve()

    @staticmethod
    def clean_str(dirty):
        # strip/clean strings (attempt to manage data entry errors)
        if dirty is None:
            return None
        if isinstance(dirty, str):
            if len(dirty.strip()) > 0:
                return "".join(dirty.strip())
        else:
            return dirty
        return None

    @staticmethod
    def split_keep(s, d):
        # string to list conversion including delimiters
        if not s:
            return [""]  # same as string.split()
        # get highest available char +1 not used in the string
        # this will fail if ord(max(s)) = 0x10FFFF (ValueError)
        p = chr(ord(max(s)) + 1)
        return s.replace(d, d + p).split(p)

    @staticmethod
    def calc_percent(pct, tot):
        return int((pct * tot) / 100.0)

    @staticmethod
    def check_version(version):
        if version is not None:
            if not isinstance(version, str):
                version = str(version)
            if not version.startswith("v"):
                version = f"v{version}"
            return version

    @staticmethod
    def get_template_attr(yaml, attr):
        cattr = ReadMe.clean_str(attr)
        return ReadMe.clean_str(yaml.get(cattr))

    @staticmethod
    def get_style_attr(yaml, attr):
        cattr = ReadMe.clean_str(attr)
        return ReadMe.clean_str(getattr(yaml, cattr, None))

    @staticmethod
    def get_default_attr(yaml, attr):
        cattr = ReadMe.clean_str(attr)
        return ReadMe.clean_str(getattr(yaml, cattr, None))

    @staticmethod
    def get_fallback_attr(style_yaml, default_yaml, attr):
        # try to get attr from style doc, else fallback to default
        sval = ReadMe.get_style_attr(style_yaml, attr)
        if sval is None:
            sval = ReadMe.get_default_attr(default_yaml, attr)
            logger.warning("Using fallback value '%s' for '%s'." % (sval, attr))
            # assign fallback value to the template value, no need to repeat
            # this warning each time the attribute is accessed from now on.
            setattr(style_yaml, ReadMe.clean_str(attr), sval)
        return sval

    @staticmethod
    def get_resource_data(group, file):
        # load resource file as byte stream
        try:
            d = pkgutil.get_data(__name__, f"{group}/{file}")
            return d
        except Exception:
            logger.error("Invalid resource file: %s/%s" % (group, file))
            return None

    @staticmethod
    def get_section_key(yaml, name):
        # get 'Section' key object for requested section name.
        # used to get section content and layout alignment/spacing.
        for k, v in yaml.items():
            if isinstance(k, Section):
                if k.name == name:
                    return k

    @staticmethod
    def get_yaml_mapping(list, key):
        # get clean value for non 'Section' yaml mappings
        for d in list:
            if d.get(key) is not None:
                return ReadMe.clean_str(d.get(key))

    @staticmethod
    def make_div(style_yaml, default_yaml):
        ll = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_length")
        strt = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_start_char")
        stop = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_end_char")
        chr = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_div_char")
        pct = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_div_percent")
        alg = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_div_alignment")
        ll = ll - len(strt) - len(stop)
        fl = ReadMe.calc_percent(ll, pct)
        div = "".join([char * fl for char in chr])
        if alg == "right":
            return [strt, div.rjust(ll), stop, "\n"]
        elif alg == "left":
            return [strt, div.ljust(ll), stop, "\n"]
        elif alg == "center":
            return [strt, div.center(ll), stop, "\n"]

    @staticmethod
    def make_spacer(style_yaml, default_yaml):
        ll = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_length")
        strt = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_start_char")
        stop = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_end_char")
        fl = int(ll - len(strt) - len(stop))
        spc = "".join([char * fl for char in " "])
        return [strt, spc, stop, "\n"]

    @staticmethod
    def make_text(
        style_yaml,
        default_yaml,
        text=None,
        align=None,
        delimiter=" ",
        indent=0,
        sec_indent=0,
        ll_offset=0,  # offset for non standard typefaces (see primary credits)
    ):
        if text:
            lb = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_buffer")
            ll = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_length")
            strt = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_start_char")
            stop = ReadMe.get_fallback_attr(style_yaml, default_yaml, "line_end_char")
            # calc max length of a line
            ml = ll - (len(strt) + len(stop) + int(lb) + int(lb) + indent + ll_offset)
            if len(text) > ml:
                lines = []
                # split text to list w/delimiters and spaces
                sk = ReadMe.split_keep(text, delimiter)
                # iterate each string and calculate running length for slice
                total = 0
                start = 0
                index = 0
                for i, v in enumerate(sk):
                    total += len(v)
                    if total > ml:
                        s = "".join(sk[start : index + 1]).lstrip()
                        if align == "center":
                            lines.extend(ReadMe.center_text(s, ml, lb, strt, stop))
                        if align == "left":
                            if start == 0:
                                lines.extend(
                                    ReadMe.left_text(s, ml, lb, strt, stop, indent)
                                )
                            else:  # include secondary indent (not the first line)
                                lines.extend(
                                    ReadMe.left_text(
                                        s, ml, lb, strt, stop, indent, sec_indent
                                    )
                                )
                        # adjust max length with secondary indent for remaining lines
                        if start == 0:
                            ml -= sec_indent
                        # update start index, count index, reset total char count
                        start = i
                        index = i
                        total = len(v)
                    else:
                        index = i
                # use any remaining totals on loop completion
                if total > 0:
                    s = "".join(sk[start : index + 1]).lstrip()
                    if align == "center":
                        lines.extend(ReadMe.center_text(s, ml, lb, strt, stop))
                    if align == "left":
                        lines.extend(
                            ReadMe.left_text(s, ml, lb, strt, stop, indent, sec_indent)
                        )
                # return properly sized and aligned lines
                return lines
            else:
                if align == "center":
                    return ReadMe.center_text(text, ml, lb, strt, stop)
                elif align == "left":
                    return ReadMe.left_text(text, ml, lb, strt, stop, indent)

    @staticmethod
    def left_text(text, maxlen, edgbuf, startchr, stopchr, indent=0, sec_indent=0):
        if indent < 0:
            logger.warning("Using a negative indent value: %s" % (indent))
        return [
            startchr
            + f'{"": ^{edgbuf + indent + sec_indent}}'
            + f"{text: <{maxlen}}"
            + f'{"": ^{edgbuf}}'
            + stopchr
            + "\n"
        ]

    @staticmethod
    def center_text(text, maxlen, edgbuf, startchr, stopchr):
        return [
            startchr
            + f'{"": ^{edgbuf}}'
            + f"{text: ^{maxlen}}"
            + f'{"": ^{edgbuf}}'
            + stopchr
            + "\n"
        ]

    @staticmethod
    def make_section(style_yaml, default_yaml, text=None):
        if text:
            lst = ReadMe.make_div(style_yaml, default_yaml)
            pr = ReadMe.get_fallback_attr(style_yaml, default_yaml, "section_pre")
            ps = ReadMe.get_fallback_attr(style_yaml, default_yaml, "section_post")
            al = ReadMe.get_fallback_attr(style_yaml, default_yaml, "section_alignment")
            nl = len(text)
            if len(pr) > 0:
                nl += 1  # add for the space between pre and title chars
            if len(ps) > 0:
                nl += 1  # same as above but between title and post chars
            txt = pr + f"{text:^{nl}}" + ps
            tl = ReadMe.make_text(style_yaml, default_yaml, text=txt, align=al)
            lst.extend(tl)
            bd = ReadMe.make_div(style_yaml, default_yaml)
            lst.extend(bd)
            return lst

    @staticmethod
    def make_subsection(style_yaml, default_yaml, text=None):
        if text:
            lst = []  # ReadMe.make_spacer(style_yaml, default_yaml)
            pr = ReadMe.get_fallback_attr(style_yaml, default_yaml, "subsection_pre")
            ps = ReadMe.get_fallback_attr(style_yaml, default_yaml, "subsection_post")
            al = ReadMe.get_fallback_attr(
                style_yaml, default_yaml, "subsection_alignment"
            )
            nl = len(text)
            if len(pr) > 0:
                nl += 1  # add for the space between pre and title chars
            if len(ps) > 0:
                nl += 1  # same as above but between title and post chars
            txt = pr + f"{text:^{nl}}" + ps
            tl = ReadMe.make_text(style_yaml, default_yaml, text=txt, align=al)
            lst.extend(tl)
            bd = ReadMe.make_spacer(style_yaml, default_yaml)
            lst.extend(bd)
            return lst

    @staticmethod
    def primary_credits(data, styl, dflt):
        lines = []
        if "primary_thx" in data:
            thx = data["primary_thx"]
            if thx is not None:
                lines.extend(ReadMe.make_spacer(styl, dflt))
                hd = ReadMe.get_fallback_attr(styl, dflt, "credits_primary_thx")
                lines.extend(ReadMe.make_subsection(styl, dflt, text=hd))
                pr = ReadMe.get_fallback_attr(styl, dflt, "credits_pre")
                ps = ReadMe.get_fallback_attr(styl, dflt, "credits_post")
                of = ReadMe.get_fallback_attr(styl, dflt, "credits_offset")
                for t in thx:
                    nl = len(t)
                    if len(pr) > 0:
                        nl += 1  # add for the space between pre and thnx chars
                    if len(ps) > 0:
                        nl += 1  # same as above but between thnx and post chars
                    txt = pr + f"{t:^{nl}}" + ps
                    lines.extend(
                        ReadMe.make_text(
                            styl,
                            dflt,
                            text=txt,
                            align="center",
                            delimiter=" ",
                            indent=0,
                            sec_indent=0,
                            ll_offset=int(of),
                        )
                    )
        return lines

    @staticmethod
    def secondary_credits(data, styl, dflt):
        lines = []
        if "secondary_thx" in data:
            thx = data["secondary_thx"]
            if thx is not None:
                lines.extend(ReadMe.make_spacer(styl, dflt))
                hd = ReadMe.get_fallback_attr(styl, dflt, "credits_secondary_thx")
                lines.extend(ReadMe.make_subsection(styl, dflt, text=hd))
                # add ' and' to the last creditor if needed
                if len(thx) >= 2:
                    i = len(thx) - 1
                    v = thx[i]
                    thx[i] = "and " + v
                # convert to string adding commas
                thxstr = ", ".join(map(str, thx))
                lines.extend(ReadMe.make_text(styl, dflt, thxstr, "center", ","))
        return lines

    @staticmethod
    def additional_thanks(data, styl, dflt):
        lines = []
        lines.extend(ReadMe.make_spacer(styl, dflt))
        hd = ReadMe.get_fallback_attr(styl, dflt, "credits_additional_thx")
        lines.extend(ReadMe.make_subsection(styl, dflt, text=hd))
        if "additional_thx" in data:
            thx = data["additional_thx"]
            if thx is not None:
                thxstr = ", ".join(map(str, thx)) + ", and"  # add ', and' for team thx
                lines.extend(ReadMe.make_text(styl, dflt, thxstr, "center", ","))
                lines.extend(ReadMe.make_spacer(styl, dflt))
        if "team_thx" in data:
            tthx = data["team_thx"]
            if tthx is None:
                tthx = ReadMe.get_fallback_attr(styl, dflt, "credits_team_thx")
        else:
            tthx = ReadMe.get_fallback_attr(styl, dflt, "credits_team_thx")
        lines.extend(ReadMe.make_text(styl, dflt, tthx, "center"))
        lines.extend(ReadMe.make_spacer(styl, dflt))
        return lines

    def write_to_file(self):
        if hasattr(self, "readme_path"):
            if len(self.doc_lines) > 0:
                with open(self.readme_path, "w", encoding="utf-8") as wf:
                    wf.writelines(self.doc_lines)
            else:
                logger.error("Failed readme file creation, no content to write.")

    def make_line(
        self,
        type=None,
        text=None,
        align=None,
        delimiter=" ",
        indent=0,
        sec_indent=0,
        ll_offset=0,
    ):
        r = None
        if type is LineType.TEXT:
            r = self.make_text(
                self._doc_style,
                self._def_style,
                text,
                align,
                delimiter,
                indent,
                sec_indent,
                ll_offset,
            )
        elif type is LineType.SPACER:
            r = self.make_spacer(self._doc_style, self._def_style)
        elif type is LineType.DIVIDER:
            r = self.make_div(self._doc_style, self._def_style)
        elif type is LineType.SECTION:
            r = self.make_section(self._doc_style, self._def_style, text)
        elif type is LineType.SUBSECTION:
            r = self.make_subsection(self._doc_style, self._def_style, text)
        # add valid line results to doc_lines
        if r is not None:
            self.doc_lines.extend(r)

    def make_optionals(self):
        for sk, sc in self._doc_template.items():
            if isinstance(sk, Section):
                if sk.name not in self.comp_sects:
                    if sc is not None:
                        # reset lc_cols, init state, and indent count props
                        self.init_lc_col = 0
                        self.used_lc_col = 0
                        self.curr_lc_col = 0
                        self.undent_count = 0
                        self.indent_count = 0
                        self.indent_is_init = False
                        # make optional section
                        logger.info("=> %s ..." % sk.name)
                        self.make_line(type=LineType.SECTION, text=sk.name)
                        self.make_line(type=LineType.SPACER)
                        self.process_content(sk, sc)
                        if sk.spacing == "single":
                            self.make_line(type=LineType.SPACER)

    def init_indent(self):
        # track indent init per section
        self.indent_is_init = True
        self.init_lc_col = self.curr_lc_col
        self.used_lc_col = self.curr_lc_col

    def calc_indent(self, lc_col):
        # determine line indentation
        if self.indent_is_init == False:
            self.curr_lc_col = lc_col
            return 0
        else:
            if lc_col == self.init_lc_col:
                return 0
            if lc_col == self.used_lc_col:
                return self.indent_count
            if lc_col > self.used_lc_col:
                r = (lc_col - self.used_lc_col) // 2
                self.indent_count += r
            elif lc_col < self.used_lc_col:
                r = (self.used_lc_col - lc_col) // 2
                self.indent_count -= r
            self.curr_lc_col = lc_col
            idnt = self.indent_count * 2
            udnt = self.undent_count * 2
            return idnt - udnt

    def process_content(self, sect, cont, indent=-1, sec_indent=0):
        logger.debug("sect: %s" % (sect))
        logger.debug("cont: %s" % (cont))
        logger.debug("indent: %s" % (indent))
        logger.debug("sec_indent: %s" % (sec_indent))

        if isinstance(cont, str):
            logger.debug("(String Instance)")
            ls = cont.split("\n")
            for i, l in enumerate(ls):
                if len(l) == 0:
                    # do not add spacer for last element (textblocks)
                    if i != len(ls) - 1:
                        self.make_line(type=LineType.SPACER)
                else:
                    # handle negative indent (textblocks)
                    if indent == -1:
                        indent = 0
                    # bake bread...
                    self.make_line(
                        type=LineType.TEXT,
                        text=l,
                        align=sect.alignment,
                        delimiter=" ",
                        indent=indent,
                        sec_indent=sec_indent,
                    )
                    if sect.spacing == "double":
                        self.make_line(type=LineType.SPACER)
                    # set indent_init flag true
                    self.init_indent()
        elif isinstance(cont, CommentedMap):
            logger.debug("(CommentedMap Instance)")
            for k, v in cont.items():
                if isinstance(k, Subsection):
                    logger.debug("(Subsection Instance (key))")
                    # no longer used, but left for now, just in case...
                    # self.undent_count += 1  # increment unindent count
                    if self.indent_is_init:
                        self.make_line(type=LineType.SPACER)
                    self.make_line(type=LineType.SUBSECTION, text=k.name)
                else:
                    if indent == -1:
                        ident = self.calc_indent(cont.lc.col - 2)
                    else:
                        ident = indent
                if isinstance(v, str):
                    logger.debug("Process String (value)")
                    self.process_content(
                        sect, str(k) + ": " + v, ident, len(str(k) + ": ")
                    )
                if isinstance(v, CommentedMap):
                    if not isinstance(k, Subsection):
                        logger.debug("Process CommentedMap (value)")
                        self.process_content(
                            sect, str(k) + ": ", ident, len(str(k) + ": ")
                        )
                        self.process_content(sect, v, ident)
                    else:
                        logger.debug("Process Subsection (value)")
                        self.process_content(sect, v)
                if isinstance(v, CommentedSeq):
                    if not isinstance(k, Subsection):
                        logger.debug("Process CommentedSeq (key)")
                        self.process_content(
                            sect, str(k) + ": ", ident, len(str(k) + ": ")
                        )
                        self.process_content(sect, v, ident + 2)  # +2 indent tracking
                    else:
                        logger.debug("Process Subsection (value)")
                        self.process_content(sect, v)
        elif isinstance(cont, CommentedSeq):
            logger.debug("(CommentedSeq Instance)")
            for idx, item in enumerate(cont):
                if indent == -1:
                    ident = self.calc_indent(cont.lc.col - 2)
                else:
                    ident = indent
                if isinstance(item, str):
                    logger.debug("Process String (item)")
                    self.process_content(sect, item, ident)
                if isinstance(item, CommentedMap):
                    logger.debug("Process CommentedMap (item)")
                    self.process_content(sect, item, ident)
                if isinstance(item, CommentedSeq):
                    logger.debug("Process CommentedSeq (item)")
                    self.process_content(sect, item, ident)

    def make_rls_notes(self):
        logger.info("=> Release Notes ...")
        # get required section key and verify it exists
        sk = self.check_req(
            self.get_section_key(self._doc_template, "Release Notes"),
            "Required template section '%s', not found." % "Release Notes",
        )
        # make release notes section head
        self.make_line(type=LineType.SECTION, text=sk.name)
        self.make_line(type=LineType.SPACER)
        # get section content
        sv = self._doc_template.get(sk)
        if sv is not None:
            self.process_content(sk, sv, 0)
            if sk.spacing == "single":
                self.make_line(type=LineType.SPACER)
        else:  # blank release notes
            self.make_line(type=LineType.SPACER)
        # add to completed sections
        self.comp_sects.append(sk.name)

    def make_credits(self):
        logger.info("=> Credits ...")
        # get required section key and verify it exists
        sk = self.check_req(
            self.get_section_key(self._doc_template, "Credits"),
            "Required template section '%s', not found." % "Credits",
        )
        # make credits section head
        self.make_line(type=LineType.SECTION, text=sk.name)
        # get section content
        sv = self._doc_template.get(sk)
        if sv is not None:
            r = ReadMe.primary_credits(sv, self._doc_style, self._def_style)
            if r is not None:
                self.doc_lines.extend(r)
            s = ReadMe.secondary_credits(sv, self._doc_style, self._def_style)
            if s is not None:
                self.doc_lines.extend(s)
            a = ReadMe.additional_thanks(sv, self._doc_style, self._def_style)
            if a is not None:
                self.doc_lines.extend(a)
        else:  # if no credits are set, thank the team and move on
            self.make_line(type=LineType.SPACER)
            tmthx = ReadMe.get_fallback_attr(
                self._doc_style, self._def_style, "credits_team_thx"
            )
            self.make_line(type=LineType.TEXT, text=tmthx, align="center")
            self.make_line(type=LineType.SPACER)
        # add section to completed
        self.comp_sects.append(sk.name)

    def make_about(self):
        logger.info("=> About ...")
        self.make_line(type=LineType.DIVIDER)
        self.make_line(type=LineType.SPACER)
        # get required section key and verify it exists
        sk = self.check_req(
            self.get_section_key(self._doc_template, "About"),
            "Required template section '%s', not found." % "About",
        )
        # get section content
        sv = self._doc_template.get(sk)
        # verify required section attributes exist
        t = self.check_req(
            self.get_yaml_mapping(sv, "title"),
            "Required template attribute '%s', not found." % "title",
        )
        v = self.check_req(
            self.check_version(self.get_yaml_mapping(sv, "version")),
            "Required template attribute '%s', not found." % "version",
        )
        # finally, make lines for available attributes
        self.make_line(type=LineType.TEXT, text=t, align=sk.alignment)
        s = self.get_yaml_mapping(sv, "subtitle")
        self.make_line(type=LineType.TEXT, text=s, align=sk.alignment)
        self.make_line(type=LineType.TEXT, text=v, align=sk.alignment)
        self.make_line(type=LineType.SPACER)
        # add section to completed
        self.comp_sects.append(sk.name)

    def make_footer(self):
        logger.info("=> Footer...")
        self.make_line(type=LineType.DIVIDER)
        self.make_line(type=LineType.SPACER)
        algn = self.get_fallback_attr(
            self._doc_style, self._def_style, "footer_alignment"
        )
        ftr = self.get_fallback_attr(self._doc_style, self._def_style, "footer")
        self.make_line(type=LineType.TEXT, text=ftr, align=algn)
        sub = self.get_fallback_attr(self._doc_style, self._def_style, "subfooter")
        self.make_line(type=LineType.TEXT, text=sub, align=algn)
        join = self.get_fallback_attr(self._doc_style, self._def_style, "contact_us")
        self.make_line(type=LineType.TEXT, text=join, align=algn)
        self.make_line(type=LineType.SPACER)
        self.make_line(type=LineType.DIVIDER)

    def make_header(self):
        hbytes = io.BytesIO(self.load_header())
        halign = self.get_header_alignment()
        lineln = self.get_fallback_attr(self._doc_style, self._def_style, "line_length")
        logger.info("=> Header...")
        # for each line, rstrip (remove \n), then readd the right side block spacing,
        # (restoring original line length), align, add new \n, and append to doc_lines.
        for hbl in hbytes.readlines():
            otxt = hbl.decode(encoding="utf-8")
            olen = len(otxt)
            stxt = otxt.rstrip()
            slen = len(stxt)
            spce = "".join([char * (olen - slen) for char in " "])
            ntxt = "".join([stxt, spce])
            if halign == "right":
                self.doc_lines.extend([ntxt.rjust(lineln), "\n"])
            elif halign == "left":
                self.doc_lines.extend([ntxt.ljust(lineln), "\n"])
            elif halign == "center":
                self.doc_lines.extend([ntxt.center(lineln), "\n"])
        # add subheader block (always centered)
        logger.info("=> Subheader...")
        subhdr = self.get_fallback_attr(self._doc_style, self._def_style, "subheader")
        self.doc_lines.extend(["\n", subhdr.center(lineln), "\n", "\n"])

    def get_header_alignment(self):
        alignments = ["center", "left", "right"]
        ha = self.get_template_attr(self._doc_template, "header_alignment")
        if ha is not None and ha.lower() in alignments:
            logger.info("HeaderAlignment: '%s' (template)" % ha)
            return ha
        ha = self.get_style_attr(self._doc_style, "header_alignment")
        if ha is not None and ha.lower() in alignments:
            logger.info("HeaderAlignment: '%s' (style)" % ha)
            return ha
        ha = self.get_default_attr(self._def_style, "header_alignment").lower()
        if ha in alignments:
            logger.warning("Using fallback value '%s' for 'header_alignment'." % ha)
            logger.info("HeaderAlignment: '%s' (default)" % ha)
            return ha

    def load_header(self):
        hptr = self.load_header_params()
        if hptr is None:
            hptr = self.load_header_template()
        if hptr is None:
            hptr = self.load_header_style()
        if hptr is None:
            hptr = self.load_header_default()
        if hptr is None:
            hdrdflt = self.check_ext(
                self.get_default_attr(self._def_style, "header").lower(), ".txt"
            )
            raise IOError(ENOENT, "Invalid default fallback header '%s'." % hdrdflt)
        return hptr

    def load_header_default(self):
        hdrdflt = self.check_ext(
            self.get_default_attr(self._def_style, "header").lower(), ".txt"
        )
        hptr = self.get_resource_data("headers", hdrdflt)
        if hptr is not None:
            logger.info("Header: '%s' (default)," % hdrdflt)
            return hptr
        return None

    def load_header_style(self):
        headername = self.check_ext(
            self.get_style_attr(self._doc_style, "header"), ".txt"
        )
        if headername is not None:
            headername = headername.lower()
            hptr = self.get_resource_data("headers", headername)
            if hptr is not None:
                logger.info("Header: '%s' (style)" % headername)
                return hptr
            hdrdflt = self.check_ext(
                self.get_default_attr(self._def_style, "header").lower(), ".txt"
            )
            logger.warning(
                "Invalid header style '%s', falling back to default '%s' header."
                % (headername, hdrdflt)
            )
        return None

    def load_header_template(self):
        headername = self.check_ext(
            self.get_template_attr(self._doc_template, "header"), ".txt"
        )
        if headername is not None:
            headername = headername.lower()
            hptr = self.get_resource_data("headers", headername)
            if hptr is not None:
                logger.info("Header: '%s' (template)" % headername)
                return hptr
            logger.warning(
                "Invalid header template '%s', falling back to style header."
                % (headername)
            )
        return None

    def load_header_params(self):
        if self.header is not None:
            hptr = None
            headername = self.check_ext(self.header.lower(), ".txt")
            pp = PurePath(headername)
            if Path(pp).is_file():  # external header file
                hptr = self.abs_path(pp).read_bytes()
            else:  # check if header is a package resource
                hptr = self.get_resource_data("headers", headername)
            if hptr is not None:
                logger.info("Header: '%s' (parameter)" % headername)
                return hptr
            logger.warning(
                "Invalid header parameter '%s', falling back to template header."
                % headername
            )
        return None

    def load_style(self):
        sptr = self.load_style_params()
        if sptr is None:
            sptr = self.load_style_template()
        if sptr is None:
            sptr = self.load_style_default()
        if sptr is None:
            raise IOError(ENOENT, "Invalid default fallback style '%s'." % def_style)
        return yaml.load(sptr)

    def load_style_default(self):
        sptr = self.get_resource_data("styles", def_style)
        if sptr is not None:
            if isinstance(yaml.load(sptr), ReadMeStyle):
                logger.info("Style: '%s' (default)," % def_style)
                return sptr
        return None

    def load_style_template(self):
        stylename = self.check_ext(
            self.get_template_attr(self._doc_template, "style").lower(), ".yaml"
        )
        sptr = self.get_resource_data("styles", stylename)
        if sptr is not None:
            if isinstance(yaml.load(sptr), ReadMeStyle):
                logger.info("Style: '%s' (template)" % stylename)
                return sptr
        logger.warning(
            "Invalid style template '%s', falling back to default '%s' style."
            % (stylename, def_style)
        )
        return None

    def load_style_params(self):
        if self.style is not None:
            sptr = None
            stylename = self.check_ext(self.style.lower(), ".yaml")
            pp = PurePath(stylename)
            if Path(pp).is_file():  # external style file
                sptr = self.abs_path(pp)
            else:  # check if style is a package resource
                sptr = self.get_resource_data("styles", stylename)
            if sptr is not None:
                if isinstance(yaml.load(sptr), ReadMeStyle):
                    logger.info("Style: '%s' (parameter)" % stylename)
                    return sptr
            logger.warning(
                "Invalid style parameter '%s', falling back to template style."
                % stylename
            )
        return None

    def set_yaml_path(self):
        if self.yamlfile is not None:
            yf = self.check_ext(self.yamlfile, ".yaml")
            pp = PurePath(yf)
            if Path(pp).is_file():
                self.yaml_path = self.abs_path(pp)
        else:
            raise IOError(ENOENT, "Missing file", self.yamlfile)
        if self.yaml_path is None:
            raise IOError(ENOENT, "Invalid file", yf)
        else:
            logger.info("Input: '%s'" % self.yaml_path)

    def set_readme_path(self):
        pp = None
        ppy = PurePath(self.yaml_path)
        if self.output is not None:
            ppo = PurePath(self.output)
        if self.filename is not None:
            ppf = PurePath(self.filename)
        # output and filename params
        if self.output is not None and self.filename is not None:
            if Path(ppo).is_file():
                logger.warning("'%s' is a file, using parent directory" % self.output)
                pp = PurePath.joinpath(ppo.parent, ppf)
            else:
                pp = PurePath.joinpath(ppo, ppf)
        # output param only
        elif self.output is not None and self.filename is None:
            if Path(ppo).is_dir():
                pp = PurePath.joinpath(ppo, ppy.stem + ".txt")
            else:
                if ppo.suffix == ".txt":  # if .txt suffix treat as output file
                    pp = PurePath(self.check_ext(self.output, ".txt"))
                else:
                    pp = PurePath.joinpath(ppo, ppy.stem + ".txt")
        # filename param only
        elif self.output is None and self.filename is not None:
            pp = PurePath.joinpath(ppy.parent, ppf)
        # no additional params
        else:
            pp = PurePath.joinpath(ppy.parent, ppy.stem + ".txt")
        # assign and validate output
        self.readme_path = self.abs_path(pp)
        if not self.readme_path.parent.exists():
            Path.mkdir(self.readme_path.parent, parents=True)
        if self.readme_path.exists():
            logger.warning("Existing file '%s' will be overwritten." % self.readme_path)
        logger.info("Output: '%s'" % self.readme_path)

    def start_proclog(self):
        ht = "..:: " + app_name + " LOG ::.."
        hl = (80 - len(ht)) + len(ht)  # 80 chars (terminal width)
        logger.info("".join([char * hl for char in "~"]))
        logger.info(ht.center(hl))
        logger.info("".join([char * hl for char in "~"]))
        logger.info("Created: %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("Parameters: %s" % self.__str__())

    def conf_proclog(self):
        # The output directory and log file name will be the same as the readme file.
        # To determine this, the input parameters: yamlfile, output, and filename, need
        # to be processed. Because this occurs before the log file exists, log to a
        # tempfile. Once known, copy log contents, update log handler and kill tempfile.
        with temp_filename(".log") as tf:
            # create logging filehandler with tempfile
            fhndl = logging.FileHandler(tf)
            fhndl.name = __package__ + "_file"
            fhndl.setLevel(self.log_verbosity)
            fhndl.setFormatter(ProcLogFileFormatter())
            logger.addHandler(fhndl)
            # start process log
            self.start_proclog()
            # process input/output paths
            self.set_yaml_path()
            self.set_readme_path()
            # copy temp log and update handler
            readme_log = self.readme_path.with_suffix(".log")
            fhndl.close()
            shutil.copy2(tf, readme_log)
            fhndl.baseFilename = readme_log

    def create_readme(self):
        try:
            # load default style (for fallbacks)
            self._def_style = yaml.load(self.get_resource_data("styles", def_style))
            # prepare input parameters
            if self.log_to_file:
                self.conf_proclog()
            else:
                self.set_yaml_path()
                self.set_readme_path()
            # load configuration templates
            self._doc_template = yaml.load(self.yaml_path)
            self._doc_style = self.load_style()
            # process readme.txt creation
            self.make_header()
            self.make_about()
            self.make_rls_notes()
            self.make_credits()
            self.make_optionals()
            self.make_footer()
        except Exception as e:
            logger.exception(e)
        finally:
            # write all doc lines to readme.txt file
            self.write_to_file()
            # cleanup any remaining file handler
            for handler in logger.handlers:
                if handler.get_name() == __package__ + "_file":
                    handler.close()

    def __repr__(self):
        return (
            "%s(yamlfile=%r, output=%r, filename=%r, header=%r, style=%r, log=%r)"
            % (
                self.__class__.__name__,
                self.yamlfile,
                self.output,
                self.filename,
                self.header,
                self.style,
                self.log_to_file,
            )
        )

    def __str__(self):
        return "yamlfile=%s, output=%s, filename=%s, header=%s, style=%s, log=%s" % (
            self.yamlfile,
            self.output,
            self.filename,
            self.header,
            self.style,
            self.log_to_file,
        )
