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


def include_hierarchy_and_siblings(diff_result):
    """
    Ensure all parents and siblings of changed lines are included in the output.
    """
    filtered_result = []
    context_stack = []  # Stack to maintain the hierarchy

    for symbol, (indent_level, line) in diff_result:
        # Remove irrelevant levels from the stack
        while context_stack and context_stack[-1][0] > indent_level:
            context_stack.pop()

        # Always include the current line if it has changes
        if symbol != " ":
            # Add all parents in the stack to the output
            for parent_level, parent_line in context_stack:
                if (parent_level, parent_line) not in [entry[1] for entry in filtered_result]:
                    filtered_result.append((" ", (parent_level, parent_line)))

            # Add the current line
            filtered_result.append((symbol, (indent_level, line)))

        # Track this line in the context stack
        context_stack.append((indent_level, line))

    return filtered_result


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
    filtered_diff = include_hierarchy_and_siblings(raw_diff)

    # Format the diff for display
    diff_output = format_diff(filtered_diff)

    # Print the diff
    print(diff_output)


if __name__ == "__main__":

    #r1 = "config1.txt"
    #r2 = "config2.txt"
    r1 = "router1.cfg"
    r2 = "router2.cfg"

    main(r1, r2)