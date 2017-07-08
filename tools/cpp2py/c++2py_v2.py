#!@PYTHON_INTERPRETER@
import os, re, sys, itertools

script_path = os.path.dirname(os.path.abspath( __file__ ))
sys.path.append(script_path)
sys.path.append(script_path + '/..')  # Fix this !

import config
import cpp2py.util as util
import cpp2py.doc as doc
import clang_parser2 as CL
from mako.template import Template
import dependency_analyzer

# the instruction that created this file
shell_command = ' '.join([ sys.argv[0].rsplit('/')[-1]] + [x if ' ' not in x else '"%s"'%x for x in sys.argv[1:]])

#
print "Welcome to C++2py"

# --- Parsing the arguments of the script and options
import argparse

parser = argparse.ArgumentParser(description="""
Generate the C++/Python wrapper desc file from C++ header code
""")

parser.add_argument('filename', help = "Name of the file")
parser.add_argument('--outputname', '-o',  help="Name of the xxx_desc.py file [default is same as the filename]", default = '')
parser.add_argument('--modulename', '-m',  help="Name of the Python module [default ='', it will be modulename", default = '')
parser.add_argument('--appname', '-a',  help="Name of the Python module [default ='', it will take the name of file", default = '')
parser.add_argument('--moduledoc',  help="Documentation of the module", default = '')
parser.add_argument('--properties', '-p',  action='store_true',
        help="""Transforms i) every method with no arguments into read-only property
                ii) every method get_X into read-only property
                iii) every couple of methods get_X, set_X into rw property
              """)
parser.add_argument('--members_read_only',  action='store_true',
        help="""Makes members read only (only the getter, not the setter) """)

parser.add_argument('--libclang_location', help='Location of the libclang', default = config.LIBCLANG_LOCATION)
parser.add_argument('--compiler_options', nargs ='*', help='Options to pass to clang')
parser.add_argument('--includes', '-I', action='append',  help='Includes to pass to clang')
parser.add_argument('--only_converters',  action='store_true', help="[Experts only] Do not generate the desc file, just the converters if there are")
parser.add_argument('--namespace', '-N', action='append',  help="Specify the namespace to explore for classes and function to wrap", default= [])
parser.add_argument('--only', action='append',  help="Specify functions or class to be wrapped", default= [])

args = parser.parse_args()

args.includes = (args.includes or []) +  config.TRIQS_INCLUDE_DEPS.split(';')
args.includes.append(config.TRIQS_INCLUDE)

# -------- compiler options
compiler_options = (args.compiler_options or []) + ["-std=c++14"] + ['-I%s'%x for x in args.includes] + config.LIBCLANG_CXX_ADDITIONAL_FLAGS.strip().split()

# ---------- parse the file
root = CL.parse(args.filename, compiler_options = compiler_options, where_is_libclang = args.libclang_location)

# ---------- lambda to yield functions, etc..
 
def keep_ns(n):
    if n.location.file.name != args.filename: return False
    ign = len(args.namespace)>0 and n.get_canonical().spelling not in args.namespace
    return not ign 

def keep_cls(c):
    #print c.spelling, c.location.file.name == args.filename 
    if c.location.file.name != args.filename: return False
    if args.only : return c.spelling in args.only
    ign = len(args.namespace)>0 and c.get_canonical().spelling.rsplit('::',1) in args.namespace
    return not(ign or CL.is_template(c) or ("ignore_in_python" in CL.get_annotations(c)))

def keep_fnt(f) :
    ign = f.spelling.startswith('operator') or f.spelling in ['begin','end']
    return keep_cls(f) and not(ign)

# ---------- Treatment of properties

def separate_method_and_properties(c, keep = None):
    """
    c:  a cursor to a class
    return : a tuple (proplist, methodlist) where proplist : a list of property_  and methodlist : the others methods
    """  
    if not args.properties : return CL.get_methods(c, keep), []

    class property_ :
        def __init__ (self, **kw) :
            self.__dict__.update(kw)

    d = dict ( (m.spelling, m) for m in CL.get_methods(c, keep))
    dfinal = d.copy()
    proplist = []
    for n, m in d.items():
        if len(list(CL.get_params(m))) == 0 and not m.is_static_method(): # has no parameter and is not static
            X = n[4:] if n.startswith('get_') else n                      # remove the get_ if present
            set_m = d.get('set_' + X, None)                               # corresponding setter or None 
            p = list(CL.get_params(set_m)) if set_m else None
            if set_m and set_m.result_type.spelling == "void" and len(p) ==1 :
                if decay(p[0].spelling) == m.result_type.spelling :
                  del dfinal['set_' + X]
                else :
                    print "Warning :"
                    print "   in get_%s/set_%s" %(X,X)
                    print "     The type taken from set_%s is not the return type of get_%s"%(X,X)
                    print "    Expected ",m.result_type.spelling
                    print "    Got ", decay(p[0].spelling)
                    print "     I am not adding the setter to the property"
                    set_m = None
            print "Property : ", m.spelling, set_m.spelling if set_m else ''
            proplist.append(property_(name= X, doc = doc.make_doc(m), getter = m, setter = set_m))
            del dfinal[n]
    return dfinal.values(), proplist

# ---------- all classes, all functions

def all_classes_gen() : 
    return CL.get_classes(root, keep_cls, traverse_namespaces = True, keep_ns = keep_ns)

def all_functions_gen():
    return CL.get_functions(root, keep_fnt, traverse_namespaces = True, keep_ns = keep_ns)

def get_all_functions_and_methods() :
    for f in all_functions_gen(): 
        yield f
    for c in all_classes_gen(): 
        for m in CL.get_methods(c):
            yield m
        for m in CL.get_constructors(c):
            yield m

# ---------------  Find all classes with param

def get_all_param_classes():
    """ yields all param classes """
    for f in get_all_functions_and_methods():
        r = util.get_decl_param_class(f)
        if r : 
            yield r

# 
classes_of_parameters = list(get_all_param_classes())
if len(classes_of_parameters):
    print "Parameters classes found: "
    for c in classes_of_parameters:
        print "   ", c.spelling
    # TODO : PORT THIS MAKO FILE 
    generate_mako ('converters.hxx', classes = classes_of_parameters) # **locals())
    #TODO : No mako for this one !
    generate_mako ('parameters.rst', **locals())

# ---------------  deduction of modules and using to be used
def params_ret_type_generator():
    """ generator yielding all types of every methods, function"""
    for f in all_functions_gen():
        yield getattr(f, 'result_type', None)
        for p in CL.get_params(f) : 
            yield p.type

    for x in itertools.chain(classes_of_parameters, all_classes_gen()): 
        for m in CL.get_members(x, False): # False : no inherited
            yield m.type
        for m in itertools.chain(CL.get_constructors(x), CL.get_methods(x)): 
            yield getattr(m, 'result_type', None)
            for p in CL.get_params(m) : 
                yield p.type

# analyse the modules and converters that need to be added
used_module_list, converters_list, using_list = dependency_analyzer.run(params_ret_type_generator())

# ---------------  Function to render with mako
def generate_mako(mako_filename, **kw) : 
    """Write one file"""
    tpl = Template(filename=script_path + '/mako/' + mako_filename)
    rendered = tpl.render(**kw)
    rendered = re.sub(re.compile(r"[ \t\r\f\v]+$",re.MULTILINE),'',rendered.strip())# clean end and while char 
    print rendered
    output_name = args.outputname or os.path.split(args.filename)[1].split('.',1)[0]
    with open("{output_name}_{filename}".format(output_name=output_name, filename = mako_filename), "w") as f:
        f.write(rendered)

# ---------------  now write the desc
# WHY ONLY CONVERTERS ????
if not args.only_converters:
    modulename = args.modulename or os.path.split(args.filename)[1].split('.',1)[0]
    appname = args.appname or modulename
    filename = args.filename
    members_read_only = args.members_read_only 
    generate_mako ('desc.py', classes = all_classes_gen(), functions = all_functions_gen(), **locals())

