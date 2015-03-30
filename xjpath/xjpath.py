"""XJPATH simplifies access to the python data structures using relatively
simple path syntax.

A returned element is the actual pointer to the object that can be modified
in place if it is possible. However, in case if returned value is a tuple
it is a copied list of values that can not be modified. For example a list
of dictionary values is a good example.

Let's assume we have the following data structure:

>>> d = {'data': {
  'a_array': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  'b_dict': {'a': 'xxx', 'b': 'yyy', 'c': 'zzz'},
  'c_array': [{'v1': 'vdata1'}, {'v2': 'vdata2'}]}}

Get value ['data']['b_dict']['a']:

>>> path_lookup(d, 'data.b_dict.a')
('xxx', True)

Get first element of a_array:
>>> path_lookup(d, 'data.a_array.@first')
(0, True)

Get the last element of a_array:

>>> path_lookup(d, 'data.a_array.@last')
(10, True)

Get a second element of a_array:

>>> path_lookup(d, 'data.a_array.@1')
(1, True)

Get element before a last one:

>>> path_lookup(d, 'data.a_array.@-2')
(9, True)

Get all elements of a_array as non modifiable tuple:
>>> path_lookup(d, 'data.a_array.*')
((1, 2, 3, 4, 5, 6, 7, 8, 9, 0), True)

Get all values of b_dict as a tuple:
>>> path_lookup(d, 'data.b_dict.*')
((1, 2, 3, 4, 5, 6, 7, 8, 9, 0), True)

>>> path_lookup(d, 'data.b_dict.*')
(('yyy', 'zzz', 'xxx'), True)

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
                raise StopIteration
            word_chars.clear()

    yield ''.join(word_chars)


def _full_sub_array(data_obj, xj_path):
    """Retrieves all array or dictionary elements for '*' JSON path marker.

    :param dict|list data_obj: The current data object.
    :param str xj_path: A json path.
    :return: tuple with two values: first is a result and second
             a boolean flag telling if this value exists or not.
    """

    if isinstance(data_obj, list):
        if xj_path:
            res = []
            for d in data_obj:
                val, exists = path_lookup(d, xj_path)
                if exists:
                    res.append(val)
            return tuple(res), True
        else:
            return tuple(data_obj), True
    elif isinstance(data_obj, dict):
        if xj_path:
            res = []
            for d in data_obj.values():
                val, exists = path_lookup(d, xj_path)
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


def _single_array_element(data_obj, xj_path, array_path):
    """Retrieves a single array for a '@' JSON path marker.

    :param list data_obj: The current data object.
    :param str xj_path: A json path.
    :param str array_path: A lookup key.
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
                return path_lookup(value, xj_path)
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

    root_key, *sub_key = xj_path.rsplit('.', 1)
    if sub_key:
        return root_key, sub_key[0]
    else:
        if root_key and root_key != '.':
            return None, root_key
        else:
            raise XJPathError('Path cannot be empty', (xj_path,))


def _set_dict_value(data_obj, xj_path, key, value):
    """Set a dictionary key->value.

    :param dict data_obj: Dictionary data object.
    :param str xj_path: xj path.
    :param str key: A dictionary key.
    :param value: A value that should be assigned.
    """

    value_ref = strict_path_lookup(data_obj, xj_path, force_type=dict)

    value_ref[key] = value


def _update_dict_value(data_obj, xj_path, key, updater):
    """Update value under at given dictionary key.

    :param dict data_obj: Dictionary data object.
    :param str xj_path: xj path.
    :param str key: A dictionary key.
    :param (object) -> object updater: Object updater callable.
    """

    value_ref = strict_path_lookup(data_obj, xj_path, force_type=dict)
    value_ref[key] = updater(value_ref.get(key, None))


def _del_dict_value(data_obj, xj_path, key):
    """Delete a dictionary key->value pair

    :param dict data_obj: Dictionary data object.
    :param str xj_path: xj path.
    :param str key: A dictionary key.
    """

    value_ref = strict_path_lookup(data_obj, xj_path, force_type=dict)
    value_ref.pop(key, None)


def _set_array_value(data_obj, xj_path, array_idx_key, value):
    """Set a value into array to a provided index. Index must exist.

    :param dict|list data_obj: Dictionary data object.
    :param str xj_path: xj path.
    :param str array_idx_key: An array index specification.
    :param value: A value that should be assigned.
    """

    value_ref = strict_path_lookup(data_obj, xj_path, force_type=list)

    try:
        value_ref[_get_array_index(array_idx_key)] = value
    except IndexError:
        raise XJPathError('Array index error', (xj_path, array_idx_key))


def _update_array_value(data_obj, xj_path, array_idx_key, updater):
    """Update value at given index in the array.

    :param dict|list data_obj: Dictionary data object.
    :param str xj_path: xj path.
    :param str array_idx_key: An array index specification.
    :param (object) -> object updater: Object updater callable.
    """

    value_ref = strict_path_lookup(data_obj, xj_path, force_type=list)
    try:
        updated_value = updater(value_ref[_get_array_index(array_idx_key)])
        value_ref[_get_array_index(array_idx_key)] = updated_value
    except IndexError:
        raise XJPathError('Array index error', (xj_path, array_idx_key))


def _del_array_value(data_obj, xj_path, array_idx_key):
    """Delete value from array according to its index.

    :param dict|list data_obj: Dictionary data object.
    :param str xj_path: xj path.
    :param str array_idx_key: An array index specification.
    """

    value_ref = strict_path_lookup(data_obj, xj_path, force_type=list)
    try:
        value_ref.pop(_get_array_index(array_idx_key))
    except IndexError:
        raise XJPathError('Array index error', (xj_path, array_idx_key))


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
                                  '@first or @last') from None


_KEY_SPLIT = {
    '$': str,
    '#': int,
    '%': float,
    '{}': dict,
    '[]': list,
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


def path_lookup(data_obj, xj_path):
    """Looks up a xj path in the data_obj.

    :param dict|list data_obj: An object to look into.
    :param str xj_path: A path to extract data from.
    :return: A tuple where 0 value is an extracted value and a second
             field that tells if value either was found or not found.
    """

    if not xj_path or xj_path == '.':
        return data_obj, True

    top_key, *leftover = split(xj_path, '.', maxsplit=1)
    leftover = leftover[0] if leftover else None
    if top_key == '*':
        return _full_sub_array(data_obj, leftover)
    elif top_key.startswith('@'):
        return _single_array_element(data_obj, leftover, top_key)
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
                return path_lookup(value, leftover)
            else:
                return value, True
        else:
            if val_type is not None:
                if not isinstance(data_obj, dict):
                    raise XJPathError('Accessed object must be a dict type '
                                      'for the key: "%s"' % top_key)
                data_obj[top_key] = val_type()
                if leftover:
                    return path_lookup(data_obj[top_key], leftover)
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

