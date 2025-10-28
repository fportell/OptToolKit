"""
Advanced Query Parser for RSS Manager

Parses Lucene-style query syntax with field modifiers and boolean operators.
Implements Phase 1 (field modifiers) + Minimal Phase 2 (NOT operator).

Supported syntax:
- Field modifiers: lan:en, country:USA, type:MED, scope:National, sub:NAT, title:health, url:cdc.gov
- NOT operator: lan:en NOT country:USA
- Implicit AND: Multiple space-separated terms are combined with AND
- Quoted strings: title:"New York Times"

Example queries:
- lan:en type:MED country:USA
- lan:en NOT country:USA
- title:health lan:en
- type:MED NOT scope:International
"""

import re
from typing import Dict, List, Any, Optional


class QueryParseError(Exception):
    """Exception raised for query parsing errors."""
    pass


# Field modifier mapping: alias -> actual column name
FIELD_MAPPING = {
    'lan': 'language',
    'language': 'language',
    'country': 'country',
    'type': 'type',
    'scope': 'scope',
    'sub': 'subdivision',
    'subdivision': 'subdivision',
    'title': 'title',
    'url': 'url',
}

# Type code expansion: shortcode -> full name
TYPE_CODES = {
    'MED': 'Media Outlet',
    'GOV': 'Government Agency',
    'PHA': 'Public Health Agency',
    'NGO': 'Non-Governmental Organization',
    'ACA': 'Academic Institution',
    'PRO': 'Professional Association',
    'SCI': 'Scientific Journal',
}

# Field types: exact-match vs FTS5 search
EXACT_MATCH_FIELDS = {'language', 'country', 'type', 'scope', 'subdivision'}
FTS_FIELDS = {'title', 'url'}


def tokenize(query_string: str) -> List[str]:
    """
    Tokenize query string, preserving quoted strings.

    Args:
        query_string: Raw query string from user

    Returns:
        List of tokens (field:value pairs, operators, or standalone terms)

    Example:
        'lan:en title:"New York" NOT country:USA'
        -> ['lan:en', 'title:"New York"', 'NOT', 'country:USA']
    """
    tokens = []
    current_token = []
    in_quotes = False
    escape_next = False

    for char in query_string:
        if escape_next:
            current_token.append(char)
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '"':
            in_quotes = not in_quotes
            current_token.append(char)
            continue

        if char.isspace() and not in_quotes:
            if current_token:
                tokens.append(''.join(current_token))
                current_token = []
            continue

        current_token.append(char)

    # Add final token
    if current_token:
        tokens.append(''.join(current_token))

    return tokens


def strip_quotes(value: str) -> str:
    """Remove surrounding quotes from a value."""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def expand_type_code(value: str) -> str:
    """
    Expand type code to full name if it's a recognized code.

    Args:
        value: Type value (e.g., 'MED' or 'Media Outlet')

    Returns:
        Full type name
    """
    value_upper = value.upper()
    if value_upper in TYPE_CODES:
        return TYPE_CODES[value_upper]
    return value


def parse_field_modifier(token: str) -> Optional[Dict[str, Any]]:
    """
    Parse a field:value token.

    Args:
        token: Token like 'lan:en' or 'title:"New York"'

    Returns:
        Dict with 'field', 'value', 'searchType', or None if not a field modifier

    Raises:
        QueryParseError: If field name is invalid
    """
    # Match field:value pattern
    match = re.match(r'^([a-zA-Z_]+):(.+)$', token)
    if not match:
        return None

    field_name = match.group(1).lower()
    field_value = match.group(2)

    # Validate field name
    if field_name not in FIELD_MAPPING:
        available = ', '.join(sorted(set(FIELD_MAPPING.keys())))
        raise QueryParseError(
            f"Unknown field '{field_name}'. Available fields: {available}"
        )

    # Map to actual column name
    actual_field = FIELD_MAPPING[field_name]

    # Strip quotes from value
    field_value = strip_quotes(field_value)

    # Expand type codes
    if actual_field == 'type':
        field_value = expand_type_code(field_value)

    # Determine search type
    search_type = 'fts' if actual_field in FTS_FIELDS else 'exact'

    return {
        'field': actual_field,
        'value': field_value,
        'searchType': search_type,
    }


class TokenStream:
    """Helper class for parsing token stream with lookahead."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        """Look at current token without consuming it."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self):
        """Consume and return current token."""
        if self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            self.pos += 1
            return token
        return None

    def is_at_end(self):
        """Check if we've consumed all tokens."""
        return self.pos >= len(self.tokens)


def parse_or_expression(stream: TokenStream) -> Dict[str, Any]:
    """
    Parse OR expression (lowest precedence).

    Grammar: or_expr := and_expr ('OR' and_expr)*
    """
    left = parse_and_expression(stream)

    while stream.peek() and stream.peek().upper() == 'OR':
        stream.consume()  # Consume 'OR'
        right = parse_and_expression(stream)
        left = {
            'type': 'BINARY_OP',
            'operator': 'OR',
            'left': left,
            'right': right
        }

    return left


def parse_and_expression(stream: TokenStream) -> Dict[str, Any]:
    """
    Parse AND expression (medium precedence).

    Grammar: and_expr := not_expr ('AND' not_expr | not_expr)*

    Note: Handles both explicit AND and implicit AND (space-separated terms)
    """
    left = parse_not_expression(stream)

    while stream.peek():
        token = stream.peek()
        token_upper = token.upper()

        if token_upper == 'AND':
            stream.consume()  # Consume 'AND'
            right = parse_not_expression(stream)
            left = {
                'type': 'BINARY_OP',
                'operator': 'AND',
                'left': left,
                'right': right
            }
        elif token_upper == 'OR':
            # Stop at OR (lower precedence)
            break
        elif token_upper == 'NOT' or ':' in token:
            # Implicit AND: another NOT expression or field:value without explicit operator
            right = parse_not_expression(stream)
            left = {
                'type': 'BINARY_OP',
                'operator': 'AND',
                'left': left,
                'right': right
            }
        else:
            break

    return left


def parse_not_expression(stream: TokenStream) -> Dict[str, Any]:
    """
    Parse NOT expression (highest precedence).

    Grammar: not_expr := 'NOT' not_expr | primary
    """
    token = stream.peek()

    if token and token.upper() == 'NOT':
        stream.consume()  # Consume 'NOT'
        operand = parse_not_expression(stream)  # NOT is right-associative
        return {
            'type': 'UNARY_OP',
            'operator': 'NOT',
            'operand': operand
        }

    return parse_primary(stream)


def parse_primary(stream: TokenStream) -> Dict[str, Any]:
    """
    Parse primary expression (field:value).

    Grammar: primary := field:value
    """
    token = stream.consume()

    if not token:
        raise QueryParseError("Unexpected end of query")

    # Parse field modifier
    field_mod = parse_field_modifier(token)

    if not field_mod:
        raise QueryParseError(
            f"Invalid token '{token}'. Expected field:value format "
            f"(e.g., lan:en, title:health)"
        )

    # Return as a FIELD node
    return {
        'type': 'FIELD',
        'field': field_mod['field'],
        'value': field_mod['value'],
        'searchType': field_mod['searchType']
    }


def parse_query(query_string: str) -> Dict[str, Any]:
    """
    Parse advanced query string into AST.

    Full Phase 2 implementation:
    - Field modifiers (lan:, country:, type:, etc.)
    - AND, OR, NOT operators
    - Operator precedence: NOT > AND > OR
    - Implicit AND for space-separated terms

    Args:
        query_string: Query string from user

    Returns:
        AST dict with tree structure:
        {
            'type': 'BINARY_OP' | 'UNARY_OP' | 'FIELD',
            'operator': 'AND' | 'OR' | 'NOT',
            'left': <AST node>,    # for BINARY_OP
            'right': <AST node>,   # for BINARY_OP
            'operand': <AST node>, # for UNARY_OP
            'field': str,          # for FIELD
            'value': str,          # for FIELD
            'searchType': str      # for FIELD
        }

    Raises:
        QueryParseError: If query has syntax errors
    """
    if not query_string or not query_string.strip():
        raise QueryParseError("Query string cannot be empty")

    # Tokenize
    tokens = tokenize(query_string.strip())

    if not tokens:
        raise QueryParseError("Query string cannot be empty")

    # Parse using recursive descent parser
    stream = TokenStream(tokens)

    try:
        ast = parse_or_expression(stream)

        # Check for unconsumed tokens
        if not stream.is_at_end():
            remaining = ', '.join(stream.tokens[stream.pos:])
            raise QueryParseError(f"Unexpected tokens after parsing: {remaining}")

        return ast
    except QueryParseError:
        raise
    except Exception as e:
        raise QueryParseError(f"Parse error: {str(e)}")


def is_advanced_query(query_string: str) -> bool:
    """
    Detect if a query string uses advanced syntax.

    Args:
        query_string: Query string to check

    Returns:
        True if query uses field modifiers (field:value pattern)
    """
    if not query_string:
        return False

    # Check for field modifier pattern
    return bool(re.search(r'\w+:', query_string))


# Example usage and testing
if __name__ == '__main__':
    # Test cases
    test_queries = [
        'lan:en type:MED',
        'lan:en NOT country:USA',
        'title:health lan:en',
        'type:MED NOT scope:International',
        'title:"New York Times" lan:en',
        'country:BRA type:MED',
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            ast = parse_query(query)
            print(f"  Conditions: {len(ast['conditions'])}")
            for cond in ast['conditions']:
                negation = "NOT " if cond.get('negated') else ""
                print(f"    {negation}{cond['field']}:{cond['value']} ({cond['searchType']})")
        except QueryParseError as e:
            print(f"  ERROR: {e}")
