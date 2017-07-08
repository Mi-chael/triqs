# This module defines the function parse that
# call libclang to parse a C++ file, and retrieve
# A few helper functions for libclang
import sys,re,os
import clang.cindex
import itertools
from mako.template import Template
from clang.cindex import CursorKind

def pretty_print(x, keep= None, s='...') : 
   print x
   for y in x.get_children():
        if keep and not keep(y) : continue 
        print s, y.spelling
        print s, y.kind
        print s, [z.spelling for z in y.get_tokens()]
        pretty_print(y, keep, s + '...')

def get_annotations(node):
    return [c.displayname for c in node.get_children() if c.kind == CursorKind.ANNOTATE_ATTR]

def get_tokens(node): 
    return [t.spelling for t in node.get_tokens()]

def get_type_alias_value(node) : 
    """ node is a using, get the rhs"""
    return list(node.get_tokens())[3].spelling

def extract_bracketed(tokens):
    r = []
    bracket_count = 0
    for t in tokens:
        if t == '<': bracket_count += 1
        else: bracket_count -= len(t) - len(t.lstrip('>'))
        r.append(t)
        if bracket_count == 0: return r

def is_deprecated(node):
    """Check if the node is deprecated"""
    tokens = get_tokens(node)
    return len(tokens)>3 and tokens[0] =='__attribute__' and tokens[3] =='deprecated'

def is_public(node): 
    return node.access_specifier == clang.cindex.AccessSpecifier.PUBLIC 

def jump_to_declaration(node):
    """
    Precondition : node is a parameter of a function/method, or a base class
    Return : a cursor on its declaration
    """
    tt = node.get_declaration()  # guess it is not a ref
    if not tt.location.file : tt = node.get_pointee().get_declaration() # it is a T &
    return tt

def keep_all(x) : return True

#--------------------  function related ---------------------------------------------------------

def is_explicit(node) : # for a constructor
    return 'explicit' in get_tokens(node)
   
def is_noexcept(node): 
    return 'noexcept' in get_tokens(node)[-2:]

def get_method_qualification(node): 
    """
    Detects from the tokens the trailing const, const &, &, &&, etc ...
    It is just after a ) if it exists (a type can not end with a ) )
    """
    s = ' '.join(get_tokens(node))
    for pat in ["const &*","&+", "noexcept"] :
        m = re.search(r"\) (%s)"%pat, s)
        if m: return m.group(1).strip()
    return ''

def get_template_params(node):
    """
    Precondition : node is a function/method
    returns a list of (typename, name, default) or (Type, name)
    returns [] is not a template
    """
    tparams = []
    def get_default(c) : 
        tokens = get_tokens(c)
        return ''.join(tokens[tokens.index('=') + 1:-1]) if '=' in tokens else None
          
    for c in node.get_children():
        if c.kind == CursorKind.TEMPLATE_TYPE_PARAMETER :
            tparams.append(("typename", c.spelling, get_default(c)))
        elif c.kind == CursorKind.TEMPLATE_NON_TYPE_PARAMETER:
            tparams.append((list(c.get_tokens())[0].spelling, c.spelling, get_default(c)))
    return tparams

def is_template(node) : 
    return len(get_template_params(node))>0 # optimize ?

def get_params(node):
    """
    Precondition : node is a function/method
    Yields the node of the parameters of the function
    """
    for c in node.get_children():
        if c.kind == CursorKind.PARM_DECL : 
            yield c

def get_param_default_value(node):
    """
    Precondition : node is a parameter of a function/method
    returns a list of (typename, name, default) or (Type, name, 
    """
    default_value = None
    for ch in node.get_children() :
        if ch.kind in [CursorKind.INTEGER_LITERAL, CursorKind.FLOATING_LITERAL,
                       CursorKind.CHARACTER_LITERAL, CursorKind.STRING_LITERAL,
                       CursorKind.UNARY_OPERATOR, CursorKind.UNEXPOSED_EXPR,
                       CursorKind.CXX_BOOL_LITERAL_EXPR, CursorKind.CALL_EXPR ] :
            default_value =  ''.join([x.spelling for x in ch.get_tokens()]) 
    return default_value

#--------------------  class components ---------------------------------------------------------

def get_name_with_template_specialization(node):
    """
    node is a class
    returns the name, possibly added with the <..> of the specialisation
    """
    assert node.kind in (CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION)
    tokens = get_tokens(node)
    name = node.spelling
    if tokens and tokens[0] == 'template':
       t = tokens[len(extract_bracketed(tokens[1:]))+3:]
       if t and t[0] == '<': name = name + ''.join(extract_bracketed(t))
    return name

def get_base_classes(node, keep = keep_all): 
    """
    node is a class
    yields the nodes to the public base class.
    """
    for c in node.get_children():
        if c.kind == CursorKind.CXX_BASE_SPECIFIER and keep(c): 
                yield jump_to_declaration(c)

def get_members(node, with_inherited, keep = keep_all): 
    """
    node is a class
    yields the nodes to the public members
    if with_inherited, yields the nodes to the members AND the members of the public base classes
    """
    for b in get_base_classes(node):
        for m in get_members(b, with_inherited, keep):
            yield m
    
    for c in node.get_children():
       if c.kind == CursorKind.FIELD_DECL and keep(c): 
            yield c

def get_member_initializer(node):
    """node is a field_decl, i.e. a member in a class. Gets the rhs of the = or None"""
    tokens = get_tokens(node)
    if '=' in tokens:
        end_idx = tokens.index(';') if ';' in tokens else len(tokens)
        return ''.join(tokens[tokens.index('=') + 1:end_idx])

def is_constructor(cls, m):
    """ is m a constructor of cls"""
    return m.kind == CursorKind.CONSTRUCTOR or \
          (m.kind == CursorKind.FUNCTION_TEMPLATE and cls.spelling == m.spelling.split('<')[0])

def get_methods(node, with_inherited = True, keep = keep_all): 
    """
    node is a class
    yields the nodes to the members
    if with_inherited : also the inherited methods
    """
    for b in get_base_classes(node):
        for m in get_methods(b, with_inherited, keep):
            yield m

    for c in node.get_children():
        ok = c.kind == CursorKind.CXX_METHOD or (c.kind == CursorKind.FUNCTION_TEMPLATE and not is_constructor(node, c))
        if ok and keep(c):
           yield c

def get_constructors(node, keep = keep_all): 
    """
    node is a class
    yields the nodes to the constructors 
    """
    for c in node.get_children():
        if keep(c) and c.kind == CursorKind.CONSTRUCTOR or \
                (c.kind == CursorKind.FUNCTION_TEMPLATE and is_constructor(node, c)):
            yield c

def get_usings(node, keep = keep_all): 
    """
    node is a class
    yields the nodes to the usings 
    """
    for c in node.get_children():
        if c.kind == CursorKind.TYPE_ALIAS_DECL and keep(c): 
            yield c

def get_friend_functions(node, keep = keep_all): 
    """
    node is a class
    yields the nodes to the friend functions 
    """
    for c in node.get_children():
        if c.kind == CursorKind.FRIEND_DECL and keep(c): 
            yield c.get_children().next()

#--------------------  print -----------------------------------

def make_signature_template_params(tparams):
    return "template<" + ', '.join(["%s %s = %s"%x if x[2] else "%s %s"%x[:2] for x in tparams]) + ">  " if tparams else ''

def print_fnt(f):
    s = "{name} ({args})" if is_constructor(f) else "{rtype} {name} ({args})"
    s = s.format(args = ', '.join( ["%s %s"%(t.name,n) + ("=%s"%d if d else "") for t,n,d in get_params(f)]), **self.__dict__)
    s= make_signature_template_params(get_template_params(f)) + s
    if f.is_static_method() : s = "static " + s
    return "%s\n%s\n"%(s.strip(), f.raw_comment)

def print_cls(c):
    s,s2 = "class {name}:\n  {doc}\n\n"%c.spelling,[]
    for m in get_members(c):
        s2 += ["%s %s"%(m.ctype,m.name)]
    for m in get_methods(c) :
       s2 += print_fnt(m).split('\n')
    for m in get_friend_functions(c):
       s2 += ("friend " + print_fnt(m)).split('\n')
    s2 = '\n'.join( [ "   " + l.strip() + '\n' for l in s2 if l.strip()])
    s= make_signature_template_params(get_template_params(c)) + s
    return s + s2

#--------------------  namespace components : class, function ---------------------------------------------------------

def traverse_ns(n, keep = keep_all):
    """
    n : node
    go down all sub namespace, with a filter function keep
    return : n or first sub node which is not a namespace
             None if namespace if empty or keep has returned False at some point
    """
    while n.kind is CursorKind.NAMESPACE:
        if not keep(n): return None 
        try: # for empty namespace 
            n = n.get_children().next() # next node
        except StopIteration:
            return None
    return n

_class_types = [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION, CursorKind.CLASS_TEMPLATE]

def get_classes(node, keep = keep_all, traverse_namespaces = False, keep_ns = keep_all):
    """
    node is a namespace or root.
    keep(m) : predicate
    keep_ns : predicate
    traverse_namespaces : traverse the namespaces, with keep_ns
    yields the classes/struct in node
    """
    for c in node.get_children():
        if traverse_namespaces :
            c = traverse_ns (c)
        if c and c.kind in _class_types and keep(c): 
            yield c

_fnt_types = [CursorKind.FUNCTION_DECL, CursorKind.FUNCTION_TEMPLATE]

def get_functions(node, keep = keep_all, traverse_namespaces = False, keep_ns = keep_all):
    """
    node is a namespace or root.
    yields the functions
    keep_ns : predicate
    traverse_namespaces : traverse the namespaces, with keep_ns
     """
    for c in node.get_children():
        if traverse_namespaces :
            c = traverse_ns (c)
        if c and c.kind in _fnt_types and keep(c):
            yield c
         

#--------------------  PARSE

def parse(filename, compiler_options, where_is_libclang):
  """
  filename           : name of the file to parse
  compiler_options   : options to pass to clang to compile the file 
  where_is_libclang  : location (absolute path) of libclang
  return : the root of the AST tree
  """
  print "Initialising libclang"
  compiler_options =  [ '-std=c++14', '-stdlib=libc++'] + compiler_options
  clang.cindex.Config.set_library_file(where_is_libclang)
  index = clang.cindex.Index.create()
  print "Parsing the C++ file (may take a few seconds) ..."
  translation_unit = index.parse(filename, ['-x', 'c++'] + compiler_options)

  # If clang encounters errors, we report and stop
  errors = [d for d in translation_unit.diagnostics if d.severity >= 3]
  if errors :
      s =  "Clang reports the following errors in parsing\n"
      for err in errors :
        loc = err.location
        s += '\n'.join([" file %s line %s col %s"%(loc.file, loc.line, loc.column), err.spelling])
      raise RuntimeError, s + "\n... Your code must compile before using clang-parser !"
  
  print "... done. \n"
  return translation_unit.cursor 

