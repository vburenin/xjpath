import unittest

import xjpath


class TestXJPath(unittest.TestCase):

    def test_get_all_dict_values_from_top(self):
        d = {'t1': 1, 't2': 2, 't3': 3, 't4': 4}
        v = xjpath.strict_path_lookup(d, '*')
        self.assertTrue(isinstance(v, tuple))
        self.assertEqual([1, 2, 3, 4], sorted(v))

    def test_get_all_dict_values_from_level_down(self):
        d = {'l1': {'t1': 1, 't2': 2, 't3': 3, 't4': 4}}
        v = xjpath.strict_path_lookup(d, 'l1.*')
        self.assertTrue(isinstance(v, tuple))
        self.assertEqual([1, 2, 3, 4], sorted(v))

    def test_get_all_list_values_copy(self):
        d = {'l1': [1, 2, 3, 4]}
        v = xjpath.strict_path_lookup(d, 'l1.*')
        self.assertEqual((1, 2, 3, 4), v)

    def test_get_all_same_attribute_values_if_list(self):
        d = {'l1': [{'s': 5, 'r': ''}, {'s': 6, 'r': ''}, {'s': 7}]}
        v = xjpath.strict_path_lookup(d, 'l1.*.s')
        self.assertEqual((5, 6, 7), v)

    def test_get_all_same_attribute_values_if_dict(self):
        d = {'l1': {'t0': {'s': 5, 'r': ''},
                    't1': {'s': 6, 'r': ''},
                    't2': {'s': 7}}}
        v = xjpath.strict_path_lookup(d, 'l1.*.s')
        self.assertEqual([5, 6, 7], sorted(v))

    def test_get_last_array_element(self):
        d = [1, 2, 3]
        v = xjpath.strict_path_lookup(d, '@last')
        self.assertEqual(3, v)

    def test_get_first_array_element(self):
        d = [1, 2, 3]
        v = xjpath.strict_path_lookup(d, '@first')
        self.assertEqual(1, v)

    def test_get_second_array_element(self):
        d = [1, 2, 3]
        v = xjpath.strict_path_lookup(d, '@1')
        self.assertEqual(2, v)

    def test_get_element_from_dict_that_is_second_element_in_array(self):
        d = ['1', {'element': 999}, '3']
        v = xjpath.strict_path_lookup(d, '@1.element')
        self.assertEqual(999, v)

    def test_get_element_from_wrong_index_with_exception(self):
        d = [1, 2, 3]
        with self.assertRaises(xjpath.XJPathError):
            xjpath.strict_path_lookup(d, '@10')

    def test_get_element_from_wrong_index_with_no_exception(self):
        d = [1, 2, 3]
        value, exists = xjpath.path_lookup(d, '@10')
        self.assertIsNone(value)
        self.assertFalse(exists)

    def test_get_element_from_dict_using_array_index(self):
        d = {'1': '1', '2': '2'}
        value, exists = xjpath.path_lookup(d, '@1')
        self.assertIsNone(value)
        self.assertFalse(exists)

    def test_test_no_values(self):
        with self.assertRaises(xjpath.XJPathError):
            xjpath.strict_path_lookup({}, 'path')

    def test_test_no_values_deep(self):
        with self.assertRaises(xjpath.XJPathError):
            xjpath.strict_path_lookup({'path': {'test': [1]}}, 'path.test.num')

    def test_with_one_escape(self):
        value, exists = xjpath.path_lookup({'v.v': {'t': 31}}, 'v\.v.t')
        self.assertEqual(31, value)
        self.assertTrue(exists)

    def test_with_two_escape(self):
        value, exists = xjpath.path_lookup({'v.v': {'t.t': 31}}, 'v\.v.t\.t')
        self.assertEqual(31, value)
        self.assertTrue(exists)

    def test_with_last_escape(self):
        value, exists = xjpath.path_lookup({'v': {'t.t': 31}}, 'v.t\.t')
        self.assertEqual(31, value)
        self.assertTrue(exists)

    def test_with_sobachka_escape(self):
        """Sobachka == '@'"""
        value, exists = xjpath.path_lookup({'v': {'@id': 31}}, 'v.\@id')
        self.assertEqual(31, value)
        self.assertTrue(exists)

    def test_with_sobachka_double_escape(self):
        """Sobachka == '@'"""
        value, exists = xjpath.path_lookup({'v': {'\@id': 31}}, 'v.\\\\@id')
        self.assertEqual(31, value)
        self.assertTrue(exists)

    def test_with_sobachka_triple_escape(self):
        """Sobachka == '@'"""
        value, exists = xjpath.path_lookup({'v': {'\\\\@id': 31}},
                                           'v.\\\\\\\\@id')
        self.assertEqual(31, value)
        self.assertTrue(exists)

    def test_with_star_escape(self):
        value, exists = xjpath.path_lookup({'v': {'*id': 31}}, 'v.\*id')
        self.assertEqual(31, value)
        self.assertTrue(exists)

    def test_escapes_non_special(self):
        value, exists = xjpath.path_lookup({'v': {'\\': 31}}, r'v.\\')
        self.assertEqual(31, value)
        self.assertTrue(exists)

    def test_validate_path_ok(self):
        xjpath.validate_path('x.f.g.@first')
        xjpath.validate_path('x.f.g.@last')
        xjpath.validate_path('x.*.*.@last')
        xjpath.validate_path('x.@first.\*.@last')

    def test_validate_path_fail(self):
        with self.assertRaises(xjpath.XJPathError):
            xjpath.validate_path('x.@wedwe')

        with self.assertRaises(xjpath.XJPathError):
            xjpath.validate_path(10)

    def test_auto_dict_creations(self):
        a = {}
        xjpath.path_lookup(a, 'a{}.b{}.c{}')
        self.assertEqual({'a': {'b': {'c': {}}}}, a)

    def test_auto_dict_and_last_array_creations(self):
        a = {}
        xjpath.path_lookup(a, 'a{}.b{}.c[]')
        self.assertEqual({'a': {'b': {'c': []}}}, a)

    def test_path_create_type_mismatch1(self):
        a = {'a': 1}
        with self.assertRaises(xjpath.XJPathError):
            xjpath.path_lookup(a, 'a[]')

    def test_path_create_type_mismatch2(self):
        a = {'a': []}
        with self.assertRaises(xjpath.XJPathError):
            xjpath.path_lookup(a, 'a{}')

    def test_path_create_type_mismatch3(self):
        a = [{}]
        with self.assertRaises(xjpath.XJPathError):
            xjpath.path_lookup(a, '@first[]')

    def test_path_create_type_mismatch4(self):
        a = [{}]
        with self.assertRaises(xjpath.XJPathError):
            xjpath.path_lookup(a, '@-1[]')

    def test_path_lookup_dict_as_array(self):
        a = []
        with self.assertRaises(xjpath.XJPathError):
            xjpath.path_lookup(a, 'a{}')

    def test_path_lookup_array_as_dict(self):
        a = {}
        with self.assertRaises(xjpath.XJPathError):
            xjpath.path_lookup(a, '@first[]')

    def test_type_escape_for_str(self):
        self.assertEqual(('v', True), xjpath.path_lookup({'a$': 'v'}, 'a\$'))
        self.assertEqual(('', True), xjpath.path_lookup({'a$': 'a'}, 'a$'))

    def test_type_escape_for_number(self):
        self.assertEqual((123, True), xjpath.path_lookup({'a#': 123}, 'a\#'))
        self.assertEqual((0, True), xjpath.path_lookup({'a$': 123}, 'a#'))

    def test_type_escape_for_float(self):
        self.assertEqual((.1, True), xjpath.path_lookup({'a%': .1}, 'a\%'))
        self.assertEqual((.0, True), xjpath.path_lookup({'a%': 123}, 'a%'))

    def test_type_escape_for_dict(self):
        self.assertEqual(({"1": 1}, True),
                         xjpath.path_lookup({'a{}': {"1": 1}}, 'a\{}'))
        self.assertEqual(({}, True),
                         xjpath.path_lookup({'a{}': {"1": 1}}, 'a{}'))

    def test_type_escape_for_list(self):
        self.assertEqual(([1], True), xjpath.path_lookup({'a[]': [1]}, 'a\[]'))
        self.assertEqual(([], True), xjpath.path_lookup({'a[]': [1]}, 'a[]'))


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.CRITICAL)
    unittest.main()
