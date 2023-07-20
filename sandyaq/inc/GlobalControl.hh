#ifndef GLOBALCONTORL_HH
#define GLOBALCONTORL_HH

#include "Digitizer.hh"

/*************************************************
 * Global settings that are only to be used by
 * the main function once all the individual board
 * settings have been programmed! 
**************************************************/

//Standard library
#include <iostream>
#include <vector>
#include <string>

//CAEN libraries
#include <CAENDigitizer.h>

//Internal headers
#include "CommonConfig.hh"
#include "Digitizer.hh"
#include "Utils.hh"


// Set Synchronization Mode
static int SetSyncMode(std::vector<Digitizer*> &Boards, CommonConfig_t* commonConfig){
    int ret = 0;
    uint32_t reg;
    int totalBoardIndex = 0;
    int totalBoards = 0;
    for (int bt = 0; bt<Boards.size(); bt++) {
        totalBoards+=Boards[bt]->m_iNBoards;
    }
    printf("\n\nTotal boards: %d\n\n", totalBoards);

    for (int bt = 0; bt<Boards.size(); bt++){
        Digitizer* boards = Boards[bt];
        for (int b = 0; b < boards->m_iNBoards; b++){
            if (commonConfig->SyncMode == "COMMONT_EXTERNAL_TRIGGER_TRGIN_TRGOUT") {
                std::cout <<"Programming synchronization mode for a common external trigger\n";
                if ((b == 0)&&(bt == 0)) {// inhibit TRGIN on board 0 in order to avoid start of run with external triggers
                    ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_EXT_TRG_INHIBIT, 1);
                    PrintError(b, "Writng", "Register[ADDR_EXT_TRG_INHIBIT]", ret);
                    std::cout << "Wrote to the master board\n";
                }

                //If we are using an EXTERNAL trigger, we shall overwrite the channel triggers
                ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_GLOBAL_TRG_MASK, 0xC0000000);  // accept EXT TRGIN or SW trg 
                PrintError(b, "Writng", "Register[ADDR_GLOBAL_TRG_MASK]", ret);
                
                ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_TRG_OUT_MASK, 0xC0000000);     // propagate both EXT and SW TRG to TRGOUT
                PrintError(b, "Writng", "Register[ADDR_TRG_OUT_MASK]", ret);
                
                ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_ACQUISITION_MODE, RUN_START_ON_TRGIN_RISING_EDGE);  // Run starts with 1st trigger edge
                PrintError(b, "Writng", "Register[ADDR_ACQUISITION_MODE]", ret);
                
                ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_RUN_DELAY, 4*(totalBoards-1-totalBoardIndex));   // Run Delay decreases with the position (to compensate for run the propagation delay)        }
                std::cout << "Run delay of "<< 4*(totalBoards-1-totalBoardIndex)<<"\n";
                PrintError(b, "Writng", "Register[ADDR_RUN_DELAY]", ret);
                // continue;        
            }
            else if (commonConfig->SyncMode == "INDIVIDUAL_TRIGGER_SIN_TRGOUT"){
                printf("\n\nTotal board index: %d\n\n", totalBoardIndex);
                if (totalBoardIndex == totalBoards - 1){ // Run starts with S-IN on the last board
                    ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_ACQUISITION_MODE, RUN_START_ON_SIN_LEVEL);
                    uint32_t acquisition_mode_register_data;
                    ret |= CAEN_DGTZ_ReadRegister(boards->m_iHandles[b], ADDR_ACQUISITION_MODE, &acquisition_mode_register_data);
                    PrintError(b, "Writng", "Register[ADDR_ACQUISITION_MODE]", ret);
                    printf("Board %d starts on SIN level, register: %u\n", totalBoardIndex, acquisition_mode_register_data);
                }
                // for (int c = 0; c < m_iOpenChannels[i].size(); c++){
                //     ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_GLOBAL_TRG_MASK, 0x40000000 + (1<<(int)m_iOpenChannels[i][c]));  //  accept EXT TRGIN or trg from selected channel
                //     PrintError(i, "Writng", "Register[ADDR_GLOBAL_TRG_MASK]", ret);

                // }
                uint32_t global_trg_mask_reg; 
                ret |= CAEN_DGTZ_ReadRegister(boards->m_iHandles[b], ADDR_GLOBAL_TRG_MASK, &global_trg_mask_reg);
                printf("Global trigger mask register: %u\n", global_trg_mask_reg);

                //Keep in mind, if we do INDIVIDUAL_TRIGGER_SIN_TRGOUT, then we need to overwrite any propagation of trgout
                ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_TRG_OUT_MASK, 0); // no trigger propagation to TRGOUT
                PrintError(b, "Writng", "Register[ADDR_TRG_OUT_MASK]", ret);
                
                ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_RUN_DELAY, 2*(totalBoards-1-totalBoardIndex));   // Run Delay decreases with the position (to compensate for run the propagation delay)
                PrintError(b, "Writng", "Register[ADDR_RUN_DELAY]", ret);
                
                // Set TRGOUT=RUN to propagate run through S-IN => TRGOUT daisy chain
                ret |= CAEN_DGTZ_ReadRegister(boards->m_iHandles[b], ADDR_FRONT_PANEL_IO_SET, &reg);
                PrintError(b, "Writng", "Register[ADDR_FRONT_PANEL_IO_SET]", ret);
                
                reg = reg & 0xFFF0FFFF | 0x00010000;
                ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_FRONT_PANEL_IO_SET, reg);
                PrintError(b, "Writng", "Register[ADDR_FRONT_PANEL_IO_SET]", ret);
                // continue;
            }
            else if (commonConfig->SyncMode == "TRIGGER_ONE2ALL_EXTOR") {
                // for (int c = 0; c < m_iOpenChannels[i].size(); c++){    
                //     ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_TRG_OUT_MASK, 0x80000000);     // propagate SW TRG and auto trg to TRGOUT
                //     PrintError(i, "Writng", "Register[ADDR_TRG_OUT_MASK]", ret);
                // }

                ret |= CAEN_DGTZ_ReadRegister(boards->m_iHandles[b], ADDR_TRG_OUT_MASK, &reg);
                reg = reg | 0x80000000;
                ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_TRG_OUT_MASK, reg);     // propagate SW TRG and auto trg to TRGOUT
                PrintError(b, "Writng", "Register[ADDR_TRG_OUT_MASK]", ret);

                ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_GLOBAL_TRG_MASK, 0x40000000);  // accept EXT TRGIN (from trg OR) 
                PrintError(b, "Writng", "Register[ADDR_GLOBAL_TRG_MASK]", ret);
                
                ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_ACQUISITION_MODE, RUN_START_ON_TRGIN_RISING_EDGE);    // Arm acquisition (Run will start with 1st trigger)
                PrintError(b, "Writng", "Register[ADDR_ACQUISITION_MODE]", ret);
                
                ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_RUN_DELAY, 0);   // Run Delay due to the transmission of the SW TRG in the TRGIN of the slaves
                
                // continue;
            }
            else{
                return -1;
            }

            totalBoardIndex++;
        }
    }
    
    return ret;
}

static int ForceClockSync(int handle)
{    
    int ret;
    sleep(1);
    /* Force clock phase alignment */
    ret = CAEN_DGTZ_WriteRegister(handle, ADDR_FORCE_SYNC, 1);
    /* Wait an appropriate time before proceeding */
    sleep(10);
    return ret;
}



//Start acquisition
static int StartRun(std::vector<Digitizer*> &Boards, CommonConfig_t* commonConfig) {
    int ret = 0;
    Digitizer* masterBoard = Boards[0];

    if(commonConfig->SyncMode == "TRIGGER_ONE2ALL_EXTOR" || commonConfig->SyncMode == "COMMONT_EXTERNAL_TRIGGER_TRGIN_TRGOUT"){
        // Start on first software trigger
        if(commonConfig->StartMode == "START_SW_CONTROLLED"){
            ret |= CAEN_DGTZ_SendSWtrigger(masterBoard->m_iHandles[0]);
            PrintError(0, "Sending SW Trigger", "Digitizer", ret);
        }
        if(commonConfig->SyncMode == "COMMONT_EXTERNAL_TRIGGER_TRGIN_TRGOUT"){
            ret |= CAEN_DGTZ_WriteRegister(masterBoard->m_iHandles[0], ADDR_EXT_TRG_INHIBIT, 0); // Enable TRGIN of the first board
            PrintError(0, "Writng", "Register[ADDR_EXT_TRG_INHIBIT]", ret);
        }
        return ret;
    }
    if(commonConfig->SyncMode == "INDIVIDUAL_TRIGGER_SIN_TRGOUT"){
        if(commonConfig->StartMode == "START_SW_CONTROLLED"){
            ret |= CAEN_DGTZ_WriteRegister(masterBoard->m_iHandles[0], ADDR_ACQUISITION_MODE, 0x4);
            PrintError(0, "Writng", "Register[ADDR_ACQUISITION_MODE]", ret);
        }
        else{
            ret |= CAEN_DGTZ_WriteRegister(masterBoard->m_iHandles[0], ADDR_ACQUISITION_MODE, 0x5);
            PrintError(0, "Writng", "Register[ADDR_ACQUISITION_MODE]", ret);
            
            printf("Run starts/stops on the S-IN high/low level\n");
        }
        return ret;
    }
    return ret;
};


//Stop acquisition
int StopRun(std::vector<Digitizer*> &Boards, CommonConfig_t* commonConfig)
{
    int ret = 0;

    if (commonConfig->SyncMode == "COMMONT_EXTERNAL_TRIGGER_TRGIN_TRGOUT" || commonConfig->SyncMode == "TRIGGER_ONE2ALL_EXTOR") {
        for (int bt = 0; bt<Boards.size(); bt++){
            Digitizer* boards = Boards[bt];
            for (int b = 0; b < boards->m_iNBoards; b++){
                ret |= CAEN_DGTZ_WriteRegister(boards->m_iHandles[b], ADDR_ACQUISITION_MODE, 0);
                PrintError(b, "Writng", "Register[ADDR_ACQUISITION_MODE]", ret);

            }
        }
        return ret;
    }
    if (commonConfig->SyncMode == "INDIVIDUAL_TRIGGER_SIN_TRGOUT") {
        Digitizer* masterBoard = Boards[0];
        ret |= CAEN_DGTZ_WriteRegister(masterBoard->m_iHandles[0], ADDR_ACQUISITION_MODE, 0x0);
        PrintError(0, "Writng", "Register[ADDR_ACQUISITION_MODE]", ret);
        
        return ret;
    }
    else{
        return -1;
    }
    // return ret;
}


#endif
