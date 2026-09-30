import os

# 1. Rename assemble_commercial_eda.py to assemble_soc.py
old_name = "eda_framework/assemble_commercial_eda.py"
new_name = "eda_framework/assemble_soc.py"
if os.path.exists(old_name):
    os.rename(old_name, new_name)

# 2. Text replacements across all files
replacements = {
    "tcl::": "tcl::",
    "Commercial EDA": "Commercial EDA",
    "commercial_eda": "commercial_eda",
    "derivgen:": "derivgen:",
    "Commercial Vendor": "Commercial Vendor",
    "Commercial Commercial EDA": "Proprietary EDA tools",
    "Commercial": "Commercial",
    "Vendor": "Vendor"
}

def scrub_directory(directory):
    for root, dirs, files in os.walk(directory):
        if ".git" in root: continue
        for file in files:
            if file.endswith(".py") or file.endswith(".md") or file.endswith(".core") or file.endswith(".v"):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                modified = False
                for old, new in replacements.items():
                    if old in content:
                        content = content.replace(old, new)
                        modified = True
                
                if modified:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"Scrubbed: {filepath}")

scrub_directory(".")
