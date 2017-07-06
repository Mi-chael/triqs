#pragma once
#include <Python.h>
#include "structmember.h"
#include <string>
#include <complex>
#include <vector>
#include <triqs/utility/exceptions.hpp>
#include <triqs/utility/c17.hpp>
#include "./pyref.hpp"
#include <time.h>

// silence warning on intel
#ifndef __INTEL_COMPILER
#pragma clang diagnostic ignored "-Wdeprecated-writable-strings"
#endif
#pragma GCC diagnostic ignored "-Wwrite-strings"

inline char *get_current_time() { // helper function to print the time in the CATCH_AND_RETURN macro
 time_t rawtime;
 time(&rawtime);
 return ctime(&rawtime);
}

// I can use the trace in triqs::exception
#define CATCH_AND_RETURN(MESS,RET)\
 catch(triqs::keyboard_interrupt const & e) {\
 PyErr_SetString(PyExc_KeyboardInterrupt, e.what());\
 return RET; }\
 catch(triqs::exception const & e) {\
 auto err = std::string(".. Error occurred at ") + get_current_time() + "\n.. Error " + MESS + "\n.. C++ error was : \n"  + e.what();\
 PyErr_SetString(PyExc_RuntimeError, err.c_str());\
 return RET; }\
 catch(std::exception const & e) {\
 auto err = std::string(".. Error occurred at ") + get_current_time() + "\n.. Error " + MESS + "\n.. C++ error was : \n"  + e.what();\
 PyErr_SetString(PyExc_RuntimeError, err.c_str());\
 return RET; }\
 catch(...) { PyErr_SetString(PyExc_RuntimeError,"Unknown error " MESS ); return RET; }\

namespace triqs { namespace py_tools {

//---------------------  py_converters -----------------------------

// default version for a wrapped type. To be specialized later.
// py2c behaviour is undefined is is_convertible return false
// c2py should return NULL on failure
template<typename T> struct py_converter;
 //{ 
 //  static PyObject * c2py(T const & x);
 //  static T & py2c(PyObject * ob);
 //  static bool is_convertible(PyObject * ob, bool raise_exception);
 //}

// helpers for better error message
// some class (e.g. range !) only have ONE conversion, i.e. C -> Py, but not both 
// we need to distinguish
template <class, class = std17::void_t<>> struct does_have_a_converterPy2C : std::false_type {};
template <class T> struct does_have_a_converterPy2C<T, std17::void_t<decltype(py_converter<std14::decay_t<T>>::py2c(nullptr))>> : std::true_type {};

template <class, class = std17::void_t<>> struct does_have_a_converterC2Py : std::false_type {};
template <class T> struct does_have_a_converterC2Py<T, std17::void_t<decltype(py_converter<std14::decay_t<T>>::c2py(std::declval<T>()))>> : std::true_type {};

// We only use these functions in the code, not directly the converter
template <typename T> static PyObject *convert_to_python(T &&x) {
 static_assert(does_have_a_converterC2Py<T>::value, "The type does not have a converter from C++ to Python");
 return py_converter<std14::decay_t<T>>::c2py(std::forward<T>(x));
}
template <typename T> static bool convertible_from_python(PyObject *ob, bool raise_exception) {
 return py_converter<T>::is_convertible(ob, raise_exception);
}

/*
 * type          T            py_converter<T>::p2yc     convert_from_python<T>   converter_for_parser type of p      impl
 *                                                 
 * regular       R            R or R&& or R const&      R  or R&& or R const&    R*                                *p = py_converter<T>::p2yc(ob))
 * view          V            V                         V                        V*                                p->rebind(py_converter<T>::p2yc(ob))
 * wrapped       W            W *                       W                        W**                               *p = py_converter<T>::p2yc(ob))  
 * wrapped view  WV           WV *                      WV                       WV**                              p->rebind(py_converter<T>::p2yc(ob))
 * PyObejct *    PyObject *   PyObject *                PyObject *               PyObject **                       *p = py_converter<T>::p2yc(ob))  
 * U*            U*           U*                        U*                       U**                               *p = py_converter<T>::p2yc(ob)) 
 *
 */ 

// is_wrapped<T>  if py_converter has been reimplemented.
template<typename T, class = void> struct is_wrapped : std::false_type{};
template<typename T> struct is_wrapped<T, typename py_converter<T>::is_wrapped_type> : std::true_type{};

template<typename T> inline constexpr bool is_wrapped_v = is_wrapped<T>::value;

template <typename T> static auto convert_from_python(PyObject *ob) -> decltype(py_converter<T>::py2c(ob)) {
 static_assert(does_have_a_converterPy2C<T>::value, "The type does not have a converter from Python to C++");
 return py_converter<T>::py2c(ob);
}

/*template<typename T> static auto & convert_from_python_helper(PyObject * ob, std::true_type) { 
  return *py_converter<T>::py2c(ob);
}
template<typename T> static auto convert_from_python_helper(PyObject * ob, std::false_type) -> decltype(py_converter<T>::py2c(ob))  { 
  return py_converter<T>::py2c(ob);
}
template <typename T> static auto convert_from_python(PyObject *ob) -> decltype(convert_from_python_helper<T>(ob , is_wrapped<T>{})){ 
 static_assert(does_have_a_converterPy2C<T>::value, "The type does not have a converter from Python to C++");
 return convert_from_python_helper<T>(ob , is_wrapped<T>{});
}
*/

 // TODO C17 : if constexpr
 // used by PyParse_xxx : U is a pointer iif we have a wrapped object.
 template<typename T> 
 static void converter_for_parser_dispatch(PyObject * ob, T * p, std::false_type, std::false_type) { 
  *p = py_converter<T>::py2c(ob);
 }
 template<typename T> 
 static void converter_for_parser_dispatch(PyObject * ob, T * p, std::false_type, std::true_type) { 
  p->rebind(py_converter<T>::py2c(ob));
 }
 template<typename T>
 static void converter_for_parser_dispatch(PyObject * ob, T ** p, std::true_type, std::false_type) {
  *p = &py_converter<T>::py2c(ob);
 }
 template<typename T>
 static void converter_for_parser_dispatch(PyObject * ob, T ** p, std::true_type, std::true_type) {
  *p = &py_converter<T>::py2c(ob);
 }

 template<typename T> 
  static int converter_for_parser(PyObject * ob, std::conditional_t<is_wrapped_v<T>, T*, T> * p) {
   if (!convertible_from_python<T>(ob,true)) return 0;
   converter_for_parser_dispatch(ob, p, is_wrapped<T>{}, triqs::is_view<T>{} );
   return 1;
 }

// pointer -> ref except PyObject *. We assume here that there is no 
// converter py_converter<U*>. The dereference should be only for wrapped type. Check by static_assert
// Generalize if needed.
inline PyObject * deref_is_wrapped(PyObject * x) { return x;}
template <typename T> auto & deref_is_wrapped(T* x) { 
 static_assert(is_wrapped<T>::value, "Internal assumption invalid");
 return *x;
}
template <typename T> auto & deref_is_wrapped(T& x) { return x;}


// -----------------------------------
//    Tools for the implementation of reduce (V2)
// -----------------------------------

 // auxiliary object to reduce the object into a tuple
 class reductor {
  std::vector<PyObject *> elem;
  PyObject *as_tuple() {
   int l = elem.size();
   PyObject *tup = PyTuple_New(l);
   for (int pos = 0; pos < l; ++pos) PyTuple_SetItem(tup, pos, elem[pos]);
   return tup;
  }
  public:
  template <typename T> reductor & operator&(T &x) { elem.push_back(convert_to_python(x)); return *this;}
  template<typename T>
  PyObject * apply_to(T & x) { x.serialize(*this,0); return as_tuple();}
 };

 // inverse : auxiliary object to reconstruct the object from the tuple ...
 class reconstructor {
  PyObject * tup; // borrowed ref
  int pos=0, pos_max = 0;
  public:
  reconstructor(PyObject *borrowed_ref) : tup(borrowed_ref) { pos_max = PyTuple_Size(tup)-1;}
  template <typename T> reconstructor &operator&(T &x) {
   if (pos > pos_max) TRIQS_RUNTIME_ERROR << " Tuple too short in reconstruction";
   x = convert_from_python<T>(PyTuple_GetItem(tup, pos++));
   return *this;
  }
 };

 // no protection for convertion !
 template <typename T> struct py_converter_from_reductor {
 template<typename U> static PyObject *c2py(U && x) { return reductor{}.apply_to(x); }
 static T py2c(PyObject *ob) {
  T res;
  auto r = reconstructor{ob};
  res.serialize(r, 0);
  return res;
 }
 static bool is_convertible(PyObject *ob, bool raise_exception) { return true;}
};

// -----------------------------------
//       basic types
// -----------------------------------

// PyObject *
template <> struct py_converter<PyObject *> {
 static PyObject *c2py(PyObject *ob) { return ob; }
 static PyObject *py2c(PyObject *ob) { return ob; }
 static bool is_convertible(PyObject *ob, bool raise_exception) { return true;}
};

// --- bool
template <> struct py_converter<bool> {
 static PyObject *c2py(bool b) {
  if (b)
   Py_RETURN_TRUE;
  else
   Py_RETURN_FALSE;
 }
 static bool py2c(PyObject *ob) { return ob == Py_True; }
 static bool is_convertible(PyObject *ob, bool raise_exception) {
  if (PyBool_Check(ob)) return true;
  if (raise_exception) { PyErr_SetString(PyExc_TypeError, "Cannot convert to bool");}
  return false;
 }
};

// --- long

template <> struct py_converter<long> {
 static PyObject *c2py(long i) { return PyInt_FromLong(i); }
 static long py2c(PyObject *ob) { return PyInt_AsLong(ob); }
 static bool is_convertible(PyObject *ob, bool raise_exception) {
  if (PyInt_Check(ob)) return true;
  if (raise_exception) { PyErr_SetString(PyExc_TypeError, "Cannot convert to long");}
  return false;
 }
};

template <> struct py_converter<int> : py_converter<long> {};
template <> struct py_converter<unsigned int> : py_converter<long> {};
template <> struct py_converter<unsigned long> : py_converter<long> {};
template <> struct py_converter<unsigned long long> : py_converter<long> {};

// --- double

template <> struct py_converter<double> {
 static PyObject *c2py(double x) { return PyFloat_FromDouble(x); }
 static double py2c(PyObject *ob) { return PyFloat_AsDouble(ob); }
 static bool is_convertible(PyObject *ob, bool raise_exception) {
  if (PyFloat_Check(ob) || PyInt_Check(ob)) return true;
  if (raise_exception) { PyErr_SetString(PyExc_TypeError, "Cannot convert to double");}
  return false;
 }
};

// --- complex

template <> struct py_converter<std::complex<double>> {
 static PyObject *c2py(std::complex<double> x) { return PyComplex_FromDoubles(x.real(), x.imag()); }
 static std::complex<double> py2c(PyObject *ob) {
  if (PyComplex_Check(ob)) {
    auto r = PyComplex_AsCComplex(ob);
    return {r.real, r.imag};
  }
  return PyFloat_AsDouble(ob);
 }
 static bool is_convertible(PyObject *ob, bool raise_exception) {
  if (PyComplex_Check(ob) || PyFloat_Check(ob) || PyInt_Check(ob)) return true;
  if (raise_exception) { PyErr_SetString(PyExc_TypeError, "Cannot convert to complex");}
  return false;
 }
};

}}
