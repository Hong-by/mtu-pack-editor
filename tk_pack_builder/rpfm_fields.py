"""Logical row order returned by the bundled RPFM server.

RPFM moves merged RGB fields to the end of decoded rows. Its older server
serializes only the raw definition, unlike versions exposing fields_processed.
Keep the raw definition intact for binary encoding.
"""


def field_names(table):
    definition = table['definition']
    if definition.get('fields_processed'):
        return [f['name'] for f in definition['fields_processed']]
    fields = definition['fields']
    colours = sorted({f['is_part_of_colour'] for f in fields if f.get('is_part_of_colour') is not None})
    names = []
    for field in fields:
        if field.get('is_part_of_colour') is not None:
            continue
        bits = field.get('is_bitwise', 0)
        if bits > 1:
            names.extend(f"{field['name']}_{index + 1}" for index in range(bits))
        else:
            names.append(field['name'])
    names.extend(f'__colour_{group}_hex' for group in colours)
    return names
