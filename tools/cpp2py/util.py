# This module contains a few utilities
import re
import clang_parser2 as CL

def get_decl_param_class(f):
    """ Given a node f of a function, returns the node of declaration of the param class or None"""
    if 'use_parameter_class' not in CL.get_annotations(f) : 
        return None
    p = list(get_params(f))
    assert len(p) == 1, "A function/method with PARAM technique must have exacly one parameter"
    print "parameters class : %s"%p[0].get_canonical().spelling
    return jump_to_declaration(p[0])

def use_parameter_class(m): 
    return 'use_parameter_class' in CL.get_annotations(m) 

def decay(s) :
    for tok in ['const ', 'const&', '&&', '&'] :
        s = re.sub(tok,'',s)
    s = s.replace('const_view', 'view') # DISCUSS THIS
    return s.strip()

def deduce_normalized_python_class_name(s) :
    return ''.join([x.capitalize() for x in s.split('_')])
 

def make_signature_for_desc(f, is_constructor = False):
    """Given a node of a function/methods, it makes the signature for desc file"""
    # first format the arguments
    if use_parameter_class(f) : 
        r = '**%s'%CL.get_params(m).next().type.spelling
    else:
        plist = [ (p.type.spelling, p.spelling, CL.get_param_default_value(p)) for p in CL.get_params(f)]
        r = ', '.join("%s %s"%(t, n) + (" = %s"%d.replace('"','\\"') if d else "") for t, n, d  in plist ) 

    if is_constructor:
        return "(%s)"%r
    else :
        return ("%s %s (%s)"%(f.result_type.spelling, f.spelling, r)).strip()


