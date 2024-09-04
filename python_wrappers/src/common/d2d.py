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
from collections.abc import Sequence
from dataclasses import dataclass
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
from common.logger import setup_logger

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

@dataclass
class data(Sequence):
    def __init__(self, input: object):
        self.import_data(input)
        super().__init__()
    
    def import_data(self, input: object):
        if isinstance(input, pd.DataFrame):
            self.import_df(input)
        elif isinstance(input, dict):
            self.import_dict(input)
        else:
            raise TypeError("Input should be either pd.DataFrame or dict")
        
    def import_df(self, df: pd.DataFrame):
        for col_name in df.columns:
            setattr(self, col_name, df[col_name].to_numpy())
            
    def import_dict(self, dictionary: dict):
        for var_name in dictionary.keys():
            setattr(self, var_name, np.array(dictionary[var_name]))
    
    def get_df(self):
        df = pd.DataFrame(self.__dict__,index=None)
        return df
    
    def get_dict(self):
        return self.__dict__
            
    def apply_mask(self, mask, inplace = False, dry = True):
        if not dry:
            logger.info(f"Before cut: {len(self)}")
        new_dict = {}
        for i in self.__dict__.keys():
            if inplace:
                self.__dict__[i] = self.__dict__[i][mask]
            else:
                new_dict[i] = self.__dict__[i][mask]
        
        if not dry:
            logger.info(f"After cut: {len(self)}")
                
        if inplace:   
            return
        else:
            return data(new_dict)
        
    def __len__(self):
        # the length of all array should be the same
        # so just picked a random one
        first = next(iter(self.__dict__.values()))
        return len(first)
    
    def __getitem__(self, index):
        # so that the class is index-able
        new_dict = {}
        for i in self.__dict__.keys():
            new_dict[i] = self.__dict__[i][index]
        return data(new_dict)
            
