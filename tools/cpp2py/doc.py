# This module contains functions to process the documentation
# of classes, functions, from C++ to Python
# make_doc(x) is the general function, where x is a node.

import re
import clang_parser2 as CL
import util

def replace_latex(s, escape_slash=False):
    """replace 
       $XX X$  by :math:`XX X`
       $$X XX$$  by \n\n.. math:\n\t\tX XX\n\n..\n
       [[ XXX]]  by :ref:` XXX`
     
     """
    return s
    any_math_char = 'A-Za-z0-9{}\[\],;|\(\)=./\/+-_^\'' #any math character
    #matches all expressions starting and ending with any math char, with possibly whitespaces in between
    pattern_1 = '\$(['+any_math_char+']['+any_math_char+' ]*['+any_math_char+']+)\$'
    #matches any single math char
    pattern_2 = '\$(['+any_math_char+'])\$'
    #out of line formula
    text=re.sub('\$'+pattern_1+'\$', r'\n\n.. math::\n\t\t\1\n\n..\n', s)
    text=re.sub('\$'+pattern_2+'\$', r'\n\n.. math::\n\t\t\1\n\n..\n', text)
    #inline formula
    text=re.sub(pattern_1, r':math:`\1`', text)
    text=re.sub(pattern_2, r':math:`\1`', text)
    #to create a hyperlink
    text=re.sub('\[\[([A-Za-z0-9{}\(,\)=./\/+-_]+)\]\]', r':ref:`\1`', text)

    if escape_slash: text=text.encode('string_escape')
    return text

def make_table(head_list, list_of_list):
    """
    :param head_list: list of strings with table headers
    :param list_of_list: list of list of strings
    :returns: a valid rst table
    """
    l = len (head_list)
    lcols = [len(x) for x in head_list]
    for li in list_of_list : # compute the max length of the columns
        lcols = [ max(len(x), y) for x,y in zip(li, lcols)]
    form =  '| ' + " | ".join("{:<%s}"%x for x in lcols).strip() + ' |'
    header= form.format(*head_list)
    w = len(header)
    sep = '+' + '+'.join((x+2) *'-' for x in lcols) + '+'
    sep1 = sep.replace('-','=')
    r = [sep, header, sep1]
    for li in list_of_list: r += [form.format(*li), sep] 
    return '\n'.join(r)

def replace_cpp_keywords_by_py_keywords(s):
    """replace syntax 
       @param XXX blabla 
       by
       :param XXX: blabla
    """
    s=re.sub('@param ([A-Za-z0-9_]*) ',r':param \1: ', s)
    return s

def doc_format_param(member_list):
   h = ['Parameter Name','Type','Default', 'Documentation']
   l = [(m.name, m.ctype, m.initializer if m.initializer else '', replace_latex(m.doc)) for m in member_list]
   return make_table(h, l)

   
def make_doc(node):
    """ process doc of node"""
   
    doc = node.raw_comment
    if not doc : return ""
    for p in ["/\*","\*/","^\s*\*", "///", "//", r"\\brief"] : 
        doc = re.sub(p,"",doc,flags = re.MULTILINE)
    doc = doc.strip()
    doc = replace_latex(doc, True)

    if util.use_parameter_class(node):
        doc = doc + '\n' + doc_format_param(CL.get_members(util.get_decl_param_class(f)))
    
    return replace_cpp_keywords_by_py_keywords(doc)
    
