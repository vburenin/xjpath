"""XJPATH simplifies access to the python data structures using relatively
simple path syntax. It doesn't not only lookup value, it also can
validate found data type as well as create value if a target structure is a
dictionary.

The typical scenarios are:

 - you need to lookup an element from nested dicts.
 - you need to lookup and element from array that is a value of nested dictionary
 - you need to get a list of X values from multiple nested dictionaries.
 - you just want to operate with a complex data structure in the way you
   operate with the dictionary.
 - you want to make sure that found data has an expected type.

The expression syntax is trivial it looks like:

'key1.key2.key3'

Each key name is a nested data index/key. Key may refer to a dictionary,
an array index or iterator.

To refer a dictionary key, just use its name as in the example above.

An array index is prepended with '@' symbol:

    @2 - Means seconds element.
    @-2 - Means second element from the end.
    @last - Means last element.
    @first - Means first element of the array.

In case if dictionary key contains any reserved symbols, just escape them.

'2.\@2' - will lookup key 2 and then key '@2'.

You also can specify a type of expected value as a postfix for expected value:

  'keyname[]', '@last[], '@first{}', 'data$', 'data#'

  [] - Expected value is a list.
  () - Expected value is a tuple.
  {} - Expected value is a dictionary.
  # - Expected value is an integer.
  % - Expected value is a float.
  $ - Expected value is a string.


Here is a bunch of examples:

>>> d = {'data': {
  'a_array': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  'b_dict': {'a': 'xxx', 'b': 'yyy', 'c': 'zzz'},
  'c_array': [{'v': 'vdata1'}, {'v': 'vdata2'}]}}
>>> xj = xjpath.XJPath(d)

To get 'a_array' array:

>>> xj['data.a_array']
[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

>>> xj['data.a_array{}']
IndexError: ('Path error: data.a_array{}', 'Key a_array expects type "dict", but found value type is "list"')

To get a last element of 'a_array' array:

>>> xj['data.a_array.@last']
10

To get the first element of 'a_array' array:

>>> xj['data.a_array.@first']
0

To get 9th element from 'a_array':

>>> xj['data.a_array.@9']
9

To get third element from the back from 'a_array':

>>> xj['data.a_array.@-3']
8

To get all values that are stored in dictionaries with key 'v1' of array c_array:

>>> xj['data.c_array.*.v']
('vdata1', 'vdata2')

To return a frozen copy of a_array:

>>> xj['data.a_array.*']
(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)

To get all values of b_dict dictionary:

>>> xj['data.b_dict.*']
('zzz', 'yyy', 'xxx')


If you don't like a dictionary like interface. Feel free to use path_lookup
function instead that returns a found value as well as a boolean value telling
you if result is found or not.


Author: vburenin@gmail.com
"""


ESCAPE_STR1 = '111' * 5
ESCAPE_STR2 = '222' * 5
ESCAPE_SEQ = '\\'  # '\' character used as an escape sequence in xjpath.
DOUBLE_ESCAPE_SEQ = ESCAPE_SEQ + ESCAPE_SEQ


class XJPathError(Exception):
    pass


def split(inp_str, sep_char, maxsplit=-1, escape_char='\\'):
    """Separates a string on a character, taking into account escapes.

    :param str inp_str: string to split.
    :param str sep_char: separator character.
    :param int maxsplit: maximum number of times to split from left.
    :param str escape_char: escape character.
    :rtype: __generator[str]
    :return: sub-strings generator separated on the `sep_char`.

    """

    word_chars = []
    word_chars_append = word_chars.append

    inp_str_iter = iter(inp_str)

    for c in inp_str_iter:
        word_chars_append(c)
        if c == escape_char:
            try:
                next_char = next(inp_str_iter)
            except StopIteration:
                continue
            if next_char == sep_char:
                word_chars[-1] = next_char
            else:
                word_chars.append(next_char)
        elif c == sep_char:
            word_chars.pop()
            yield ''.join(word_chars)
            maxsplit -= 1
            if maxsplit == 0:
                yield ''.join(inp_str_iter)
                return
            del word_chars[:]

    yield ''.join(word_chars)


def _full_sub_array(data_obj, xj_path, create_dict_path):
    """Retrieves all array or dictionary elements for '*' JSON path marker.

    :param dict|list data_obj: The current data object.
    :param str xj_path: A json path.
    :param bool create_dict_path create a dict path.
    :return: tuple with two values: first is a result and second
             a boolean flag telling if this value exists or not.
    """

    if isinstance(data_obj, list):
        if xj_path:
            res = []
            for d in data_obj:
                val, exists = path_lookup(d, xj_path, create_dict_path)
                if exists:
                    res.append(val)
            return tuple(res), True
        else:
            return tuple(data_obj), True
    elif isinstance(data_obj, dict):
        if xj_path:
            res = []
            for d in data_obj.values():
                val, exists = path_lookup(d, xj_path, create_dict_path)
                if exists:
                    res.append(val)
            return tuple(res), True
        else:
            return tuple(data_obj.values()), True
    else:
        return None, False


def _get_array_index(array_path):
    """Translates @first @last @1 @-1 expressions into an actual array index.

    :param str array_path: Array path in XJ notation.
    :rtype: int
    :return: Array index.
    """

    if not array_path.startswith('@'):
        raise XJPathError('Array index must start from @ symbol.')
    array_path = array_path[1:]
    if array_path == 'last':
        return -1
    if array_path == 'first':
        return 0
    if array_path.isdigit() or (array_path.startswith('-')
                                and array_path[1:].isdigit()):
        return int(array_path)
    else:
        raise XJPathError('Unknown index reference', (array_path,))


def _single_array_element(data_obj, xj_path, array_path, create_dict_path):
    """Retrieves a single array for a '@' JSON path marker.

    :param list data_obj: The current data object.
    :param str xj_path: A json path.
    :param str array_path: A lookup key.
    :param bool create_dict_path create a dict path.
    """

    val_type, array_path = _clean_key_type(array_path)
    array_idx = _get_array_index(array_path)
    if data_obj and isinstance(data_obj, (list, tuple)):
        try:
            value = data_obj[array_idx]
            if val_type is not None and not isinstance(value, val_type):
                raise XJPathError('Index array "%s" of "%s" type does not '
                                  'match expected type "%s"' %
                                  (array_idx, type(value).__name__,
                                   val_type.__name__))

            if xj_path:
                return path_lookup(value, xj_path, create_dict_path)
            else:
                return value, True
        except IndexError:
            return None, False
    else:
        if val_type is not None:
            raise XJPathError('Expected the list element type, but "%s" found' %
                              type(data_obj).__name__)
        return None, False


def _split_path(xj_path):
    """Extract the last piece of XJPath.

    :param str xj_path: A XJPath expression.
    :rtype: tuple[str|None, str]
    :return: A tuple where first element is a root XJPath and the second is
             a last piece of key.
    """

    res = xj_path.rsplit('.', 1)
    root_key = res[0]
    if len(res) > 1:
        return root_key, res[1]
    else:
        if root_key and root_key != '.':
            return None, root_key
        else:
            raise XJPathError('Path cannot be empty', (xj_path,))


def validate_path(xj_path):
    """Validates XJ path.

    :param str xj_path: XJ Path
    :raise: XJPathError if validation fails.
    """

    if not isinstance(xj_path, str):
        raise XJPathError('XJPath must be a string')

    for path in split(xj_path, '.'):
        if path == '*':
            continue
        if path.startswith('@'):
            if path == '@first' or path == '@last':
                continue
            try:
                int(path[1:])
            except ValueError:
                raise XJPathError('Array index must be either integer or '
                                  '@first or @last')


_KEY_SPLIT = {
    '$': str,
    '#': int,
    '%': float,
    '{}': dict,
    '[]': list,
    '()': tuple,
}


def unescape(in_str, escape_char=ESCAPE_SEQ):
    str_iter = iter(in_str)
    chars = []
    chars_append = chars.append

    try:
        for c in str_iter:
            if c == escape_char:
                chars_append(next(str_iter))
            else:
                chars_append(c)
    except StopIteration:
        pass

    return ''.join(chars)


def _clean_key_type(key_name, escape_char=ESCAPE_SEQ):
    """Removes type specifier returning detected type and
    a key name without type specifier.

    :param str key_name: A key name containing type postfix.
    :rtype: tuple[type|None, str]
    :returns: Type definition and cleaned key name.
    """

    for i in (2, 1):

        if len(key_name) < i:
            return None, key_name

        type_v = key_name[-i:]

        if type_v in _KEY_SPLIT:
            if len(key_name) <= i:
                return _KEY_SPLIT[type_v], ''

            esc_cnt = 0
            for pos in range(-i - 1, -len(key_name) - 1, -1):
                if key_name[pos] == escape_char:
                    esc_cnt += 1
                else:
                    break

            if esc_cnt % 2 == 0:
                return _KEY_SPLIT[type_v], key_name[:-i]
            else:
                return None, key_name

    return None, key_name


def path_lookup(data_obj, xj_path, create_dict_path=False):
    """Looks up a xj path in the data_obj.

    :param dict|list data_obj: An object to look into.
    :param str xj_path: A path to extract data from.
    :param bool create_dict_path: Create an element if type is specified.
    :return: A tuple where 0 value is an extracted value and a second
             field that tells if value either was found or not found.
    """

    if not xj_path or xj_path == '.':
        return data_obj, True

    res = list(split(xj_path, '.', maxsplit=1))
    top_key = res[0]
    leftover = res[1] if len(res) > 1 else None
    if top_key == '*':
        return _full_sub_array(data_obj, leftover, create_dict_path)
    elif top_key.startswith('@'):
        return _single_array_element(data_obj, leftover, top_key,
                                     create_dict_path)
    else:
        val_type, top_key = _clean_key_type(top_key)
        top_key = unescape(top_key)
        if top_key in data_obj:
            value = data_obj[top_key]
            if val_type is not None and not isinstance(value, val_type):
                raise XJPathError(
                    'Key %s expects type "%s", but found value type is "%s"' %
                    (top_key, val_type.__name__, type(value).__name__))
            if leftover:
                return path_lookup(value, leftover, create_dict_path)
            else:
                return value, True
        else:
            if val_type is not None:
                if not isinstance(data_obj, dict):
                    raise XJPathError('Accessed object must be a dict type '
                                      'for the key: "%s"' % top_key)
                if create_dict_path:
                    data_obj[top_key] = val_type()
                else:
                    return None, False
                if leftover:
                    return path_lookup(data_obj[top_key], leftover,
                                       create_dict_path)
                else:
                    return data_obj[top_key], True
            return None, False


def strict_path_lookup(data_obj, xj_path, force_type=None):
    """Looks up a xj path in the data_obj.

    :param dict|list data_obj: An object to look into.
    :param str xj_path: A path to extract data from.
    :param type force_type: A type that excepted to be.
    :return: Returns result or throws an exception if value is not found.
    """

    value, exists = path_lookup(data_obj, xj_path)
    if exists:
        if force_type is not None:
            if not isinstance(value, force_type):
                raise XJPathError('Found value is a wrong type',
                                  (xj_path, force_type))
        return value
    else:
        raise XJPathError('Path does not exist', (xj_path,))


class XJPath(object):

    def __init__(self, data_structure):
        self.data_structure = data_structure

    def __getitem__(self, item):
        try:
            value, exists = path_lookup(self.data_structure, item)
        except XJPathError as e:
            raise IndexError('Path error: %s' % str(item), *e.args)
        except TypeError as e:
            raise IndexError('Path error: %s' % str(item), *e.args)

        if exists:
            return value
        else:
            raise IndexError('Path does not exist %s' % str(item))

    def get(self, path, default=None):
        try:
            return self[path]
        except IndexError:
            return default


if __name__ == '__main__':
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description='JSON data structure lookup. This utility performs a XJPath'
        ' lookup on a given data structure and writes the result as JSON.')
    parser.add_argument('-i', '--input-file', default=None,
                        help='Path to JSON data structure. Default is STDIN.')
    parser.add_argument('-o', '--output-file', default=None,
                        help='Where to write XJPath result. Default is STDOUT.')
    parser.add_argument('-m', '--multiple-lines', action='store_true',
                        help='Expect multiple newline-deliminated JSON objects.')
    parser.add_argument('path', type=str,
                        help='XJPath expression to apply to data structure.')
    args = parser.parse_args()

    input_file = sys.stdin if args.input_file is None else open(args.input_file)
    output_file = (sys.stdout if args.output_file is None
                   else open(args.output_file, 'w'))

    def dump_xjpath(obj):
        xj = XJPath(obj)
        output_file.write(json.dumps(xj[args.path]))
        output_file.write('\n')

    with input_file, output_file:
        if args.multiple_lines:
            for line in input_file:
                line = line.strip()
                if line:
                    dump_xjpath(json.loads(line))
        else:
            dump_xjpath(json.load(input_file))
