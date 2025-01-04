import difflib


def parse_config(config_lines):
    """
    Parse configuration lines into a structured format.
    Returns a list of tuples: (indentation_level, line).
    """
    parsed_config = []
    for line in config_lines:
        stripped_line = line.rstrip()  # Remove trailing whitespace
        indent_level = len(line) - len(line.lstrip())  # Count leading spaces
        parsed_config.append((indent_level, stripped_line))
    return parsed_config


def diff_configs(config1, config2):
    """
    Compute the difference between two parsed configurations.
    Returns a list of differences while preserving context.
    """
    diff_result = []
    matcher = difflib.SequenceMatcher(None, config1, config2)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for line in config1[i1:i2]:
                diff_result.append((" ", line))
        elif tag == 'replace':
            for line in config1[i1:i2]:
                diff_result.append(("-", line))
            for line in config2[j1:j2]:
                diff_result.append(("+", line))
        elif tag == 'delete':
            for line in config1[i1:i2]:
                diff_result.append(("-", line))
        elif tag == 'insert':
            for line in config2[j1:j2]:
                diff_result.append(("+", line))

    return diff_result


def include_hierarchy(diff_result):
    """
    Include all parent and sibling lines of changed sections.
    """
    result_with_context = []
    context_stack = []  # Stack to track the hierarchy of parents

    for symbol, (indent_level, line) in diff_result:
        # Remove irrelevant levels from the stack
        while context_stack and context_stack[-1][0] >= indent_level:
            context_stack.pop()

        if symbol != " ":
            # Include all siblings and parents of this change
            if context_stack:
                parent_level, parent_line = context_stack[-1]
                for sibling_symbol, sibling in diff_result:
                    sibling_level, sibling_line = sibling
                    if sibling_level == parent_level and sibling_line not in [r[1] for r in result_with_context]:
                        result_with_context.append((sibling_symbol, sibling))
            result_with_context.append((symbol, (indent_level, line)))

        # Add the current line to the context stack for future hierarchy tracking
        context_stack.append((indent_level, line))

    return result_with_context


def format_diff(diff_result):
    """
    Format the diff output to respect indentation levels.
    """
    formatted_diff = []
    for symbol, (indent_level, line) in diff_result:
        formatted_diff.append(f"{symbol}{' ' * indent_level}{line}")
    return "\n".join(formatted_diff)


def main(config1_path, config2_path):
    # Read the configuration files
    with open(config1_path, 'r') as file1, open(config2_path, 'r') as file2:
        config1_lines = file1.readlines()
        config2_lines = file2.readlines()

    # Parse the configurations to capture indentation levels
    parsed_config1 = parse_config(config1_lines)
    parsed_config2 = parse_config(config2_lines)

    # Generate the diff
    raw_diff = diff_configs(parsed_config1, parsed_config2)

    # Include hierarchy and siblings for changed sections
    diff_with_context = include_hierarchy(raw_diff)

    # Format the diff for display
    diff_output = format_diff(diff_with_context)

    # Print the diff
    print(diff_output)


if __name__ == "__main__":
    # Example usage: python diff_configs.py config1.txt config2.txt
#    import sys
#   if len(sys.argv) != 3:
#        print("Usage: python diff_configs.py <config1_path> <config2_path>")
#        sys.exit(1)
#
    r1 = "router1.cfg"
    r2 = "router2.cfg"
    main(r1, r2)