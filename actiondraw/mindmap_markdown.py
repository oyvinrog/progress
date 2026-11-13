"""Occurrence-specific wiki links for Markdown mindmap notes.

Offsets are Python string offsets in the exact Markdown source, never Qt cursor
positions. Bindings belong to the authoring node, not its display occurrences.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import copy
import re
import uuid


WIKI = re.compile(r'\[\[([^\]\n]+)\]\]')
INLINE_CODE = re.compile(r'(?<!`)(`+)(?!`)[\s\S]*?(?<!`)\1(?!`)')


def tokens(text):
    excluded = []
    fence = None
    offset = 0
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line.rstrip('\n'))
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                excluded.append((fence[2], offset + len(line)))
                fence = None
        elif marker:
            fence = (marker[1][0], len(marker[1]), offset)
        elif line.startswith(('    ', '\t')):
            excluded.append((offset, offset + len(line)))
        offset += len(line)
    if fence:
        excluded.append((fence[2], len(text)))
    excluded.extend(m.span() for m in INLINE_CODE.finditer(text)
                    if not any(a <= m.start() < b for a, b in excluded))
    result = []
    for match in WIKI.finditer(text):
        prefix = text[:match.start()]
        escaped = (len(prefix) - len(prefix.rstrip('\\'))) % 2
        if not escaped and not any(a <= match.start() < b for a, b in excluded):
            result.append(match)
    return result


def reconcile(old, new, bindings, resolve=lambda name: None):
    """Carry identities only across unchanged source ranges; resolve new tokens."""
    matches = tokens(new)
    if not matches:
        return []
    ranges = [(0, 0, len(old))] if old == new else SequenceMatcher(None, old, new, autojunk=False).get_matching_blocks()
    carried = {}
    for item in bindings:
        for a, b, size in ranges:
            if a <= item['start'] and item['end'] <= a + size:
                carried[b + item['start'] - a] = item
                break
    result = []
    for match in matches:
        previous = carried.get(match.start())
        result.append({'start': match.start(), 'end': match.end(),
                       'id': previous['id'] if previous else uuid.uuid4().hex,
                       'target': previous['target'] if previous and previous['target'] else resolve(match.group(1))})
    return result


def prepare(text, bindings):
    """Replace wiki tokens with Markdown anchors without parsing code as links."""
    by_start = {b['start']: b for b in bindings}
    for match in reversed(tokens(text)):
        binding = by_start.get(match.start())
        href = 'mindmap:' + (binding['id'] if binding else 'unbound-' + str(match.start()))
        label = match.group(1).replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]')
        text = text[:match.start()] + f'[{label}]({href})' + text[match.end():]
    return text


def validate_bindings(data, mindmap):
    if not isinstance(data, dict):
        raise ValueError('Malformed mindmap text links')
    for node_id, fields in data.items():
        node = mindmap.find(node_id)
        if node is None or not isinstance(fields, dict) or set(fields) - {'text', 'note'}:
            raise ValueError('Malformed mindmap text link owner')
        for field, items in fields.items():
            spans = {m.span() for m in tokens(getattr(node, field) or '')}
            if not isinstance(items, list):
                raise ValueError('Malformed mindmap text link bindings')
            seen = set()
            starts = set()
            for b in items:
                if (not isinstance(b, dict) or set(b) != {'start', 'end', 'id', 'target'}
                        or type(b['start']) is not int or type(b['end']) is not int
                        or (b['start'], b['end']) not in spans or b['start'] in starts
                        or not isinstance(b['id'], str) or not b['id'] or b['id'] in seen
                        or (b['target'] is not None and not isinstance(b['target'], str))):
                    raise ValueError('Malformed mindmap text link binding')
                seen.add(b['id'])
                starts.add(b['start'])


def note_bindings(data):
    """Keep note links when loading snapshots from the earlier title-link editor."""
    return {node_id: {'note': copy.deepcopy(fields['note'])}
            for node_id, fields in data.items() if fields.get('note')}
