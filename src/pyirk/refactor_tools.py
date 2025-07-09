from ipydex import IPS
import re

def change_entity_label(key, new_label, fpath):
    with open(fpath, "r", encoding="utf-8") as fp:
        src_lines = fp.readlines()

    # TODO: this might be more generic
    regex1 = re.compile(f"^{key}[ ]?=[ ]?(p|pyirk).create_(item|relation)")

    matching_lines = [(i, line) for i, line in enumerate(src_lines) if regex1.match(line)]

    assert len(matching_lines) == 1, "Unexpected number of matching lines"

    start_idx = matching_lines[0][0]
    end_idx = start_idx + 5

    # TODO: make this more robust
    assert len(src_lines) >= end_idx

    # TODO: This is not robust if label contains quotes or spans multiple lines
    regex2 = re.compile(r"""^\s*R1(?:__\w+)?\s*=\s*["|'](.*)["|']""")

    for i, line in enumerate(src_lines[start_idx:end_idx]):
        if match := regex2.match(line):
            break
    else:
        # break was not called
        msg = f"Could not find matching R1 pattern in lines {start_idx} to {end_idx} of {fpath}"
        raise ValueError(msg)

    original_label = match.group(1)
    defining_line = src_lines[start_idx + i]
    nbr_of_occurrences = defining_line.count(original_label)
    err_msg = f"original label unexpectedly occurs {nbr_of_occurrences} times in {fpath}:{start_idx + i}"
    assert nbr_of_occurrences == 1, err_msg
    new_defining_line = defining_line.replace(original_label, new_label)

    src_lines[start_idx + i] = new_defining_line

    new_src = "".join(src_lines)

    replacements = [
        (f'{key}["{original_label}"]', f'{key}["{new_label}"]'),
        (f"{key}['{original_label}']", f"{key}['{new_label}']"),
        # TODO: add underscore_version
    ]

    for rplm in replacements:
        new_src = new_src.replace(*rplm)

    with open(fpath, "w", encoding="utf-8") as fp:
        fp.write(new_src)