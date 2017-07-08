SET(PYTHON_SOURCES
  ${CMAKE_CURRENT_SOURCE_DIR}/__init__.py
  ${CMAKE_CURRENT_SOURCE_DIR}/block2_gf.py
  ${CMAKE_CURRENT_SOURCE_DIR}/block_gf.py
  ${CMAKE_CURRENT_SOURCE_DIR}/descriptor_base.py
  ${CMAKE_CURRENT_SOURCE_DIR}/descriptors.py
  ${CMAKE_CURRENT_SOURCE_DIR}/gf.py
  ${CMAKE_CURRENT_SOURCE_DIR}/lazy_expressions.py
  ${CMAKE_CURRENT_SOURCE_DIR}/mesh_product.py
  ${CMAKE_CURRENT_SOURCE_DIR}/tools.py
)

install (FILES ${PYTHON_SOURCES} DESTINATION ${TRIQS_PYTHON_LIB_DEST}/gf)
install (FILES ${CMAKE_SOURCE_DIR}/pytriqs/__init__.py.template DESTINATION "include/pytriqs/gf" RENAME __init__.py)

# Build C extension module
triqs_python_extension(meshes)
add_dependencies(meshes lattice_tools)

# Build C extension module
triqs_python_extension(singularities)
add_dependencies(singularities lattice_tools)

# Build C extension module
triqs_python_extension(gf_fnt)
add_dependencies(gf_fnt meshes )
add_dependencies(gf_fnt singularities)

# Build C extension module
triqs_python_extension(wrapped_aux)
add_dependencies(wrapped_aux meshes )
add_dependencies(wrapped_aux singularities)

add_subdirectory(backwd_compat)
add_subdirectory(plot)

# Backward compatibility only
add_subdirectory(local)

