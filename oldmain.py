#!/usr/bin/env python3
import textfsm

# Define the path to the TextFSM template
TEMPLATE_PATH = "lldp_parse.textfsm"  # Update with the actual path to your template

# Sample LLDP table data
with open("lldp_data.txt", "r") as f:
    LLDP_DATA = f.read()
lldp_lines = LLDP_DATA.splitlines()
print([len(l) for l in lldp_lines])

# Define the path to the TextFSM template
TEMPLATE_PATH = "lldp_parse.textfsm"  # Update with the actual path to your template

# Function to parse LLDP data
def parse_lldp_data(data, template_path):
    with open(template_path) as template_file:
        # Initialize TextFSM parser
        fsm = textfsm.TextFSM(template_file)
        # Parse the data
        parsed_data = fsm.ParseText(data)

    # Extract column names and records
    headers = fsm.header
    return headers, parsed_data

# Run the parser
if __name__ == "__main__":
    try:
        headers, records = parse_lldp_data(LLDP_DATA, TEMPLATE_PATH)

        # Print parsed data
        print("\nParsed LLDP Data:")
        print(" | ".join(headers))
        print("-" * 50)
        for record in records:
            print(" | ".join(record))

    except Exception as e:
        print(f"Error parsing LLDP data: {e}")