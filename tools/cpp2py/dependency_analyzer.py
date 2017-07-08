# This module contains a function that 
# given a iterable of the type (as node) of all parameters and return type
# of the methods/functions to be wrapped
# deduces tentatively the modules and converter to import.
import clang_parser2 as CL
import util, re

recognized_namespace_for_using = {
    'triqs::gfs::' : 'pytriqs.gf',
    'triqs::operators::many_body_operator' : 'pytriqs.operators',
    'triqs::lattice' : 'pytriqs.lattice'
    }

using_needed_for_modules = {
    'pytriqs.gf' : 'namespace triqs::gfs',
    'pytriqs.operators' : 'triqs::operators::many_body_operator',
    'pytriqs.lattice' : 'namespace triqs::lattice'
    }

converters_to_include = {
    'std::.*map' : 'map',
    'std::.*set' : 'set',
    'std::.*vector' : 'vector',
    'std::.*string' : 'string',
    'std::.*function' : 'function',
    'std::.*pair' : 'pair',
    'std::.*tuple' : 'tuple',
    'std::.*optional' : 'optional',
    'triqs::utility::variant' : 'variant',
    'triqs::arrays::array' : 'arrays',
    'triqs::arrays::matrix' : 'arrays',
    'triqs::arrays::vector' : 'arrays',
    }

def run(all_type_nodes): 
    used_module_list, converters_list = [], set()

    for x in all_type_nodes : 
        can = x.get_canonical().spelling
        for ns, mod in recognized_namespace_for_using.items() :
          if ns in util.decay(can):
            used_module_list.append(mod)

        for ns, mod in converters_to_include.items() :
          if re.compile(ns).search(util.decay(can)): 
            converters_list.add(mod)
       
    used_module_list = set(used_module_list) # makes unique
    converters_list = set(converters_list)
    using_list = [using_needed_for_modules[m] for m in used_module_list]
    return used_module_list, converters_list, using_list

