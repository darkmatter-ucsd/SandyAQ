"""
This wrapper is used to take single channel calibration data. It does the following steps:
- Generate temporary config files based on the config template and user inputs (data_taking_settings)
- run calibration runs with sandyaq
- run sandyaq to take data according to the temp config file
- write the user inputs as metadata 
"""

import os
import configparser
import datetime
import json
from copy import deepcopy
from tqdm import tqdm
import glob
import numpy as np
import sys
import configparser
import json

import threading
import time
import subprocess

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
import common.utils as util
import data_processing.waveform_processor as waveform_processor
import data_taking.single_channel as single_channel
import common.config_reader as common_config_reader

sys.path.insert(0,"/home/daqtest/Processor/sandpro")
import sandpro

class AllChannel_DataTaking:

    def __init__(self, data_taking_settings, 
                 config_template_path = "/home/daqtest/DAQ/SandyAQ/sandyaq/config/config_template.ini", 
                 calibration = True, same_threshold = False):
        
        self.common_cfg_reader = common_config_reader.ConfigurationReader()
        self.config = self.common_cfg_reader.get_data_taking_config()
        
        self.DC_offset = self.config.get('DATA_TAKING_SETTINGS', 'DC_offset')
        
        self.same_threshold = same_threshold
        self.run_sandyaq_command = "/home/daqtest/DAQ/SandyAQ_vera/SandyAQ/sandyaq/build/sandyaq"
        
        # check if the data_taking_settings is a dictionary, and have all of the required keys
        if not isinstance(data_taking_settings, dict):
            raise ValueError("data_taking_settings should be a dictionary")
        
        if not all(key in data_taking_settings for key in ["number_of_events",
                                                           "output_folder", 
                                                           "voltage_config", 
                                                           "temperature",
                                                           "threshold_multiplier",
                                                           "channel_list"]):
            raise ValueError("data_taking_settings should have all of the required keys: \
                              number_of_events, output_folder, voltage_config, temperature, threshold_multiplier")
        self.data_taking_settings = data_taking_settings
        self.threshold_multiplier = self.data_taking_settings["threshold_multiplier"] * np.ones(24)
        self.timeout = 1800 # in second; kill run after this time
        self.data_taking_settings["timeout"] = self.timeout

        # check if the config_template is a string and exists
        if not isinstance(config_template_path, str):
            raise ValueError("config_template should be a string")
        if not os.path.exists(config_template_path):
            raise ValueError("config_template does not exist")
        
        # load the config template
        self.config_template = configparser.ConfigParser()
        self.config_template.optionxform = str
        self.config_template.read(config_template_path)

        #threshold calibration
        SingleCalibration = single_channel.SingleChannel_DataTaking(self.data_taking_settings, calibration=calibration, same_threshold=self.same_threshold)
        self.data_taking_settings["channel_threshold_dict"] = SingleCalibration.data_taking_settings["channel_threshold_dict"]
        
        print("Configurations: ")
        print(self.data_taking_settings)
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.tmp_config_file = self._gen_tmp_configs()

        print("end")
        

    def _gen_tmp_configs(self):
        # the template config is an ini file. We need to do the following modifications:
        # 1. add the channel list
        # 2. add the thresholds

        # create a separate set of config from the given config for the threshold calibration

        data_taking_settings = self.data_taking_settings.copy()

        temp_folder = os.path.join(data_taking_settings["output_folder"], "tmp")

        # first: make a tmp folder to store the temp config files
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
            
        new_config_path = os.path.join(temp_folder, f"config_all_{self.timestamp}.ini")

        # skip if the config file already exists
        if os.path.exists(new_config_path):
            print(f"Config file {new_config_path} already exists. Reading from the file.")
            return new_config_path
        
        new_config = deepcopy(self.config_template)

        channel_list = np.array(data_taking_settings["channel_list"], dtype=int)
        
        # calculate the channel list for a board
        board_0_channel_list = channel_list[channel_list <= 11]
        board_1_channel_list = channel_list[channel_list > 11]
        
        for i, _board_channel_list in enumerate([board_0_channel_list, board_1_channel_list]):
            _board_channel_list_str = ""
            board_number = i
            if board_number == 1:
                board_channel_subtration = 12 # the channel on the board starts from zero
            elif board_number == 0:
                board_channel_subtration = 0
            else:
                raise
            
            for channel in _board_channel_list:
                board_channel = channel - board_channel_subtration
                _board_channel_list_str = _board_channel_list_str + str(board_channel) + " "
                
                section_name = f'BOARD-{board_number}_CHANNEL-{board_channel}'
                if not new_config.has_section(section_name):
                    new_config.add_section(section_name)

                # Add the new configuration to the BOARD-0 section
                new_config.set(section_name, 'DC_OFFSET', str(self.DC_offset))
                new_config.set(section_name, 'TRIGGER_THRESHOLD', f'{data_taking_settings["channel_threshold_dict"][channel]}')
                new_config.set(section_name, 'CHANNEL_TRIGGER', 'ACQUISITION_ONLY')
                new_config.set(section_name, 'PULSE_POLARITY', '1')
                
                
            _board_channel_list = _board_channel_list_str[:-1]
            
            new_config.set(f"BOARD-{board_number}", "CHANNEL_LIST", f"{_board_channel_list}")
            # new_config.set(f"BOARD-{board_number}", "POST_TRIGGER", f"{90}")
        
            # then modify the config template
            # new_config.set(f"BOARD-0", "CHANNEL_LIST", f"{board_0_channel_list}")
            # new_config.set(f"BOARD-1", "CHANNEL_LIST", f"{board_1_channel_list}")
            
            # for channel in channel_list:
            #     if channel <= 15:
            #         board_number = 0
            #     else:
            #         board_number = 1

            

        # write the new config to a file. The file name is the channel number and the threshold
        with open(new_config_path, "w") as f:
            new_config.write(f)
            
        return new_config_path
    
    def _metadata_checklist(self, data_taking_settings):
        # check if the dictionary have all the essential entries before writing
        # prevent changes in the code messing up with the recording of meta_data_file
        try:
            assert(data_taking_settings["runtime"] != None)
            assert(data_taking_settings["record_length"]!= None)
            assert(data_taking_settings["start_timestamp"]!= None)
            assert(data_taking_settings["timeout"]!= None)
            assert(data_taking_settings["comment"]!= None)
            assert(data_taking_settings["number_of_events"]!= None)
            assert(data_taking_settings["run_tag"]!= None)
        except Exception as e:
            print(f"Required metadata entry {e} is missing! Please check the code. ")
            raise
   
    # for multi-threading and timeout
    def _run_executable(self, e, tmp_config_file, number_of_events, base_path, data_file_name):
        # os.system(f"{self.run_sandyaq_command} -c {tmp_config_file} -n {self.data_taking_settings['number_of_events']} -d {base_path} -f {data_file_name}")
        # if e.isSet():
        #     print("Timeout")
        #     os.system(f"pkill -f {self.run_sandyaq_command}")

        print("Running sandyaq")
        process = subprocess.Popen(
            [self.run_sandyaq_command, '-c', tmp_config_file, '-n', str(number_of_events), '-d', base_path, '-f', data_file_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        

        # Check for timeout
        while process.poll() is None:
            if e.is_set():
                process.terminate()  # Gracefully terminate the process
                print("Timeout")
                break
            time.sleep(1)  # Check every second

        # Wait for the process to terminate if it hasn’t been terminated already
        process.wait()

        if process.returncode != 0:
            print(f"Process terminated with errors: {process.stderr.read().decode()}")
   
    
    def run(self, dry_run = False):
        if dry_run: # This is not doing anything?? -> Yue
                print(f"Running sandyaq -c {self.tmp_config_file} -n {self.data_taking_settings['number_of_events']} -d {base_path} -f {data_file_name}")
                raise ValueError("Dry run not implemented yet. Please set dry_run to False. Exiting...")
        
        data_taking_settings = self.data_taking_settings
        
        # get the current timestamp (global to all channel for the same run), and add it to the file name
        timestamp = self.timestamp

        base_path = data_taking_settings["output_folder"]
        number_of_events = data_taking_settings["number_of_events"]
        # meta_file_name = os.path.join(base_path, f"meta_{data_file_name}.json")
        
        # run sandyaq to take data
        # the executable is in: /home/daqtest/DAQ/SandyAQ/sandyaq/build
        # run_sandyaq_command = "/home/daqtest/DAQ/SandyAQ/sandyaq/build/sandyaq"
        # -c: config file
        # -n: number of events
        # -d: output folder
        # -f: file name

        # parts = self.tmp_config_file.split('/')[-1].split('_')
        # channel = int(parts[1])

        # extract the file name from the tmp config file
        data_file_name = os.path.basename(self.tmp_config_file).replace(".ini", "")
        # get the current timestamp, and add it to the file name
        # moved this out of the loop: so that all channel from the same run has the same timestamp
        # timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        data_file_name = f"{data_file_name}"
        
        start_timestamp = datetime.datetime.now()

        print(f"Taking data with config file: {self.tmp_config_file}")
        
        try:
            print(f"Taking data with config file: {self.tmp_config_file}")
            os.system(f"{self.run_sandyaq_command} -c {self.tmp_config_file} -n {number_of_events} -d {base_path} -f {data_file_name}")
        except Exception as e:
            print(f"Error running sandyaq: {e}")
                    
        # e = threading.Event()
        # exit_current_loop = False

        # # start a thread to run the executable
        # t = threading.Thread(target=self._run_executable, args=(e, self.tmp_config_file, number_of_events, base_path, data_file_name))
        
        # t.start()
        # t.join(timeout=data_taking_settings["timeout"])

        # if t.is_alive():
        #     e.set()
        #     t.join()
        #     print("Timeout occurred and process terminated")

        #     # remove the corrupted data file
        #     files_to_be_removed = glob.glob(os.path.join(base_path, f"{data_file_name}*.bin"))
        #     for _file in files_to_be_removed:
        #         print(f"Removing file: {_file}")
        #         os.remove(_file)

        #     exit_current_loop = True
            
        # else:
        #     print("Thread finished successfully")
        
        # # Thread can still be alive at this point. Do another join without a timeout 
        # # to verify thread shutdown.
        # # https://stackoverflow.com/questions/34562473/most-pythonic-way-to-kill-a-thread-after-some-period-of-time
        # t.join()

        end_timestamp = datetime.datetime.now()

        meta_file_name = os.path.join(base_path, f"meta_{data_file_name}.json")

        # note that the dictionary is assigned by reference, so this will update
        # either self.calib_data_taking_setting or self.data_taking_settings, which
        # is desired, i.e. this is on purpose.
        data_taking_settings["runtime"] = str(end_timestamp - start_timestamp)
        data_taking_settings["start_timestamp"] = str(start_timestamp)
        # retrieve record length from data takking configuration
        tmp_config = configparser.ConfigParser()
        tmp_config.optionxform = str
        tmp_config.read(self.tmp_config_file)
        data_taking_settings["record_length"] = tmp_config.get("COMMON", "RECORD_LENGTH")
        
        self._metadata_checklist(data_taking_settings)
        with open(meta_file_name, "w") as f:
            json.dump(data_taking_settings, f, indent=4)

        return 
    
if __name__ == "__main__":
    test_config = {}
    test_config["channel_threshold_dict"] = {0:2000,1:2319,2:2618,3:2273,4:2426,5:2341,6:2468,7:2567,8:2801,9:2371,10:2210,11:2352,12:2470,13:2496,14:2602,15:2264,16:2284,17:2531,18:2216,19:2147,20:2522,21:2306,22:2369,23:2465}
    test_config["number_of_events"] = 5000
    test_config["output_folder"] = "./test_calibration"
    test_config["voltage_config"] = {"preamp_1": -49, "preamp_2": -49,"preamp_3": -49,"preamp_4": -49,"preamp_5": -49}
    test_config["temperature"] = -98
    test_config["threshold_multiplier"] = 3.5


    test_calibration = AllChannel_DataTaking(test_config, calibration=False)
    test_calibration.run(dry_run=False)

        
        

            


