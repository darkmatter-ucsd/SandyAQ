'''
This is a tool to unify, if possible and desired, the data format of the meta-data json files.
'''


import os
import glob
import json
import re
import numpy as np
import sys
import datetime
import configparser


DATA_FOLDERS = [
    "/kalinka/storage/darkmatter/XENONnT/sk6801/UCSD_data/raw_data/"
    # "/home/daqtest/DAQ/SandyAQ_vera/SandyAQ/softlink_to_data/all_data/202405_202406_GXe_threshold/",
    # "/home/daqtest/DAQ/SandyAQ_vera/SandyAQ/softlink_to_data/all_data/202405_202409_GXe",
    # "/home/daqtest/DAQ/SandyAQ_vera/SandyAQ/softlink_to_data/all_data/202409_tests",
    # "/home/daqtest/DAQ/SandyAQ_vera/SandyAQ/softlink_to_data/all_data/202410_LXe",
    # "/home/daqtest/DAQ/SandyAQ_vera/SandyAQ/softlink_to_data/all_data/202410_LXe_new"
    # Add more data folders as needed, need to be an absolute path
    # "/home/daqtest/DAQ/SandyAQ_vera/SandyAQ/softlink_to_data/all_data/202410_LXe/20241018_all_T98_all_voltages_3.0sig/threshold_calibration/"
]

class Info:
    def __init__(self, channel, threshold, date, time):
        self.channel = channel
        self.threshold = threshold
        self.date = date
        self.time = time

def check_dir_path():
    # find the files that match the criteria
    #     # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

def get_data_files(data_directories, pattern="meta_config*.json"):
    """
    Get all the data files in the given data directories
    Also search subdirectories
    """
    data_files = []
    for data_directory in data_directories:
        data_files.extend(glob.glob(os.path.join(data_directory, f"**/{pattern}"), recursive=True))

    return data_files
    
def get_meta_data_from_file_name(data_file):
    """
    Get the meta data from the file name
    """
    
    match = re.match(r"meta_config_(\d+)_(\d+)_(\d{8})_(\d{6})\.json", data_file)

    # Extract the basic identifier information from the file name that matches the pattern
    if match:
        channel, threshold, date, time = match.groups()
        date = str(date)
        time = str(time)
        channel = int(channel)
        threshold = int(threshold)

    else:
        match = re.match(r"meta_config_all_(\d{8})_(\d{6})\.json", data_file)

        if match:
            date, time = match.groups()
            channel, threshold = None, None
        
        else:
            print(f"File name {data_file} does not match the pattern")

            return None
        
    meta_data_info = Info(channel, threshold, date, time)
        
    return meta_data_info
v_meta_data_from_file_name = np.vectorize(get_meta_data_from_file_name, otypes=[np.ndarray])

v_basename = np.vectorize(os.path.basename, otypes=[np.ndarray])
v_dirname = np.vectorize(os.path.dirname, otypes=[np.ndarray])

def get_test_name(full_path):
    dir_name = os.path.dirname(full_path)
    test_name = os.path.basename(full_path)[-20:]
    return dir_name+"|"+test_name

v_get_test_name = np.vectorize(get_test_name, otypes=[np.ndarray])

def step_0_check_item():
    count=0
    
    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS, pattern="meta_config*.json")
    print(f"Found {len(data_files_name)} meta data files in {DATA_FOLDERS}")

    file_name = v_basename(data_files_name)
    dir_name = v_dirname(data_files_name)

    #turn all list into np.array
    data_files_name = np.array(data_files_name) # path + file name
    file_name = np.array(file_name)
    dir_name = np.array(dir_name)
    
    assert(len(file_name)==len(dir_name))
    
    for i in range(len(file_name)):
        
        data_file = data_files_name[i]
        # print(f"Processing {data_file}")

        with open(data_file, "r") as file:
            meta_data = json.load(file)
            
        # check if variable already exist
        if "run_tag" not in meta_data:
            print(f'channel is not in {data_file}.')
            count +=1

    print(count)

    return


### step 1: create new meta data file (to be replaced in step 2)
### check if everything make sense in the new meta data
def step_1_add_items():
    
    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS, pattern="meta_config*.json")
    print(f"Found {len(data_files_name)} meta data files in {DATA_FOLDERS}")

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
        rewrite_bool = False
        # if DC_OFFSET is not in the meta data, add it
        if "DC_OFFSET" not in new_meta_data:
            new_meta_data["DC_OFFSET"] = "+40"
            rewrite_bool = True

        if "data_taking_mode" not in new_meta_data:
            new_meta_data["data_taking_mode"] = ""
            rewrite_bool = True

        if "post_trigger" not in new_meta_data:
            new_meta_data["post_trigger"] = int(60)
            rewrite_bool = True

        if rewrite_bool:
            new_file_name = os.path.join(dir_name[i], f"new_{file_name[i]}")
            with open(new_file_name, "w") as file:
                json.dump(new_meta_data, file, indent=4)

def step_1_edit_item():
    
    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS, pattern="meta_config*.json")
    print(f"Found {len(data_files_name)} meta data files in {DATA_FOLDERS}")

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

        new_meta_data["data_taking_mode"] = "all_channels"

        new_meta_data["board_0_channels"] = np.arange(0,16).tolist()
        new_meta_data["board_1_channels"] = np.arange(16,24).tolist()

        new_file_name = os.path.join(dir_name[i], f"new_{file_name[i]}")
        with open(new_file_name, "w") as file:
            json.dump(new_meta_data, file, indent=4)

def step_1_edit_item_from_config():
    
    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS, pattern="meta_config*.json")
    print(f"Found {len(data_files_name)} meta data files in {DATA_FOLDERS}")

    file_name = v_basename(data_files_name)
    dir_name = v_dirname(data_files_name)
    meta_data_info = v_meta_data_from_file_name(file_name)

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

        # remove all "DC_offset" key from new_meta_data
        if "DC_offset" in new_meta_data:
            del new_meta_data['DC_offset']

        # get the channel number for each board
        if meta_data_info[i].channel != None:
            
            config_file_path = os.path.join(dir_name[i], "DAQ_config/", f"config_{meta_data_info[i].channel}_{meta_data_info[i].threshold}.ini")
            # Check if the config file exists
            if not os.path.isfile(config_file_path):
                raise ValueError(f"Config file {config_file_path} does not exist")
            
            # Read the config file
            config = configparser.ConfigParser()
            config.read(config_file_path)

            new_meta_data["data_taking_mode"] = "single_channel"
            
            new_meta_data["post_trigger"] = float(config.get("BOARD-0", "POST_TRIGGER"))
            
            test_channel = 0
            # try different channel on board until we find the DC_OFFSET
            while(test_channel < 16):
                if config.has_option(f"BOARD-0_CHANNEL-{test_channel}", "DC_OFFSET"):
                    new_meta_data["DC_OFFSET"] = config.get(f"BOARD-0_CHANNEL-{test_channel}", "DC_OFFSET")
                    board_number = 0
                    break

                if config.has_option(f"BOARD-1_CHANNEL-{test_channel}", "DC_OFFSET"):
                    new_meta_data["DC_OFFSET"] = config.get(f"BOARD-1_CHANNEL-{test_channel}", "DC_OFFSET")
                    board_number = 1
                    break

                test_channel += 1   

            channel_list = config.get(f"BOARD-{board_number}", "CHANNEL_LIST")
            if (len(channel_list) == 0):
                raise ValueError(f"CHANNEL_LIST is empty in {config_file_path}")
            channel_list = channel_list.split(" ")
            channel_list = [int(x) for x in channel_list]
            new_meta_data[f"board_{board_number}_channels"] = channel_list

            new_file_name = os.path.join(dir_name[i], f"new_{file_name[i]}")
            with open(new_file_name, "w") as file:
                json.dump(new_meta_data, file, indent=4)

        elif meta_data_info[i].channel == None:
            
            config_file_path = os.path.join(dir_name[i], "DAQ_config/", f"config_all_{meta_data_info[i].date}_{meta_data_info[i].time}.ini")
            # Check if the config file exists
            if not os.path.isfile(config_file_path):
                config_file_path = os.path.join(dir_name[i], "DAQ_config/", f"config_all.ini")

                if not os.path.isfile(config_file_path):
                    raise ValueError(f"Config file {config_file_path} does not exist")
            
            # Read the config file
            config = configparser.ConfigParser()
            config.read(config_file_path)

            new_meta_data["data_taking_mode"] = "all_channels"
            
            new_meta_data["post_trigger"] = int(config.get("BOARD-0", "POST_TRIGGER"))
            
            new_meta_data["DC_OFFSET"] = config.get(f"BOARD-0_CHANNEL-0", "DC_OFFSET")

            channel_list = config.get(f"BOARD-0", "CHANNEL_LIST")
            if (len(channel_list) > 0):
                channel_list = channel_list.split(" ")
                channel_list = [int(x) for x in channel_list]
                new_meta_data["board_0_channels"] = channel_list
                n_channel_board_0 = len(channel_list)
            
            channel_list = config.get(f"BOARD-1", "CHANNEL_LIST")
            if (len(channel_list) > 0):
                channel_list = channel_list.split(" ")
                channel_list = [int(x) + n_channel_board_0 for x in channel_list]
                new_meta_data["board_1_channels"] = channel_list

            new_file_name = os.path.join(dir_name[i], f"new_{file_name[i]}")
            with open(new_file_name, "w") as file:
                json.dump(new_meta_data, file, indent=4)

        else:
            raise ValueError("Channel number has wrong format")
    
def step1_add_runtime():

    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS)
    print(f"Found {len(data_files_name)} data files in {DATA_FOLDERS}")

    file_name = v_basename(data_files_name)
    dir_name = v_dirname(data_files_name)
    channel, threshold, date, time = v_meta_data_from_file_name(file_name)

    #turn all list into np.array
    data_files_name = np.array(data_files_name) # path + file name
    file_name = np.array(file_name)
    dir_name = np.array(dir_name)
    channel = np.array(channel)
    threshold = np.array(threshold)
    date = np.array(date)
    time = np.array(time)

    date_time = np.array([f"{d}_{t}" for d, t in zip(date, time)])
    unique_id = np.array([f"{dir}!!!{dt}" for dir, dt in zip(dir_name, date_time)])
    unique_id = np.unique(unique_id)

    for id in unique_id:

        unique_path, unique_date_time = id.split("!!!")

        # create mask
        mask = (dir_name == unique_path) & (date_time == unique_date_time)

        # after filtering with mask, sort the data_files by channel
        sorted_data_file = data_files_name[mask][channel[mask].argsort()]

        if len(sorted_data_file) < 2:
            print(f"Found less than 2 files for {id}")
            continue
        
        print(f"Loading {sorted_data_file[0]}")
        with open(sorted_data_file[0], "r") as file:
            first_meta_data = json.load(file)
                        
        previous_runtime = first_meta_data.get("runtime")

        if previous_runtime is not None:
            previous_runtime = datetime.datetime.strptime(previous_runtime, "%H:%M:%S.%f")

            for data_file in sorted_data_file[1:]:

                print(f"Processing {data_file}")

                with open(data_file, "r") as file:
                    meta_data = json.load(file)
                
                _runtime = datetime.datetime.strptime(meta_data.get("runtime"), "%H:%M:%S.%f")

                new_runtime = _runtime - previous_runtime

                new_meta_data = meta_data.copy()
                new_meta_data["runtime"] = str(new_runtime)

                _base_name = os.path.basename(data_file)
                _path_name = os.path.dirname(data_file)
                new_file_name = os.path.join(_path_name, f"new_{_base_name}")

                with open(new_file_name, "w") as file:
                    json.dump(new_meta_data, file, indent=4)

                previous_runtime = _runtime

def step1_add_metadata_from_filename():
    
    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS, pattern="meta_config*.json")
    print(f"Found {len(data_files_name)} meta data files in {DATA_FOLDERS}")

    file_name = v_basename(data_files_name)
    dir_name = v_dirname(data_files_name)

    #turn all list into np.array
    data_files_name = np.array(data_files_name) # path + file name
    file_name = np.array(file_name)
    dir_name = np.array(dir_name)
    
    md_info = v_meta_data_from_file_name(file_name)
    
    assert(len(file_name)==len(dir_name))

    for i in range(len(file_name)):
        
        data_file = data_files_name[i]
        print(f"Processing {data_file}")

        with open(data_file, "r") as file:
            meta_data = json.load(file)

        new_meta_data = meta_data.copy()
        rewrite_bool = False
        
        info = md_info[i]
        date = info.date
        time = info.time
        channel = info.channel
        threshold = info.threshold
        
        if "start_timestamp" not in new_meta_data:
            year = date[:4]
            month = date[4:6]
            day = date[6:]

            hour = time[:2]
            minute = time[2:4]
            second = time[4:]
            
            time_str = f'{year}-{month}-{day} {hour}:{minute}:{float(second):.6f}'
            
            new_meta_data["start_timestamp"] = time_str
            rewrite_bool = True
        
        if ("data_taking_mode" not in new_meta_data):
            if (new_meta_data["run_tag"] == "threshold_calibration"):
                new_meta_data["data_taking_mode"] = "single_channel"
                rewrite_bool = True
            else:
                raise ValueError("Data taking mode missing!")
        
        
        if new_meta_data["data_taking_mode"] == "single_channel":
            if "channel" not in new_meta_data:
                if channel != None: 
                    new_meta_data["channel"] = channel
                    rewrite_bool = True
                else:
                    raise ValueError("There is a problem, single channel must have channel number on the datafile name")

            if "board" not in new_meta_data:
                if ("board_0_channels" in new_meta_data):
                    if (len(new_meta_data["board_0_channels"]) == 1) and (new_meta_data["board_0_channels"][0] < 12):
                        board = 0
                    elif channel in new_meta_data["board_0_channels"]:
                        board = 0
                    # else:
                    #     raise ValueError("the format for board_0_channels is wrong! ")
                elif ("board_1_channels" in new_meta_data):
                    if (len(new_meta_data["board_1_channels"]) == 1) and (new_meta_data["board_1_channels"][0] < 12):
                        board = 1
                    elif channel in new_meta_data["board_1_channels"]:
                        board = 1
                    # else:
                    #     raise ValueError("the format for board_1_channels is wrong! ")
                    
                    # and (channel in new_meta_data["board_1_channels"]):
                    # board = 1
                else:
                    raise ValueError("board list missing...")
                
                new_meta_data["board"] = board
                rewrite_bool = True

            if "threshold" not in new_meta_data:
                if threshold != None: 
                    new_meta_data["threshold"] = threshold
                    rewrite_bool = True
                else:
                    raise ValueError("There is a problem, single channel must have threshold on the datafile name")

        elif new_meta_data["data_taking_mode"] != "all_channels":
            raise ValueError("data_taking_mode should only be single_channel or all_channels")
        
        
        if rewrite_bool:
            new_file_name = os.path.join(dir_name[i], f"new_{file_name[i]}")
            with open(new_file_name, "w") as file:
                json.dump(new_meta_data, file, indent=4)

# def step0_find_problems():

#     # Get the list of data files from DATA_FOLDERS
#     data_files_name = get_data_files(DATA_FOLDERS, pattern="meta_config*.json")
#     print(f"Found {len(data_files_name)} meta data files in {DATA_FOLDERS}")

#     file_name = v_basename(data_files_name)
#     dir_name = v_dirname(data_files_name)
#     test_name = v_get_test_name(data_files_name)

#     #turn all list into np.array
#     data_files_name = np.array(data_files_name) # path + file name
#     file_name = np.array(file_name)
#     dir_name = np.array(dir_name)

def step1_add_board_list():

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS, pattern="meta_config*.json")
    print(f"Found {len(data_files_name)} meta data files in {DATA_FOLDERS}")
    
    #turn all list into np.array
    data_files_name = np.array(data_files_name) # path + file name
    file_name = v_basename(data_files_name)
    file_name = np.array(file_name)
    
    problem_data_list = np.array([])

    # loop all the files and find which dataset is a problem -> problem_data_list
    for i in range(len(file_name)):
        
        data_file = data_files_name[i]

        with open(data_file, "r") as file:
            meta_data = json.load(file)
        
        if meta_data["data_taking_mode"] == "single_channel":
            
            if ("board_0_channels" in meta_data):
                if (len(meta_data["board_0_channels"]) == 1):
                    problem_data_list = np.append(problem_data_list, get_test_name(data_file))
            elif ("board_1_channels" in meta_data):
                if (len(meta_data["board_1_channels"]) == 1):
                    problem_data_list = np.append(problem_data_list, get_test_name(data_file))
            else: 
                raise ValueError("Neither board_0_channels or board_0_channels exist! ")
            
    # cluster the data -> sets
    unique, unique_counts = np.unique(problem_data_list, return_counts=1)
    setname_list = np.char.split(unique,sep="|")

    # go through all sets with problems
    for setname in setname_list:
        
        print(f"Processing: \nDir: {setname[0]}\nFilename: {setname[0]}")
        
        print("Find set...")
        set_files_full_path = get_data_files(DATA_FOLDERS, pattern=f"meta_config*{setname[1]}")
        
        set_file_name = v_basename(set_files_full_path)
        set_dir_name = v_dirname(set_files_full_path)

        set_files_full_path = np.array(set_files_full_path) # path + file name
        set_file_name = np.array(set_file_name)
        set_dir_name = np.array(set_dir_name)
        
        board_0_list = np.array([])
        board_1_list = np.array([])
        board_id = None
        
        breakpoint = 0 # whether 12 or 16
        
        # loop over all files in the set, max 24
        for i in range(len(set_files_full_path)):
            
            if breakpoint != 0:
                break
            
            full_path = set_files_full_path[i]
            # print(f"Processing {full_path}")

            with open(full_path, "r") as file:
                meta_data = json.load(file)
                
            if meta_data["channel"]<12:
                continue
            else:
                if ("board_0_channels" in meta_data):
                    board_id = meta_data["board_0_channels"][0]
                elif ("board_1_channels" in meta_data):
                    board_id = meta_data["board_1_channels"][0]
                    
                if (meta_data["channel"]==16) and (board_id==0):
                    breakpoint = 16
                elif (meta_data["channel"]==16) and (board_id==4):
                    breakpoint = 12
                    
                elif (meta_data["channel"]==17) and (board_id==1):
                    breakpoint = 16
                elif (meta_data["channel"]==17) and (board_id==5):
                    breakpoint = 12
                    
                elif (meta_data["channel"]==18) and (board_id==2):
                    breakpoint = 16
                elif (meta_data["channel"]==18) and (board_id==6):
                    breakpoint = 12
                    
                elif (meta_data["channel"]==19) and (board_id==3):
                    breakpoint = 16
                elif (meta_data["channel"]==19) and (board_id==7):
                    breakpoint = 12
                    
                elif (meta_data["channel"]==20) and (board_id==4):
                    breakpoint = 16
                elif (meta_data["channel"]==20) and (board_id==8):
                    breakpoint = 12
                    
                elif (meta_data["channel"]==21) and (board_id==5):
                    breakpoint = 16
                elif (meta_data["channel"]==21) and (board_id==9):
                    breakpoint = 12
                    
                elif (meta_data["channel"]==22) and (board_id==6):
                    breakpoint = 16
                elif (meta_data["channel"]==22) and (board_id==10):
                    breakpoint = 12
                    
                elif (meta_data["channel"]==23) and (board_id==7):
                    breakpoint = 16
                elif (meta_data["channel"]==23) and (board_id==11):
                    breakpoint = 12
                
                elif (meta_data["channel"]==12) and (board_id==0):
                    breakpoint = 12
                elif (meta_data["channel"]==12) and (board_id==12):
                    breakpoint = 16
                    
                elif (meta_data["channel"]==13) and (board_id==1):
                    breakpoint = 12
                elif (meta_data["channel"]==13) and (board_id==13):
                    breakpoint = 16
                
                elif (meta_data["channel"]==14) and (board_id==2):
                    breakpoint = 12
                elif (meta_data["channel"]==14) and (board_id==14):
                    breakpoint = 16
                
                elif (meta_data["channel"]==15) and (board_id==3):
                    breakpoint = 12
                elif (meta_data["channel"]==15) and (board_id==15):
                    breakpoint = 16
                    
        if breakpoint == 0: # meaning that no files above 12 to determine the breakpoint -> not so important -> default case: 16
            breakpoint = 16
            
        if breakpoint == 12:
            board_0_list = np.arange(0,12)
            board_1_list = np.arange(12,24)
        elif breakpoint == 16:
            board_0_list = np.arange(0,16)
            board_1_list = np.arange(16,24)
        else: 
            raise ValueError
        
        # write the new list to the meta_data_files
        for i in range(len(set_files_full_path)):
            
            full_path = set_files_full_path[i]

            with open(full_path, "r") as file:
                meta_data = json.load(file)

            new_meta_data = meta_data.copy()
            new_meta_data["board_0_channels"] = board_0_list.tolist()
            new_meta_data["board_1_channels"] = board_1_list.tolist()
            
            new_file_name = os.path.join(set_dir_name[i], f"new_{set_file_name[i]}")
            print("New file name: "+new_file_name)
            with open(new_file_name, "w") as file:
                json.dump(new_meta_data, file, indent=4)
    
    return 

# replace the old meta data file by the new ones
def step_2_replace_meta():

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS, pattern="new_meta_config*.json")
    print(f"Found {len(data_files_name)} data files in {DATA_FOLDERS}")

    # Replace the "meta_config_..." by "new_meta_config_..." 
    for data_file in data_files_name:
        existing_data_file = data_file.replace("new_meta_config_", "meta_config_")

        # remove the existing "meta_config_..." file
        os.remove(existing_data_file)

        # rename the "new_meta_config_..." to "meta_config_..."
        print(f"Renaming {data_file} to {existing_data_file}")
        os.rename(data_file, existing_data_file)

if __name__ == "__main__":
    check_dir_path()
    step_0_check_item()
    # step_1_edit_item()
    # step_1_edit_item_from_config()
    # step_1_add_items()
    # step_1_add_record_length()
    # step1_add_metadata_from_filename()
    # step1_add_board_list()
    # step_2_replace_meta()