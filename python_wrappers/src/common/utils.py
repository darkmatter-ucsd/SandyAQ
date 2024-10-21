"""
This script contains common utility functions that are used in 
multiple scripts.
"""

from datetime import datetime
import numpy as np
import os
import pandas as pd
import re

def _re_search(pattern: str, string):
    """
    This function check if the pattern matches with the string
    The vectorized function is defined afterwards
    
    Return: boolean
    """
    if pd.isnull(string):
        return False #does not match
    else:
        return bool(re.search(pattern, string))

vec_regex_search = np.vectorize(_re_search, excluded=["pattern"], otypes=[np.ndarray])


# def load_run_info(path = "../run_info.csv"):
#     """
#     Load the run info from {path in csv} into pandas dataframe
    
#     Return dataframe
#     """
#     df = pd.read_csv(path)

#     return df

def extract_date_meta_data(meta_data_path):

    #reorganize the order of the meta_data_list, so the final one should be the newest one.
    parts = meta_data_path.split('_')
    date_part = parts[-2]
    time_part = parts[-1].split('.')[0]  # Remove the file extension
    datetime_str = date_part + '_' + time_part

    # Parse the datetime using the format YYYYMMDD_HHMMSS
    return datetime.strptime(datetime_str, '%Y%m%d_%H%M%S')

# v_extract_date_meta_data = np.vectorize(extract_date_meta_data, otypes=[np.ndarray])

def extract_channel_meta_data(meta_data_path):

    meta_data_basename = os.path.basename(meta_data_path)
    parts = meta_data_basename.split('_')
    # config_name = "_".join(parts[1:4]) + ".ini"
    channel = int(parts[2])

    return channel

# v_extract_channel_meta_data = np.vectorize(extract_channel_meta_data, otypes=[np.ndarray])

def adc_to_mv(adc, DCOFFSET=+50, vpp=2.0, bit_of_daq=14): 
    #DC OFFSET = +40: -0.2 - 1.8
    #DC OFFSET = +50: 0.0 - 2.0
    #DC OFFSET = -50: -2 - 0.0
    start_voltage = (DCOFFSET/50) -1
    # end_voltage = start_voltage + vpp
    # voltage_per_adc = vpp / (2**bit_of_daq-1)
    return (adc/(2**bit_of_daq-1) * vpp + start_voltage) * 1000

# v_adc_to_mv = np.vectorize(adc_to_mv, otypes=[np.ndarray])

def mv_to_adc(mv, DCOFFSET=+50, vpp=2.0, bit_of_daq=14):
    start_voltage = (DCOFFSET/50) -1.0
    # end_voltage = start_voltage + vpp
    # voltage_per_adc = vpp / (2**bit_of_daq-1)
    return (mv/1000 - start_voltage) / vpp * (2**bit_of_daq-1)

v_mv_to_adc = np.vectorize(mv_to_adc, excluded=['DCOFFSET', 'vpp', 'bit_of_daq'],otypes=[np.ndarray])

def V_to_adc(V, DCOFFSET=+50, vpp=2.0, bit_of_daq=14):
    start_voltage = (DCOFFSET/50) -1.0
    # end_voltage = start_voltage + vpp
    # voltage_per_adc = vpp / (2**bit_of_daq-1)
    return (V - start_voltage) / vpp * (2**bit_of_daq-1)

# v_V_to_adc = np.vectorize(mv_to_adc, otypes=[np.ndarray])
