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

import WaveformProcessor
import util
sys.path.insert(0,"/home/daqtest/Processor/sandpro")
import sandpro

class SingleCalibration:

    def __init__(self, data_taking_settings, 
                 config_template_path = "/home/daqtest/DAQ/SandyAQ/sandyaq/config/config_template.ini", 
                 calibration = True):
        
        self.run_sandyaq_command = "/home/daqtest/DAQ/SandyAQ/sandyaq/build/sandyaq"
        
        # check if the data_taking_settings is a dictionary, and have all of the required keys
        if not isinstance(data_taking_settings, dict):
            raise ValueError("data_taking_settings should be a dictionary")
        
        if not all(key in data_taking_settings for key in ["number_of_events",
                                                           "output_folder", 
                                                           "voltage_config", 
                                                           "temperature",
                                                           "threshold_multiplier"]):
            raise ValueError("data_taking_settings should have all of the required keys: \
                              number_of_events, output_folder, voltage_config, temperature, threshold_multiplier")
        self.data_taking_settings = data_taking_settings
        self.threshold_multiplier = self.data_taking_settings["threshold_multiplier"] * np.ones(24)


        # calibration settings
        self.n_calibration_events = 3000
        self.calibration_start_index = 2000 # cannot be lower than this

        # check if the config_template is a string and exists
        if not isinstance(config_template_path, str):
            raise ValueError("config_template should be a string")
        if not os.path.exists(config_template_path):
            raise ValueError("config_template does not exist")
        
        # load the config template
        self.config_template = configparser.ConfigParser()
        self.config_template.optionxform = str
        self.config_template.read(config_template_path)

        if calibration:
            print("Running calibration...")
            self.run_calibration()
        else:
            # generate the temporary config files
            self.tmp_config_files = self.generate_temp_configs()

    def generate_temp_configs(self, calibration = False):
        # the template config is an ini file. We need to do the following modifications:
        # 1. add the channel list
        # 2. add the thresholds

        # create a separate set of config from the given config for the threshold calibration
        if calibration:
            data_settings = self.data_taking_settings.copy()
            # set a very low threshold for all channels, to take noise data
            # data_settings["channel_threshold_dict"] = {0:2305,1:2269,2:2200,3:2209,4:2378,5:2274,6:2386,7:2516,8:2627,9:2316,10:2162,11:2066,12:2456,13:2446,14:2413,15:2192,16:2230,17:2468,18:2158,19:2090,20:2342,21:2258,22:2313,23:2266}
            data_settings["channel_threshold_dict"] = {0:2297,1:2269,2:2200,3:2209,4:2378,5:2274,6:2386,7:2516,8:2585,9:2305,10:2162,11:2066,12:2414,13:2446,14:2277,15:2192,16:2230,17:2468,18:2158,19:2090,20:2280,21:2258,22:2313,23:2233}
            data_settings["number_of_events"] = self.n_calibration_events
            data_settings["output_folder"] = data_settings["output_folder"] + "/threshold_calibration"
            data_settings["run_tag"] = "threshold_calibration"

        else:
            data_settings = self.data_taking_settings
        
        temp_folder = os.path.join(data_settings["output_folder"], "tmp")

        print("Thrsesholds: ", data_settings["channel_threshold_dict"])

        # first: make a tmp folder to store the temp config files
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
            
        tmp_config_files = []
        for channel in data_settings["channel_threshold_dict"].keys():
            new_config_path = os.path.join(temp_folder, f"config_{channel}_{data_settings['channel_threshold_dict'][channel]}.ini")

            # skip if the config file already exists
            if os.path.exists(new_config_path):
                print(f"Config file {new_config_path} already exists. Reading from the file.")
                tmp_config_files.append(new_config_path)
                continue

            # calculate the board number
            if channel <= 15:
                board_number = 0
                local_channel = channel
            else:
                board_number = 1
                local_channel = channel - 16
            # then modify the config template
            new_config = deepcopy(self.config_template)
            new_config.set(f"BOARD-{board_number}", "CHANNEL_LIST", f"{local_channel}")

            section_name = f'BOARD-{board_number}_CHANNEL-{local_channel}'
            if not new_config.has_section(section_name):
                new_config.add_section(section_name)

            # Add the new configuration to the BOARD-0 section
            new_config.set(section_name, 'DC_OFFSET', '+40')
            new_config.set(section_name, 'TRIGGER_THRESHOLD', f'{data_settings["channel_threshold_dict"][channel]}')
            new_config.set(section_name, 'CHANNEL_TRIGGER', 'ACQUISITION_ONLY')
            new_config.set(section_name, 'PULSE_POLARITY', '1')
            # new_config.set(section_name, 'N_EVENTS', f'{data_settings["number_of_events"]}')

            # write the new config to a file. The file name is the channel number and the threshold
            with open(new_config_path, "w") as f:
                new_config.write(f)
            tmp_config_files.append(new_config_path)
        return tmp_config_files
    
    def run_calibration(self, dry_run = False):
        # settings for the calibration run
        self.tmp_config_files = self.generate_temp_configs(calibration=True)
        self.run(dry_run=False, calibration=True)

        # get threshold
        print("Determining thresholds from calibration run...")
        self.data_taking_settings["channel_threshold_dict"] = self.get_adc_threshold_from_calibration()

        self.tmp_config_files = self.generate_temp_configs(calibration=False)
        
   # for multi-threading and timeout
    def run_executable(self, e, tmp_config_file, base_path, data_file_name):
        os.system(f"{self.run_sandyaq_command} -c {tmp_config_file} -n {self.data_taking_settings['number_of_events']} -d {base_path} -f {data_file_name}")
        if e.isSet():
            print("Timeout")
            os.system(f"pkill -f {self.run_sandyaq_command}")
    
    def run(self, dry_run = False, calibration = False):
        
        # get the current timestamp, and add it to the file name
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if calibration:
            base_path = os.path.join(self.data_taking_settings["output_folder"], "threshold_calibration")
            # meta_file_name = os.path.join(base_path, f"meta_{data_file_name}.json")
        else:
            base_path = self.data_taking_settings["output_folder"]
            # meta_file_name = os.path.join(self.data_taking_settings["output_folder"], f"meta_{data_file_name}.json")
        

        runtime_csv_file = os.path.join(base_path, f"runtime_all_channel_{timestamp}.csv")
        with open(runtime_csv_file, "w") as f:
                f.write("channel,elapsed_time\n")

        # run sandyaq to take data
        # the executable is in: /home/daqtest/DAQ/SandyAQ/sandyaq/build
        # run_sandyaq_command = "/home/daqtest/DAQ/SandyAQ/sandyaq/build/sandyaq"

        for tmp_config_file in tqdm(self.tmp_config_files):
            # -c: config file
            # -n: number of events
            # -d: output folder
            # -f: file name

            parts = tmp_config_file.split('/')[-1].split('_')
            channel = int(parts[1])

            # extract the file name from the tmp config file
            data_file_name = os.path.basename(tmp_config_file).replace(".ini", "")
            # get the current timestamp, and add it to the file name
            # moved this out of the loop: so that all channel from the same run has the same timestamp
            # timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            data_file_name = f"{data_file_name}_{timestamp}"
            
            start_timestamp = datetime.datetime.now()

            e = threading.Event()
            exit_current_loop = False

            if not dry_run:
                print(f"Taking data with config file: {tmp_config_file}")

                t = threading.Thread(target=self.run_executable, args=(e, tmp_config_file, base_path, data_file_name))
                
                t.start()
                t.join(timeout=7200)
                if t.is_alive():
                    print(f"Timeout: killing the thread")
                    e.set()

                    # remove the corrupted data file
                    files_to_be_removed = glob.glob(os.path.join(base_path, f"{data_file_name}*.bin"))
                    for _file in files_to_be_removed:
                        print(f"Removing file: {_file}")
                        os.remove(_file)

                    exit_current_loop = True
                    
                else:
                    print(f"Thread finished")
                
                # Thread can still be alive at this point. Do another join without a timeout 
                # to verify thread shutdown.
                # https://stackoverflow.com/questions/34562473/most-pythonic-way-to-kill-a-thread-after-some-period-of-time
                t.join()

                if exit_current_loop:
                    continue


            else:
                print(f"Running sandyaq -c {tmp_config_file} -n {self.data_taking_settings['number_of_events']} -d {base_path} -f {data_file_name}")

                # This is not doing anything?? -> Yue
                raise ValueError("Dry run not implemented yet. Please set dry_run to False. Exiting...")
        
            end_timestamp = datetime.datetime.now()

            meta_file_name = os.path.join(base_path, f"meta_{data_file_name}.json")

            self.data_taking_settings["runtime"] = str(end_timestamp - start_timestamp)
            self.data_taking_settings["start_timestamp"] = str(start_timestamp)

            with open(meta_file_name, "w") as f:
                json.dump(self.data_taking_settings, f, indent=4)

            with open(runtime_csv_file, "a") as f:
                f.write(f"{channel},{(end_timestamp - start_timestamp).total_seconds()}\n")
                
        return 

    def get_adc_threshold_from_calibration(self):
        # read the data from the calibration run
        data_folder = os.path.join(self.data_taking_settings["output_folder"],"threshold_calibration")
        meta_data_list = glob.glob(f"{data_folder}/*meta*")

        # Sort the file paths based on the extracted date and time in ascending order (oldest to newest)
        new_meta_data_list = sorted(meta_data_list, key=util.extract_date_meta_data)
        meta_data_list=new_meta_data_list[-24:] # 24 = total number of channels

        # Check if all calibration runs are successful
        # by checking if the timestamps are the same
        datetime_list = util.v_extract_date_meta_data(meta_data_list)
        if not np.all(datetime_list == datetime_list[0]):
            raise ValueError("Not all calibration runs are successful: \n the 24 channels (or last 24 data) don't have the same timestamps. \nCheck the data. Exiting.")
        
        # Sort the meta data according to channel number
        sorted_meta_data_list = sorted(meta_data_list, key=util.extract_channel_meta_data)

        # Get the thresholds from the last 24 calibration runs
        baseline_mean_array = []
        baseline_std_array = []
        channels = []

        for i, meta_data in enumerate(sorted_meta_data_list):
            print(sorted_meta_data_list[i])
            # meta_data = sorted_meta_data_list[i]
            meta_data_basename = os.path.basename(meta_data)
            parts = meta_data_basename.split('_')
            config_name = "_".join(parts[1:4]) + ".ini"
            channel = int(parts[2])

            print(config_name)
            config_path = os.path.join(data_folder, "tmp", config_name)
            config = configparser.ConfigParser()
            config.optionxform = str
            config.read(config_path)

            process_config = {"nchs": 1,
                "nsamps": int(config.get("COMMON", "RECORD_LENGTH")),
                "sample_selection": 120,
                "samples_to_average": 40
                }
            
            # dump the config to a json file
            with open("process_config.json", "w") as f:
                json.dump(process_config, f)
            if len(config.get("BOARD-0", "CHANNEL_LIST")) > 0:
                board_number = 0
            else:
                board_number = 1

            processor= sandpro.processing.rawdata.RawData(config_file = "process_config.json",
                                                perchannel=False)
            data_file_basename = meta_data_basename.replace("meta_", "").replace(".json", f"_board_{board_number}.bin")
            try:
                data = processor.get_rawdata_numpy(n_evts=self.n_calibration_events-1,
                                            file=os.path.join(data_folder, data_file_basename),
                                            bit_of_daq=14,
                                            headersize=4,inversion=False)
                start_index, end_index = self.calibration_start_index, self.n_calibration_events-1-500
            except Exception as e:
                print(e)
                data = processor.get_rawdata_numpy(n_evts=200,
                                            file=os.path.join(data_folder, data_file_basename),
                                            bit_of_daq=14,
                                            headersize=4,inversion=False)
                start_index, end_index = 0, 119
            
            wfp = WaveformProcessor.WFProcessor(data_folder, volt_per_adc=2/2**14)
            wfp.set_data(data["data_per_channel"][start_index:end_index,0], in_adc = False)
            wfp.process_wfs()
            
            baseline_std = np.mean(wfp.baseline_rms)
            baseline_mean = np.mean(wfp.baseline)
            baseline_mean_array.append(baseline_mean)
            baseline_std_array.append(baseline_std)
            channels.append(channel)

        baseline_mean_array = np.array(baseline_mean_array)
        baseline_std_array = np.array(baseline_std_array)

        # threshold_mV = (baseline_mean_array + 2 * (2 * np.sqrt(2) * baseline_std_array)) * 1000
        threshold_mV = (baseline_mean_array + self.threshold_multiplier[channels] * baseline_std_array) * 1000

        threshold_adc = util.v_mv_to_adc(threshold_mV)
        
        threshold_dict = {i:int(thres) for i, thres in enumerate(threshold_adc.astype(int))}

        return threshold_dict
    
if __name__ == "__main__":
    test_config = {}
    test_config["channel_threshold_dict"] = {0:2000,1:2319,2:2618,3:2273,4:2426,5:2341,6:2468,7:2567,8:2801,9:2371,10:2210,11:2352,12:2470,13:2496,14:2602,15:2264,16:2284,17:2531,18:2216,19:2147,20:2522,21:2306,22:2369,23:2465}
    test_config["number_of_events"] = 5000
    test_config["output_folder"] = "./test_calibration"
    test_config["voltage_config"] = {"preamp_1": -49, "preamp_2": -49,"preamp_3": -49,"preamp_4": -49,"preamp_5": -49}
    test_config["temperature"] = -98
    test_config["threshold_multiplier"] = 3.5


    test_calibration = SingleCalibration(test_config, calibration=False)
    test_calibration.run(dry_run=False)

        
        

            


