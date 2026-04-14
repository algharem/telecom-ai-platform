import os
import re
import sys

def parse_markdown_and_build_project(md_file_path, output_base_dir="telecom-ai-platform"):
    """
    Parses a markdown file to extract code blocks and saves them to a structured directory.
    """
    
    if not os.path.exists(md_file_path):
        print(f"Error: File '{md_file_path}' not found.")
        return

    with open(md_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # State variables
    current_file_path = None
    code_block_content = []
    inside_code_block = False
    files_created = set()
    dirs_created = set()
    
    # Ensure base directory exists
    if not os.path.exists(output_base_dir):
        os.makedirs(output_base_dir)
        print(f"Created base directory: {output_base_dir}")

    lines = content.split('\n')
    
    # Regex to find file paths in headers. 
    # Looks for patterns like `dir/file.py` or just `file.py` inside backticks
    # or standard headers like "### 14. Dockerfile"
    file_path_regex = re.compile(r'`([^`]+\.[a-z]+)`') # Matches `filename.ext`
    simple_file_regex = re.compile(r'###\s+\d+\.\s+([a-zA-Z0-9_]+(?:file|File))') # Matches "### 14. Dockerfile"
    
    print("--- Starting Extraction ---")

    for line in lines:
        # Check for headers that define files
        if line.startswith("### "):
            # Try to find `filename` pattern
            match = file_path_regex.search(line)
            if match:
                current_file_path = match.group(1)
            else:
                # Fallback for headers like "### 14. Dockerfile"
                simple_match = simple_file_regex.search(line)
                if simple_match:
                    current_file_path = simple_match.group(1)
                else:
                    # If no file detected in this header, reset path
                    current_file_path = None

        # Handle code block delimiters
        if line.strip().startswith("```"):
            if inside_code_block:
                # End of block - Save the file
                if current_file_path:
                    full_path = os.path.join(output_base_dir, current_file_path)
                    dir_name = os.path.dirname(full_path)
                    
                    # Create directory if needed
                    if dir_name and not os.path.exists(dir_name):
                        os.makedirs(dir_name, exist_ok=True)
                        if dir_name not in dirs_created:
                            print(f"Created directory:  {dir_name}")
                            dirs_created.add(dir_name)
                    
                    # Write file
                    final_content = "\n".join(code_block_content)
                    with open(full_path, 'w', encoding='utf-8') as cf:
                        cf.write(final_content)
                    
                    print(f"Created file:       {full_path}")
                    files_created.add(full_path)
                
                # Reset state
                code_block_content = []
                inside_code_block = False
                current_file_path = None
            
            else:
                # Start of block
                inside_code_block = True
                # Clear content just in case
                code_block_content = []
        
        elif inside_code_block:
            code_block_content.append(line)

    # Post-processing: Create missing __init__.py files for Python packages
    print("\n--- Initializing Python Packages ---")
    python_dirs = set()
    
    # Find all directories that contain .py files
    for root, dirs, files in os.walk(output_base_dir):
        for file in files:
            if file.endswith(".py"):
                python_dirs.add(root)
    
    # Add __init__.py where missing
    for p_dir in python_dirs:
        init_file = os.path.join(p_dir, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                # Optional: Add a comment or pass
                f.write("# Auto-generated __init__.py\n")
            print(f"Initialized:        {init_file}")

    # Create empty data directory if specified in architecture
    data_dir = os.path.join(output_base_dir, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        gitkeep = os.path.join(data_dir, ".gitkeep")
        with open(gitkeep, 'w') as f:
            pass
        print(f"Created data dir:   {data_dir}")

    print("\n--- Build Complete ---")
    print(f"Total files extracted: {len(files_created)}")

if __name__ == "__main__":
    # Default to 'phase1.md' or accept command line argument
    input_file = "phase3.md"
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    
    parse_markdown_and_build_project(input_file)