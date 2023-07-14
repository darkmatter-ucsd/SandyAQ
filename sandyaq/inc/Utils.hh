#ifndef UTILS_HH
#define UTILS_HH

//****************************************************************************
// Some register addresses
//****************************************************************************
#define ADDR_GLOBAL_TRG_MASK     0x810C
#define ADDR_TRG_OUT_MASK        0x8110
#define ADDR_FRONT_PANEL_IO_SET  0x811C
#define ADDR_ACQUISITION_MODE    0x8100
#define ADDR_EXT_TRG_INHIBIT     0x817C
#define ADDR_RUN_DELAY           0x8170
#define ADDR_FORCE_SYNC			 0x813C
#define ADDR_RELOAD_PLL			 0xEF34
#define ADDR_GROUP_TRG_MASK      0x10A8

//****************************************************************************
// Run Modes
//****************************************************************************
// start on software command 
#define RUN_START_ON_SOFTWARE_COMMAND     0xC 
// start on S-IN level (logical high = run; logical low = stop)
#define RUN_START_ON_SIN_LEVEL            0xD
// start on first TRG-IN or Software Trigger 
#define RUN_START_ON_TRGIN_RISING_EDGE    0xE
// start on LVDS I/O level
#define RUN_START_ON_LVDS_IO              0xF

//Standard library
#include <iostream>
#include <vector>
#include <string>

//CAEN libraries
#include <CAENDigitizer.h>

//Internal headers
#include "CommonConfig.hh"

template<typename T>
static void PrintVec1d(std::vector<T> &tArray){
    std::cout << "[";
    for (int j = 0; j<tArray.size(); j++){
        std::cout << tArray[j];
        if (j!=tArray.size()-1)
            std::cout << ",";
    }
    std::cout << "]\n";
}

template<typename T>
static void PrintVec2d(std::vector<T> &tArray){
    std::cout << "[";
    for (int i = 0; i < tArray.size(); i++){
        std::cout << "[";
        for (int j = 0; j<tArray[i].size(); j++){
            std::cout << tArray[i][j];
            if (j!=tArray[i].size()-1)
                std::cout << ",";
        }
        std::cout << "]";
        if (i!=tArray.size()-1)
            std::cout<<"\n";
    }
    std::cout<<"]\n";
}

static int CheckBoardFailureStatus(int handle, CAEN_DGTZ_BoardInfo_t BoardInfo) {

	int ret = 0;
	uint32_t status = 0;
	ret = CAEN_DGTZ_ReadRegister(handle, 0x8104, &status);
	if (ret != 0) {
		printf("Error: Unable to read board failure status.\n");
		return -1;
	}
    
	//read twice (first read clears the previous status)
	ret = CAEN_DGTZ_ReadRegister(handle, 0x8104, &status);
	if (ret != 0) {
		printf("Error: Unable to read board failure status.\n");
		return -1;
	}

	if(!(status & (1 << 7))) {
		printf("Board error detected: PLL not locked.\n");
		return -1;
	}

	return 0;
}

static void PrintError(int BoardNum, const char* Action, const char* Quantity, int ret) {
    if (ret) std::cout << "Error in "<<Action<<" the "<<Quantity<<" for board " << BoardNum << "\n";
}

/* Get time in milliseconds from the computer internal clock */
static double get_time(){
    long time_ms;
#ifdef WIN32
    struct _timeb timebuffer;
    _ftime( &timebuffer );
    time_ms = (long)timebuffer.time * 1000 + (long)timebuffer.millitm;
#else
    struct timeval t1;
    struct timezone tz;
    gettimeofday(&t1, &tz);
    time_ms = (t1.tv_sec) * 1000 + t1.tv_usec / 1000;
#endif
    return time_ms;
}

//Set Synchronization Mode
// static int SetSyncMode(std::vector<int*> BoardTypes, CommonConfig_t* commonConfig){
//     int ret = 0;
//     uint32_t reg;
//     for (int b = 0; b<BoardTypes.size(); b++){
//         int* bt = BoardTypes[b];
//         for ()
//     }
//     for (int i = 0; i < commonConfig->iNBoards; i++) {
//         if (commonConfig->SyncMode == "COMMONT_EXTERNAL_TRIGGER_TRGIN_TRGOUT") {

//             if (i == 0) {// inhibit TRGIN on board 0 in order to avoid start of run with external triggers
//                 ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_EXT_TRG_INHIBIT, 1);
//                 PrintError(i, "Writng", "Register[ADDR_EXT_TRG_INHIBIT]", ret);
//             }
//             ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_GLOBAL_TRG_MASK, 0xC0000000);  // accept EXT TRGIN or SW trg 
//             PrintError(i, "Writng", "Register[ADDR_GLOBAL_TRG_MASK]", ret);
            
//             ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_TRG_OUT_MASK, 0xC0000000);     // propagate both EXT and SW TRG to TRGOUT
//             PrintError(i, "Writng", "Register[ADDR_TRG_OUT_MASK]", ret);
            
//             ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_ACQUISITION_MODE, RUN_START_ON_TRGIN_RISING_EDGE);  // Run starts with 1st trigger edge
//             PrintError(i, "Writng", "Register[ADDR_ACQUISITION_MODE]", ret);
            
//             ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_RUN_DELAY, 4*(1-i));   // Run Delay decreases with the position (to compensate for run the propagation delay)        }
//             PrintError(i, "Writng", "Register[ADDR_RUN_DELAY]", ret);
//         continue;        
//         }
//         else if (commonConfig->SyncMode == "INDIVIDUAL_TRIGGER_SIN_TRGOUT"){

//             if (i > 0){ // Run starts with S-IN on thr 2nd board
//                 ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_ACQUISITION_MODE, RUN_START_ON_SIN_LEVEL);
//                 PrintError(i, "Writng", "Register[ADDR_ACQUISITION_MODE]", ret);

//             }
//             for (int c = 0; c < m_iOpenChannels[i].size(); c++){
//                 ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_GLOBAL_TRG_MASK, 0x40000000 + (1<<(int)m_iOpenChannels[i][c]));  //  accept EXT TRGIN or trg from selected channel
//                 PrintError(i, "Writng", "Register[ADDR_GLOBAL_TRG_MASK]", ret);

//             }
//             ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_TRG_OUT_MASK, 0); // no trigger propagation to TRGOUT
//             PrintError(i, "Writng", "Register[ADDR_TRG_OUT_MASK]", ret);
            
//             ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_RUN_DELAY, 2*(1-i));   // Run Delay decreases with the position (to compensate for run the propagation delay)
//             PrintError(i, "Writng", "Register[ADDR_RUN_DELAY]", ret);
            
//             // Set TRGOUT=RUN to propagate run through S-IN => TRGOUT daisy chain
//             ret |= CAEN_DGTZ_ReadRegister(handle[i], ADDR_FRONT_PANEL_IO_SET, &reg);
//             PrintError(i, "Writng", "Register[ADDR_FRONT_PANEL_IO_SET]", ret);
            
//             reg = reg & 0xFFF0FFFF | 0x00010000;
//             ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_FRONT_PANEL_IO_SET, reg);
//             PrintError(i, "Writng", "Register[ADDR_FRONT_PANEL_IO_SET]", ret);
//             continue;
//         }
//         else if (commonConfig->SyncMode == "TRIGGER_ONE2ALL_EXTOR") {
//             for (int c = 0; c < m_iOpenChannels[i].size(); c++){    
//                 ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_TRG_OUT_MASK, (0x80000000 + (1<<m_iOpenChannels[i][c])));     // propagate SW TRG and auto trg to TRGOUT
//                 PrintError(i, "Writng", "Register[ADDR_TRG_OUT_MASK]", ret);

//             }
//             ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_GLOBAL_TRG_MASK, 0x40000000);  // accept EXT TRGIN (from trg OR) 
//             PrintError(i, "Writng", "Register[ADDR_GLOBAL_TRG_MASK]", ret);
            
//             ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_ACQUISITION_MODE, RUN_START_ON_TRGIN_RISING_EDGE);    // Arm acquisition (Run will start with 1st trigger)
//             PrintError(i, "Writng", "Register[ADDR_ACQUISITION_MODE]", ret);
            
//             ret |= CAEN_DGTZ_WriteRegister(handle[i], ADDR_RUN_DELAY, 0);   // Run Delay due to the transmission of the SW TRG in the TRGIN of the slaves
            
//             continue;
//         }
//         else{
//             return -1;
//         }
//     }
//     return ret;
// }

// static int StartRun(int *handle, CommonConfig_t* commonConfig) {
//     int ret = 0;
//     if(commonConfig->SyncMode == "TRIGGER_ONE2ALL_EXTOR" || commonConfig->SyncMode == "COMMONT_EXTERNAL_TRIGGER_TRGIN_TRGOUT"){
//         // Start on first software trigger
//         if(commonConfig->StartMode == "START_SW_CONTROLLED"){
//             ret |= CAEN_DGTZ_SendSWtrigger(handle[0]);
//             PrintError(0, "Sending SW Trigger", "Digitizer", ret);
//         }
//         if(commonConfig->SyncMode == "COMMONT_EXTERNAL_TRIGGER_TRGIN_TRGOUT"){
//             ret |= CAEN_DGTZ_WriteRegister(handle[0], ADDR_EXT_TRG_INHIBIT, 0); // Enable TRGIN of the first board
//             PrintError(0, "Writng", "Register[ADDR_EXT_TRG_INHIBIT]", ret);
//         }
//         return ret;
//     }
//     if(commonConfig->SyncMode == "INDIVIDUAL_TRIGGER_SIN_TRGOUT"){
//         if(commonConfig->StartMode == "START_SW_CONTROLLED"){
//             ret |= CAEN_DGTZ_WriteRegister(handle[0], ADDR_ACQUISITION_MODE, 0x4);
//             PrintError(0, "Writng", "Register[ADDR_ACQUISITION_MODE]", ret);
//         }
//         else{
//             ret |= CAEN_DGTZ_WriteRegister(handle[0], ADDR_ACQUISITION_MODE, 0x5);
//             PrintError(0, "Writng", "Register[ADDR_ACQUISITION_MODE]", ret);
            
//             printf("Run starts/stops on the S-IN high/low level\n");
//         }
//         return ret;
//     }
//     return ret;
// };

#endif