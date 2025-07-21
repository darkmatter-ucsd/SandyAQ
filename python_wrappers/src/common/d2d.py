#!/home/daqtest/anaconda3/bin python

"""
This module read in the dataframe or dictionaries of np.array
- convert them interchangably
- apply masks to all data
- get the length of the table (i.e. how many entries)
"""

import numpy as np
import sys
sys.path.insert(0,"/home/daqtest/Processor/sandpro")
import pandas as pd
from dataclasses import dataclass
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
from common.logger import setup_logger
import data_structure.run_info as run_info
import json

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

@dataclass
class data():
    def __init__(self, input: object):
        self.import_data(input)
    
    def import_data(self, input: object):
        if isinstance(input, pd.DataFrame):
            self.import_df(input)
        elif isinstance(input, dict):
            self.import_dict(input)
        else:
            raise TypeError("Input should be either pd.DataFrame or dict")
        
    def import_df(self, df: pd.DataFrame):
        # for col_name in df.column():
        for series_name, series in df.items():
            setattr(self, series_name, series.to_numpy())
            
    def import_dict(self, dictionary: dict):
        for var_name in dictionary.keys():
            setattr(self, var_name, np.array(dictionary[var_name]))
    
    def get_df(self):
        df = pd.DataFrame(self.__dict__,index=None)
        return df
    
    def get_dict(self):
        return self.__dict__
            
    def apply_mask(self, mask, inplace = False, dry = True):
        
        mask = mask.astype(bool)
        
        if not dry:
            logger.info(f"Before cut: {len(self)}")
            
        new_dict = {}
        for column in self.__dict__.keys():
            new_dict[column] = self.__dict__[column][mask]
            if inplace:
                self.__dict__[column] = new_dict[column]
        
        if not dry:
            logger.info(f"After cut: {len(new_dict[column])}")
                
        if inplace:   
            return
        else:
            return data(new_dict)
        
    def get_row_info(self, row: int) -> run_info.RunInfo:
        """
        Return run_info.RunInfo from the row of the df from 
        d2d.data class with a given index or row_id.

        Args:
            row (int): which row of the df

        Returns:
            run_info.RunInfo: coverted run_info.RunInfo from
            the row of the df from the d2d.data class
        """
        df = self.get_df()
        
        single_run = df.iloc[row].to_dict()
        RunInfo = run_info.RunInfo()
        RunInfo.set_info_from_dict(single_run)
            
        return RunInfo
    
    def get_row_info_to_dict(self, row: int):
        """
        Return run_info.RunInfo from the row of the df from 
        d2d.data class with a given index or row_id.

        Args:
            row (int): which row of the df

        Returns:
            run_info.RunInfo: coverted run_info.RunInfo from
            the row of the df from the d2d.data class
        """
        
        df = self.get_df()
        
        single_run = df.iloc[row].to_dict()
        
        for key, value in single_run.items():
            if isinstance(value, np.ndarray):
                if len(value) == 1:
                    single_run[key] = value[0]
            
        return single_run
    
    def get_common_info_dict(self):
        """
        Get the common information from the data structure.
        
        Returns:
            dict: common information from the data structure
        """
        common_info = {}
        for key, value in self.__dict__.items():
            if isinstance(value, np.ndarray) and not (value.shape): # avoid array(nan)
                continue
            if isinstance(value[0], np.ndarray):
                # convert each row to string
                value = np.array([json.dumps(x.tolist()) for x in value])
            if len(np.unique(value)) == 1:
                common_info[key] = value[0]
        return common_info
    
    def __len__(self):
        # the length of all array should be the same
        # so just picked a random one
        first = next(iter(self.__dict__.values()))
        return len(first)
    
    def copy(self):
        df = self.get_df().copy()
        return data(df)
        

