
# Build C extension module
triqs_python_extension(my_module)
triqs_python_extension(my_moduleB)
triqs_python_extension(test_g)
triqs_python_extension(test_bl)
triqs_python_extension(test_multivar)

add_dependencies(test_multivar meshes singularities gf_fnt wrapped_aux)
add_dependencies(test_g meshes singularities gf_fnt wrapped_aux)
add_dependencies(test_bl meshes singularities gf_fnt wrapped_aux)

add_dependencies(my_moduleB my_module)

include_directories( ${CMAKE_CURRENT_SOURCE_DIR} )

# A sample test with text output
add_python_test(wrap_a)
add_python_test(wrap_B)
add_python_test(wrap_g)
add_python_test(wrap_multivar)
add_python_test(blockgf)

