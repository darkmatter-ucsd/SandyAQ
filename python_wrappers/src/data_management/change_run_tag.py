'''
This is a tool to change the tag of a run to other tags, e.g. "trash"

!!!!! Not tested yet !!!!!

'''

import os
import glob
import json
import re
import numpy as np
import sys
import datetime

def _get_data_files(data_directories, pattern="meta_config*.json"):
    """
    Get all the data files in the given data directories
    Also search subdirectories
    """
    data_files = []
    for data_directory in data_directories:
        data_files.extend(glob.glob(os.path.join(data_directory, f"**/{pattern}"), recursive=True))

    return data_files
    
def _get_meta_data_from_file_name(data_file):
    """
    Get the meta data from the file name
    """
    match = re.match(r"meta_config_(\d+)_(\d+)_(\d{8})_(\d{6})\.json", data_file)

    # Extract the basic identifier information from the file name that matches the pattern
    if match:
        channel, threshold, date, time = match.groups()
        channel = int(channel)
        threshold = int(threshold)

        return channel, threshold, date, time
    else:
        print(f"File name {data_file} does not match the pattern")
        return None

v_meta_data_from_file_name = np.vectorize(_get_meta_data_from_file_name, otypes=[np.ndarray])

v_basename = np.vectorize(os.path.basename, otypes=[np.ndarray])
v_dirname = np.vectorize(os.path.dirname, otypes=[np.ndarray])

### step 1: create new meta data file (to be replaced in step 2)

def gen_new_metadata_w_updated_tags(data_folders, remove_run_tag, add_run_tag):
    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in data_folders:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files_name = _get_data_files(data_folders, pattern="meta_config*.json")
    print(f"Found {len(data_files_name)} meta data files in {data_folders}")

    file_name = v_basename(data_files_name)
    dir_name = v_dirname(data_files_name)

    #turn all list into np.array
    data_files_name = np.array(data_files_name) # path + file name
    file_name = np.array(file_name)
    dir_name = np.array(dir_name)
    
    assert(len(file_name)==len(dir_name))

    for i in range(len(file_name)):
        
        data_file = data_files_name[i]
        print(f"Processing {data_file}")

        with open(data_file, "r") as file:
            meta_data = json.load(file)
        new_meta_data = meta_data.copy()
        
        # checking the flags:
        
        
        
        new_meta_data["run_tag"] = str("fill_in_your_tag")

        new_file_name = os.path.join(dir_name[i], f"new_{file_name[i]}")

        with open(new_file_name, "w") as file:
            json.dump(new_meta_data, file, indent=4)
                
# replace the old meta data file by the new ones
def replace_old_metadata_w_new_metadata(new_metadata_files):

    existing_data_file = new_metadata_files.replace("new_meta_config_", "meta_config_")

    # remove the existing "meta_config_..." file
    os.remove(existing_data_file)

    # rename the "new_meta_config_..." to "meta_config_..."
    print(f"Renaming {new_metadata_files} to {existing_data_file}")
    os.rename(new_metadata_files, existing_data_file)
        
def main():
    
    

if __name__ == "__main__":
    main()